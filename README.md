# Autonomous Market & News Intelligence Agent

Initial Python 3.11 scaffold for a separated market/news intelligence pipeline. Fetching, processing, analysis, persistence, reporting, and orchestration boundaries are present; the pipeline implementation will be added in subsequent steps.

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
.venv/bin/python main.py
```

The current command confirms the scaffold is ready and intentionally does not run an unfinished pipeline.

Run the fully offline synthetic pipeline with:

```bash
.venv/bin/python main.py --demo
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
