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
