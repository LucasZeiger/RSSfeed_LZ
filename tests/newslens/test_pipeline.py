import json
from datetime import UTC, datetime

import httpx
import pytest
import yaml

from backend.cli import ROOT, collect, configuration
from backend.cluster import cluster
from backend.export import atomic_json
from backend.horizon import parse_feed
from backend.transport import fetch, safe_url
from backend.financial import exposures
from backend.market.alpha import AlphaVantage, benchmark_returns
from backend.models import Article, Dataset, MarketSeries, Price, Source
from backend.normalize import canonical_url, clean, identifier

STAMP = "2026-11-09T14:00:00+00:00"


@pytest.fixture
def source():
    return Source(
        id="test", name="Example", url="https://example.org/rss", category="World", country="US"
    )


@pytest.fixture
def settings():
    return configuration()[0]


def article(title, source_id="test", timestamp=STAMP, language="en"):
    url = "https://example.org/" + identifier(title + source_id)
    return Article(
        id=identifier(url),
        source_id=source_id,
        title=title,
        url=url,
        published_at=timestamp,
        fetched_at=STAMP,
        country="US",
        category="World",
        language=language,
    )


def test_rss_normalization_dedup_and_safe_text(source):
    assert clean("Costs &amp; demand: &lt;b&gt;a review&lt;/b&gt;") == "Costs & demand: a review"
    articles = parse_feed((ROOT / "fixtures/news.xml").read_bytes(), source, STAMP)
    assert len(articles) == 3
    assert articles[0].id == articles[1].id
    assert str(articles[0].url) == "https://example.org/rates"
    assert "<script" not in articles[0].summary and "<b>" not in articles[0].summary
    assert articles[2].date_estimated and articles[2].published_at == STAMP
    assert (
        canonical_url("https://EXAMPLE.org/a?b=2&utm_campaign=x&a=1#top")
        == "https://example.org/a?a=1&b=2"
    )


def test_atom_dates_are_utc(source):
    articles = parse_feed((ROOT / "fixtures/atom.xml").read_bytes(), source, STAMP)
    assert len(articles) == 1
    assert articles[0].published_at == "2026-11-09T10:00:00+00:00"
    assert articles[0].author == "Example author"


@pytest.mark.parametrize(
    "address", ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "fc00::1", "0.0.0.0"]
)
def test_private_dns_blocked(address, monkeypatch):
    async def resolver(*args, **kwargs):
        return {address}

    monkeypatch.setattr("src.url_security._resolve_hostname", resolver)
    with pytest.raises(ValueError, match="non-public"):
        safe_url("https://example.org/rss")


@pytest.mark.parametrize(
    "url",
    ["file:///etc/passwd", "http://user:pass@example.org/rss", "https://example.org:8080/rss"],
)
def test_invalid_destinations_blocked(url):
    with pytest.raises(ValueError):
        safe_url(url)


def test_public_destination(monkeypatch):
    async def resolver(*args, **kwargs):
        return {"93.184.215.14"}

    monkeypatch.setattr("src.url_security._resolve_hostname", resolver)
    assert safe_url("https://example.org")


def test_redirect_revalidated_and_response_bounded(monkeypatch, source, settings):
    validated = []

    def guard(url):
        validated.append(url)
        if "127.0.0.1" in url:
            raise ValueError("Non-public")

    monkeypatch.setattr("backend.transport.safe_url", guard)
    real_client = httpx.Client
    client = real_client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(302, headers={"location": "http://127.0.0.1/secret"})
        )
    )
    monkeypatch.setattr("backend.transport.httpx.Client", lambda **kw: client)
    with pytest.raises(ValueError, match="Non-public"):
        fetch(source, {}, settings)
    assert len(validated) == 2
    client = real_client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b"x" * 30))
    )
    monkeypatch.setattr("backend.transport.httpx.Client", lambda **kw: client)
    with pytest.raises(ValueError, match="size"):
        fetch(source, {}, {**settings, "max_response_bytes": 10})


def test_conditional_headers_and_304(monkeypatch, source, settings):
    def respond(request):
        assert request.headers["If-None-Match"] == "tag"
        assert request.headers["If-Modified-Since"] == "date"
        return httpx.Response(304)

    client = httpx.Client(transport=httpx.MockTransport(respond))
    monkeypatch.setattr("backend.transport.httpx.Client", lambda **kw: client)
    monkeypatch.setattr("backend.transport.safe_url", lambda url: url)
    assert fetch(source, {"etag": "tag", "modified": "date"}, settings)[0] is None


def test_conservative_clustering_and_stable_ids(source, settings):
    first = article("Government introduces semiconductor chip export restrictions")
    second = article("New semiconductor chip export restrictions affect suppliers")
    unrelated = article("Government debates school transport and local funding")
    groups = cluster([first, second, unrelated], [source], settings)
    assert sorted(len(s.article_ids) for s in groups) == [1, 2]
    original = next(s for s in groups if first.id in s.article_ids)
    mapping = {aid: s.id for s in groups for aid in s.article_ids}
    earlier = article(
        "Government semiconductor chip export restrictions announced",
        timestamp="2026-11-09T13:00:00+00:00",
    )
    next_run = cluster([earlier, first, second, unrelated], [source], settings, mapping)
    assert next(s for s in next_run if first.id in s.article_ids).id == original.id
    # One shared politician is never sufficient.
    groups = cluster(
        [
            article("Trump addresses tariffs and trade"),
            article("Trump attends school graduation ceremony"),
        ],
        [source],
        settings,
    )
    assert len(groups) == 2


def test_cluster_time_and_language_boundaries(source, settings):
    text = "Semiconductor chip export restrictions affect suppliers"
    groups = cluster(
        [
            article(text),
            article(text, timestamp="2026-11-01T14:00:00+00:00"),
            article(text + " heute", language="de"),
        ],
        [source],
        settings,
    )
    assert len(groups) == 3


def test_split_does_not_reuse_anchor_id(source, settings):
    # The old anchor joined two headlines which no longer match one another.
    anchor = article("Alpha beta gamma delta epsilon zeta", timestamp="2026-11-09T12:00:00+00:00")
    first = article("Alpha beta gamma report", timestamp="2026-11-09T13:00:00+00:00")
    second = article("Delta epsilon zeta report")
    original = cluster([anchor, first, second], [source], settings)
    assert len(original) == 1
    mapping = {aid: story.id for story in original for aid in story.article_ids}
    # The remaining group's new anchor becomes the basis of its ID.
    split = cluster([first, second], [source], settings, mapping)
    assert len({s.id for s in split}) == 2

    # Reproduce a historical ID equal to the later split's anchor-derived ID.
    shared_id = "story-" + identifier(second.id)
    mapping = {first.id: shared_id, second.id: shared_id}
    split = cluster([first, second], [source], settings, mapping)
    assert len({s.id for s in split}) == 2
    assert next(s for s in split if first.id in s.article_ids).id == shared_id
    next_mapping = {aid: s.id for s in split for aid in s.article_ids}
    repeated = cluster([second, first], [source], settings, next_mapping)
    assert {s.id for s in repeated} == {s.id for s in split}


def test_financial_evidence_and_no_generic_ticker_match():
    _, _, instruments = configuration()
    no_match = exposures([article("A spy novel wins a literary award")], instruments)
    assert no_match == []
    item = article("Semiconductor chip export restrictions affect NVIDIA")
    results = exposures([item], instruments)
    assert "NVDA" in results[0].symbols
    assert results[0].article_ids == [item.id]
    assert "price" not in results[0].positive.lower()


def test_market_cache_quota_and_benchmark(monkeypatch, tmp_path):
    _, _, instruments = configuration()
    instrument = instruments[0]
    day = datetime.now(UTC).date().isoformat()
    cached = MarketSeries(
        symbol=instrument.symbol,
        currency="USD",
        exchange="NYSE Arca",
        source="fixture",
        fetched_at=day + "T12:00:00+00:00",
        prices=[Price(date="2026-11-06", close=100)],
    )
    path = tmp_path / "cache.json"
    atomic_json(
        path, {"day": day, "requests": 20, "series": {instrument.symbol: cached.model_dump()}}
    )
    provider = AlphaVantage("not-a-real-key", path)
    assert provider.daily(instrument).source == "fixture"
    with pytest.raises(ValueError, match="budget"):
        provider.daily(instruments[1])
    asset = cached.model_copy(
        update={
            "symbol": "NVDA",
            "prices": [Price(date="2026-11-05", close=50), Price(date="2026-11-06", close=55)],
        }
    )
    cached.prices = [Price(date="2026-11-05", close=100), Price(date="2026-11-06", close=102)]
    benchmark_returns([cached, asset], instruments)
    assert asset.benchmark_change_pct == 2
    assert asset.excess_return_pct == 8


def setup_root(tmp_path):
    (tmp_path / "config").mkdir()
    settings, sources, instruments = configuration()
    settings["article_days"] = 36500
    for name, value in [
        ("settings", settings),
        ("feeds", {"feeds": [s.model_dump(mode="json") for s in sources[:2]]}),
        ("instruments", {"instruments": [i.model_dump() for i in instruments]}),
    ]:
        (tmp_path / f"config/{name}.yaml").write_text(yaml.safe_dump(value))
    return tmp_path


def test_pipeline_dedup_repeated_run_partial_and_failure(monkeypatch, tmp_path):
    root = setup_root(tmp_path)
    body = (ROOT / "fixtures/news.xml").read_bytes()
    monkeypatch.setattr("backend.horizon.fetch", lambda *args: (body, {"etag": "example"}))
    assert collect(root) == 0
    path = root / "web/public/data/latest.json"
    original = Dataset.model_validate_json(path.read_text())
    assert len(original.articles) == 2
    assert collect(root) == 0
    repeat = Dataset.model_validate_json(path.read_text())
    assert {s.id for s in repeat.stories} == {s.id for s in original.stories}

    def partial(source, *args):
        if source.id == "guardian-us":
            raise httpx.ConnectError("offline")
        return None, {"etag": "example"}

    monkeypatch.setattr("backend.horizon.fetch", partial)
    assert collect(root) == 0
    assert json.loads(path.read_text())["status"]["state"] == "partial"
    prior = path.read_bytes()

    def fail(*args):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr("backend.horizon.fetch", fail)
    assert collect(root) == 1
    assert path.read_bytes() == prior
    assert json.loads((root / "web/public/data/status.json").read_text())["state"] == "failed"


def test_validation_failure_reports_failed_attempt_and_preserves_output(monkeypatch, tmp_path):
    root = setup_root(tmp_path)
    body = (ROOT / "fixtures/news.xml").read_bytes()
    monkeypatch.setattr("backend.horizon.fetch", lambda *args: (body, {}))
    assert collect(root) == 0
    output = root / "web/public/data/latest.json"
    state = root / "data/state.json"
    previous_output, previous_state = output.read_bytes(), state.read_bytes()
    last_success = json.loads(previous_output)["status"]["last_success_at"]

    def invalid_clusters(*args, **kwargs):
        stories = cluster(*args, **kwargs)
        return stories + [stories[0].model_copy(deep=True)]

    monkeypatch.setattr("backend.cli.cluster", invalid_clusters)
    with pytest.raises(ValueError, match="Duplicate story IDs"):
        collect(root)
    assert output.read_bytes() == previous_output
    assert state.read_bytes() == previous_state
    status = json.loads((root / "web/public/data/status.json").read_text())
    assert status["state"] == "failed"
    assert status["last_success_at"] == last_success
    assert "Dataset validation failed" in status["errors"][-1]


def test_demo_contract():
    data = Dataset.model_validate_json((ROOT / "web/public/data/demo.json").read_text())
    assert data.mode == "demo" and len(data.stories) == 6
    assert len([s for s in data.stories if s.exposures]) >= 2
    assert any(
        s.article_counts["left"] and s.article_counts["centre"] and s.article_counts["right"]
        for s in data.stories
    )
    assert any("Insufficient coverage for comparison." in s.limitations for s in data.stories)
    for story in data.stories:
        assert sum(story.article_counts.values()) == len(story.article_ids)
    assert all("SIMULATED" in m.source for m in data.markets)


def test_ai_rejects_unknown_references():
    from backend.ai.provider import HorizonComparisonProvider
    from src.models import AIConfig

    class Client:
        async def complete(self, **kwargs):
            return json.dumps(
                {
                    "title": "Unverified",
                    "blocks": [
                        {
                            "id": "summary",
                            "title": "Summary",
                            "content": "Unsubstantiated [fake]",
                            "source_refs": [],
                        }
                    ],
                }
            )

    config = AIConfig(provider="openai", model="fixture", api_key_env="UNUSED_FIXTURE_KEY")
    with pytest.raises(ValueError, match="references"):
        HorizonComparisonProvider(config, ROOT, client=Client()).enrich([article("Real article")])


def test_market_adapter_parses_daily_prices_and_caches(monkeypatch, tmp_path):
    _, _, instruments = configuration()
    calls = []

    def respond(request):
        calls.append(request)
        assert request.url.params["function"] == "TIME_SERIES_DAILY"
        return httpx.Response(
            200,
            json={
                "Time Series (Daily)": {
                    "2026-11-09": {"4. close": "110"},
                    "2026-11-06": {"4. close": "100"},
                }
            },
        )

    real_client = httpx.Client
    monkeypatch.setattr(
        "backend.market.alpha.httpx.Client",
        lambda **kw: real_client(transport=httpx.MockTransport(respond)),
    )
    provider = AlphaVantage("fixture-only", tmp_path / "cache.json")
    series = provider.daily(instruments[0])
    assert series.change_pct == 10
    assert [p.date for p in series.prices] == ["2026-11-06", "2026-11-09"]
    assert not series.adjusted
    assert provider.daily(instruments[0]) == series
    assert len(calls) == 1


def test_dataset_rejects_incorrect_coverage_counts():
    payload = json.loads((ROOT / "web/public/data/demo.json").read_text())
    payload["stories"][0]["article_counts"]["left"] += 5
    with pytest.raises(ValueError, match="Coverage counts"):
        Dataset.model_validate(payload)


def test_settings_reject_unbounded_requests():
    from backend.models import Settings

    with pytest.raises(ValueError):
        Settings(concurrency=1000, max_response_bytes=999999999)


def test_ai_accepts_grounded_structured_response():
    from backend.ai.provider import HorizonComparisonProvider
    from src.models import AIConfig

    item = article("Federal Reserve reviews interest rate policy")
    calls = []

    class Client:
        async def complete(self, **kwargs):
            calls.append(kwargs)
            assert item.id in kwargs["user"]
            assert "newslens" in kwargs["system"].lower() or "compare" in kwargs["system"].lower()
            return json.dumps(
                {
                    "title": "Reported rate review",
                    "blocks": [
                        {
                            "id": "summary",
                            "title": "What happened",
                            "content": f"An interest rate review is reported [{item.id}]",
                            "source_refs": [],
                        }
                    ],
                }
            )

    config = AIConfig(provider="openai", model="fixture", api_key_env="UNUSED_FIXTURE_KEY")
    output = HorizonComparisonProvider(config, ROOT, client=Client()).enrich([item])
    assert output.provider == "Horizon/openai/fixture" and output.article_ids == [item.id]
    assert len(calls) == 1


def test_malformed_feed_is_isolated(source):
    with pytest.raises(ValueError, match="Invalid RSS/Atom"):
        parse_feed(b"<not-a-feed><broken>", source, STAMP)


def test_long_retry_after_defers_to_next_run(monkeypatch, source, settings):
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(429, headers={"retry-after": "3600"})
        )
    )
    monkeypatch.setattr("backend.transport.httpx.Client", lambda **kw: client)
    monkeypatch.setattr("backend.transport.safe_url", lambda url: url)
    monkeypatch.setattr("backend.transport.rate_limit", lambda url: None)
    with pytest.raises(httpx.HTTPStatusError) as error:
        fetch(source, {}, settings)
    assert error.value.response.status_code == 429
