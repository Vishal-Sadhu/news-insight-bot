"""Typed, serialisable domain objects shared by the news pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class NormalizedArticle:
    title: str
    url: str
    canonical_url: str
    published_at: datetime | None = None
    summary: str = ""
    content: str = ""
    source: str = ""
    article_id: str = ""
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CatalystEvidence:
    category: str
    evidence_snippet: str
    source_reference: str = ""
    confidence: float = 0.0

    @property
    def text(self) -> str:
        return self.evidence_snippet

    @property
    def source_url(self) -> str:
        return self.source_reference


@dataclass(frozen=True, slots=True)
class AnalyzedArticle:
    article: NormalizedArticle
    summary: str = ""
    sentiment_label: str = "neutral"
    sentiment_score: float = 0.0
    catalysts: tuple[CatalystEvidence, ...] = ()
    attention_priority: int = 0

    @property
    def evidence(self) -> tuple[CatalystEvidence, ...]:
        return self.catalysts

    @property
    def sentiment(self) -> float:
        return self.sentiment_score


@dataclass(frozen=True, slots=True)
class SourceResult:
    source_url: str
    articles: tuple[NormalizedArticle, ...] = ()
    error: str | None = None
    status_code: int | None = None
    attempts: int = 0
    fetched_at: datetime = field(default_factory=utc_now)
    payload: bytes | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RunResult:
    run_id: str = ""
    status: str = "success"
    articles: tuple[NormalizedArticle, ...] = ()
    analyzed_articles: tuple[AnalyzedArticle, ...] = ()
    source_results: tuple[SourceResult, ...] = ()
    started_at: datetime = field(default_factory=utc_now)
    completed_at: datetime = field(default_factory=utc_now)
    errors: tuple[str, ...] = ()
    report_path: str | None = None

    @property
    def analyzed(self) -> tuple[AnalyzedArticle, ...]:
        return self.analyzed_articles


# Compatibility with the initial scaffold.
NewsItem = NormalizedArticle
