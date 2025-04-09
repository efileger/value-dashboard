
import streamlit as st
import pandas as pd
from yahooquery import Ticker

THRESHOLDS = {
    "P/E Ratio": lambda x: x is not None and x < 15,
    "P/B Ratio": lambda x: x is not None and x < 1.5,
    "Dividend Yield (%)": lambda x: x is not None and x > 2,
    "ROE (%)": lambda x: x is not None and x > 15,
    "Net Profit Margin (%)": lambda x: x is not None and x > 10,
    "Current Ratio": lambda x: x is not None and x >= 2,
}

def display_stock(ticker, score_data):
    t = Ticker(ticker)
    summary = t.summary_detail.get(ticker, {})
    financial = t.financial_data.get(ticker, {})
    key_stats = t.key_stats.get(ticker, {})
    quote_type = t.quote_type.get(ticker, {})
    profile = t.asset_profile.get(ticker, {})

    data = {
        "Price": financial.get("currentPrice"),
        "Net Profit Margin (%)": key_stats.get("profitMargins", 0) * 100 if key_stats.get("profitMargins") else None,
        "ROE (%)": key_stats.get("returnOnEquity", 0) * 100 if key_stats.get("returnOnEquity") else None,
        "P/E Ratio": financial.get("trailingPE"),
        "P/B Ratio": financial.get("priceToBook"),
        "P/S Ratio": financial.get("priceToSalesTrailing12Months"),
        "Dividend Yield (%)": summary.get("dividendYield", 0) * 100 if summary.get("dividendYield") else None,
        "Current Ratio": financial.get("currentRatio"),
    }

    st.subheader(f"{ticker} - {quote_type.get('longName', 'Unknown')}")
    st.markdown(f"**Industry:** {profile.get('industry', '—')}")
    st.markdown(f"**Sector:** {profile.get('sector', '—')}")
    st.markdown(f"**Market Cap:** {financial.get('marketCap', '—'):,}" if financial.get('marketCap') else "**Market Cap:** —")

    metrics = []
    pass_count = 0
    for metric, value in data.items():
        if metric in THRESHOLDS:
            healthy = THRESHOLDS[metric](value)
            color = "✅" if healthy else "❌"
            if healthy:
                pass_count += 1
        else:
            color = "ℹ️"
        display_val = "N/A" if value is None else round(value, 2)
        metrics.append((metric, display_val, color))

    df = pd.DataFrame(metrics, columns=["Metric", "Value", "Status"])
    st.dataframe(df, use_container_width=True)

    total = len(THRESHOLDS)
    red_count = total - pass_count
    score = pass_count

    rating = "Buy" if score >= 6 else "Hold" if score >= 4 else "Sell"
    st.markdown(f"**Snapshot Score:** {pass_count} ✅ / {red_count} ❌")
    st.markdown(f"**📌 Rating:** {rating}")

    score_data.append((ticker, pass_count, red_count))

st.title("📊 Value Investing Dashboard (Self-Hosted)")

use_watchlist = st.checkbox("📌 Use saved watchlist (watchlist.txt)", value=False)

if use_watchlist:
    try:
        with open("watchlist.txt", "r") as wl:
            tickers = wl.read().strip()
    except FileNotFoundError:
        st.error("⚠️ watchlist.txt not found in the script directory.")
        tickers = ""
else:
    tickers = st.text_input("Enter comma-separated stock tickers (e.g. AAPL,MSFT,META):")

if tickers:
    tickers_list = [t.strip().upper() for t in tickers.split(",")]
    score_data = []
    for ticker in tickers_list:
        try:
            display_stock(ticker, score_data)
        except Exception as e:
            st.warning(f"{ticker}: Failed to fetch or process data. ({e})")
