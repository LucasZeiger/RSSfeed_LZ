"""NewsLens evidence checks around Horizon's AI clients and profile enricher."""

import asyncio
import io
import inspect
import json
import os
import re
from datetime import datetime
from pathlib import Path

from rich.console import Console
from src.ai.client import create_ai_client
from src.ai.enricher import ContentEnricher
from src.models import (
    AIConfig,
    ClassificationResult,
    ContentAnalysis,
    ContentItem,
    ProcessingResult,
    SourceType,
)
from src.processing.profiles import ProfileRegistry

from backend.models import AIAnalysis
from backend.normalize import now


class HorizonComparisonProvider:
    def __init__(self, config: AIConfig, root: Path, client=None):
        self.runner = asyncio.Runner()
        self.config = config
        self.client = client if client is not None else create_ai_client(config)
        self.profiles = ProfileRegistry.load(root / "config/profiles", "newslens-comparison")
        self.console = Console(file=io.StringIO())

    def close(self):
        async def close_client(client):
            for child in getattr(client, "_client_cache", {}).values():
                await close_client(child)
            inner = getattr(client, "client", None)
            async_close = getattr(getattr(inner, "aio", None), "aclose", None)
            if callable(async_close):
                await async_close()
            close = getattr(inner, "close", None)
            if callable(close):
                result = close()
                if inspect.isawaitable(result):
                    await result

        try:
            self.runner.run(close_client(self.client))
        finally:
            self.runner.close()

    @classmethod
    def from_config(cls, root):
        values = json.loads((root / "config/horizon-ai.json").read_text())
        if os.environ.get("NEWSLENS_AI_MODEL"):
            values["model"] = os.environ["NEWSLENS_AI_MODEL"]
        if os.environ.get("NEWSLENS_AI_BASE_URL"):
            values["base_url"] = os.environ["NEWSLENS_AI_BASE_URL"]
        return cls(AIConfig.model_validate(values), root)

    def groups(self, articles):
        from src.processing.topics import find_topic_groups

        candidates = []
        for article in articles[:40]:
            candidates.append(
                ContentItem(
                    id=article.id,
                    source_type=SourceType.RSS,
                    title=article.title,
                    url=article.url,
                    content=article.summary,
                    published_at=datetime.fromisoformat(article.published_at),
                    processing=ProcessingResult(
                        classification=ClassificationResult(
                            profile="newslens-comparison", method="source_override"
                        ),
                        analysis=ContentAnalysis(
                            score=None, reason="Source evidence", summary=article.summary
                        ),
                    ),
                )
            )
        indices = self.runner.run(find_topic_groups(candidates, self.client))
        return [[candidates[index].id for index in group] for group in indices]

    def enrich(self, articles):
        articles = articles[:30]
        if not articles:
            raise ValueError("No articles supplied")
        payload = [
            {
                "id": a.id,
                "title": a.title,
                "excerpt": a.summary,
                "source_id": a.source_id,
                "language": a.language,
            }
            for a in articles
        ]
        item = ContentItem(
            id="comparison-" + articles[0].id,
            source_type=SourceType.RSS,
            title=articles[0].title,
            url=articles[0].url,
            content=json.dumps(payload, ensure_ascii=False),
            published_at=datetime.fromisoformat(articles[0].published_at),
            profile="newslens-comparison",
            processing=ProcessingResult(
                classification=ClassificationResult(
                    profile="newslens-comparison", method="source_override"
                ),
                analysis=ContentAnalysis(
                    score=None,
                    reason="All supplied sources retained; no importance threshold",
                    summary=articles[0].title,
                ),
            ),
        )
        enricher = ContentEnricher(self.client, self.profiles, ["en"], console=self.console)
        outcome = self.runner.run(enricher.enrich_batch([item]))
        if outcome.failed_count:
            raise ValueError("Horizon enrichment rejected the generated comparison")
        blocks = {block.id: block.content for block in item.processing.artifacts["en"].blocks}
        valid = {a.id for a in articles}
        referenced = set()
        for content in blocks.values():
            ids = set(re.findall(r"\[([a-zA-Z0-9-]+)\]", content))
            if not ids or not ids <= valid:
                raise ValueError("AI claim lacks valid article references")
            # Require a reference for each sentence, not only one for the entire block.
            sentences = re.split(r"(?<=[.!?])\s+(?=[A-ZÄÖÜ])", content.strip())
            if any(not re.search(r"\[[a-zA-Z0-9-]+\]", sentence) for sentence in sentences):
                raise ValueError("AI sentence lacks article references")
            referenced.update(ids)
        return AIAnalysis(
            summary=blocks["summary"],
            framing=[blocks["framing"]] if "framing" in blocks else [],
            common_facts=[blocks["common_facts"]] if "common_facts" in blocks else [],
            disagreements=[blocks["disagreements"]] if "disagreements" in blocks else [],
            article_ids=sorted(referenced),
            provider=f"Horizon/{self.config.provider.value}/{self.config.model}",
            generated_at=now(),
        )
