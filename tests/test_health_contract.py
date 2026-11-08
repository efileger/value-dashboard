"""Availability is observed from provider work, never an unrelated raw HTTP probe."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from stock_dashboard import data_access


def test_readiness_does_not_probe_unrelated_quote_endpoint():
    with patch("requests.get", side_effect=AssertionError("No raw HTTP preflight")):
        state = data_access.check_data_source_health()
        assert state.ok
        assert state.message  # Explicitly unverified, not a successful Yahoo quote.
        assert data_access.check_data_source_health(force_refresh=True).ok


def test_observed_failure_cooldown_then_recovery_permission(monkeypatch):
    now = datetime(2026, 11, 8, tzinfo=timezone.utc)
    monkeypatch.setattr(data_access, "_utcnow", lambda: now)
    error = data_access.RateLimitError(status_code=429, message="provider throttled", retry_after=7, headers={})
    data_access._record_rate_limit(error)
    assert not data_access.check_data_source_health(force_refresh=True).ok
    monkeypatch.setattr(data_access, "_utcnow", lambda: now + timedelta(seconds=301))
    assert data_access.check_data_source_health(force_refresh=True).ok
