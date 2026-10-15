"""Pure RSS/Atom parsing, normalization, filtering, and deduplication."""

from __future__ import annotations

import hashlib
import html
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from time import struct_time
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import feedparser

from .models import NormalizedArticle, RunResult, SourceResult, utc_now

_TRACKING = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "fbclid", "gclid", "dclid", "mc_cid", "mc_eid"}


def canonicalize_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    parts = urlsplit(raw)
    if not parts.scheme or not parts.netloc:
        return ""
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    try:
        port = parts.port
    except ValueError:
        port = None
    netloc = host
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc += f":{port}"
    query = urlencode([(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True) if key.casefold() not in _TRACKING])
    path = parts.path or "/"
    if path != "/":
        path = path.rstrip("/") or "/"
    return urlunsplit((scheme, netloc, path, query, ""))


def clean_text(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]*>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _date(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, struct_time):
        result = datetime(*value[:6], tzinfo=timezone.utc)
    elif isinstance(value, str):
        try:
            result = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            try:
                result = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
    else:
        return None
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def _article_id(canonical_url: str, title: str, source: str) -> str:
    identity = canonical_url or f"{source}\0{title.casefold()}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def process_source(
    source: SourceResult,
    *,
    now: datetime | None = None,
    lookback_hours: int = 24,
    watchlist_keywords: Iterable[str] = (),
    max_items: int | None = None,
    bypass_lookback: bool = False,
) -> SourceResult:
    if source.error:
        return source
    if not isinstance(source.payload, bytes):
        return SourceResult(source_url=source.source_url, error="invalid feed payload", status_code=source.status_code, attempts=source.attempts, fetched_at=source.fetched_at, warnings=source.warnings)
    try:
        parsed = feedparser.parse(source.payload)
    except Exception as exc:
        return SourceResult(source_url=source.source_url, error=f"feed parse failed: {exc}", status_code=source.status_code, attempts=source.attempts, fetched_at=source.fetched_at)
    if not source.payload.strip():
        return SourceResult(source_url=source.source_url, error="empty response is not a usable feed", status_code=source.status_code, attempts=source.attempts, fetched_at=source.fetched_at)
    if getattr(parsed, "bozo", False) and not parsed.entries:
        detail = str(getattr(parsed, "bozo_exception", "invalid feed"))
        return SourceResult(source_url=source.source_url, error=f"unusable feed: {detail}", status_code=source.status_code, attempts=source.attempts, fetched_at=source.fetched_at)
    current = (now or utc_now()).astimezone(timezone.utc)
    cutoff = current - timedelta(hours=max(0, lookback_hours))
    keywords = tuple(str(word).casefold().strip() for word in watchlist_keywords if str(word).strip())
    articles: list[NormalizedArticle] = []
    warnings = list(source.warnings)
    if getattr(parsed, "bozo", False):
        warnings.append("Feed parser reported a recoverable format warning")
    seen: set[str] = set()
    entries = parsed.entries[:max_items] if max_items is not None else parsed.entries
    for entry in entries:
        title = clean_text(entry.get("title"))
        summary = clean_text(entry.get("summary") or entry.get("description"))
        content = clean_text(" ".join(str(item.get("value", "")) for item in entry.get("content", []) if isinstance(item, dict)))
        url = str(entry.get("link") or "").strip()
        canonical = canonicalize_url(url)
        published = _date(entry.get("published") or entry.get("updated") or entry.get("published_parsed") or entry.get("updated_parsed"))
        if published and not bypass_lookback and published < cutoff:
            continue
        if published is None:
            warnings.append(f"Undated article retained from {source.source_url}: {title or 'untitled'}")
        haystack = f"{title} {summary}".casefold()
        if keywords and not any(re.search(rf"(?<!\w){re.escape(word)}(?!\w)", haystack) for word in keywords):
            continue
        identity = canonical or _article_id("", title, source.source_url)
        if identity in seen:
            continue
        seen.add(identity)
        articles.append(NormalizedArticle(title=title or "Untitled", url=url, canonical_url=canonical, published_at=published, summary=summary, content=content, source=source.source_url, article_id=_article_id(canonical, title, source.source_url)))
    return SourceResult(source_url=source.source_url, articles=tuple(articles), status_code=source.status_code, attempts=source.attempts, fetched_at=source.fetched_at, warnings=tuple(dict.fromkeys(warnings)))


def process_sources(sources: Iterable[SourceResult], **kwargs: Any) -> RunResult:
    started = kwargs.pop("now", None) or utc_now()
    started = started.replace(tzinfo=timezone.utc) if started.tzinfo is None else started.astimezone(timezone.utc)
    processed = tuple(process_source(source, now=started, **kwargs) for source in sources)
    seen: set[str] = set()
    articles: list[NormalizedArticle] = []
    for source in processed:
        for article in source.articles:
            if article.article_id not in seen:
                seen.add(article.article_id)
                articles.append(article)
    articles.sort(key=lambda item: (item.published_at is not None, item.published_at or datetime.min.replace(tzinfo=timezone.utc), item.article_id), reverse=True)
    return RunResult(articles=tuple(articles), source_results=processed, started_at=started, completed_at=utc_now(), errors=tuple(source.error for source in processed if source.error))


normalize_feed = process_source
normalize_sources = process_sources
