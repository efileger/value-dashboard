import pytest

import stock_dashboard as sd


def test_safe_section_handles_non_dict():
    assert sd._safe_section([], "AAPL") == {}


def test_safe_section_returns_mapping_for_ticker():
    data = {"AAPL": {"value": 1}, "MSFT": {"value": 2}}
    assert sd._safe_section(data, "AAPL") == {"value": 1}


def test_safe_section_handles_dataframe_row():
    data = sd.pd.DataFrame(
        [{"value": 1}, {"value": 2}], index=["AAPL", "MSFT"]
    )

    assert sd._safe_section(data, "AAPL") == {"value": 1}


def test_safe_section_handles_series_name_match():
    series = sd.pd.Series({"value": 3}, name="AAPL")

    assert sd._safe_section(series, "AAPL") == {"value": 3}


def test_resolve_company_name_prefers_quote_type():
    name = sd.resolve_company_name(
        "AAPL", quote_type={"longName": "Apple Inc."}, price={"longName": "Price"}
    )
    assert name == "Apple Inc."


def test_resolve_company_name_uses_price_long_name_when_quote_type_missing():
    name = sd.resolve_company_name("AAPL", quote_type={}, price={"longName": "Price"})
    assert name == "Price"


def test_resolve_company_name_uses_short_name_then_profile_then_ticker():
    name = sd.resolve_company_name(
        "AAPL", quote_type={}, price={"shortName": "Short"}, profile={}
    )
    assert name == "Short"

    name_profile = sd.resolve_company_name(
        "AAPL", quote_type={}, price={}, profile={"longName": "Profile Name"}
    )
    assert name_profile == "Profile Name"

    name_fallback = sd.resolve_company_name("AAPL", quote_type={}, price={}, profile={})
    assert name_fallback == "AAPL"


def test_load_watchlist_reads_default_uppercase(tmp_path, monkeypatch):
    watchlist_file = tmp_path / "watchlist.txt"
    watchlist_file.write_text("aapl, msft\n nvda", encoding="utf-8")
    monkeypatch.setattr(sd, "DEFAULT_WATCHLIST_PATH", watchlist_file)

    assert sd.load_watchlist() == ["AAPL", "MSFT", "NVDA"]


def test_get_default_watchlist_string_uses_fallback(monkeypatch, tmp_path):
    missing_path = tmp_path / "missing_watchlist.txt"
    monkeypatch.setattr(sd, "DEFAULT_WATCHLIST_PATH", missing_path)

    assert sd.get_default_watchlist_string() == sd.DEFAULT_TICKERS_FALLBACK


def test_get_default_watchlist_string_joins_entries(tmp_path, monkeypatch):
    watchlist_file = tmp_path / "watchlist.txt"
    watchlist_file.write_text("AAPL,ADYEY,AMZN", encoding="utf-8")
    monkeypatch.setattr(sd, "DEFAULT_WATCHLIST_PATH", watchlist_file)

    assert sd.get_default_watchlist_string() == "AAPL,ADYEY,AMZN"


def test_display_stock_uses_available_values(monkeypatch):
    captured = {}

    class FakeTicker:
        def __init__(self, ticker):
            self.summary_detail = sd.pd.DataFrame(
                {
                    "trailingPE": [30],
                    "priceToBook": [1.5],
                    "dividendYield": [0.02],
                    "pegRatio": [1.4],
                    "priceToSalesTrailing12Months": [2.0],
                },
                index=[ticker],
            )
            self.financial_data = sd.pd.DataFrame(
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
            self.key_stats = sd.pd.DataFrame(
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
            self._history = sd.pd.DataFrame()

        def history(self, period):
            return self._history

    def noop(*args, **kwargs):
        return None

    def capture_dataframe(df, **kwargs):
        captured["df"] = df
        return None

    for func in ["subheader", "markdown", "error"]:
        monkeypatch.setattr(sd.st, func, noop)
    monkeypatch.setattr(sd.st, "dataframe", capture_dataframe)
    monkeypatch.setattr(sd, "Ticker", FakeTicker)

    sd.display_stock("AAPL")

    assert "df" in captured
    # Ensure multiple metrics were rendered with non-placeholder values
    assert all(value != "N/A" for value in captured["df"]["Value"].head(5))


def test_display_stock_raises_on_empty_data(monkeypatch):
    class EmptyTicker:
        def __init__(self, ticker):
            self.summary_detail = {}
            self.financial_data = {}
            self.asset_profile = {}
            self.key_stats = {}
            self.quote_type = {}
            self.price = {}

        def history(self, period):
            return sd.pd.DataFrame()

    for func in ["subheader", "markdown", "dataframe", "error"]:
        monkeypatch.setattr(sd.st, func, lambda *args, **kwargs: None)

    monkeypatch.setattr(sd, "Ticker", EmptyTicker)

    with pytest.raises(ValueError):
        sd.display_stock("AAPL")


def test_watchlist_entries_fail_fast(monkeypatch):
    class EmptyTicker:
        def __init__(self, ticker):
            self.summary_detail = {}
            self.financial_data = {}
            self.asset_profile = {}
            self.key_stats = {}
            self.quote_type = {}
            self.price = {}

        def history(self, period):
            return sd.pd.DataFrame()

    for func in ["subheader", "markdown", "dataframe", "error"]:
        monkeypatch.setattr(sd.st, func, lambda *args, **kwargs: None)

    monkeypatch.setattr(sd, "Ticker", EmptyTicker)

    tickers = [t.strip().upper() for t in sd.get_default_watchlist_string().split(",") if t.strip()]

    for ticker in tickers:
        with pytest.raises(ValueError):
            sd.display_stock(ticker)
