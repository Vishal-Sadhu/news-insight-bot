# Offline fixtures

`synthetic_feed.xml` is deliberately labelled `SYNTHETIC` and is consumed by
`FixtureFetcher`, then parsed by the same `feedparser` normalization path as
live sources. The demo uses fresh in-memory state, bypasses live lookback
filtering for its static dates, and writes `reports/latest-demo.md` without
touching live SQLite state or `reports/latest.md`.
