import re

from backend.models import Exposure

# Rules describe mechanisms, not predictions. An asset match also needs its own evidence.
RULES = [
    (
        "Trade policy",
        ["tariff", "trade restriction", "import duty"],
        "Trade-sensitive sectors",
        "Import duties can change input costs, consumer prices and competitive conditions.",
        "Protected domestic suppliers may face less import competition.",
        "Importers may face higher costs and weaker demand.",
    ),
    (
        "Rates and inflation",
        ["interest rate", "federal reserve", "inflation"],
        "Broad market",
        "Interest rates and inflation affect financing costs, discount rates and spending.",
        "Lower borrowing costs may support investment and demand.",
        "Persistent inflation or tighter policy may increase financing pressure.",
    ),
    (
        "Energy supply",
        ["crude oil", "oil supply", "opec"],
        "Energy",
        "Changes in energy supply can affect input costs and producer revenue.",
        "Higher realised prices may support some producers.",
        "Higher fuel costs may pressure consumers and energy-intensive businesses.",
    ),
    (
        "Semiconductor restrictions",
        ["semiconductor", "chip export"],
        "Semiconductors",
        "Export controls can change addressable markets and supply-chain access.",
        "Alternative suppliers may gain substitution demand.",
        "Exporters may face lost sales and compliance costs.",
    ),
    (
        "Defence spending",
        ["defence spending", "defense spending"],
        "Defence",
        "Government procurement can change future order books; awards and delivery timing matter.",
        "Confirmed contracts may support supplier demand.",
        "Budget reversals or execution costs may offset potential revenue.",
    ),
    (
        "Corporate announcements",
        ["earnings", "quarterly results"],
        "Company-specific",
        "Reported earnings and guidance can change expectations about business cash flows.",
        "Improved margins or demand may strengthen the business outlook.",
        "Weak guidance, costs or demand may undermine expectations.",
    ),
    (
        "Supply disruption",
        ["supply chain", "port strike", "labour strike"],
        "Supply chains",
        "Disruptions can delay output and raise transport or labour costs.",
        "Substitute suppliers may see additional demand.",
        "Affected businesses may face delays and margin pressure.",
    ),
    (
        "Regulation and spending",
        ["government spending", "antitrust", "regulation"],
        "Regulated sectors",
        "Policy changes can alter compliance costs, public demand and market access.",
        "Public investment or clearer rules may benefit some suppliers.",
        "New constraints may increase costs or restrict activity.",
    ),
]


def contains(text, phrase):
    return re.search(r"(?<!\w)" + re.escape(phrase.lower()) + r"(?!\w)", text.lower()) is not None


def exposures(articles, instruments):
    output = []
    for category, keywords, sector, mechanism, positive, negative in RULES:
        evidence = [
            a for a in articles if any(contains(a.title + " " + a.summary, k) for k in keywords)
        ]
        if not evidence:
            continue
        matches = {}
        for instrument in instruments:
            for article in evidence:
                text = article.title + " " + article.summary
                matched = next(
                    (k for k in instrument.aliases + instrument.keywords if contains(text, k)), None
                )
                if matched:
                    matches[instrument.symbol] = (
                        f"Available reporting mentions “{matched}”; this links to the configured {instrument.sector} exposure, not proof of a price effect."
                    )
        output.append(
            Exposure(
                category=category,
                sector=sector,
                symbols=list(matches),
                mechanism=mechanism,
                positive=positive,
                negative=negative,
                uncertainty="Magnitude, policy details, timing and existing market expectations are uncertain. Scenarios may not materialise.",
                article_ids=[a.id for a in evidence],
                matches=matches,
            )
        )
    return output
