import hashlib
import re
from datetime import UTC, datetime
from html import unescape
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import bleach


def now():
    return datetime.now(UTC).isoformat()


def clean(value, limit=600):
    return re.sub(
        r"\s+", " ", unescape(bleach.clean(unescape(str(value or "")), tags=[], strip=True))
    ).strip()[:limit]


def canonical_url(url):
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username:
        raise ValueError("Invalid article URL")
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in ("fbclid", "gclid")
    ]
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path or "/",
            urlencode(sorted(query)),
            "",
        )
    )


def identifier(value):
    return hashlib.sha256(value.encode()).hexdigest()[:20]


def tokens(text):
    stop = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "that",
        "this",
        "into",
        "over",
        "after",
        "says",
        "said",
        "have",
        "will",
        "new",
        "news",
        "der",
        "die",
        "das",
        "und",
        "eine",
        "einer",
        "einem",
        "den",
        "von",
        "mit",
        "auf",
        "ist",
        "sich",
        "für",
    }
    return {t for t in re.findall(r"[\w]+", text.lower()) if len(t) > 2 and t not in stop}
