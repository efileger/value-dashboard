import pytest

from stock_dashboard import data_access, ui


def test_display_stock_uses_available_values(streamlit_spy, fake_ticker_cls):
    captured = streamlit_spy

    ui.display_stock("AAPL", ticker_cls=fake_ticker_cls)

    assert "df" in captured
    # Ensure multiple metrics were rendered with non-placeholder values
    assert all(value != "N/A" for value in captured["df"]["Value"].head(5))


def test_display_stock_raises_on_empty_data(stubbed_streamlit, empty_ticker_cls):
    with pytest.raises(ValueError):
        ui.display_stock("AAPL", ticker_cls=empty_ticker_cls)


def test_watchlist_entries_fail_fast(stubbed_streamlit, empty_ticker_cls):
    tickers = [
        t.strip().upper()
        for t in data_access.get_default_watchlist_string().split(",")
        if t.strip()
    ]

    for ticker in tickers:
        with pytest.raises(ValueError):
            ui.display_stock(ticker, ticker_cls=empty_ticker_cls)
