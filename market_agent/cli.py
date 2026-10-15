"""Command-line interface for live cycles and offline demonstrations."""

from __future__ import annotations

import argparse
from pathlib import Path

from .agent import run_cycle
from .analyzer import MarketAnalyzer
from .config import load_settings
from .fetcher import FeedFetcher, FixtureFetcher
from .state import InMemoryState, StateStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="market-agent", description="Autonomous Market & News Intelligence Agent")
    parser.add_argument("--demo", action="store_true", help="Run the synthetic offline fixture demo.")
    parser.add_argument("--output-dir", dest="OUTPUT_DIR", help="Relative directory for generated reports.")
    parser.add_argument("--data-dir", dest="DATA_DIR", help="Relative directory for persistent state.")
    parser.add_argument("--log-level", dest="LOG_LEVEL", choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    overrides = {key: value for key, value in vars(args).items() if key.isupper() and value is not None}
    settings = load_settings(overrides)
    if args.demo:
        fixture = FixtureFetcher(Path(__file__).resolve().parent.parent / "sample_data")
        result = run_cycle(("synthetic_feed.xml",), fixture, MarketAnalyzer(), InMemoryState(), settings.output_dir, run_id="synthetic-demo", synthetic=True, bypass_lookback=True)
        print(f"Synthetic demo {result.status}: {result.report_path or 'no report'}")
        return 0 if result.status in {"success", "partial"} else 1
    fetcher = FeedFetcher(timeout=settings.http_timeout_seconds, max_retries=settings.max_retries, max_bytes=settings.max_feed_bytes)
    result = run_cycle(settings.rss_urls, fetcher, MarketAnalyzer(), StateStore(settings.data_dir), settings.output_dir, lookback_hours=settings.lookback_hours, watchlist_keywords=settings.watchlist_keywords, max_items_per_feed=settings.max_items_per_feed)
    print(f"Cycle {result.status}: {result.report_path or 'no report'}")
    return 0 if result.status in {"success", "partial"} else 1
