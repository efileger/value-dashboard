# Data-provider investigation — November 8, 2026

Constraints: free only, private personal use; delayed/end-of-day quotes are sufficient.

## Findings in this app

The repeated 299-second notices represent one locally generated cooldown displayed per ticker,
not evidence of separate Yahoo responses or a server-provided Retry-After header. The independent
bare-HTTP quote health probe used a different access path from Yahooquery's authenticated session.
Its rejection could prevent the real client from ever trying. The preceding cooldown fix therefore
did not establish that the actual data source was unavailable.

Static inspection of Yahooquery 2.4.1 also found six quoteSummary module properties each requesting
all symbols, and annual income statements requested for the entire watchlist separately for each
row. Thirteen tickers could approach 260 cold-start HTTP requests including validation/setup.
This is a code-derived estimate, not measured production traffic. Native get_modules combines
six modules into one request per symbol; share history needs one watchlist-wide fetch per cache TTL.
Native-library transport tests now measure this boundary rather than only mocked properties.

Yahooquery can mask a non-JSON 429 as a pseudo-404. Preserving transport status is necessary to
separate actual throttling from session/authentication failures and missing symbols. A successful
library call and usable data are separate from mere permission to attempt a request.

Shared-host IP blocking and cookie/crumb problems remain plausible external causes, not confirmed
production diagnoses. There is no evidence yet that switching from yahooquery to yfinance or another
undocumented Yahoo wrapper would remove Yahoo's shared upstream restrictions.

## Free provider comparison

| Service | Official free limits / useful coverage | Important gap |
| --- | --- | --- |
| Finnhub | Quote, profile and basic financial metrics documented; free-key entitlements need a real account test | Exact free coverage and ADR/OTC symbols not verified; do not assume statement history or calendars are free |
| SEC EDGAR | Free, no API key; company facts and filings; identifying User-Agent; maximum 10 requests/second | No market quotes; IFRS, periods, units and ADR mapping need validation |
| Twelve Data | Basic: 8 credits/minute, 800/day; advertised US/OTC quote coverage | Fundamentals have separate paid entitlements; ADYEY payload unverified |
| Alpha Vantage | 25 requests/day; verified open-source/educational projects can request an exception | Daily quota cannot refresh 15 quotes and complete fundamentals on every run; exception is not guaranteed |
| FMP | 250 calls/day advertised | Free fundamental endpoints are symbol restricted, annual only for relevant ratios; not a full quarterly replacement |
| Massive/Polygon | Basic: 5 requests/minute; previous-day bars after midnight ET, two years of history | Financials/ratios separately advertised at $29/month |
| EODHD | Free: 20 calls/day, one year of EOD/splits/dividends | Fundamentals excluded; advertised $59.99/month fundamentals excludes EOD; all-in-one $99.99/month |

Sources checked against official pages:

- [Finnhub documentation](https://finnhub.io/docs/api) and [official API schema](https://github.com/Finnhub-Stock-API/finnhub-go/blob/master/api/openapi.yaml). Schema availability does not establish free-plan entitlement; pricing pages could not be fully read.
- [SEC APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) and [access policy](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data).
- [Twelve Data pricing](https://twelvedata.com/pricing) and [exchange coverage](https://twelvedata.com/exchanges).
- [Alpha Vantage support/limits](https://www.alphavantage.co/support/) and [API docs](https://www.alphavantage.co/documentation/).
- [FMP detailed pricing/entitlements](https://site.financialmodelingprep.com/developer/docs/pricing).
- [Massive stock plans](https://massive.com/stocks), [pricing](https://massive.com/pricing) and [free EOD timing](https://massive.com/knowledge-base/article/on-the-free-basic-plan-when-can-i-pull-the-previous-trading-days-data).
- [EODHD plans](https://eodhd.com/help/plans) and [pricing](https://eodhd.com/pricing).

## Recommendation and migration acceptance

No verified free single source replaces this dashboard's full schema across every actual symbol.
Pilot Finnhub quotes/profile/basic metrics plus SEC reported fundamentals first, with Twelve Data
as an alternative quote source. This is a recommendation for evaluation, not a tested migration.
No account keys were available and no symbol-level free entitlements have been validated.

Use a free key stored in private deployment settings, never source control or chat. Before switching
the default, test every watchlist symbol and required field, especially TSM and ADYEY. Record provider,
quote currency, reporting currency, period, timestamp, share basis, nulls, errors and entitlement
responses. Do not infer ADR EPS or cash/share from ordinary-share statements without reconciliation.
ADYEY may need manually maintained issuer assumptions; missing data must remain explicitly missing.

Persist last-good market snapshots separately from private investment profiles. Refresh quotes on
a chosen daily schedule, and fundamentals after filings; rerunning the UI should read snapshots,
not fan out to APIs. Permit stale screening with timestamps, but never let stale quotes authorize
purchases. A free provider will still impose quotas; test rate budgets and partial outages.

Private deployment suits this pilot; a public data display may require licensing beyond an API key.
An open-source repository alone does not grant redistribution rights.
