# ADR 0001: Retain Yahoo provisionally; define a free-provider migration path

- **Date:** 2026-11-08
- **Status:** Accepted direction; migration deferred pending coverage validation

## Context

Repeated Yahoo failures undermined dashboard availability. Investigation found application request
amplification and an unrelated health probe that could block the actual client; these were corrected
in [PR #60](https://github.com/efileger/value-dashboard/pull/60). External Yahoo reliability remains
unverified. Constraints are **free only**, **private personal use**, and delayed/end-of-day quotes.

## Decision

Retain the corrected Yahoo integration provisionally. If production failures persist, pilot
**Finnhub quotes/basic metrics + SEC EDGAR fundamentals**, with **Twelve Data** as an alternative
quote source. No provider migration or free-plan coverage has been validated or approved by this record.
Prefer official SDKs and established filing tools over custom financial parsers.

## Alternatives considered

| Option | Fit / reason |
| --- | --- |
| Finnhub + SEC EDGAR | Preferred pilot: market data plus free reported fundamentals; free entitlements and ADR coverage need testing |
| Twelve Data + SEC EDGAR | Quote alternative: Basic advertises 8 credits/minute and 800/day; full fundamentals are not free |
| Alpha Vantage | Standard free allowance of 25 requests/day is restrictive; open-source exceptions require approval |
| FMP | Advertised 250 calls/day does not remove free symbol and annual-fundamental restrictions |
| Massive/Polygon | Free EOD bars are useful; financials/ratios require a paid offering |
| EODHD | Free 20 calls/day could cover daily quotes narrowly; fundamentals are excluded |
| Another Yahoo wrapper | Same upstream dependency; no evidence that a wrapper switch solves availability |

Limits are a dated research snapshot, not contractual guarantees. See the
[source-cited provider assessment](../data-provider-assessment.md) for details and uncertainties.

## Revisit and acceptance criteria

Revisit if actual provider requests still fail after PR #60, or quote availability makes the app
unusable. Before changing the default:

1. Test free-key access for every required field and watchlist symbol, especially **TSM and ADYEY**.
   Preserve missing values; validate timestamps, reporting/quote currencies and ordinary-share/ADR units.
2. Confirm free quotas and private-use licensing; keep credentials in private deployment settings.
3. Persist last-good snapshots. Refresh quotes daily and fundamentals after filings; UI reruns read
   snapshots. Show stale screening data explicitly and block stale-data purchase recommendations.
4. Add native-client/HTTP contract tests for request budgets, authentication errors, throttling,
   partial coverage and recovery to the shared CI/pre-CI gate. Verify live coverage separately.

## Consequences

Avoids an unverified migration and recurring fees, but retains Yahoo availability risk for now.
A free replacement may require multiple sources and manually reviewed foreign-issuer assumptions;
no verified free single provider covers the full current schema across the entire watchlist.
