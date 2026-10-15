"""Bounded RSS/Atom fetching with injectable side effects."""

from __future__ import annotations

import email.utils
from pathlib import Path
import time
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

import httpx

from .models import SourceResult, utc_now

DEFAULT_USER_AGENT = "AutonomousMarketNewsIntelligenceAgent/0.1 (+https://example.invalid/agent)"


def _retry_after(value: str | None, now: Callable[[], datetime], maximum: float = 60.0) -> float:
    if not value:
        return 0.0
    try:
        return max(0.0, min(maximum, float(value)))
    except ValueError:
        try:
            target = email.utils.parsedate_to_datetime(value)
            if target.tzinfo is None:
                target = target.replace(tzinfo=timezone.utc)
            return max(0.0, min(maximum, (target.astimezone(timezone.utc) - now()).total_seconds()))
        except (TypeError, ValueError, OverflowError):
            return 0.0


def _body_from_response(response: Any, limit: int) -> bytes:
    if hasattr(response, "iter_bytes"):
        chunks: list[bytes] = []
        size = 0
        for chunk in response.iter_bytes():
            size += len(chunk)
            if size > limit:
                raise ValueError(f"response exceeds configured limit of {limit} bytes")
            chunks.append(chunk)
        return b"".join(chunks)
    body = getattr(response, "content", None)
    if body is None and hasattr(response, "read"):
        body = response.read(limit + 1)
    if not isinstance(body, bytes):
        body = bytes(body or b"")
    if len(body) > limit:
        raise ValueError(f"response exceeds configured limit of {limit} bytes")
    return body


class FeedFetcher:
    """Fetch raw feed bytes; parsing is deliberately handled elsewhere."""

    def __init__(
        self,
        http_client: Any | None = None,
        *,
        clock: Callable[[], datetime] = utc_now,
        sleep: Callable[[float], None] = time.sleep,
        timeout: float = 15.0,
        max_retries: int = 2,
        max_bytes: int = 2_097_152,
        user_agent: str = DEFAULT_USER_AGENT,
        backoff_cap: float = 60.0,
    ) -> None:
        self.http_client = http_client or httpx.Client()
        self.clock = clock
        self.sleep = sleep
        self.timeout = timeout
        self.max_retries = max(0, max_retries)
        self.max_bytes = max(1, max_bytes)
        self.user_agent = user_agent
        self.backoff_cap = max(0.0, backoff_cap)

    def fetch(self, source_url: str) -> SourceResult:
        attempts = 0
        last_error = "fetch failed"
        status_code: int | None = None
        for attempt in range(self.max_retries + 1):
            attempts = attempt + 1
            response: Any | None = None
            try:
                response = self.http_client.get(
                    source_url,
                    headers={"User-Agent": self.user_agent, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"},
                    timeout=self.timeout,
                )
                status_code = int(getattr(response, "status_code", 200))
                if status_code == 429 or 500 <= status_code <= 599:
                    raise httpx.HTTPStatusError(f"transient HTTP {status_code}", request=getattr(response, "request", None), response=response)
                if 400 <= status_code <= 499:
                    return SourceResult(source_url=source_url, status_code=status_code, attempts=attempts, error=f"permanent HTTP {status_code}", fetched_at=self.clock())
                payload = _body_from_response(response, self.max_bytes)
                return SourceResult(source_url=source_url, status_code=status_code, attempts=attempts, payload=payload, fetched_at=self.clock())
            except (httpx.HTTPError, OSError, TimeoutError, ValueError) as exc:
                last_error = str(exc) or exc.__class__.__name__
                if attempt >= self.max_retries:
                    break
                retry_after = None
                headers = getattr(response, "headers", None)
                if headers is not None:
                    retry_after = headers.get("Retry-After")
                delay = _retry_after(retry_after, self.clock, self.backoff_cap) if retry_after else min(self.backoff_cap, 2.0**attempt)
                self.sleep(delay)
            except Exception as exc:  # isolate unexpected source/client failures
                last_error = str(exc) or exc.__class__.__name__
                break
        return SourceResult(source_url=source_url, status_code=status_code, attempts=attempts, error=last_error, fetched_at=self.clock())

    def close(self) -> None:
        close = getattr(self.http_client, "close", None)
        if callable(close):
            close()


def fetch_sources(urls: Iterable[str], **kwargs: Any) -> tuple[SourceResult, ...]:
    fetcher = FeedFetcher(**kwargs)
    try:
        return tuple(fetcher.fetch(url) for url in urls)
    finally:
        fetcher.close()


def fetch_feed(source_url: str, **kwargs: Any) -> SourceResult:
    fetcher = FeedFetcher(**kwargs)
    try:
        return fetcher.fetch(source_url)
    finally:
        fetcher.close()


class FixtureFetcher:
    """Offline fetcher that returns fixture bytes through the production parser path."""

    def __init__(self, fixture_dir: str | Path) -> None:
        self.fixture_dir = Path(fixture_dir)

    def fetch(self, source_url: str) -> SourceResult:
        path = self.fixture_dir / source_url
        return SourceResult(source_url=source_url, payload=path.read_bytes(), attempts=1)
