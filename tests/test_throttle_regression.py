"""Production-style cold/rerun/partial-cache throttling, with real UI and offline HTTP."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import requests
from streamlit.testing.v1 import AppTest

from stock_dashboard import data_access, ui


def throttled(url="https://query1.finance.yahoo.com/v7/finance/quote"):
    response = requests.Response()
    response.status_code = 429
    response.url = url
    response._content = b"Too Many Requests"
    return response


def test_production_page_rerun_during_actual_provider_cooldown(monkeypatch):
    monkeypatch.delenv("SMOKE_TEST", raising=False)
    monkeypatch.delenv("VALUATION_PROFILE_PATH", raising=False)
    data_access._record_rate_limit(
        data_access.RateLimitError(status_code=429, message="actual provider throttled", retry_after=None, headers={})
    )
    with patch.object(data_access.Ticker, "__init__", side_effect=AssertionError("No new clients")) as constructor:
        app = AppTest.from_file(Path(__file__).resolve().parents[1] / "stock_dashboard.py").run(timeout=15)
        assert not app.exception
        app.run(timeout=15)
        assert not app.exception
        constructor.assert_not_called()
        notices = [m.value for m in app.info if "Rate limit detected from" in m.value]
        assert not notices  # A global outage is not rendered for every ticker.
        assert not app.success


def test_no_retry_after_uses_default_and_recovers_after_expiry(monkeypatch):
    now = datetime(2026, 11, 8, tzinfo=timezone.utc)
    monkeypatch.setattr(data_access, "_utcnow", lambda: now)
    data_access._record_rate_limit(
        data_access.RateLimitError(status_code=429, message="actual provider throttled", retry_after=None, headers={})
    )
    health = data_access.check_data_source_health()
    assert health.rate_limit.remaining == 300
    assert health.rate_limit.retry_after is None
    assert data_access.validate_tickers(["MSFT"]) == ["MSFT"]
    assert data_access.get_batched_ticker_client(["MSFT"]) is None
    monkeypatch.setattr(data_access, "_utcnow", lambda: now + timedelta(seconds=301))
    assert data_access.check_data_source_health(force_refresh=True).ok


def test_section_429_stops_remaining_sections_and_buyback_requests(monkeypatch):
    class Client:
        @property
        def summary_detail(self):
            raise requests.HTTPError("throttled", response=throttled())

        def __getattr__(self, name):
            raise AssertionError(f"Unexpected provider access after 429: {name}")

    result = data_access.fetch_ticker_sections("TEST", ticker_client=Client())
    assert result["error"]["rate_limit"].status_code == 429
    assert data_access._active_rate_limit() is not None


def test_cached_screen_survives_429_but_allocation_is_blocked(monkeypatch, streamlit_spy):
    monkeypatch.setenv("SMOKE_TEST", "1")
    cached = data_access.fetch_ticker_sections("TEST")
    monkeypatch.delenv("SMOKE_TEST")
    for name in ("summary_detail", "financial_data", "asset_profile", "key_stats", "quote_type", "price"):
        data_access._set_cached_section("TEST", name, cached[name])
    data_access._record_rate_limit(
        data_access.RateLimitError(status_code=429, message="actual provider throttled", retry_after=None, headers={})
    )
    with patch.object(data_access.Ticker, "__init__", side_effect=AssertionError("Must use cache")):
        result = data_access.fetch_ticker_sections("TEST")
        assert result["error"]["rate_limit"]
        ui.display_stock("TEST")
    assert "df" in streamlit_spy
    assert any("cached screening" in text for text in streamlit_spy["captions"])


def test_retry_after_http_date(monkeypatch):
    monkeypatch.setattr(data_access, "_utcnow", lambda: datetime(2026, 11, 8, 19, 34, 1, tzinfo=timezone.utc))
    assert data_access._parse_retry_after({"Retry-After": "Sun, 08 Nov 2026 19:36:01 GMT"}) == 120


def test_batched_sections_are_downloaded_once_for_whole_watchlist():
    calls = []

    class Client:
        symbols = ("A", "B")

        def __getattr__(self, name):
            if name == "income_statement":
                return None
            calls.append(name)
            return {symbol: {"value": 1} for symbol in self.symbols}

    client = Client()
    data_access.fetch_ticker_sections("A", ticker_client=client)
    data_access.fetch_ticker_sections("B", ticker_client=client)
    assert len(calls) == 6
    assert len(set(calls)) == 6


def test_actual_throttle_overrides_cached_healthy_probe():
    data_access._set_cached_health(data_access.DataSourceHealth(ok=True, host="probe", latency_ms=0, headers={}))
    data_access._record_rate_limit(
        data_access.RateLimitError(
            status_code=429, message="throttled", retry_after=60, headers={}, host="query2.finance.yahoo.com"
        )
    )
    assert not data_access.check_data_source_health().ok
