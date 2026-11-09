from collections import Counter
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

Leaning = Literal["left", "centre", "right", "unknown"]


class Settings(BaseModel):
    article_days: int = Field(default=7, ge=1, le=36500)
    max_articles: int = Field(default=1500, ge=1, le=5000)
    max_seen: int = Field(default=10000, ge=1, le=50000)
    cluster_hours: int = Field(default=48, ge=1, le=168)
    similarity_threshold: float = Field(default=0.32, ge=0.1, le=1)
    request_timeout: float = Field(default=15, ge=1, le=30)
    max_response_bytes: int = Field(default=2000000, ge=100, le=5000000)
    concurrency: int = Field(default=3, ge=1, le=4)
    retries: int = Field(default=2, ge=0, le=3)
    refresh_minutes: int = Field(default=60, ge=5, le=1440)
    market_daily_budget: int = Field(default=20, ge=0, le=25)
    market_enabled: bool = False
    ai_enabled: bool = False


class Classification(BaseModel):
    reviewer: str
    methodology: str
    reviewed_at: str


class Source(BaseModel):
    id: str
    name: str
    url: HttpUrl
    enabled: bool = True
    category: str
    country: str
    language: str = "en"
    political_leaning: Leaning = "unknown"
    classification: Classification | None = None

    @model_validator(mode="after")
    def provenance(self):
        if self.political_leaning != "unknown" and self.classification is None:
            raise ValueError("A political classification requires provenance")
        return self


class Article(BaseModel):
    id: str
    source_id: str
    title: str
    url: HttpUrl
    summary: str = ""
    published_at: str
    fetched_at: str
    date_estimated: bool = False
    author: str = ""
    categories: list[str] = Field(default_factory=list)
    language: str = "en"
    country: str
    category: str


class Instrument(BaseModel):
    symbol: str
    name: str
    exchange: str
    currency: str
    sector: str
    aliases: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    benchmark: str | None = None


class Exposure(BaseModel):
    category: str
    sector: str
    symbols: list[str]
    mechanism: str
    positive: str
    negative: str
    horizon: str = "Weeks to months; timing uncertain"
    uncertainty: str
    article_ids: list[str]
    matches: dict[str, str] = Field(default_factory=dict)


class AIAnalysis(BaseModel):
    summary: str
    framing: list[str]
    common_facts: list[str]
    disagreements: list[str]
    article_ids: list[str]
    provider: str
    generated_at: str


class Story(BaseModel):
    id: str
    title: str
    overview: str
    title_kind: str = "source_headline"
    first_published: str
    updated_at: str
    article_ids: list[str]
    publisher_count: int
    article_counts: dict[str, int]
    publisher_counts: dict[str, int]
    category: str
    countries: list[str]
    language: str
    common_terms: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    exposures: list[Exposure] = Field(default_factory=list)
    ai: AIAnalysis | None = None


class Price(BaseModel):
    date: str
    close: float = Field(gt=0, allow_inf_nan=False)

    @field_validator("date")
    @classmethod
    def valid_date(cls, value):
        date.fromisoformat(value)
        return value


class MarketSeries(BaseModel):
    symbol: str
    currency: str
    exchange: str
    source: str
    fetched_at: str
    adjusted: bool = False
    prices: list[Price] = Field(min_length=1, max_length=60)
    change_pct: float | None = None
    benchmark_change_pct: float | None = None
    excess_return_pct: float | None = None
    comparison_dates: list[str] = Field(default_factory=list)


class RunStatus(BaseModel):
    state: Literal["ok", "partial", "failed", "demo"]
    attempted_at: str
    last_success_at: str | None = None
    errors: list[str] = Field(default_factory=list)
    source_results: dict[str, str] = Field(default_factory=dict)
    market_status: str = "Market price data not configured"
    ai_status: str = "AI enrichment not configured"


class Dataset(BaseModel):
    schema_version: Literal[1] = 1
    mode: Literal["demo", "live"]
    generated_at: str
    refresh_minutes: int = 60
    sources: list[Source]
    articles: list[Article]
    stories: list[Story]
    instruments: list[Instrument]
    markets: list[MarketSeries] = Field(default_factory=list)
    status: RunStatus

    @model_validator(mode="after")
    def references(self):
        sources = {s.id for s in self.sources}
        articles = {a.id for a in self.articles}
        if len(articles) != len(self.articles) or len(sources) != len(self.sources):
            raise ValueError("Duplicate identifiers")
        source_map = {s.id: s for s in self.sources}
        article_map = {a.id: a for a in self.articles}
        if len({s.id for s in self.stories}) != len(self.stories):
            raise ValueError("Duplicate story IDs")
        assigned = set()
        for article in self.articles:
            if article.source_id not in sources:
                raise ValueError("Unknown article source")
        for story in self.stories:
            if not set(story.article_ids) <= articles:
                raise ValueError("Unknown story article")
            if len(set(story.article_ids)) != len(story.article_ids) or assigned & set(
                story.article_ids
            ):
                raise ValueError("Article assigned more than once")
            assigned.update(story.article_ids)
            group = [article_map[aid] for aid in story.article_ids]
            counts = Counter(source_map[a.source_id].political_leaning for a in group)
            for leaning in ("left", "centre", "right", "unknown"):
                publishers = {
                    a.source_id
                    for a in group
                    if source_map[a.source_id].political_leaning == leaning
                }
                if story.article_counts.get(leaning) != counts[
                    leaning
                ] or story.publisher_counts.get(leaning) != len(publishers):
                    raise ValueError("Coverage counts do not match evidence")
            if story.publisher_count != len({a.source_id for a in group}):
                raise ValueError("Incorrect distinct publisher count")
            if story.ai and not set(story.ai.article_ids) <= set(story.article_ids):
                raise ValueError("AI references another story")
            for exposure in story.exposures:
                if not set(exposure.article_ids) <= set(story.article_ids):
                    raise ValueError("Unknown exposure evidence")
        return self
