# Autonomous Market & News Intelligence Agent

Python 3.11 implementation of a separated market/news intelligence pipeline. It continuously observes configured RSS/Atom feeds, selects unseen relevant items, performs deterministic sentiment and catalyst analysis, publishes Markdown reports, remembers processed IDs, and recovers from transient cycle failures. It does not use an LLM or claim model-based reasoning.

## Setup

The project is pinned to Python 3.11.2 in `.python-version`.

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install --upgrade pip pip-tools
.venv/bin/pip-sync requirements-dev.txt
```

If network access is unavailable, dependency installation cannot complete. The lockfiles are checked in for reproducible installation when the package index is reachable.

## Configuration

Copy `.env.example` to `.env` when local overrides are needed. Configuration precedence is CLI overrides, process environment, local `.env`, then defaults. `.env` is not tracked.

```bash
cp .env.example .env
```

## Run

```bash
.venv/bin/python main.py --help
.venv/bin/python main.py run-once
.venv/bin/python main.py watch --interval 900
```

Options must follow the subcommand, for example:

```bash
.venv/bin/python main.py run-once --output-dir reports --data-dir data --log-level INFO
```

`run-once` returns 0 for a published full, partial-source, or no-new-items
report; 1 for source-wide or runtime failures; and 2 for invalid arguments or
configuration. `watch` runs the first cycle immediately, then waits
interruptibly and sequentially between cycles. SIGINT and SIGTERM request a
graceful shutdown. Failed cycles use bounded exponential recovery backoff,
which resets after success.

Run the fully offline synthetic pipeline with:

```bash
.venv/bin/python main.py run-once --demo
```

The demo uses `sample_data/synthetic_feed.xml`, fresh in-memory state, and
writes `reports/latest-demo.md`. It does not call the network or alter the
live SQLite state or `reports/latest.md`.

## Test

```bash
make test
```

Regenerate lockfiles after changing an input file:

```bash
.venv/bin/pip-compile --output-file=requirements.txt requirements.in
.venv/bin/pip-compile --constraint=requirements.txt --output-file=requirements-dev.txt requirements-dev.in
```

## Docker

```bash
docker build -t market-intelligence-agent .
docker run --rm market-intelligence-agent
```

No deployment target is configured for this initial scaffold.
