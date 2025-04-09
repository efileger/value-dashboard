import streamlit as st
import pandas as pd
from yahooquery import Ticker

st.set_page_config(page_title="Value Investing Dashboard", layout="wide")
st.title("📊 Value Investing Dashboard")

# Input section
ticker_input = st.text_input("Enter comma-separated stock tickers (e.g. AAPL,MSFT,META):", "AAPL,MSFT,META")
tickers = [t.strip().upper() for t in ticker_input.split(",") if t.strip()]

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
    "Buybacks": "Indicates if the company is actively buying back shares"
}

def format_billions(val):
    if isinstance(val, (int, float)):
        return f"{val / 1e9:.2f}B"
    return val

def display_stock(ticker):
    t = Ticker(ticker)
    summary = t.summary_detail.get(ticker, {})
    financial = t.financial_data.get(ticker, {})
    profile = t.asset_profile.get(ticker, {})
    key_stats = t.key_stats.get(ticker, {})
    quote_type = t.quote_type.get(ticker, {})

    industry = profile.get("industry", "—")
    sector = profile.get("sector", "—")
    market_cap = format_billions(key_stats.get("marketCap", "—"))
    total_revenue_val = financial.get("totalRevenue", None)
    total_revenue = format_billions(total_revenue_val)
    total_cash = format_billions(financial.get("totalCash", "—"))
    total_debt = format_billions(financial.get("totalDebt", "—"))
    shares_outstanding_val = key_stats.get("sharesOutstanding", None)
    shares_outstanding = format_billions(shares_outstanding_val)

    st.subheader(f"{ticker} - {quote_type.get('longName', 'Unknown')}")
    st.markdown(f"**Industry**: {industry}")
    st.markdown(f"**Sector**: {sector}")
    st.markdown(f"**Market Cap**: {market_cap}")
    st.markdown(f"**Total Revenue**: {total_revenue}")
    st.markdown(f"**Total Cash**: {total_cash}")
    st.markdown(f"**Total Debt**: {total_debt}")
    st.markdown(f"**Shares Outstanding**: {shares_outstanding}")

    buybacks = None
    try:
        hist_data = t.history(period="5y")
        if not hist_data.empty and 'close' in hist_data.columns:
            share_counts = t.key_stats.get(ticker, {}).get("sharesOutstanding")
            if isinstance(share_counts, list) and len(share_counts) > 1:
                buybacks = share_counts[-1] < share_counts[0]
    except:
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

    metrics = {
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
        "Buybacks": buybacks
    }

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
            label += f" ⓘ"
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

for ticker in tickers:
    try:
        display_stock(ticker)
    except Exception as e:
        st.error(f"Error loading {ticker}: {e}")
