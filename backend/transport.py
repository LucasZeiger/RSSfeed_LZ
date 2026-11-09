import asyncio
import time
from collections import defaultdict
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from threading import Lock
from urllib.parse import urljoin, urlsplit

from src.url_security import validate_public_http_url

import httpx


_HOST_LOCKS = defaultdict(Lock)
_NEXT_REQUEST = {}


def rate_limit(url):
    host = urlsplit(url).hostname
    with _HOST_LOCKS[host]:
        delay = _NEXT_REQUEST.get(host, 0) - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        _NEXT_REQUEST[host] = time.monotonic() + 1


def safe_url(url):
    """Use Horizon's public-address validation with NewsLens's standard-port policy."""
    if urlsplit(str(url)).port not in (None, 80, 443):
        raise ValueError("Nonstandard port blocked")
    return asyncio.run(validate_public_http_url(str(url)))


def fetch(source, metadata, settings):
    headers = {
        "User-Agent": "NewsLens/0.1 (RSS reader)",
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
    }
    if metadata.get("etag"):
        headers["If-None-Match"] = metadata["etag"]
    if metadata.get("modified"):
        headers["If-Modified-Since"] = metadata["modified"]
    for attempt in range(settings["retries"] + 1):
        try:
            url = str(source.url)
            with httpx.Client(
                timeout=settings["request_timeout"], follow_redirects=False
            ) as client:
                for _ in range(6):
                    safe_url(url)
                    rate_limit(url)
                    deadline = time.monotonic() + 30
                    with client.stream("GET", url, headers=headers) as response:
                        if response.status_code == 304:
                            return None, metadata
                        if response.status_code in (301, 302, 303, 307, 308):
                            url = urljoin(url, response.headers["location"])
                            continue
                        response.raise_for_status()
                        chunks, size = [], 0
                        for chunk in response.iter_bytes():
                            size += len(chunk)
                            if time.monotonic() > deadline:
                                raise ValueError("Feed exceeded total transfer deadline")
                            if size > settings["max_response_bytes"]:
                                raise ValueError("Feed exceeds response size limit")
                            chunks.append(chunk)
                        return b"".join(chunks), {
                            "etag": response.headers.get("etag", ""),
                            "modified": response.headers.get("last-modified", ""),
                        }
                raise ValueError("Too many redirects")
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            if attempt >= settings["retries"]:
                raise
            delay = min(2**attempt, 8)
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in (429, 503):
                delay = max(delay, retry_after_seconds(exc.response.headers.get("retry-after")))
                if delay > 60:
                    raise  # Defer long provider cooldowns to the next scheduled run.
            time.sleep(delay)
    raise RuntimeError("Fetch failed")


def retry_after_seconds(value):
    try:
        return max(0, int(value))
    except (ValueError, TypeError):
        try:
            return max(0, int((parsedate_to_datetime(value) - datetime.now(UTC)).total_seconds()))
        except (ValueError, TypeError):
            return 0
