from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from market_agent.agent import run_cycle
from market_agent.analyzer import analyze
from market_agent.fetcher import FeedFetcher
from market_agent.models import NormalizedArticle, SourceResult
from market_agent.processor import canonicalize_url, clean_text, process_source
from market_agent.reporter import render_report
from market_agent.state import StateStore


NOW = datetime(2026, 10, 16, 12, tzinfo=timezone.utc)


def _feed(body: str) -> bytes:
    return body.encode("utf-8")


def test_rss_and_atom_normalization_cleanup_dates_and_missing_fields():
    rss = _feed("""<rss version='2.0'><channel><title>Demo</title>
      <item><title><![CDATA[Rates &amp; Markets]]></title><link>https://example.test/a?utm_source=x&amp;view=full#frag</link>
      <pubDate>Fri, 16 Oct 2026 10:00:00 GMT</pubDate><description><![CDATA[<b>Inflation</b> &amp; rates.]]></description></item>
      <item><title>Undated</title><description>No link or date</description></item>
    </channel></rss>""")
    atom = _feed("""<feed xmlns='http://www.w3.org/2005/Atom'><title>Atom</title>
      <entry><title>Atom item</title><link href='https://example.test/atom'/><updated>2026-10-16T11:00:00Z</updated>
      <summary>Atom <i>summary</i></summary></entry></feed>""")
    rss_result = process_source(SourceResult("rss", payload=rss), now=NOW, bypass_lookback=True)
    atom_result = process_source(SourceResult("atom", payload=atom), now=NOW, bypass_lookback=True)
    assert rss_result.articles[0].published_at == datetime(2026, 10, 16, 10, tzinfo=timezone.utc)
    assert rss_result.articles[0].summary == "Inflation & rates."
    assert rss_result.articles[0].canonical_url == "https://example.test/a?view=full"
    assert rss_result.articles[1].published_at is None
    assert any("Undated article" in warning for warning in rss_result.warnings)
    assert atom_result.articles[0].summary == "Atom summary"


def test_malformed_feed_is_unusable_and_clean_text_is_safe():
    result = process_source(SourceResult("bad", payload=b"not xml at all"), now=NOW)
    assert result.error and "unusable feed" in result.error
    assert clean_text(" <b>Hello</b> &amp;  world ") == "Hello & world"


def test_canonicalization_preserves_meaningful_query_parameters():
    assert canonicalize_url("HTTPS://Example.TEST/path/?utm_campaign=x&item=42#part") == "https://example.test/path?item=42"


def test_lookback_watchlist_and_in_batch_deduplication():
    payload = _feed("""<rss version='2.0'><channel>
      <item><title>Target earnings</title><link>https://example.test/story?x=1&amp;utm_source=a</link><pubDate>Fri, 16 Oct 2026 11:00:00 GMT</pubDate><description>Profit update</description></item>
      <item><title>Duplicate target</title><link>https://example.test/story?x=1&amp;utm_medium=b</link><pubDate>Fri, 16 Oct 2026 11:01:00 GMT</pubDate><description>Profit update</description></item>
      <item><title>Old target</title><link>https://example.test/old</link><pubDate>Thu, 1 Jan 2020 00:00:00 GMT</pubDate><description>Profit update</description></item>
      <item><title>Other</title><link>https://example.test/other</link><pubDate>Fri, 16 Oct 2026 11:00:00 GMT</pubDate><description>Weather</description></item>
    </channel></rss>""")
    result = process_source(SourceResult("rss", payload=payload), now=NOW, lookback_hours=24, watchlist_keywords=("target",))
    assert len(result.articles) == 1
    assert result.articles[0].title == "Target earnings"


def test_bounded_retries_with_mock_transport_and_partial_sources():
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] < 3:
            return httpx.Response(503, headers={"Retry-After": "999"})
        return httpx.Response(200, content=b"<rss><channel /></rss>")

    sleeps: list[float] = []
    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = FeedFetcher(client, sleep=sleeps.append, max_retries=2, backoff_cap=4).fetch("https://example.test/feed")
    assert result.error is None and result.attempts == 3
    assert sleeps == [4, 4]
    client.close()

    failing = FeedFetcher(httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(500))), max_retries=1, sleep=lambda _: None)
    failed = failing.fetch("https://example.test/failing")
    assert failed.error and failed.attempts == 2
    failing.close()


def _article() -> NormalizedArticle:
    return NormalizedArticle("Quarterly earnings beat estimates", "https://example.test/a", "https://example.test/a", NOW, "The company reported strong earnings and a central bank rate cut.", source="feed", article_id="article-1")


def test_sentiment_and_evidence_backed_catalyst_detection():
    positive = _article()
    negative = NormalizedArticle("Company faces lawsuit", "https://example.test/b", "https://example.test/b", NOW, "The company faces a damaging lawsuit and default.", source="feed", article_id="b")
    neutral = NormalizedArticle("Company holds meeting", "https://example.test/c", "https://example.test/c", NOW, "The company held a meeting.", source="feed", article_id="c")
    analyzed = analyze((positive, negative, neutral))
    assert analyzed[0].sentiment_label == "positive"
    assert analyzed[1].sentiment_label == "negative"
    assert analyzed[2].sentiment_label == "neutral"
    assert analyzed[0].catalysts[0].evidence_snippet in analyzed[0].summary
    assert analyzed[0].catalysts[0].source_reference == positive.canonical_url


def test_report_sections_safe_links_and_no_new_items():
    from market_agent.analyzer import analyze

    article = analyze((_article(),))[0]
    source = SourceResult("https://example.test/feed", articles=(article.article,), attempts=1)
    report = render_report(run_id="run-1", generated_at=NOW, analyzed_articles=(article,), source_results=(source,))
    for section in ("Run Metadata", "Executive Summary", "Sentiment Overview", "Key Catalysts", "Articles", "Source Health", "Limitations"):
        assert f"## {section}" in report
    assert "[Quarterly earnings beat estimates](https://example.test/a)" in report
    assert "<script>" not in report
    empty = render_report(run_id="run-2", generated_at=NOW, source_results=(source,))
    assert "No new qualifying items." in empty


def test_persistent_deduplication_and_publication_failure(tmp_path: Path):
    source = SourceResult("feed", payload=b"<rss version='2.0'><channel><item><title>New</title><link>https://example.test/new</link><pubDate>Fri, 16 Oct 2026 11:00:00 GMT</pubDate><description>Good earnings news.</description></item></channel></rss>")
    class Fetcher:
        def fetch(self, _source):
            return source

    database = tmp_path / "data"
    first_store = StateStore(database)
    first = run_cycle(("feed",), Fetcher(), type("A", (), {"analyze": staticmethod(analyze)})(), first_store, tmp_path / "reports", clock=lambda: NOW, run_id="first")
    assert first.status == "success" and len(first.articles) == 1
    first_store.close()
    second_store = StateStore(database)
    second = run_cycle(("feed",), Fetcher(), type("A", (), {"analyze": staticmethod(analyze)})(), second_store, tmp_path / "reports", clock=lambda: NOW, run_id="second")
    assert second.status == "success" and len(second.articles) == 0

    third_store = StateStore(tmp_path / "failure-data")
    failed = run_cycle(("feed",), Fetcher(), type("A", (), {"analyze": staticmethod(analyze)})(), third_store, tmp_path / "failure-reports", clock=lambda: NOW, run_id="failed", publisher=lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk full")))
    assert failed.status == "failed"
    # The article remains eligible after publication failure.
    retry = run_cycle(("feed",), Fetcher(), type("A", (), {"analyze": staticmethod(analyze)})(), third_store, tmp_path / "failure-reports", clock=lambda: NOW, run_id="retry")
    assert len(retry.articles) == 1


def test_partial_source_success_and_all_source_failure(tmp_path: Path):
    good = SourceResult("good", payload=b"<rss version='2.0'><channel><item><title>Good</title><link>https://example.test/good</link><description>Good news.</description></item></channel></rss>")

    class MixedFetcher:
        def fetch(self, source):
            return good if source == "good" else SourceResult(source, error="offline")

    analyzer = type("A", (), {"analyze": staticmethod(analyze)})()
    partial = run_cycle(("good", "bad"), MixedFetcher(), analyzer, StateStore(tmp_path / "partial-data"), tmp_path / "partial-reports", clock=lambda: NOW, run_id="partial")
    assert partial.status == "partial"
    assert partial.report_path
    assert any(result.error for result in partial.source_results)

    class DownFetcher:
        def fetch(self, source):
            return SourceResult(source, error="unavailable")

    failed = run_cycle(("one", "two"), DownFetcher(), analyzer, StateStore(tmp_path / "all-failed-data"), tmp_path / "all-failed-reports", clock=lambda: NOW, run_id="all-failed")
    assert failed.status == "failed"
    assert failed.report_path is None
    assert not (tmp_path / "all-failed-reports" / "latest.md").exists()
