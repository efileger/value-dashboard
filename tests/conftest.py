import pandas as pd
import pytest

import stock_dashboard.ui as ui


@pytest.fixture
def streamlit_spy(monkeypatch):
    """Capture dataframe renders while stubbing out other Streamlit calls."""

    captured: dict[str, object] = {"warnings": []}

    def noop(*args, **kwargs):
        return None

    def capture_dataframe(df, **kwargs):
        captured["df"] = df
        return None

    def capture_warning(message, *args, **kwargs):
        captured["warnings"].append(message)
        return None

    for func in ["subheader", "markdown", "error"]:
        monkeypatch.setattr(ui.st, func, noop)
    monkeypatch.setattr(ui.st, "dataframe", capture_dataframe)
    monkeypatch.setattr(ui.st, "warning", capture_warning)

    return captured


@pytest.fixture
def stubbed_streamlit(monkeypatch):
    """Provide no-op Streamlit functions for error-path tests."""

    for func in ["subheader", "markdown", "dataframe", "error", "warning"]:
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
def partial_ticker_cls():
    """Ticker class fixture that omits some metrics but keeps core data."""

    class PartialTicker:
        def __init__(self, ticker):
            self.summary_detail = pd.DataFrame(
                {
                    "trailingPE": [None],
                    "priceToBook": [1.5],
                    "dividendYield": [None],
                    "pegRatio": [None],
                    "priceToSalesTrailing12Months": [None],
                },
                index=[ticker],
            )
            self.financial_data = pd.DataFrame(
                {
                    "profitMargins": [None],
                    "returnOnEquity": [0.12],
                    "currentRatio": [None],
                    "operatingCashflow": [None],
                    "revenueGrowth": [None],
                    "earningsGrowth": [None],
                    "operatingMargins": [None],
                    "debtToEquity": [None],
                    "freeCashflow": [None],
                    "ebitdaMargins": [None],
                    "returnOnAssets": [None],
                    "totalRevenue": [5_000_000_000],
                    "totalCash": [1_000_000_000],
                    "totalDebt": [None],
                },
                index=[ticker],
            )
            self.asset_profile = {ticker: {"industry": "Tech", "sector": "IT"}}
            self.key_stats = pd.DataFrame(
                {
                    "marketCap": [None],
                    "sharesOutstanding": [1_000_000_000],
                    "revenuePerShare": [10.0],
                    "enterpriseToEbitda": [None],
                    "heldPercentInsiders": [None],
                },
                index=[ticker],
            )
            self.quote_type = {ticker: {"longName": "Partial Corp"}}
            self.price = {ticker: {"shortName": "Partial"}}
            self._history = pd.DataFrame()

        def history(self, period):
            return self._history

    return PartialTicker


@pytest.fixture
def price_cap_ticker_cls():
    """Ticker class fixture with market cap only in the price section."""

    class PriceCapTicker:
        def __init__(self, ticker):
            self.summary_detail = pd.DataFrame(
                {
                    "trailingPE": [22.5],
                    "priceToBook": [3.0],
                    "dividendYield": [0.015],
                    "pegRatio": [1.2],
                    "priceToSalesTrailing12Months": [2.5],
                },
                index=[ticker],
            )
            self.financial_data = pd.DataFrame(
                {
                    "profitMargins": [0.21],
                    "returnOnEquity": [0.16],
                    "currentRatio": [1.7],
                    "quickRatio": [1.4],
                    "operatingCashflow": [2_500_000_000],
                    "revenueGrowth": [0.08],
                    "earningsGrowth": [0.09],
                    "operatingMargins": [0.13],
                    "debtToEquity": [60],
                    "freeCashflow": [750_000_000],
                    "ebitdaMargins": [0.17],
                    "returnOnAssets": [0.11],
                    "totalRevenue": [6_000_000_000],
                    "totalCash": [1_200_000_000],
                    "totalDebt": [900_000_000],
                },
                index=[ticker],
            )
            self.asset_profile = {ticker: {"industry": "Finance", "sector": "Banking"}}
            self.key_stats = pd.DataFrame(
                {
                    "marketCap": [None],
                    "sharesOutstanding": [[1_000_000_000, 900_000_000]],
                    "revenuePerShare": [6.0],
                    "enterpriseToEbitda": [11],
                    "heldPercentInsiders": [0.06],
                    "pegRatio": [1.2],
                },
                index=[ticker],
            )
            self.quote_type = {ticker: {"longName": "Price Cap Corp"}}
            self.price = {ticker: {"shortName": "PriceCap", "marketCap": 3_500_000_000}}
            self._history = pd.DataFrame({"close": [1, 2]})

        def history(self, period):
            return self._history

    return PriceCapTicker


@pytest.fixture
def summary_detail_cap_ticker_cls():
    """Ticker class fixture with market cap only in summary detail."""

    class SummaryDetailCapTicker:
        def __init__(self, ticker):
            self.summary_detail = pd.DataFrame(
                {
                    "trailingPE": [18.0],
                    "priceToBook": [2.2],
                    "dividendYield": [0.01],
                    "pegRatio": [1.1],
                    "priceToSalesTrailing12Months": [2.1],
                    "marketCap": [4_200_000_000],
                },
                index=[ticker],
            )
            self.financial_data = pd.DataFrame(
                {
                    "profitMargins": [0.2],
                    "returnOnEquity": [0.14],
                    "currentRatio": [1.9],
                    "quickRatio": [1.5],
                    "operatingCashflow": [3_000_000_000],
                    "revenueGrowth": [0.06],
                    "earningsGrowth": [0.05],
                    "operatingMargins": [0.12],
                    "debtToEquity": [55],
                    "freeCashflow": [800_000_000],
                    "ebitdaMargins": [0.16],
                    "returnOnAssets": [0.1],
                    "totalRevenue": [7_500_000_000],
                    "totalCash": [1_500_000_000],
                    "totalDebt": [850_000_000],
                },
                index=[ticker],
            )
            self.asset_profile = {ticker: {"industry": "Energy", "sector": "Utilities"}}
            self.key_stats = pd.DataFrame(
                {
                    "marketCap": [None],
                    "sharesOutstanding": [[1_200_000_000, 1_000_000_000]],
                    "revenuePerShare": [6.25],
                    "enterpriseToEbitda": [9],
                    "heldPercentInsiders": [0.04],
                    "pegRatio": [1.1],
                },
                index=[ticker],
            )
            self.quote_type = {ticker: {"longName": "Summary Cap Corp"}}
            self.price = {ticker: {"shortName": "SummaryCap"}}
            self._history = pd.DataFrame({"close": [1, 2]})

        def history(self, period):
            return self._history

    return SummaryDetailCapTicker


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
