import ipaddress
import socket
import time
from collections import defaultdict
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from threading import Lock
from urllib.parse import urljoin, urlsplit

import feedparser
import httpx

from backend.models import Article
from backend.normalize import canonical_url, clean, identifier

_HOST_LOCKS = defaultdict(Lock)
_NEXT_REQUEST = {}


def rate_limit(url):
    host = urlsplit(url).hostname
    with _HOST_LOCKS[host]:
        delay = _NEXT_REQUEST.get(host, 0) - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        _NEXT_REQUEST[host] = time.monotonic() + 1


def safe_url(url, resolver=socket.getaddrinfo):
    p = urlsplit(str(url))
    if p.scheme not in ("http", "https") or not p.hostname or p.username or p.password:
        raise ValueError("Only credential-free HTTP(S) URLs are allowed")
    if p.port not in (None, 80, 443):
        raise ValueError("Nonstandard port blocked")
    addresses = resolver(
        p.hostname, p.port or (443 if p.scheme == "https" else 80), type=socket.SOCK_STREAM
    )
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError("Non-public network destination blocked")
    return str(url)


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


def parse_feed(body, source, fetched_at):
    parsed = feedparser.parse(body)
    if parsed.bozo and not parsed.entries:
        raise ValueError("Malformed or unsupported feed")
    output = []
    for entry in parsed.entries[:300]:
        try:
            url = canonical_url(urljoin(str(source.url), entry.get("link", "")))
            # Never expose private or unsupported article links; no requests are made here.
            host = urlsplit(url).hostname
            if not host or host == "localhost" or host.endswith(".local"):
                continue
            try:
                if not ipaddress.ip_address(host).is_global:
                    continue
            except ValueError:
                pass
            title = clean(entry.get("title"), 250)
            if not title or not entry.get("link"):
                continue
            date = entry.get("published_parsed") or entry.get("updated_parsed")
            estimated = date is None
            published = datetime(*date[:6], tzinfo=UTC).isoformat() if date else fetched_at
            if datetime.fromisoformat(published) > datetime.fromisoformat(fetched_at):
                published, estimated = fetched_at, True
            output.append(
                Article(
                    id=identifier(url),
                    source_id=source.id,
                    title=title,
                    url=url,
                    summary=clean(entry.get("summary")),
                    published_at=published,
                    fetched_at=fetched_at,
                    date_estimated=estimated,
                    author=clean(entry.get("author"), 150),
                    categories=[clean(t.get("term"), 80) for t in entry.get("tags", [])[:10]],
                    language=source.language,
                    country=source.country,
                    category=source.category,
                )
            )
        except (ValueError, TypeError, OverflowError):
            continue
    return output


def retry_after_seconds(value):
    try:
        return max(0, int(value))
    except (ValueError, TypeError):
        try:
            return max(0, int((parsedate_to_datetime(value) - datetime.now(UTC)).total_seconds()))
        except (ValueError, TypeError):
            return 0
