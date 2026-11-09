"""Adapt Horizon's collectors to the publisher-preserving NewsLens contract.

RSS scheduling, parsing, date/content selection and per-entry isolation belong to
Horizon. This module adds safe conditional transport, bounded excerpts, provenance
and a no-AI path; it never applies the briefing's destructive topic merge.
"""

import asyncio
import ipaddress
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from src.models import ContentItem, RSSSourceConfig
from src.scrapers.base import FetchResult
from src.scrapers.rss import RSSScraper

from backend.models import Article, Source
from backend.normalize import canonical_url, clean, identifier
from backend.transport import fetch


def rss_source(source: Source) -> RSSSourceConfig:
    return RSSSourceConfig(
        name=source.id,
        url=source.url,
        enabled=source.enabled,
        category=source.category,
        content_extractor=None,
        profile="newslens-comparison",
    )


def to_article(item: ContentItem, source: Source, fetched_at: str) -> Article:
    url = canonical_url(str(item.url))
    host = urlsplit(url).hostname
    if (
        not host
        or host.rstrip(".").lower() == "localhost"
        or host.endswith((".local", ".localhost"))
    ):
        raise ValueError("Unsafe article link")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError("Unsafe article link")
    return Article(
        id=identifier(url),
        source_id=source.id,
        title=clean(item.title, 250),
        url=url,
        summary=clean(item.content),
        published_at=item.published_at.astimezone(UTC).isoformat(),
        fetched_at=fetched_at,
        date_estimated=item.metadata.get("date_estimated", False),
        author=clean(item.author, 150),
        categories=[clean(tag, 80) for tag in item.metadata.get("tags", [])[:10]],
        language=source.language,
        country=source.country,
        category=source.category,
    )


class ComparisonRSSScraper(RSSScraper):
    def __init__(self, sources, metadata, settings, fetched_at):
        # The override owns transport; the inherited fetch owns task scheduling.
        super().__init__(
            [rss_source(s) for s in sources],
            http_client=None,
            max_concurrent_feeds=settings["concurrency"],
        )
        self.sources = {s.id: s for s in sources}
        self.metadata, self.settings = metadata, settings
        self.fetched_at = fetched_at
        self.outcomes = {}

    async def _fetch_feed(self, source, since):
        original = self.sources[source.name]
        try:
            body, metadata = await asyncio.to_thread(
                fetch, original, self.metadata.get(original.id, {}), self.settings
            )
            if body is None:
                self.outcomes[original.id] = (original, None, metadata, [])
                return FetchResult(successful=1)
            result = await self.parse_feed(
                body,
                source,
                since,
                fallback_date=datetime.fromisoformat(self.fetched_at),
                max_entries=300,
            )
            articles, rejected = [], []
            for item in result.items:
                try:
                    article = to_article(item, original, self.fetched_at)
                    if article.title:
                        articles.append(article)
                except (ValueError, TypeError):
                    rejected.append("invalid article")
            errors = ["entry rejected" for _ in result.failures] + rejected
            self.outcomes[original.id] = (original, articles, metadata, errors)
            return result
        except Exception as exc:  # noqa: BLE001 -- keep healthy sources running
            self.outcomes[original.id] = (original, [], {}, [type(exc).__name__])
            return FetchResult(failures={original.id: type(exc).__name__})


def collect_sources(sources, metadata, settings, fetched_at):
    active = [source for source in sources if source.enabled]
    scraper = ComparisonRSSScraper(active, metadata, settings, fetched_at)
    since = datetime.fromisoformat(fetched_at) - timedelta(days=settings["article_days"])
    asyncio.run(scraper.fetch(since))
    return [scraper.outcomes[source.id] for source in active]


def parse_feed(body, source, fetched_at):
    """Offline adapter entry point; parsing is implemented in Horizon."""
    scraper = RSSScraper([rss_source(source)], http_client=None)
    result = asyncio.run(
        scraper.parse_feed(
            body,
            rss_source(source),
            datetime.min.replace(tzinfo=UTC),
            fallback_date=datetime.fromisoformat(fetched_at),
            max_entries=300,
        )
    )
    if result.status == "failure":
        raise ValueError("No valid RSS entries")
    articles = []
    for item in result.items:
        try:
            articles.append(to_article(item, source, fetched_at))
        except ValueError:
            continue
    return articles
