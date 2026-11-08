"""Consumer expectations at the Yahoo HTTP boundary; no live provider required.

These doubles must also be checked against the provider by the scheduled live probe.
"""

from types import SimpleNamespace

import pytest
import requests

from stock_dashboard import data_access


@pytest.mark.parametrize(
    "status_code,healthy,throttled", [(200, True, False), (429, False, True), (503, False, True), (500, False, False)]
)
def test_health_status_and_cache_contract(monkeypatch, status_code, healthy, throttled):
    calls = []

    def get(url, *, params, timeout):
        calls.append(url)
        assert params == {"symbols": "AAPL"}
        assert timeout == 2.5
        return SimpleNamespace(
            status_code=status_code, ok=status_code < 400, url=url, headers={"Retry-After": "7"} if throttled else {}
        )

    monkeypatch.setattr(data_access.requests, "get", get)
    health = data_access.check_data_source_health()
    assert health.ok is healthy
    assert bool(health.rate_limit) is throttled
    if throttled:
        assert health.rate_limit.retry_after == 7
    assert len(calls) == (1 if healthy or throttled else 2)
    assert data_access.check_data_source_health() is health
    assert len(calls) == (1 if healthy or throttled else 2)
    data_access.check_data_source_health(force_refresh=True)
    assert len(calls) == (1 if throttled else 2 if healthy else 4)


@pytest.mark.parametrize("failure", [requests.Timeout, requests.ConnectionError])
def test_health_failure_tries_both_hosts_and_degrades(monkeypatch, failure):
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        raise failure("unavailable")

    monkeypatch.setattr(data_access.requests, "get", get)
    health = data_access.check_data_source_health()
    assert not health.ok
    assert health.host is None
    assert not health.rate_limit
    assert len(calls) == 2
    assert data_access.check_data_source_health() is health
    assert len(calls) == 2
