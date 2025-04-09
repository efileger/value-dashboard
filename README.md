# 📊 Value Investing Dashboard

A streamlined stock analysis tool for value investors, built with **Streamlit** and powered by **yahooquery**.

This app lets you evaluate companies using key value investing principles — like strong profit margins, sustainable debt, and healthy cash flow — all in one clean, interactive dashboard.

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
