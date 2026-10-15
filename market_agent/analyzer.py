"""Deterministic, feed-content-only sentiment and catalyst analysis."""

from __future__ import annotations

import re
from typing import Iterable

from .models import AnalyzedArticle, CatalystEvidence, NormalizedArticle

try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
except ImportError:  # pragma: no cover - dependency is declared in requirements
    SentimentIntensityAnalyzer = None  # type: ignore[assignment,misc]

_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("earnings_and_guidance", (r"earnings", r"quarterly results?", r"financial results?", r"profit", r"revenue", r"guidance")),
    ("mergers_and_acquisitions", (r"merger", r"acquisition", r"acquire[sd]?", r"takeover", r"buyout")),
    ("interest_rates_and_central_banks", (r"interest rates?", r"rate (?:hike|cut)", r"central bank", r"monetary policy", r"\b(?:fed|ecb|boe|boj)\b")),
    ("inflation_and_economic_data", (r"inflation", r"consumer price", r"producer price", r"\b(?:cpi|ppi|gdp)\b", r"unemployment", r"jobs report", r"economic data")),
    ("regulation_and_litigation", (r"regulat(?:ion|ory|or)", r"lawsuit", r"litigation", r"court", r"antitrust", r"investigation", r"settlement")),
    ("financing_or_liquidity", (r"financing", r"fundrais(?:e|ing)", r"capital raise", r"liquidity", r"credit line", r"debt issuance", r"refinanc(?:e|ing)", r"bankrupt(?:cy|cies)", r"default(?:ed)?")),
)


def _sentences(article: NormalizedArticle) -> list[str]:
    sentences: list[str] = []
    for field in (article.title, article.summary, article.content):
        if field:
            sentences.extend(part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+", field) if part.strip())
    return sentences


def _catalysts(article: NormalizedArticle, sentences: list[str]) -> tuple[CatalystEvidence, ...]:
    found: list[CatalystEvidence] = []
    for category, patterns in _PATTERNS:
        compiled = [re.compile(r"(?<!\w)(?:" + pattern + r")(?!\w)", re.IGNORECASE) for pattern in patterns]
        match = next((sentence for sentence in sentences if any(pattern.search(sentence) for pattern in compiled)), None)
        if match:
            found.append(CatalystEvidence(category=category, evidence_snippet=match, source_reference=article.canonical_url or article.url))
    return tuple(found)


def _require_vader():
    if SentimentIntensityAnalyzer is None:
        raise RuntimeError("vaderSentiment is required for analysis; install requirements.txt")
    return SentimentIntensityAnalyzer()


def analyze_article(article: NormalizedArticle) -> AnalyzedArticle:
    sentences = _sentences(article)
    score = float(_require_vader().polarity_scores(" ".join(sentences)).get("compound", 0.0))
    label = "positive" if score >= 0.05 else "negative" if score <= -0.05 else "neutral"
    catalysts = _catalysts(article, sentences)
    chosen: list[str] = []
    for catalyst in catalysts:
        if catalyst.evidence_snippet not in chosen:
            chosen.append(catalyst.evidence_snippet)
    for sentence in sentences:
        if sentence not in chosen:
            chosen.append(sentence)
        if len(chosen) >= 2:
            break
    # Priority is transparent: catalysts first, then sentiment magnitude, then source order.
    priority = len(catalysts) * 10 + (1 if abs(score) >= 0.05 else 0)
    return AnalyzedArticle(article=article, summary=" ".join(chosen[:2]), sentiment_label=label, sentiment_score=score, catalysts=catalysts, attention_priority=priority)


def analyze(items: Iterable[NormalizedArticle]) -> tuple[AnalyzedArticle, ...]:
    return tuple(analyze_article(item) for item in items)


class MarketAnalyzer:
    def analyze(self, items: Iterable[NormalizedArticle]) -> tuple[AnalyzedArticle, ...]:
        return analyze(items)

    def analyze_article(self, item: NormalizedArticle) -> AnalyzedArticle:
        return analyze_article(item)


analyze_item = analyze_article
