import pandas as pd

from stock_dashboard import data_access


def test_safe_section_handles_non_dict():
    assert data_access._safe_section([], "AAPL") == {}


def test_safe_section_returns_mapping_for_ticker():
    data = {"AAPL": {"value": 1}, "MSFT": {"value": 2}}
    assert data_access._safe_section(data, "AAPL") == {"value": 1}


def test_safe_section_handles_dataframe_row():
    data = pd.DataFrame([{"value": 1}, {"value": 2}], index=["AAPL", "MSFT"])

    assert data_access._safe_section(data, "AAPL") == {"value": 1}


def test_safe_section_handles_series_name_match():
    series = pd.Series({"value": 3}, name="AAPL")

    assert data_access._safe_section(series, "AAPL") == {"value": 3}


def test_resolve_company_name_prefers_quote_type():
    name = data_access.resolve_company_name(
        "AAPL", quote_type={"longName": "Apple Inc."}, price={"longName": "Price"}
    )
    assert name == "Apple Inc."


def test_resolve_company_name_uses_price_long_name_when_quote_type_missing():
    name = data_access.resolve_company_name("AAPL", quote_type={}, price={"longName": "Price"})
    assert name == "Price"


def test_resolve_company_name_uses_short_name_then_profile_then_ticker():
    name = data_access.resolve_company_name(
        "AAPL", quote_type={}, price={"shortName": "Short"}, profile={}
    )
    assert name == "Short"

    name_profile = data_access.resolve_company_name(
        "AAPL", quote_type={}, price={}, profile={"longName": "Profile Name"}
    )
    assert name_profile == "Profile Name"

    name_fallback = data_access.resolve_company_name("AAPL", quote_type={}, price={}, profile={})
    assert name_fallback == "AAPL"


def test_load_watchlist_reads_default_uppercase(tmp_path, monkeypatch):
    watchlist_file = tmp_path / "watchlist.txt"
    watchlist_file.write_text("aapl, msft\n nvda", encoding="utf-8")
    monkeypatch.setattr(data_access, "DEFAULT_WATCHLIST_PATH", watchlist_file)

    assert data_access.load_watchlist() == ["AAPL", "MSFT", "NVDA"]


def test_get_default_watchlist_string_uses_fallback(monkeypatch, tmp_path):
    missing_path = tmp_path / "missing_watchlist.txt"
    monkeypatch.setattr(data_access, "DEFAULT_WATCHLIST_PATH", missing_path)

    assert data_access.get_default_watchlist_string() == data_access.DEFAULT_TICKERS_FALLBACK


def test_get_default_watchlist_string_joins_entries(tmp_path, monkeypatch):
    watchlist_file = tmp_path / "watchlist.txt"
    watchlist_file.write_text("AAPL,ADYEY,AMZN", encoding="utf-8")
    monkeypatch.setattr(data_access, "DEFAULT_WATCHLIST_PATH", watchlist_file)

    assert data_access.get_default_watchlist_string() == "AAPL,ADYEY,AMZN"


def test_validate_tickers_filters_and_corrects():
    class DummyTicker:
        def __init__(self, symbols):
            self.symbols = ["AAPL", "KO", "MSFT"]
            self.quote_type = {
                "AAPL": {"symbol": "AAPL"},
                "KKO": {"symbol": "KO"},
                "MSFT": {"symbol": "MSFT"},
            }

    tickers = ["AAPL", "kko", "MSFT", "BAD"]

    assert data_access.validate_tickers(tickers, ticker_cls=DummyTicker) == [
        "AAPL",
        "KO",
        "MSFT",
    ]


def test_load_watchlist_invokes_validator(tmp_path, monkeypatch):
    watchlist_file = tmp_path / "watchlist.txt"
    watchlist_file.write_text("aapl,bad", encoding="utf-8")
    monkeypatch.setattr(data_access, "DEFAULT_WATCHLIST_PATH", watchlist_file)

    captured = {}

    def fake_validate(tickers, ticker_cls=None):
        captured["tickers"] = tickers
        return ["AAPL"]

    monkeypatch.setattr(data_access, "validate_tickers", fake_validate)

    assert data_access.load_watchlist() == ["AAPL"]
    assert captured["tickers"] == ["AAPL", "BAD"]


def test_default_watchlist_uses_valid_symbol(monkeypatch):
    monkeypatch.setattr(data_access, "validate_tickers", lambda tickers, ticker_cls=None: tickers)

    watchlist = data_access.load_watchlist(data_access.DEFAULT_WATCHLIST_PATH)

    assert "KKO" not in watchlist
    assert "KO" in watchlist
