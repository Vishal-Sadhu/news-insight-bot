"""Pipeline orchestration with publish-before-commit semantics."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Callable, Iterable

from .analyzer import analyze
from .models import RunResult, SourceResult, utc_now
from .processor import process_sources
from .reporter import publish_report, render_report


def _as_utc(value: datetime) -> datetime:
    return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def _run_id(started: datetime) -> str:
    return f"{started:%Y%m%dT%H%M%SZ}-{sha256(started.isoformat().encode()).hexdigest()[:10]}"


def run_cycle(
    sources: Iterable[str],
    fetcher: Any,
    analyzer: Any,
    store: Any,
    output_dir: str,
    *,
    clock: Callable[[], datetime] = utc_now,
    run_id: str | None = None,
    publisher: Callable[..., tuple[Any, Any]] = publish_report,
    lookback_hours: int = 24,
    watchlist_keywords: Iterable[str] = (),
    max_items_per_feed: int | None = None,
    synthetic: bool = False,
    bypass_lookback: bool = False,
) -> RunResult:
    started = _as_utc(clock())
    identifier = run_id or _run_id(started)
    source_results: list[SourceResult] = []
    for source in sources:
        try:
            result = fetcher.fetch(source) if hasattr(fetcher, "fetch") else fetcher(source)
            source_results.append(result if isinstance(result, SourceResult) else SourceResult(source_url=source, payload=result))
        except Exception as exc:
            source_results.append(SourceResult(source_url=source, error=f"{type(exc).__name__}: {exc}"))
    if source_results and all(result.error for result in source_results):
        errors = tuple(result.error or "source failed" for result in source_results)
        finished = _as_utc(clock())
        store.record_run(identifier, started_at=started, finished_at=finished, status="failed", source_health={result.source_url: result.error for result in source_results}, error="all sources failed")
        return RunResult(run_id=identifier, status="failed", source_results=tuple(source_results), started_at=started, completed_at=finished, errors=errors)
    normalized = process_sources(source_results, now=started, lookback_hours=lookback_hours, watchlist_keywords=watchlist_keywords, max_items=max_items_per_feed, bypass_lookback=bypass_lookback)
    fresh = tuple(article for article in normalized.articles if not store.is_processed(article.article_id))
    analyzed = tuple(analyzer.analyze(fresh) if hasattr(analyzer, "analyze") else analyze(fresh))
    limitations = ["No new qualifying items were available in this cycle."] if not fresh else []
    content = render_report(run_id=identifier, generated_at=started, analyzed_articles=analyzed, source_results=normalized.source_results, synthetic=synthetic, limitations=limitations)
    try:
        report_path, _ = publisher(content, output_dir, run_id=identifier, clock=started, latest_name="latest-demo.md" if synthetic else "latest.md")
    except Exception as exc:
        store.record_run(identifier, started_at=started, finished_at=_as_utc(clock()), status="failed", source_health={result.source_url: (result.error or "ok") for result in normalized.source_results}, error=str(exc))
        return RunResult(run_id=identifier, status="failed", articles=fresh, analyzed_articles=analyzed, source_results=normalized.source_results, started_at=started, completed_at=_as_utc(clock()), errors=(str(exc),))
    # This is intentionally after publication. A crash before this commit can cause re-reporting, which is at-least-once behavior.
    store.mark_processed(article.article_id for article in fresh)
    finished = _as_utc(clock())
    status = "success" if not normalized.errors else "partial"
    store.record_run(identifier, started_at=started, finished_at=finished, status=status, report_path=str(report_path), source_health={result.source_url: (result.error or f"ok ({len(result.articles)})") for result in normalized.source_results})
    return RunResult(run_id=identifier, status=status, articles=fresh, analyzed_articles=analyzed, source_results=normalized.source_results, started_at=started, completed_at=finished, errors=normalized.errors, report_path=str(report_path))
