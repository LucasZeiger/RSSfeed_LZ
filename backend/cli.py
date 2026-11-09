import argparse
import fcntl
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml

from backend.cluster import cluster
from backend.export import atomic_json, read_json
from backend.feeds import fetch, parse_feed
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

    def task(source):
        try:
            body, meta = fetch(source, state["feeds"].get(source.id, {}), settings)
            parsed = None if body is None else parse_feed(body, source, timestamp)
            return source, parsed, meta, None
        except Exception as exc:  # noqa: BLE001 -- isolate failures in optional/external providers
            # Avoid URLs, response bodies and credentials in operational logs.
            return source, [], {}, type(exc).__name__

    with ThreadPoolExecutor(max_workers=max(1, min(settings["concurrency"], 4))) as pool:
        for source, parsed, meta, error in pool.map(task, [s for s in sources if s.enabled]):
            if error:
                status.errors.append(f"{source.id}: {error}; previous articles retained")
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
    stories = cluster(retained, sources, settings, state["clusters"])
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
    if settings.get("ai_enabled") and os.environ.get("NEWSLENS_AI_KEY"):
        from backend.ai.provider import OpenAICompatible

        provider = OpenAICompatible(
            os.environ["NEWSLENS_AI_KEY"],
            (os.environ.get("NEWSLENS_AI_URL") or "https://api.openai.com/v1/chat/completions"),
            (os.environ.get("NEWSLENS_AI_MODEL") or "gpt-4.1-mini"),
        )
        for story in stories[:10]:
            try:
                story.ai = provider.enrich([by_id[aid] for aid in story.article_ids])
            except Exception as exc:  # noqa: BLE001 -- isolate failures in optional/external providers
                status.errors.append(f"AI {story.id}: {type(exc).__name__}")
        status.ai_status = "Optional model interpretation; inspect references"
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
