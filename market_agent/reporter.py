"""Safe Markdown rendering and atomic report publication."""

from __future__ import annotations

import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import quote, urlparse
from uuid import uuid4

from .models import AnalyzedArticle, SourceResult

_MD = re.compile(r"([\\`*_{}\[\]()#+.!|>~-])")


def escape_markdown(value: object) -> str:
    return _MD.sub(r"\\\1", str(value if value is not None else ""))


def safe_link(url: str, label: str | None = None) -> str:
    candidate = str(url or "").strip()
    parsed = urlparse(candidate)
    shown = escape_markdown(label or candidate)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc or any(char in candidate for char in "\r\n"):
        return shown
    return f"[{shown}]({candidate.replace(')', '%29')})"


def _utc(value: datetime) -> datetime:
    return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def render_report(
    *,
    run_id: str,
    generated_at: datetime,
    analyzed_articles: Iterable[AnalyzedArticle] = (),
    source_results: Iterable[SourceResult] = (),
    synthetic: bool = False,
    limitations: Iterable[str] = (),
) -> str:
    articles = tuple(analyzed_articles)
    sources = tuple(source_results)
    sentiment_counts = {label: sum(item.sentiment_label == label for item in articles) for label in ("positive", "neutral", "negative")}
    catalysts = [(article, catalyst) for article in articles for catalyst in article.catalysts]
    errors = [f"{result.source_url}: {result.error}" for result in sources if result.error]
    warnings = [warning for result in sources for warning in result.warnings]
    lines = [
        "# Autonomous Market & News Intelligence Report",
        "",
        "## Run Metadata",
        "",
        f"- Run ID: `{escape_markdown(run_id)}`",
        f"- Generated (UTC): {escape_markdown(_utc(generated_at).isoformat())}",
        f"- Report type: {'SYNTHETIC DEMO' if synthetic else 'LIVE FEED RUN'}",
        f"- Reported items: {len(articles)}",
        "",
        "## Executive Summary",
        "",
        "No new qualifying items." if not articles else f"Reported {len(articles)} qualifying item(s). Aggregate sentiment covers only these reported items.",
        "",
        "## Sentiment Overview",
        "",
        f"- Positive: {sentiment_counts['positive']}",
        f"- Neutral: {sentiment_counts['neutral']}",
        f"- Negative: {sentiment_counts['negative']}",
        "",
        "## Key Catalysts",
        "",
    ]
    if catalysts:
        for article, catalyst in catalysts:
            lines.append(f"- **{escape_markdown(catalyst.category)}** — {escape_markdown(catalyst.evidence_snippet)} ({safe_link(article.article.canonical_url or article.article.url, 'source')})")
    else:
        lines.append("No catalysts detected in feed content.")
    lines += ["", "## Articles", ""]
    if articles:
        for number, item in enumerate(sorted(articles, key=lambda value: (-value.attention_priority, value.article.article_id)), 1):
            article = item.article
            title = safe_link(article.url or article.canonical_url, article.title) if article.url else escape_markdown(article.title)
            published = _utc(article.published_at).isoformat() if article.published_at else "unknown"
            lines += [f"{number}. {title}", f"   - Source: {safe_link(article.source, article.source) if article.source else 'unknown'}", f"   - Published (UTC): {escape_markdown(published)}", f"   - Sentiment: {escape_markdown(item.sentiment_label)} ({item.sentiment_score:.3f})", f"   - Summary: {escape_markdown(item.summary or 'No feed-provided summary.')}" ]
    else:
        lines.append("No new qualifying items.")
    lines += ["", "## Source Health", ""]
    if sources:
        for result in sources:
            status = f"failed — {result.error}" if result.error else f"ok — {len(result.articles)} qualifying item(s), {result.attempts} attempt(s)"
            lines.append(f"- {safe_link(result.source_url, result.source_url)}: {escape_markdown(status)}")
    else:
        lines.append("No source results recorded.")
    lines += ["", "## Limitations", "", "- Feed content is untrusted and was not supplemented with linked article pages.", "- Processing is at-least-once: a crash after report publication and before SQLite commit can cause an item to be reported again."]
    for limitation in tuple(limitations) + tuple(errors) + tuple(warnings):
        lines.append(f"- {escape_markdown(limitation)}")
    return "\n".join(lines) + "\n"


def publish_report(content: str, output_dir: str | Path, *, run_id: str | None = None, clock: datetime | None = None, latest_name: str = "latest.md") -> tuple[Path, Path]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    now = _utc(clock or datetime.now(timezone.utc))
    identifier = run_id or f"{now:%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}"
    report_path = destination / f"{identifier}.md"
    latest_path = destination / latest_name
    report_path.write_text(content, encoding="utf-8", newline="\n")
    fd, temporary = tempfile.mkstemp(prefix=f".{latest_path.stem}-", suffix=".tmp", dir=destination)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, latest_path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return report_path, latest_path
