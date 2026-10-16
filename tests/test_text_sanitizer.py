import pytest

from market_agent.utils.text_sanitizer import (
    is_meaningful,
    normalize_whitespace,
    strip_html,
    truncate,
)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("Plain financial news", "Plain financial news"),
        ("<p><strong>Bitcoin</strong> rises</p>", "Bitcoin rises"),
        ("<div><p>Nested <em>market</em> update</p></div>", "Nested market update"),
        ("<p>Broken <b>markup", "Broken markup"),
        ("Revenue &amp; profit &lt;estimate&gt; &quot;beat&quot; &#39;today&#39; &nbsp;now", 'Revenue & profit <estimate> "beat" \'today\' now'),
    ],
)
def test_strip_html_removes_markup_and_decodes_entities(source, expected):
    assert strip_html(source) == expected


def test_normalize_whitespace_collapses_multiline_input():
    assert normalize_whitespace("  market\t\n\n news  prices \r\n now  ") == "market news prices now"


def test_truncate_returns_original_text_within_limit():
    text = "Short article"
    assert truncate(text, max_length=len(text)) == text


def test_truncate_uses_word_boundary_and_exact_length():
    result = truncate("Bitcoin markets rally after earnings report", max_length=28)
    assert result == "Bitcoin markets rally..."
    assert len(result) <= 28
    assert not result[:-3].endswith(" ")


def test_truncate_can_fill_the_exact_limit():
    assert truncate("abcdefghij", max_length=7) == "abcd..."


def test_truncate_handles_middle_of_word_and_custom_suffix():
    result = truncate("Cryptocurrency", max_length=10, suffix="…")
    assert result == "Cryptocur…"
    assert len(result) == 10


def test_truncate_rejects_suffix_longer_than_limit():
    with pytest.raises(ValueError):
        truncate("text", max_length=2, suffix="...")


@pytest.mark.parametrize(
    ("text", "minimum", "expected"),
    [
        ("one two", 3, False),
        ("one two three", 3, True),
        ("  one\n two\tthree  ", 3, True),
        ("", 1, False),
        ("", 0, True),
    ],
)
def test_is_meaningful_word_count_boundaries(text, minimum, expected):
    assert is_meaningful(text, minimum) is expected


def test_is_meaningful_rejects_negative_minimum():
    with pytest.raises(ValueError):
        is_meaningful("one", -1)


def test_unicode_text_and_symbols_are_preserved():
    text = "🚀 Bitcoin gained $100, €90, and ₹8,000"
    assert strip_html(f"<p>{text}</p>") == text
    assert is_meaningful(text, min_words=5)
    assert truncate(text, max_length=25, suffix="…").endswith("…")
