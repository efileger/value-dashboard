import pandas as pd
import streamlit as st

from . import data_access
from .metrics import (
    compute_metrics,
    ensure_data_available,
    format_billions,
    thresholds,
    tooltips,
)


def _render_metric_rows(metrics: dict[str, object]) -> tuple[pd.DataFrame, int, int]:
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
    return df, pass_count, red_count


def display_stock(ticker: str, ticker_cls=None):
    ticker_cls = ticker_cls or data_access.Ticker
    sections = data_access.fetch_ticker_sections(ticker, ticker_cls=ticker_cls)

    core_sections = {k: v for k, v in sections.items() if k != "buybacks"}

    if all(not section for section in core_sections.values()):
        raise ValueError(f"No data available for {ticker}")

    metrics = compute_metrics(ticker, sections)
    ensure_data_available(ticker, core_sections, metrics)

    profile = core_sections.get("asset_profile", {})
    key_stats = core_sections.get("key_stats", {})
    financial = core_sections.get("financial_data", {})
    quote_type = core_sections.get("quote_type", {})
    price = core_sections.get("price", {})

    industry = profile.get("industry", "—")
    sector = profile.get("sector", "—")
    market_cap = format_billions(key_stats.get("marketCap", "—"))
    total_revenue = format_billions(financial.get("totalRevenue", "—"))
    total_cash = format_billions(financial.get("totalCash", "—"))
    total_debt = format_billions(financial.get("totalDebt", "—"))
    shares_outstanding = format_billions(key_stats.get("sharesOutstanding", "—"))

    company_name = data_access.resolve_company_name(ticker, quote_type, price, profile)

    st.subheader(f"{ticker} - {company_name}")
    st.markdown(f"**Industry**: {industry}")
    st.markdown(f"**Sector**: {sector}")
    st.markdown(f"**Market Cap**: {market_cap}")
    st.markdown(f"**Total Revenue**: {total_revenue}")
    st.markdown(f"**Total Cash**: {total_cash}")
    st.markdown(f"**Total Debt**: {total_debt}")
    st.markdown(f"**Shares Outstanding**: {shares_outstanding}")

    df, pass_count, red_count = _render_metric_rows(metrics)
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

    default_watchlist = data_access.get_default_watchlist_string()
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
