"""Command-line interface for the initial agent scaffold."""

from __future__ import annotations

import argparse

from .config import load_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="market-agent",
        description="Autonomous Market & News Intelligence Agent (initial scaffold).",
    )
    parser.add_argument("--output-dir", dest="OUTPUT_DIR", help="Relative directory for generated reports.")
    parser.add_argument("--data-dir", dest="DATA_DIR", help="Relative directory for persistent state.")
    parser.add_argument("--log-level", dest="LOG_LEVEL", choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    overrides = {key: value for key, value in vars(args).items() if value is not None}
    load_settings(overrides)
    print("Scaffold ready; data fetching and analysis pipeline are not implemented yet.")
    return 0
