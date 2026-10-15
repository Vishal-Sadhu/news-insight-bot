"""Domain models for future market and news processing."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class NewsItem:
    """A normalized news item."""

    title: str
    url: str
    published_at: datetime | None = None
    summary: str = ""
