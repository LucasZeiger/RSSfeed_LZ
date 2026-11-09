import argparse
import fcntl
import json
import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml

from backend.cluster import cluster
from backend.export import atomic_json, read_json
from backend.horizon import collect_sources
from backend.financial import exposures
from backend.models import Article, Dataset, Instrument, RunStatus, Settings, Source
from backend.normalize import now

ROOT = Path(__file__).resolve().parents[1]


def configuration(root=ROOT):
    def load(name):
        return yaml.safe_load((root / "config" / name).read_text())

    settings = Settings.model_validate(load("settings.yaml")).model_dump()
    sources = [Source.model_validate(s) for s in load("feeds.yaml")["feeds"]]
    instruments = [Instrument.model_validate(i) for i in load("instruments.yaml")["instruments"]]
    if len({s.id for s in sources}) != len(sources):
        raise ValueError("Source IDs must be unique")
    return settings, sources, instruments


def collect(root=ROOT):
    lock_path = root / "data/collector.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another collector is running") from None
        return _collect(root)


def _collect(root):
    settings, sources, instruments = configuration(root)
    state_path = root / "data/state.json"
    state = read_json(state_path, {"articles": [], "clusters": {}, "feeds": {}, "seen": {}})
    timestamp = now()
    status = RunStatus(state="ok", attempted_at=timestamp)
    articles = {a["id"]: Article.model_validate(a) for a in state["articles"]}
    successful = 0

    for source, parsed, meta, errors in collect_sources(
        sources, state["feeds"], settings, timestamp
    ):
        if errors:
            status.errors.append(
                f"{source.id}: {', '.join(sorted(set(errors)))}; previous articles retained"
            )
        if errors and not parsed:
            status.source_results[source.id] = "failed"
            continue
        successful += 1
        status.source_results[source.id] = (
            "not modified" if parsed is None else f"{len(parsed)} entries"
        )
        state["feeds"][source.id] = meta
        if parsed is not None:
            for article in parsed:
                if article.id not in articles and article.id not in state["seen"]:
                    articles[article.id] = article
                state["seen"][article.id] = timestamp
    active = {s.id for s in sources if s.enabled}
    cutoff = (datetime.now(UTC) - timedelta(days=settings["article_days"])).isoformat()
    retained = sorted(
        (a for a in articles.values() if a.published_at >= cutoff and a.source_id in active),
        key=lambda a: a.published_at,
        reverse=True,
    )[: settings["max_articles"]]
    provider = None
    candidate_groups = []
    if settings.get("ai_enabled"):
        from backend.ai.provider import HorizonComparisonProvider

        try:
            provider = HorizonComparisonProvider.from_config(root)
            if settings.get("semantic_clustering_enabled"):
                candidate_groups = provider.groups(retained)
        except Exception as exc:  # noqa: BLE001 -- optional model failures keep lexical grouping
            status.errors.append(f"Horizon AI/grouping unavailable: {type(exc).__name__}")
    stories = cluster(retained, sources, settings, state["clusters"], candidate_groups)
    by_id = {a.id: a for a in retained}
    for story in stories:
        story.exposures = exposures([by_id[aid] for aid in story.article_ids], instruments)
    status.state = "partial" if status.errors else "ok"
    if not successful or not retained:
        status.state = "failed"
        status.errors.append("No usable new dataset; last valid published dataset retained")
    previous = read_json(root / "web/public/data/latest.json", None)
    status.last_success_at = (
        timestamp
        if status.state == "ok"
        else (previous["status"]["last_success_at"] if previous else None)
    )
    markets = []
    if settings.get("market_enabled") and os.environ.get("ALPHA_VANTAGE_API_KEY"):
        from backend.market.alpha import AlphaVantage, benchmark_returns

        provider = AlphaVantage(
            os.environ["ALPHA_VANTAGE_API_KEY"],
            root / "data/markets-cache.json",
            settings["market_daily_budget"],
        )
        for instrument in instruments:
            requests_before = provider.cache["requests"]
            try:
                markets.append(provider.daily(instrument))
            except Exception as exc:  # noqa: BLE001 -- isolate failures in optional/external providers
                status.errors.append(f"Market {instrument.symbol}: {type(exc).__name__}")
                cached = provider.cache["series"].get(instrument.symbol)
                if cached:
                    from backend.models import MarketSeries

                    markets.append(MarketSeries.model_validate(cached))
            if provider.cache["requests"] > requests_before:
                time.sleep(61)  # conservative one request/minute, including quota/error responses
        benchmark_returns(markets, instruments)
        status.market_status = (
            "Daily historical data; inspect each instrument date"
            if markets
            else "Market provider unavailable"
        )
    if provider is not None:
        for story in stories[:10]:
            try:
                story.ai = provider.enrich([by_id[aid] for aid in story.article_ids])
                if len(story.article_ids) > 30:
                    story.limitations.append("AI comparison used at most 30 source excerpts.")
            except Exception as exc:  # noqa: BLE001 -- optional external model
                status.errors.append(f"AI {story.id}: {type(exc).__name__}")
        status.ai_status = "Horizon profile enrichment; inspect article references"
    elif settings.get("ai_enabled"):
        status.ai_status = "AI enrichment unavailable; deterministic comparison retained"
    if provider is not None:
        try:
            provider.close()
        except Exception as exc:  # noqa: BLE001 -- cleanup must not discard collected news
            status.errors.append(f"Horizon AI cleanup: {type(exc).__name__}")
    if status.errors and status.state == "ok":
        status.state = "partial"
    atomic_json(root / "web/public/data/status.json", status.model_dump())
    if status.state != "failed":
        dataset = Dataset(
            mode="live",
            generated_at=timestamp,
            refresh_minutes=settings["refresh_minutes"],
            sources=sources,
            articles=retained,
            stories=stories,
            instruments=instruments,
            markets=markets,
            status=status,
        )
        atomic_json(root / "web/public/data/latest.json", dataset.model_dump(mode="json"))
        state.update(
            articles=[a.model_dump(mode="json") for a in retained],
            clusters={aid: s.id for s in stories for aid in s.article_ids},
            seen=dict(
                sorted(state["seen"].items(), key=lambda kv: kv[1], reverse=True)[
                    : settings["max_seen"]
                ]
            ),
        )
        atomic_json(state_path, state)
    print(
        json.dumps(
            {
                "state": status.state,
                "articles": len(retained),
                "stories": len(stories),
                "errors": status.errors,
                "sources": status.source_results,
            },
            indent=2,
        )
    )
    return 1 if status.state == "failed" else 0


def main():
    parser = argparse.ArgumentParser(description="NewsLens batch data pipeline")
    parser.add_argument("command", choices=["demo", "collect", "validate", "schema"])
    args = parser.parse_args()
    if args.command == "schema":
        atomic_json(ROOT / "web/src/dataset.schema.json", Dataset.model_json_schema())
        return
    if args.command == "collect":
        raise SystemExit(collect())
    if args.command == "demo":
        from backend.demo import generate

        generate()
    else:
        found = False
        for name in ("demo", "latest"):
            path = ROOT / f"web/public/data/{name}.json"
            if path.exists():
                found = True
                dataset = Dataset.model_validate_json(path.read_text())
                print(
                    f"{name}: valid schema v{dataset.schema_version}, {len(dataset.stories)} stories"
                )

        if not found:
            raise SystemExit("No dataset files found; generate demo or collect first")


if __name__ == "__main__":
    main()
