"""Exercise the installed Yahooquery request builder, not mock property counts."""

import json
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import requests
from yahooquery import Ticker

from stock_dashboard import data_access


def test_native_modules_make_one_actual_request_per_symbol_and_income_once():
    calls = []
    client = object.__new__(Ticker)
    client.country = "united states"
    client.formatted = False
    client.progress = False
    client.crumb = None
    client.symbols = ["A", "B", "C"]

    def get(url, *, params):
        calls.append((url, params))
        response = requests.Response()
        response.status_code = 200
        response.url = url
        response._content = json.dumps(
            {
                "quoteSummary": {
                    "error": None,
                    "result": [{module: {"value": 1} for module in data_access._MODULE_NAMES.values()}],
                }
            }
        ).encode()
        return response

    client.session = SimpleNamespace(get=get)
    income = pd.DataFrame(
        {
            "asOfDate": ["2025-12-31", "2024-12-31"] * 3,
            "DilutedAverageShares": [90, 100] * 3,
            "periodType": ["12M"] * 6,
        },
        index=pd.Index(["A", "A", "B", "B", "C", "C"], name="symbol"),
    )
    with patch.object(client, "income_statement", return_value=income) as financials:
        results = [data_access.fetch_ticker_sections(symbol, ticker_client=client) for symbol in client.symbols]
    assert len(calls) == 3
    assert all(len(params["modules"].split(",")) == 6 for _, params in calls)
    assert financials.call_count == 1
    assert all(result["buybacks"] is True for result in results)
    assert all(not result["error"] for result in results)


def test_readiness_has_no_independent_probe_or_false_verification():
    with patch.object(requests, "get", side_effect=AssertionError("No HTTP preflight")):
        status = data_access.check_data_source_health(force_refresh=True)
    assert status.ok
    assert not status.verified
    assert "not yet verified" in status.message


def test_yahooquery_non_json_429_preserves_status_before_library_masking():
    client = object.__new__(Ticker)
    client.country = "united states"
    client.formatted = False
    client.progress = False
    client.crumb = None
    client.symbols = ["A"]

    def get(url, *, params):
        response = requests.Response()
        response.status_code = 429
        response.url = url
        response._content = b"Too Many Requests"
        return response

    client.session = SimpleNamespace(get=get)
    result = data_access.fetch_ticker_sections("A", ticker_client=client)
    assert result["error"]["status_code"] == 429
    assert result["error"]["rate_limit"].status_code == 429
    assert "404" not in result["error"]["message"]
    assert data_access._active_rate_limit() is not None
