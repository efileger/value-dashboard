import pytest

from stock_dashboard import data_access, ui


def test_display_stock_uses_available_values(streamlit_spy, fake_ticker_cls):
    captured = streamlit_spy

    ui.display_stock("AAPL", ticker_cls=fake_ticker_cls)

    assert "df" in captured
    # Ensure multiple metrics were rendered with non-placeholder values
    assert all(value != "N/A" for value in captured["df"]["Value"].head(5))


def test_display_stock_falls_back_to_price_market_cap(
    streamlit_spy, price_cap_ticker_cls
):
    captured = streamlit_spy

    ui.display_stock("PCAP", ticker_cls=price_cap_ticker_cls)

    assert "df" in captured
    assert not any("missing required fields" in msg.lower() for msg in captured["warnings"])


def test_display_stock_falls_back_to_summary_detail_market_cap(
    streamlit_spy, summary_detail_cap_ticker_cls
):
    captured = streamlit_spy

    ui.display_stock("SCAP", ticker_cls=summary_detail_cap_ticker_cls)

    assert "df" in captured
    assert not any("missing required fields" in msg.lower() for msg in captured["warnings"])


def test_display_stock_allows_partial_data_with_warnings(streamlit_spy, partial_ticker_cls):
    captured = streamlit_spy

    ui.display_stock("PART", ticker_cls=partial_ticker_cls)

    assert "df" in captured
    assert captured["warnings"], "Expected warnings to be shown for partial data"
    assert any("Missing required fields" in message for message in captured["warnings"])
    assert any("Missing metrics" in message for message in captured["warnings"])


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


def test_display_stock_surfaces_error_reason(streamlit_spy, erroring_ticker_cls):
    data_access.RATE_LIMIT_COOLDOWNS.clear()
    captured = streamlit_spy

    ui.display_stock("ERR", ticker_cls=erroring_ticker_cls)

    assert any("Rate limit" in message for message in captured["info"])
    assert not captured["warnings"]
    data_access.RATE_LIMIT_COOLDOWNS.clear()


def test_display_stock_warns_when_no_error_details(streamlit_spy, empty_ticker_cls):
    data_access.RATE_LIMIT_COOLDOWNS.clear()

    with pytest.raises(ValueError) as excinfo:
        ui.display_stock("AAPL", ticker_cls=empty_ticker_cls)

    message = str(excinfo.value)
    assert "reason" in message
    assert any("Yahoo Finance" in warning or "outage" in warning for warning in streamlit_spy["warnings"])
