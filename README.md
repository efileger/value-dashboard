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
- Snapshot scorecard with Buy / Hold / Sell recommendation
- Auto-formatted financials (cash, debt, FCF, etc.)
- Dark mode interface and mobile-friendly layout
- Optional watchlist and persistent ticker memory (via browser)

---

## 🚀 Getting Started
[Go here directly to use the app](https://value-dashboard.streamlit.app/)
Or build it yourself below

### Requirements
- Python 3.9+
- `pip install -r requirements.txt`

### Run the App
```
streamlit run stock_dashboard.py
```

### Development
- Install dev tools: `pip install -r requirements-dev.txt`
- Run linting: `ruff check .`
- Run tests: `pytest`
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
- 4-Year EPS & Sales Growth  
- Debt/Equity, PEG Ratio  
- Insider Ownership  
- Buybacks (Yes/No)  
...and more

---

## 🤔 Why?

This dashboard was built to support a **FIRE-focused, empirically driven approach** to long-term investing. It helps filter out noise and surface stocks that meet classic Graham-style value filters — in seconds.

---

## 📌 Future Improvements

- Stock screener mode  
- Sector/industry filtering  
- Export watchlist  
- Integration with personal portfolio tools (e.g. Notion, Sheets)

---

## 🛠 Built With

- [Streamlit](https://streamlit.io/)  
- [yahooquery](https://pypi.org/project/yahooquery/)  
- [Pandas](https://pandas.pydata.org/)

---

## 📄 License

MIT License
