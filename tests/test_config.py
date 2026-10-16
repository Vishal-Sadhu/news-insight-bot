import pytest

from market_agent.config import load_settings


def test_defaults_are_valid_and_resolve_relative_paths(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    settings = load_settings(environ={})
    assert settings.output_dir == tmp_path / "reports"
    assert settings.state_path == tmp_path / "data" / "state.sqlite3"
    assert settings.rss_urls[0].startswith("https://")


def test_cli_overrides_environment_and_dotenv(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("OUTPUT_DIR=dotenv\n", encoding="utf-8")
    settings = load_settings(
        {"OUTPUT_DIR": "cli-output"},
        environ={"OUTPUT_DIR": "environment"},
    )
    assert settings.output_dir == tmp_path / "cli-output"


@pytest.mark.parametrize("value", ["/tmp/reports", "../reports", "reports/../outside"])
def test_paths_must_be_safe_relative_paths(value):
    with pytest.raises(ValueError, match="relative path"):
        load_settings({"OUTPUT_DIR": value}, environ={})


def test_urls_must_be_http_or_https():
    with pytest.raises(ValueError, match=r"invalid HTTP\(S\) URL"):
        load_settings({"RSS_URLS": '["ftp://example.com/feed"]'}, environ={})


def test_invalid_json_numeric_bounds_and_path_validation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="RSS_URLS must be a JSON array"):
        load_settings({"RSS_URLS": "not-json"}, environ={})
    with pytest.raises(ValueError, match="POLL_INTERVAL_SECONDS"):
        load_settings({"POLL_INTERVAL_SECONDS": "0"}, environ={})
    with pytest.raises(ValueError, match="MAX_FEED_BYTES"):
        load_settings({"MAX_FEED_BYTES": "-1"}, environ={})
    for value in ("/absolute/reports", "../reports", "reports/../outside", r"C:\\reports"):
        with pytest.raises(ValueError, match="relative path"):
            load_settings({"OUTPUT_DIR": value}, environ={})


def test_precedence_includes_environment_dotenv_and_cli(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text('OUTPUT_DIR=dotenv\nPOLL_INTERVAL_SECONDS=30\n', encoding="utf-8")
    settings = load_settings({"OUTPUT_DIR": "cli", "POLL_INTERVAL_SECONDS": "10"}, environ={"OUTPUT_DIR": "environment"})
    assert settings.output_dir == tmp_path / "cli"
    assert settings.poll_interval_seconds == 10
    dotenv_settings = load_settings(environ={"OUTPUT_DIR": "environment"})
    assert dotenv_settings.output_dir == tmp_path / "environment"
    assert dotenv_settings.poll_interval_seconds == 30
