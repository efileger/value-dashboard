import pandas as pd
import pytest

import stock_dashboard.ui as ui


@pytest.fixture
def streamlit_spy(monkeypatch):
    """Capture dataframe renders while stubbing out other Streamlit calls."""

    captured: dict[str, object] = {}

    def noop(*args, **kwargs):
        return None

    def capture_dataframe(df, **kwargs):
        captured["df"] = df
        return None

    for func in ["subheader", "markdown", "error"]:
        monkeypatch.setattr(ui.st, func, noop)
    monkeypatch.setattr(ui.st, "dataframe", capture_dataframe)

    return captured


@pytest.fixture
def stubbed_streamlit(monkeypatch):
    """Provide no-op Streamlit functions for error-path tests."""

    for func in ["subheader", "markdown", "dataframe", "error"]:
        monkeypatch.setattr(ui.st, func, lambda *args, **kwargs: None)


@pytest.fixture
def fake_ticker_cls():
    """Ticker class fixture that returns rich data for UI rendering tests."""

    class FakeTicker:
        def __init__(self, ticker):
            self.summary_detail = pd.DataFrame(
                {
                    "trailingPE": [30],
                    "priceToBook": [1.5],
                    "dividendYield": [0.02],
                    "pegRatio": [1.4],
                    "priceToSalesTrailing12Months": [2.0],
                },
                index=[ticker],
            )
            self.financial_data = pd.DataFrame(
                {
                    "profitMargins": [0.25],
                    "returnOnEquity": [0.18],
                    "currentRatio": [1.8],
                    "operatingCashflow": [1_000_000_000],
                    "revenueGrowth": [0.05],
                    "earningsGrowth": [0.07],
                    "operatingMargins": [0.12],
                    "debtToEquity": [50],
                    "freeCashflow": [500_000_000],
                    "ebitdaMargins": [0.15],
                    "returnOnAssets": [0.09],
                    "totalRevenue": [5_000_000_000],
                    "totalCash": [1_000_000_000],
                    "totalDebt": [500_000_000],
                },
                index=[ticker],
            )
            self.asset_profile = {ticker: {"industry": "Tech", "sector": "IT"}}
            self.key_stats = pd.DataFrame(
                {
                    "marketCap": [2_000_000_000],
                    "sharesOutstanding": [1_000_000_000],
                    "revenuePerShare": [5.0],
                    "enterpriseToEbitda": [10],
                    "heldPercentInsiders": [0.1],
                },
                index=[ticker],
            )
            self.quote_type = {ticker: {"longName": "Fake Corp"}}
            self.price = {ticker: {"shortName": "Fake"}}
            self._history = pd.DataFrame()

        def history(self, period):
            return self._history

    return FakeTicker


@pytest.fixture
def empty_ticker_cls():
    """Ticker class fixture that returns empty sections for failure testing."""

    class EmptyTicker:
        def __init__(self, ticker):
            self.summary_detail = {}
            self.financial_data = {}
            self.asset_profile = {}
            self.key_stats = {}
            self.quote_type = {}
            self.price = {}

        def history(self, period):
            return pd.DataFrame()

    return EmptyTicker
