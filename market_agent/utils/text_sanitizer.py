"""Pure standard-library helpers for cleaning incoming article text."""

from __future__ import annotations

import html
import re

_TAG_RE = re.compile(r"<[^>]*>|<[^>]*$")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_whitespace(text: str) -> str:
    """Collapse whitespace runs and trim the result."""

    return _WHITESPACE_RE.sub(" ", text).strip()


def strip_html(text: str) -> str:
    """Remove markup, decode HTML entities, and normalize whitespace."""

    without_tags = _TAG_RE.sub(" ", text)
    return normalize_whitespace(html.unescape(without_tags))


def truncate(text: str, max_length: int = 280, suffix: str = "...") -> str:
    """Limit text without splitting a word when possible."""

    if max_length < len(suffix):
        raise ValueError("max_length must be at least as long as suffix")
    if len(text) <= max_length:
        return text

    available = max_length - len(suffix)
    boundary = text[:available].rstrip()
    if available < len(text) and not text[available].isspace():
        boundary = boundary.rsplit(" ", 1)[0] if " " in boundary else ""
    if not boundary:
        boundary = text[:available].rstrip()
    return boundary + suffix


def is_meaningful(text: str, min_words: int = 3) -> bool:
    """Return whether normalized text contains at least ``min_words`` words."""

    if min_words < 0:
        raise ValueError("min_words must not be negative")
    normalized = normalize_whitespace(text)
    return len(normalized.split(" ")) >= min_words if normalized else min_words == 0
