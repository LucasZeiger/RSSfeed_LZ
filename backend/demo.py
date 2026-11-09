from datetime import UTC, datetime, timedelta

from backend.cli import ROOT, configuration
from backend.cluster import cluster
from backend.export import atomic_json
from backend.financial import exposures
from backend.models import Article, Classification, Dataset, MarketSeries, Price, RunStatus, Source
from backend.normalize import identifier

EVENTS = [
    (
        "US chip export restrictions reshape semiconductor trade",
        "Technology",
        "US",
        "en",
        "A fictional proposal would tighten semiconductor and chip export rules. NVIDIA and Advanced Micro Devices are mentioned as potentially exposed suppliers.",
        [
            "Export limits put semiconductor suppliers under pressure",
            "New rules define the scope of chip exports",
            "Restrictions aim to strengthen domestic production",
        ],
    ),
    (
        "Federal Reserve interest rate decision follows inflation report",
        "Business",
        "US",
        "en",
        "In this simulated event, the Federal Reserve reviews its interest rate policy after an inflation report. The future policy path remains uncertain.",
        [
            "Household borrowing costs remain in focus",
            "Policymakers weigh incoming economic data",
            "Inflation discipline remains a policy priority",
        ],
    ),
    (
        "Crude oil supply disruption raises energy cost concerns",
        "World",
        "UK",
        "en",
        "A fictional crude oil supply disruption affects shipping schedules. The duration is unknown; producer revenue and consumer costs may respond differently.",
        [
            "Consumers face possible fuel cost pressure",
            "Oil supply uncertainty clouds the outlook",
            "Producers seek alternative supply routes",
        ],
    ),
    (
        "UK government announces local transport spending review",
        "Politics",
        "UK",
        "en",
        "A fictional government spending review considers local transport funding. No project awards or final budgets have been confirmed.",
        [
            "Access to services takes centre stage",
            "Review sets out next consultation steps",
            "Spending scrutiny focuses on value for money",
        ],
    ),
    (
        "Österreich diskutiert neue Regeln für Schulwege",
        "Politics",
        "AT",
        "de",
        "Synthetisches Beispiel: Gemeinden diskutieren sichere Schulwege. Es liegen nur Auszüge einer fiktiven Quelle vor.",
        ["Gemeinden prüfen Vorschläge für sichere Schulwege"],
    ),
    (
        "Independent science festival opens its autumn programme",
        "World",
        "UK",
        "en",
        "A fictional regional science festival announces workshops and public talks. This story has no identified financial exposure.",
        ["Public workshops feature in science festival programme"],
    ),
]


def generate():
    settings, _, instruments = configuration()
    base = datetime(2026, 11, 9, 14, 0, tzinfo=UTC)
    classification = Classification(
        reviewer="Synthetic demo fixture",
        methodology="Invented perspectives, not real publisher ratings",
        reviewed_at="2026-11-09",
    )
    sources = [
        Source(
            id=f"demo-{leaning}",
            name=f"{name} (fictional)",
            url=f"https://example.com/{leaning}/rss",
            category="World",
            country="US",
            political_leaning=leaning,
            classification=classification if leaning != "unknown" else None,
        )
        for leaning, name in [
            ("left", "The Civic Review"),
            ("centre", "The Daily Record"),
            ("right", "The National Ledger"),
            ("unknown", "Regional Journal"),
        ]
    ]
    articles = []
    for index, (title, category, country, language, summary, angles) in enumerate(EVENTS):
        perspectives = ["left", "centre", "right"] if index < 4 else ["unknown"]
        for offset, (leaning, angle) in enumerate(zip(perspectives, angles)):
            url = f"https://example.com/demo/{index}/{leaning}"
            timestamp = (base - timedelta(hours=index * 3, minutes=offset * 12)).isoformat()
            articles.append(
                Article(
                    id=identifier(url),
                    source_id=f"demo-{leaning}",
                    title=f"{title}: {angle}",
                    url=url,
                    summary=summary,
                    published_at=timestamp,
                    fetched_at=base.isoformat(),
                    language=language,
                    country=country,
                    category=category,
                )
            )
    stories = cluster(articles, sources, settings)
    by_id = {a.id: a for a in articles}
    for story in stories:
        group = [by_id[i] for i in story.article_ids]
        event = next(e for e in EVENTS if group[0].title.startswith(e[0]))
        story.title = event[0]
        story.title_kind = "synthetic_event_title"
        story.exposures = exposures(group, instruments)
    markets = []
    for index, symbol in enumerate(["SPY", "NVDA", "XLE"]):
        instrument = next(i for i in instruments if i.symbol == symbol)
        prices = [
            Price(
                date=(base - timedelta(days=35 - day)).date().isoformat(),
                close=round(100 + index * 40 + day * 0.35 + ((day * 7) % 9) * 0.6, 2),
            )
            for day in range(35)
            if (base - timedelta(days=35 - day)).weekday() < 5
        ]
        markets.append(
            MarketSeries(
                symbol=symbol,
                currency=instrument.currency,
                exchange=instrument.exchange,
                source="SIMULATED demo prices",
                fetched_at=base.isoformat(),
                prices=prices,
                change_pct=round((prices[-1].close / prices[-2].close - 1) * 100, 2),
            )
        )
    from backend.market.alpha import benchmark_returns

    benchmark_returns(markets, instruments)
    dataset = Dataset(
        mode="demo",
        generated_at=base.isoformat(),
        sources=sources,
        articles=articles,
        stories=stories,
        instruments=instruments,
        markets=markets,
        status=RunStatus(
            state="demo",
            attempted_at=base.isoformat(),
            last_success_at=base.isoformat(),
            market_status="SIMULATED demo prices",
        ),
    )
    atomic_json(ROOT / "web/public/data/demo.json", dataset.model_dump(mode="json"))
    print(f"Demo: {len(stories)} stories, {len(articles)} articles; all content synthetic")
