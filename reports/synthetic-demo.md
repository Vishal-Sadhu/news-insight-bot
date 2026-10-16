# Autonomous Market & News Intelligence Report

## Run Metadata

- Run ID: `synthetic\-demo`
- Generated (UTC): 2026\-10\-15T16:12:39\.245248\+00:00
- Report type: SYNTHETIC DEMO
- Reported items: 2

## Executive Summary

Reported 2 qualifying item(s). Aggregate sentiment covers only these reported items.

## Sentiment Overview

- Positive: 1
- Neutral: 0
- Negative: 1

## Key Catalysts

- **interest\_rates\_and\_central\_banks** — SYNTHETIC: Central bank holds interest rates ([source](https://example.invalid/synthetic/rates-001))
- **earnings\_and\_guidance** — SYNTHETIC: Company reports quarterly earnings ([source](https://example.invalid/synthetic/earnings-002))

## Articles

1. [SYNTHETIC: Company reports quarterly earnings](https://example.invalid/synthetic/earnings-002)
   - Source: synthetic\_feed\.xml
   - Published (UTC): 2026\-10\-15T07:00:00\+00:00
   - Sentiment: negative (-0.128)
   - Summary: SYNTHETIC: Company reports quarterly earnings Synthetic quarterly earnings were reported for offline pipeline validation\.
2. [SYNTHETIC: Central bank holds interest rates](https://example.invalid/synthetic/rates-001?utm_source=fixture)
   - Source: synthetic\_feed\.xml
   - Published (UTC): 2026\-10\-15T08:00:00\+00:00
   - Sentiment: positive (0.586)
   - Summary: SYNTHETIC: Central bank holds interest rates The synthetic central bank held interest rates steady\.

## Source Health

- synthetic\_feed\.xml: ok — 2 qualifying item\(s\), 1 attempt\(s\)

## Limitations

- Feed content is untrusted and was not supplemented with linked article pages.
- Processing is at-least-once: a crash after report publication and before SQLite commit can cause an item to be reported again.
