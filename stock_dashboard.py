from pathlib import Path

import pandas as pd
import streamlit as st
from yahooquery import Ticker

# Define thresholds
thresholds = {
    "Net Profit Margin (%)": 10,
    "ROE (%)": 10,
    "P/E Ratio": 25,
    "P/B Ratio": 3,
    "P/S Ratio": 3,
    "Dividend Yield (%)": 2,
    "Current Ratio": 1.5,
    "Quick Ratio": 1,
    "Cash Flow/Share": 0,
    "Sales/Share": 0,
    "4 Yr Sales Growth (%)": 5,
    "4 Yr EPS Growth (%)": 5,
    "Operating Margin (%)": 10,
    "Debt/Equity": 100,
    "Free Cash Flow": 0,
    "EBITDA Margin (%)": 10,
    "Return on Assets (%)": 5,
    "EV / EBITDA": 20,
    "PEG Ratio": 1.5,
    "Insider Ownership (%)": 5,
    "Buybacks": True
}

# Define metric info tooltips
tooltips = {
    "Net Profit Margin (%)": "Should have top 20% profit margin in its industry",
    "Dividend Yield (%)": "Graham recommends ONLY to invest in well known companies with solid div yields.",
    "Insider Ownership (%)": "Higher is better",
    "P/E Ratio": "Lower is better. P/E less than 5 year avg = good sign",
    "Buybacks": "Indicates if the company is actively buying back shares",
}

DEFAULT_WATCHLIST_PATH = Path(__file__).with_name("watchlist.txt")
DEFAULT_TICKERS_FALLBACK = "AAPL,MSFT,META"


def load_watchlist(path: Path | None = None) -> list[str]:
    """Load the default watchlist from disk.

    Returns
    -------
    list[str]
        A list of uppercase ticker symbols.
    """

    watchlist_path = path or DEFAULT_WATCHLIST_PATH

    try:
        content = watchlist_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []

    symbols = []
    for part in content.replace("\n", ",").split(","):
        symbol = part.strip()
        if symbol:
            symbols.append(symbol.upper())

    return symbols


def get_default_watchlist_string(path: Path | None = None) -> str:
    """Return the default comma-separated tickers for the UI input."""

    watchlist = load_watchlist(path)
    if watchlist:
        return ",".join(watchlist)

    return DEFAULT_TICKERS_FALLBACK


def _safe_section(section, ticker):
    """Return ticker-specific data when the yahooquery section is a mapping."""

    if isinstance(section, pd.DataFrame):
        if ticker in section.index:
            row = section.loc[ticker]
            if isinstance(row, pd.Series):
                return row.to_dict()
        return {}

    if isinstance(section, pd.Series):
        return section.to_dict() if section.name == ticker else {}

    if hasattr(section, "get"):
        value = section.get(ticker, {})
        return value if isinstance(value, dict) else {}

    return {}


def validate_metrics(metrics: dict, ticker: str):
    """Ensure the dashboard has real values to display.

    Raises a ``ValueError`` when every metric is missing so the caller can
    fail fast instead of rendering placeholder UI elements.
    """

    if not metrics or all(value is None for value in metrics.values()):
        raise ValueError(f"No metrics available for {ticker}")

    return metrics


def resolve_company_name(ticker, quote_type=None, price=None, profile=None):
    """Return the most descriptive company name available for the ticker.

    Fallback order: quote_type longName -> price longName -> price shortName
    -> profile longName -> ticker symbol.
    """

    quote_type = quote_type or {}
    price = price or {}
    profile = profile or {}

    return (
        quote_type.get("longName")
        or price.get("longName")
        or price.get("shortName")
        or profile.get("longName")
        or ticker
    )


def format_billions(val):
    if isinstance(val, (int, float)):
        return f"{val / 1e9:.2f}B"
    return val


def ensure_data_available(ticker, sections, metrics):
    """Validate that required sections and metrics are populated for the ticker."""

    missing_sections = [name for name, data in sections.items() if not data]
    if missing_sections:
        joined = ", ".join(missing_sections)
        raise ValueError(f"No data found for {ticker}: missing sections {joined}.")

    has_metric_value = any(value is not None for value in metrics.values())
    if not has_metric_value:
        raise ValueError(f"No metrics available for {ticker} from Yahoo Finance.")

    critical_fields = {
        "market cap": sections.get("key_stats", {}).get("marketCap"),
        "total revenue": sections.get("financial_data", {}).get("totalRevenue"),
        "total debt": sections.get("financial_data", {}).get("totalDebt"),
    }
    missing_fields = [name for name, value in critical_fields.items() if value is None]
    if missing_fields:
        joined = ", ".join(missing_fields)
        raise ValueError(f"Missing required fields for {ticker}: {joined}.")


def display_stock(ticker):
    t = Ticker(ticker)
    summary = _safe_section(t.summary_detail, ticker)
    financial = _safe_section(t.financial_data, ticker)
    profile = _safe_section(t.asset_profile, ticker)
    key_stats = _safe_section(t.key_stats, ticker)
    quote_type = _safe_section(t.quote_type, ticker)
    price = _safe_section(t.price, ticker)

    if all(not section for section in (summary, financial, profile, key_stats, price)):
        raise ValueError(f"No data available for {ticker}")

    industry = profile.get("industry", "—")
    sector = profile.get("sector", "—")
    market_cap = format_billions(key_stats.get("marketCap", "—"))
    sections = {
        "summary_detail": summary,
        "financial_data": financial,
        "asset_profile": profile,
        "key_stats": key_stats,
        "price": price,
    }

    total_revenue_val = financial.get("totalRevenue", None)
    shares_outstanding_val = key_stats.get("sharesOutstanding", None)

    buybacks = None
    try:
        hist_data = t.history(period="5y")
        if not hist_data.empty and "close" in hist_data.columns:
            share_counts = key_stats.get("sharesOutstanding")
            if isinstance(share_counts, list) and len(share_counts) > 1:
                buybacks = share_counts[-1] < share_counts[0]
    except Exception:
        buybacks = None

    operating_cashflow = financial.get("operatingCashflow", None)
    cashflow_per_share = None
    if isinstance(operating_cashflow, (int, float)) and isinstance(shares_outstanding_val, (int, float)) and shares_outstanding_val != 0:
        cashflow_per_share = operating_cashflow / shares_outstanding_val

    sales_per_share = key_stats.get("revenuePerShare", None)
    if sales_per_share is None and isinstance(total_revenue_val, (int, float)) and isinstance(shares_outstanding_val, (int, float)) and shares_outstanding_val != 0:
        sales_per_share = total_revenue_val / shares_outstanding_val

    free_cash_flow = financial.get("freeCashflow", None)
    if isinstance(free_cash_flow, (int, float)):
        free_cash_flow = free_cash_flow / 1e9

    peg_ratio = key_stats.get("pegRatio", summary.get("pegRatio", None))

    metrics = validate_metrics(
        {
        "Net Profit Margin (%)": financial.get("profitMargins", None),
        "ROE (%)": financial.get("returnOnEquity", None),
        "P/E Ratio": summary.get("trailingPE", None),
        "P/B Ratio": summary.get("priceToBook", None),
        "P/S Ratio": summary.get("priceToSalesTrailing12Months", None),
        "Dividend Yield (%)": summary.get("dividendYield", None),
        "Current Ratio": financial.get("currentRatio", None),
        "Quick Ratio": financial.get("quickRatio", None),
        "Cash Flow/Share": cashflow_per_share,
        "Sales/Share": sales_per_share,
        "4 Yr Sales Growth (%)": financial.get("revenueGrowth", None),
        "4 Yr EPS Growth (%)": financial.get("earningsGrowth", None),
        "Operating Margin (%)": financial.get("operatingMargins", None),
        "Debt/Equity": financial.get("debtToEquity", None),
        "Free Cash Flow": free_cash_flow,
        "EBITDA Margin (%)": financial.get("ebitdaMargins", None),
        "Return on Assets (%)": financial.get("returnOnAssets", None),
        "EV / EBITDA": key_stats.get("enterpriseToEbitda", None),
        "PEG Ratio": peg_ratio,
        "Insider Ownership (%)": key_stats.get("heldPercentInsiders", None),
        "Buybacks": buybacks,
    },
        ticker,
    )

    ensure_data_available(ticker, sections, metrics)

    industry = profile.get("industry", "—")
    sector = profile.get("sector", "—")
    market_cap = format_billions(key_stats.get("marketCap", "—"))
    total_revenue = format_billions(total_revenue_val)
    total_cash = format_billions(financial.get("totalCash", "—"))
    total_debt = format_billions(financial.get("totalDebt", "—"))
    shares_outstanding = format_billions(shares_outstanding_val)

    company_name = resolve_company_name(ticker, quote_type, price, profile)

    st.subheader(f"{ticker} - {company_name}")
    st.markdown(f"**Industry**: {industry}")
    st.markdown(f"**Sector**: {sector}")
    st.markdown(f"**Market Cap**: {market_cap}")
    st.markdown(f"**Total Revenue**: {total_revenue}")
    st.markdown(f"**Total Cash**: {total_cash}")
    st.markdown(f"**Total Debt**: {total_debt}")
    st.markdown(f"**Shares Outstanding**: {shares_outstanding}")

    rows = []
    pass_count = 0
    red_count = 0
    for metric, value in metrics.items():
        threshold = thresholds.get(metric)
        tooltip = tooltips.get(metric, "")

        display_val = "N/A"
        if isinstance(value, (int, float)):
            if "Margin" in metric or "%" in metric or "Growth" in metric or "Yield" in metric:
                value *= 100
            display_val = f"{value:.2f}"

        status = "ℹ️"
        if isinstance(value, (int, float)):
            if isinstance(threshold, bool):
                status = "✅" if value == threshold else "❌"
            elif "Debt/Equity" in metric or "P/E" in metric or "PEG" in metric or "P/B" in metric or "P/S" in metric or "EV / EBITDA" in metric:
                status = "✅" if value <= threshold else "❌"
            else:
                status = "✅" if value >= threshold else "❌"
        elif isinstance(value, bool):
            status = "✅" if value else "❌"

        if status == "✅":
            pass_count += 1
        elif status == "❌":
            red_count += 1

        label = f"{metric}"
        if tooltip:
            label += " ⓘ"
            st.markdown(f"<span title='{tooltip}' style='cursor: help;'>{label}</span>", unsafe_allow_html=True)

        rows.append((metric, display_val, status))

    df = pd.DataFrame(rows, columns=["Metric", "Value", "Status"])
    st.dataframe(df, use_container_width=True)

    score = f"{pass_count} ✅ / {red_count} ❌"
    st.markdown(f"### Snapshot Score: {score}")

    decision = "Hold"
    if pass_count >= 12:
        decision = "Buy"
    elif red_count >= 10:
        decision = "Sell"

    st.markdown(f"### 📌 Suggested Action: **{decision}**")


def main():
    st.set_page_config(page_title="Value Investing Dashboard", layout="wide")
    st.title("📊 Value Investing Dashboard")

    default_watchlist = get_default_watchlist_string()
    ticker_input = st.text_input(
        "Enter comma-separated stock tickers (e.g. AAPL,MSFT,META):",
        default_watchlist,
    )
    tickers = [t.strip().upper() for t in ticker_input.split(",") if t.strip()]

    for ticker in tickers:
        try:
            display_stock(ticker)
        except Exception as e:
            st.error(f"Error loading {ticker}: {e}")


if __name__ == "__main__":
    main()
