# 📊 Value Investing Dashboard

A streamlined stock analysis tool for value investors, built with **Streamlit** and powered by **yahooquery**.

This app lets you evaluate companies using key value investing principles — like strong profit margins, sustainable debt, and healthy cash flow — all in one clean, interactive dashboard.

---

## 🧭 Operating Model

- **Trunk-based delivery**: create short-lived branches off `main` and merge back only through reviewed pull requests.
- **MinimumCD-aligned CI**: every change must pass the GitHub Actions workflow (`CI`) covering linting and import validation before merging.
- **12-Factor friendly**: any future secrets or configuration (e.g., API keys, caching flags) should be supplied via environment variables rather than hard-coding them.
- **Branch protections**: enable required status checks on `main`, require pull requests for merges, and block force-pushes/deletions to keep the delivery stream healthy.
- **Dev environment gate**: pull requests target a `dev` environment check that launches the Streamlit app headlessly to confirm it boots (and captures logs on failure) before merging.
- **Pipeline as the path to prod**: ship only through the application pipeline with quality gates (static analysis, tests, security checks) and stop-the-line behavior on failures.
- **Artifacts and rollback**: build immutable artifacts per commit, carry configuration with the artifact, and keep deployments reversible.
- **Environments**: reserve GitHub environments (e.g., `production`) with required reviewers for deployments if additional stages are added later.
- **Visibility and telemetry**: add monitoring/alerting and observability when we introduce infrastructure to spot regressions quickly.

---

## 🔍 Features

- Enter any stock tickers (e.g. `AAPL, MSFT, NVDA`)
- View 20+ fundamental metrics with pass/fail scoring
- Hoverable tooltips for key investing concepts
- Cash deployment planner with a ranked top five, explicit purchase gates and suggested dollar amounts
- Bear/base/bull scenario values, annualized returns and quarterly review dates
- Screening scorecard kept separate from purchase eligibility
- Portable private deployment profiles and purchase-tranche tracking
- Auto-formatted financials (cash, debt, FCF, etc.)
- Dark mode interface and mobile-friendly layout
- Optional watchlist and persistent ticker memory (via browser)

---

## 🚀 Getting Started
[Go here directly to use the app](https://value-dashboard.streamlit.app/)
Or build it yourself below

### Requirements
- Python 3.11 (validated Dev/CI runtime)
- `pip install -r requirements.txt`

### Run the App
```
streamlit run stock_dashboard.py
```

### Development
- Install Python 3.11 dev tools: `pip install --require-hashes -r requirements-dev.txt`
- Install workflow checker: `bash scripts/install-actionlint.sh`
- Run shared pre-CI checks: `bash scripts/check.sh fast`
- Run local server smoke: `bash scripts/check.sh smoke`
- Install secret scanner: `bash scripts/install-gitleaks.sh`; then `bash scripts/check.sh secrets`
- Audit locked runtime dependencies and emit SBOM: `bash scripts/check.sh audit`
- Full gate mapping, setup, and remaining release controls: [Quality gates](docs/quality-gates.md)
- Run the CLI headlessly (no Streamlit UI): `python -m stock_dashboard.cli --tickers AAPL,MSFT --verbose`
- Deterministic CI/smoke runs: set `SMOKE_TEST=1` to use stubbed data and `YF_DISABLE_CACHE=1` to disable caching, e.g. `SMOKE_TEST=1 YF_DISABLE_CACHE=1 python -m stock_dashboard.cli --tickers AAPL`

### Operational checks
- **Live data probe**: A dedicated GitHub Actions workflow (`Live data probe`) runs hourly and on-demand to hit Yahoo Finance via `python -m stock_dashboard.cli --tickers AAPL --verbose` with a short timeout. It captures latency plus stdout/stderr as artifacts and job summaries to flag outages or rate limiting. The workflow is alerting-only and separate from required CI; configure `SMOKE_TEST=1` via the manual dispatch input if you need a stubbed, low-flake run.

---

## 📈 Metrics Evaluated

- Net Profit Margin  
- Return on Equity (ROE)  
- Price/Earnings (P/E), Price/Book (P/B), Price/Sales (P/S)  
- Dividend Yield  
- Current & Quick Ratios  
- Cash Flow/Share, Sales/Share, Free Cash Flow  
- Reported EPS & Sales Growth (Yahoo growth fields, not four-year CAGR)
- Debt/Equity, PEG Ratio  
- Insider Ownership  
- Buybacks (Yes/No)  
...and more

---

## 🤔 Why?

This dashboard was built to support a **FIRE-focused, empirically driven approach** to long-term investing. It helps filter out noise and surface stocks that meet classic Graham-style value filters — in seconds.

---

## Valuation-gated cash deployment

The dashboard answers “where should this cash go today?” using reviewed business assumptions and
current Yahoo quotes. Set **Cash to deploy today** (for example $5,000) and **Maximum businesses this
review** (1 for the best candidate, or up to 10 for a larger budget). The first candidate receives up
to its permitted tranche, then additional candidates receive cash in rank order. The app may leave
some or all of the request unallocated; it never forces an investment to meet a deadline.

### First review

1. Open **Cash, portfolio and review settings**. Enter the available cash/SGOV pool, its protected
   reserve, portfolio value including that cash, and the portfolio snapshot date. Use a consistent
   account or household scope. IRA reserves and accessible taxable reserves are separate decisions.
   Refresh the cash alternative yield; the initial 3.83% is an unverified conversation example.
2. Open **Review business valuations and position limits** for each watchlist company. Enter
   normalized EPS, dividends, bear/base/bull growth and exit P/E assumptions, holding period, required
   return, current position value, maximum weight and the maximum addition for this deployment.
   Add the financial period, review date, source links, normalization rationale and thesis failure
   condition. Confirm the latest results support the thesis and verify quote currency / listed share
   or ADR units. Low-confidence cases stay in research rather than receiving an allocation.
3. Run **Rank deployment opportunities**. Read the best candidate and **Top five qualifying
   opportunities**. The full watchlist shows every exclusion, including incomplete business cases.
4. After a real purchase, **Record executed purchase**. This updates the cash pool, holding value and
   tranche history. Viewing or rerunning the app never records a purchase. A partial fill consumes
   that review's tranche; manually reconcile actual holdings and cash at the next review.
5. **Download deployment profile for next quarter** after changes. Import it in the next session.
   The assessment is also downloadable as CSV or JSON. Do not commit personal portfolio exports.

The initial profile retains the conversation's qualitative research cautions for all 13 businesses.
Only PEP, MSFT and TSM have numeric starting scenarios: EPS 8.38 / 17.75 / 15.00, flat dividends
5.92 / 3.92 / 4.32, growth ranges 3–5% / 10–15% / 10–15%, exit P/E 18 / 25 / 20, and return
hurdles 10% / 10% / 12%. The base case uses the midpoint growth. Addition caps are $7,500 / $10,000 /
$10,000; the balance of a $35,000 pool remains unassigned. **These are unverified drafts from the
conversation, not current verified fair values or approved purchases.** Review dates are blank,
confidence starts Low and approvals start off. Other businesses need numeric assumptions.

### Model and gates

This first model discounts flat annual dividends and terminal EPS × exit P/E. `numpy-financial`
calculates NPV and IRR. All scenarios use the same required return; bear/base/bull growth and multiples
must be ordered. All returns are nominal and before investor taxes, withholding, fees and future FX
changes. This earnings scenario model is not a full cash-flow valuation. Reconcile capex, dilution,
nonrecurring gains, debt and settlement cash in the business case; leave it unapproved when EPS is
not a defensible valuation basis. Yahoo trailing EPS and growth are references, not normalized forecasts.

- Discount = `1 - price / conservative scenario value`. The conservative scenario, rather than the
  optimistic upper value, sets the gate. Initial / second / third / confirmation tranches require
  15% / 25% / 35% / 15% discounts. The fourth tranche also needs a later financial period than the first.
- Conservative annual return must exceed the greater of the company's required return and current
  cash yield + the configurable spread (default 4 percentage points).
- Rank qualifying businesses by conservative annual return, then conservative discount, confidence,
  available portfolio headroom and ticker for deterministic ties. There is no opaque weighted score.
  Unknown and failing cases have no purchase rank; their blockers remain visible.
- Each allocation is capped by 25% of the company's addition cap, remaining cap, portfolio headroom
  (`maximum weight × portfolio value - position value`), remaining request and unreserved cash.
  Prices and dollar amounts do not imply an order or a whole-share quantity.
- Only one tranche per business review date. A price gap through multiple thresholds does not release
  multiple tranches. Repeated runs preserve this limit using recorded executions. After four tranches,
  use **Archive plan and begin a fresh review** to retain history, preserve cash and holdings and
  clear business approvals for the next plan. Changing price alone does not reset it.
- Business reviews expire after 95 days by default (configurable downwards). A newer Yahoo-reported
  quarter blocks purchases sooner. Financial periods older than 200 days need a fresh report. Review
  material news between visits; thesis failures are not automatically monitored.
- Quote timestamps must be known, nonfuture and at most four calendar days old to allow weekends.
  A data error blocks recommendations even with cached values. The portfolio snapshot must be within
  30 days. Inputs display their currencies; original Yahoo receipt timestamps survive cache hits and
  are separate from actual quote and financial report dates. No automatic FX conversion is performed:
  USD deployment requires reviewed per-listed-share USD inputs and a USD quote.
- Unused requested cash remains unallocated. A six-month-old plan prompts a deliberate review of
  continued waiting versus ordinary DCA. Nothing is automatically bought or scheduled.

### Profile storage

By default, assumptions and holdings stay in the Streamlit session; **they do not survive a new
session unless exported/imported**. No personal file is shared across visitors. For a private,
single-user installation with a durable disk, optionally set
`VALUATION_PROFILE_PATH=/private/path/deployment-profile.json`. Saves use atomic replacement with
private file permissions. Do not enable a shared profile path on a public/multi-user deployment.
A hosted ephemeral filesystem is not durable storage. JSON profiles are versioned and validated on
import; a profile with missing approvals remains ineligible.

The screen also fixes the mislabeled four-year growth fields, key-statistics P/B lookup, nonpositive
valuation-ratio passes and the buyback extraction. The buyback check now compares dated annual diluted
average share counts (net share reduction), rather than treating price history as share history.
Cross-currency or unknown-currency totals are not divided into derived per-share screen metrics.
Dividends do not get a standalone bonus in deployment ranking.

---

## 🛠 Built With

- [Streamlit](https://streamlit.io/)  
- [yahooquery](https://pypi.org/project/yahooquery/)  
- [Pandas](https://pandas.pydata.org/)
- [numpy-financial](https://numpy.org/numpy-financial/) for NPV and annual return calculations

---

## 📄 License

MIT License

### Yahoo throttling and regression coverage

An HTTP 429 pauses Yahoo requests across the dashboard, including symbol validation and client
creation. The app honors `Retry-After` (seconds or HTTP date), otherwise waits five minutes.
Reruns and watchlist changes do not bypass that cooldown. Available unexpired cached screening
metrics remain visible, but throttled data cannot produce an actionable deployment recommendation.
Batched module responses are cached for all returned watchlist symbols to avoid downloading the
same watchlist repeatedly. Actual provider 401/403 responses are surfaced as authentication/access failures.
There is no independent raw-HTTP health probe: availability comes from the actual provider session.

The shared `scripts/check.sh fast` suite exercises cold production-style 429 responses, page reruns,
cooldown recovery, partial/cache behavior, immediate stop after a section fails, and batched request
counts offline. The UI no longer has a pytest-only health-gate bypass. These tests catch application
regressions; they cannot guarantee that Yahoo will accept a shared hosting provider's outbound IP.

See [the data-provider assessment](docs/data-provider-assessment.md) for the underlying request-path
defects, free-provider comparison, sources, and migration acceptance criteria. Tests now exercise
the installed Yahooquery HTTP request builder and real response objects, including plain-text 429s.
