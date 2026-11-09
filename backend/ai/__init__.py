"""Optional enrichment is independent of deterministic analysis."""

from typing import Protocol

from backend.models import AIAnalysis, Article


class AnalysisProvider(Protocol):
    def enrich(self, articles: list[Article]) -> AIAnalysis: ...
