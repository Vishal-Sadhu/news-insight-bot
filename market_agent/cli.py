"""Usable CLI for one-shot and continuous market/news monitoring."""

from __future__ import annotations

import argparse
import logging
import signal
import threading
from pathlib import Path
from typing import Any

from .agent import run_cycle
from .analyzer import MarketAnalyzer
from .config import Settings, load_settings
from .fetcher import FeedFetcher, FixtureFetcher
from .models import RunResult
from .state import InMemoryState, StateStore
from .watch import WatchPolicy, run_watch

logger = logging.getLogger("market_agent")


class UtcFormatter(logging.Formatter):
    converter = __import__("time").gmtime


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(UtcFormatter("%(asctime)sZ %(levelname)s %(name)s %(message)s", "%Y-%m-%dT%H:%M:%S"))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="market-agent",
        description="Autonomous Market & News Intelligence Agent: continuously observes configured feeds, selects unseen relevant items, analyzes and reports them, and remembers processed IDs.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (("run-once", "Run one observation and reporting cycle."), ("watch", "Run cycles continuously until interrupted.")):
        subparser = subparsers.add_parser(name, help=help_text)
        subparser.add_argument("--demo", action="store_true", help="Use synthetic local fixtures without network or live state.")
        subparser.add_argument("--output-dir", dest="OUTPUT_DIR", help="Relative directory for reports.")
        subparser.add_argument("--data-dir", dest="DATA_DIR", help="Relative directory for SQLite state.")
        subparser.add_argument("--log-level", dest="LOG_LEVEL", choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"))
        if name == "watch":
            subparser.add_argument("--interval", type=float, help="Seconds between successful cycles; defaults to POLL_INTERVAL_SECONDS.")
    return parser


def _settings(args: argparse.Namespace) -> Settings:
    overrides = {key: value for key, value in vars(args).items() if key.isupper() and value is not None}
    return load_settings(overrides)


def _relative(path: str | Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path)


def _log_result(result: RunResult) -> None:
    source_count = len(result.source_results)
    logger.info("run_id=%s status=%s sources=%d articles=%d errors=%d report=%s", result.run_id, result.status, source_count, len(result.articles), len(result.errors), _relative(result.report_path) if result.report_path else "none")
    for source in result.source_results:
        logger.info("run_id=%s source=%s status=%s articles=%d attempts=%d", result.run_id, source.source_url, "failed" if source.error else "ok", len(source.articles), source.attempts)


def _components(settings: Settings, *, demo: bool) -> tuple[Any, Any, Any, tuple[str, ...], bool]:
    if demo:
        return FixtureFetcher(Path(__file__).resolve().parent.parent / "sample_data"), InMemoryState(), MarketAnalyzer(), ("synthetic_feed.xml",), True
    return FeedFetcher(timeout=settings.http_timeout_seconds, max_retries=settings.max_retries, max_bytes=settings.max_feed_bytes), StateStore(settings.data_dir), MarketAnalyzer(), settings.rss_urls, False


def _run_once(settings: Settings, *, demo: bool) -> int:
    fetcher, store, analyzer, sources, synthetic = _components(settings, demo=demo)
    try:
        result = run_cycle(sources, fetcher, analyzer, store, settings.output_dir, lookback_hours=settings.lookback_hours, watchlist_keywords=settings.watchlist_keywords, max_items_per_feed=settings.max_items_per_feed, synthetic=synthetic, bypass_lookback=synthetic)
        _log_result(result)
        if result.report_path:
            print(f"Completed {result.status} cycle; report: {_relative(result.report_path)}")
        return 0 if result.status in {"success", "partial"} else 1
    except Exception:
        logger.exception("run-once failed before a successful report publication")
        return 1
    finally:
        for resource in (fetcher, store):
            close = getattr(resource, "close", None)
            if callable(close):
                close()


def _watch(settings: Settings, *, demo: bool, interval: float | None) -> int:
    fetcher, store, analyzer, sources, synthetic = _components(settings, demo=demo)
    stop_event = threading.Event()
    handlers: dict[int, Any] = {}

    def stop(signum: int, _frame: Any) -> None:
        logger.info("shutdown requested signal=%s", signum)
        stop_event.set()

    try:
        for signum in (signal.SIGINT, signal.SIGTERM):
            handlers[signum] = signal.getsignal(signum)
            signal.signal(signum, stop)
        def cycle() -> RunResult:
            return run_cycle(sources, fetcher, analyzer, store, settings.output_dir, lookback_hours=settings.lookback_hours, watchlist_keywords=settings.watchlist_keywords, max_items_per_feed=settings.max_items_per_feed, synthetic=synthetic, bypass_lookback=synthetic)
        run_watch(cycle, interval=interval or settings.poll_interval_seconds, stop_event=stop_event, on_result=_log_result)
        return 0
    finally:
        for signum, previous in handlers.items():
            signal.signal(signum, previous)
        for resource in (fetcher, store):
            close = getattr(resource, "close", None)
            if callable(close):
                close()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        try:
            args = parser.parse_args(argv)
        except SystemExit as exc:
            return int(exc.code)
        settings = _settings(args)
        configure_logging(settings.log_level)
        if args.command == "run-once":
            return _run_once(settings, demo=args.demo)
        return _watch(settings, demo=args.demo, interval=args.interval)
    except (ValueError, TypeError) as exc:
        parser.print_usage()
        print(f"market-agent: error: {exc}")
        return 2
    except KeyboardInterrupt:
        logger.info("shutdown requested by keyboard interrupt")
        return 0
