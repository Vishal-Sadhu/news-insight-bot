"""Application configuration loading and validation."""

from __future__ import annotations

import json
import ntpath
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping
from urllib.parse import urlparse

DEFAULTS: dict[str, object] = {
    "RSS_URLS": [
        "https://feeds.bbci.co.uk/news/business/rss.xml",
        "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    ],
    "OUTPUT_DIR": "reports",
    "DATA_DIR": "data",
    "POLL_INTERVAL_SECONDS": 900,
    "HTTP_TIMEOUT_SECONDS": 15,
    "MAX_RETRIES": 2,
    "MAX_FEED_BYTES": 2_097_152,
    "MAX_ITEMS_PER_FEED": 50,
    "LOOKBACK_HOURS": 24,
    "WATCHLIST_KEYWORDS": [],
    "LOG_LEVEL": "INFO",
}
ENV_KEYS = tuple(DEFAULTS)
LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


@dataclass(frozen=True, slots=True)
class Settings:
    """Validated settings for the agent runtime."""

    rss_urls: tuple[str, ...]
    output_dir: Path
    data_dir: Path
    poll_interval_seconds: int = 900
    http_timeout_seconds: int = 15
    max_retries: int = 2
    max_feed_bytes: int = 2_097_152
    max_items_per_feed: int = 50
    lookback_hours: int = 24
    watchlist_keywords: tuple[str, ...] = field(default_factory=tuple)
    log_level: str = "INFO"

    @property
    def state_path(self) -> Path:
        """Return the SQLite state path under the configured data directory."""

        return self.data_dir / "state.sqlite3"


def _parse_json_array(name: str, value: object) -> list[object]:
    if isinstance(value, (list, tuple)):
        parsed = list(value)
    else:
        try:
            parsed = json.loads(str(value))
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError(f"{name} must be a JSON array") from exc
    if not isinstance(parsed, list):
        raise ValueError(f"{name} must be a JSON array")
    return parsed


def _parse_urls(value: object) -> tuple[str, ...]:
    urls = _parse_json_array("RSS_URLS", value)
    if not urls or any(not isinstance(url, str) or not url.strip() for url in urls):
        raise ValueError("RSS_URLS must contain at least one non-empty URL")
    normalized = tuple(url.strip() for url in urls)
    for url in normalized:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(f"RSS_URLS contains an invalid HTTP(S) URL: {url}")
    return normalized


def _parse_keywords(value: object) -> tuple[str, ...]:
    keywords = _parse_json_array("WATCHLIST_KEYWORDS", value)
    if any(not isinstance(keyword, str) for keyword in keywords):
        raise ValueError("WATCHLIST_KEYWORDS must contain only strings")
    return tuple(keyword.strip() for keyword in keywords if keyword.strip())


def _parse_int(name: str, value: object, *, minimum: int, maximum: int | None = None) -> int:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if parsed < minimum or (maximum is not None and parsed > maximum):
        bound = f" between {minimum} and {maximum}" if maximum is not None else f" >= {minimum}"
        raise ValueError(f"{name} must be{bound}")
    return parsed


def _safe_relative_path(name: str, value: object) -> Path:
    raw = str(value).strip()
    path = Path(raw)
    if not raw or path.is_absolute() or ntpath.isabs(raw) or ".." in path.parts or ".." in ntpath.normpath(raw).split(ntpath.sep):
        raise ValueError(f"{name} must be a non-empty relative path without parent traversal")
    return Path.cwd() / path


def load_settings(
    cli_overrides: Mapping[str, object] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    dotenv_path: str | Path = ".env",
) -> Settings:
    """Load settings with CLI > environment > local .env > defaults precedence."""

    process_environment = os.environ if environ is None else environ
    if Path(dotenv_path).is_file():
        from dotenv import dotenv_values

        local_dotenv = dotenv_values(dotenv_path)
    else:
        local_dotenv = {}
    overrides = cli_overrides or {}
    values: dict[str, object] = {}
    for key in ENV_KEYS:
        if key in overrides and overrides[key] is not None:
            values[key] = overrides[key]
        elif key in process_environment:
            values[key] = process_environment[key]
        elif key in local_dotenv and local_dotenv[key] is not None:
            values[key] = local_dotenv[key]
        else:
            values[key] = DEFAULTS[key]

    level = str(values["LOG_LEVEL"]).upper()
    if level not in LOG_LEVELS:
        raise ValueError(f"LOG_LEVEL must be one of: {', '.join(sorted(LOG_LEVELS))}")
    return Settings(
        rss_urls=_parse_urls(values["RSS_URLS"]),
        output_dir=_safe_relative_path("OUTPUT_DIR", values["OUTPUT_DIR"]),
        data_dir=_safe_relative_path("DATA_DIR", values["DATA_DIR"]),
        poll_interval_seconds=_parse_int("POLL_INTERVAL_SECONDS", values["POLL_INTERVAL_SECONDS"], minimum=1),
        http_timeout_seconds=_parse_int("HTTP_TIMEOUT_SECONDS", values["HTTP_TIMEOUT_SECONDS"], minimum=1),
        max_retries=_parse_int("MAX_RETRIES", values["MAX_RETRIES"], minimum=0),
        max_feed_bytes=_parse_int("MAX_FEED_BYTES", values["MAX_FEED_BYTES"], minimum=1),
        max_items_per_feed=_parse_int("MAX_ITEMS_PER_FEED", values["MAX_ITEMS_PER_FEED"], minimum=1),
        lookback_hours=_parse_int("LOOKBACK_HOURS", values["LOOKBACK_HOURS"], minimum=1),
        watchlist_keywords=_parse_keywords(values["WATCHLIST_KEYWORDS"]),
        log_level=level,
    )
