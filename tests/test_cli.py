from datetime import datetime, timezone
from pathlib import Path
import threading

from market_agent.cli import main
from market_agent.models import RunResult
from market_agent.watch import run_watch


def test_run_once_demo_can_repeat_without_live_state(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["run-once", "--demo"]) == 0
    first = (tmp_path / "reports" / "latest-demo.md").read_text(encoding="utf-8")
    assert main(["run-once", "--demo"]) == 0
    second = (tmp_path / "reports" / "latest-demo.md").read_text(encoding="utf-8")
    assert "SYNTHETIC DEMO" in first
    assert "SYNTHETIC DEMO" in second
    assert not (tmp_path / "data" / "state.sqlite3").exists()
    assert "report: reports" in capsys.readouterr().out


def test_watch_runs_sequentially_and_wait_is_injectable():
    calls: list[int] = []
    waits: list[float] = []
    stop = threading.Event()

    def cycle() -> RunResult:
        calls.append(len(calls))
        if len(calls) == 2:
            stop.set()
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        return RunResult(run_id=str(len(calls)), status="success", started_at=now, completed_at=now)

    def wait(seconds: float) -> bool:
        waits.append(seconds)
        return stop.is_set()

    assert run_watch(cycle, interval=900, stop_event=stop, wait=wait) == 0
    assert calls == [0, 1]
    assert waits == [900]


def test_invalid_subcommand_option_returns_exit_code_two(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main(["run-once", "--interval", "not-a-number"]) == 2
