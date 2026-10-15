from datetime import datetime, timezone
from pathlib import Path

from market_agent.agent import run_cycle
from market_agent.analyzer import MarketAnalyzer
from market_agent.fetcher import FixtureFetcher
from market_agent.state import InMemoryState


def test_synthetic_fixture_cycle_is_offline_and_uses_demo_latest(tmp_path: Path):
    fixture_dir = Path(__file__).parents[1] / "sample_data"
    output_dir = tmp_path / "reports"
    result = run_cycle(
        ("synthetic_feed.xml",),
        FixtureFetcher(fixture_dir),
        MarketAnalyzer(),
        InMemoryState(),
        output_dir,
        clock=lambda: datetime(2026, 10, 15, 12, tzinfo=timezone.utc),
        run_id="synthetic-smoke",
        synthetic=True,
        bypass_lookback=True,
    )
    assert result.status == "success"
    assert len(result.articles) == 2
    assert (output_dir / "latest-demo.md").is_file()
    assert not (output_dir / "latest.md").exists()
    report = (output_dir / "latest-demo.md").read_text(encoding="utf-8")
    assert "SYNTHETIC DEMO" in report
    assert "## Run Metadata" in report
    assert "## Source Health" in report
