import asyncio
import json

from backend.ai.provider import HorizonComparisonProvider
from backend.cli import ROOT, configuration
from backend.cluster import cluster
from backend.horizon import collect_sources, parse_feed
from backend.models import Article, Source
from backend.normalize import identifier
from src.models import AIConfig

STAMP = "2026-11-09T14:00:00+00:00"


def make_article(title, source_id, language="en", timestamp=STAMP):
    url = f"https://example.org/{source_id}/{identifier(title)}"
    return Article(
        id=identifier(url),
        source_id=source_id,
        title=title,
        url=url,
        published_at=timestamp,
        fetched_at=STAMP,
        language=language,
        country="US",
        category="World",
    )


def test_horizon_atom_full_content_selection_is_used():
    source = Source(
        id="atom",
        name="Example",
        url="https://example.org/atom",
        country="AT",
        category="World",
        language="de",
    )
    body = b"""<feed xmlns="http://www.w3.org/2005/Atom"><title>Example</title><entry>
    <title>Transport review</title><link href="https://example.org/transport"/>
    <updated>2026-11-09T10:00:00Z</updated><summary>Short</summary>
    <content type="html">A much longer feed-provided account of local transport funding.</content>
    </entry></feed>"""
    articles = parse_feed(body, source, STAMP)
    assert len(articles) == 1
    assert articles[0].summary.startswith("A much longer feed-provided account")
    assert articles[0].language == "de"


def test_horizon_collection_reports_304_and_partial_failures(monkeypatch):
    settings, sources, _ = configuration()
    selected = sources[:2]
    calls = []

    def transport(source, metadata, settings):
        calls.append(source.id)
        if source.id == selected[0].id:
            return None, {"etag": "unchanged"}
        raise OSError("offline")

    monkeypatch.setattr("backend.horizon.fetch", transport)
    outcomes = collect_sources(selected, {}, settings, STAMP)
    assert set(calls) == {source.id for source in selected}
    assert outcomes[0][1] is None and outcomes[0][2]["etag"] == "unchanged"
    assert outcomes[1][3] == ["OSError"]


def test_semantic_grouping_keeps_source_records_and_same_event_identity():
    settings, _, _ = configuration()
    sources = [
        Source(id=s, name=s, url=f"https://example.org/{s}", category="World", country="US")
        for s in ["one", "two", "three"]
    ]
    articles = [
        make_article("Washington raises import duties", "one"),
        make_article("New tariffs reshape trade costs", "two"),
        make_article("A science festival opens today", "three"),
    ]
    assert len(cluster(articles, sources, settings)) == 3
    loops = []

    class Client:
        async def complete(self, **kwargs):
            loops.append(id(asyncio.get_running_loop()))
            if (
                "duplicates" in kwargs["system"].lower()
                or "deduplication" in kwargs["system"].lower()
            ):
                return json.dumps({"duplicates": [[0, 1, 999, True]]})
            return json.dumps(
                {
                    "title": "Trade policy",
                    "blocks": [
                        {
                            "id": "summary",
                            "title": "Summary",
                            "content": f"Import duties changed [{articles[0].id}]",
                            "source_refs": [],
                        }
                    ],
                }
            )

    provider = HorizonComparisonProvider(
        AIConfig(provider="openai", model="fixture", api_key_env="UNUSED"), ROOT, client=Client()
    )
    try:
        groups = provider.groups(articles)
        stories = cluster(articles, sources, settings, candidate_groups=groups)
        assert sorted(len(story.article_ids) for story in stories) == [1, 2]
        joined = next(story for story in stories if len(story.article_ids) == 2)
        assert joined.publisher_count == 2
        assert set(joined.article_ids) == {articles[0].id, articles[1].id}
        assert sum(story.article_counts["unknown"] for story in stories) == 3
        output = provider.enrich(articles[:2])
        assert output.article_ids == [articles[0].id]
        assert len(set(loops)) == 1  # pooled async provider requests share one loop
    finally:
        provider.close()


def test_semantic_candidates_cannot_cross_language_or_time_boundaries():
    settings, _, _ = configuration()
    source = Source(
        id="one", name="Example", url="https://example.org/rss", country="US", category="World"
    )
    articles = [
        make_article("Import duties change today", "one"),
        make_article("Zölle verändern den Handel", "one", language="de"),
        make_article("New trade policy begins", "one", timestamp="2026-11-01T14:00:00+00:00"),
    ]
    stories = cluster(articles, [source], settings, candidate_groups=[[a.id for a in articles]])
    assert len(stories) == 3


def test_two_feeds_from_one_publisher_count_once():
    settings, _, _ = configuration()
    sources = [
        Source(
            id=feed,
            publisher_id="publisher",
            name=feed,
            url=f"https://example.org/{feed}",
            country="UK",
            category="Business",
        )
        for feed in ["world", "business"]
    ]
    articles = [
        make_article("Federal Reserve interest rate policy changes today", feed)
        for feed in ["world", "business"]
    ]
    stories = cluster(articles, sources, settings)
    assert len(stories) == 1
    assert stories[0].article_counts["unknown"] == 2
    assert stories[0].publisher_counts["unknown"] == 1
    assert stories[0].publisher_count == 1
