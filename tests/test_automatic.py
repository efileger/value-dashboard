import json
from copy import deepcopy
from datetime import datetime, timezone

import pytest
from streamlit.testing.v1 import AppTest

from stock_dashboard.automatic import DEFAULT_WEIGHTS, GROUPS, assess_watchlist, metric_score
from stock_dashboard.deployment_profile import decode_profile, encode_profile, new_profile

NOW = datetime(2026, 11, 8, 22, tzinfo=timezone.utc)


def rich_data():
    return {
        "summary_detail": {"trailingPE": 15, "priceToSalesTrailing12Months": 2},
        "financial_data": {
            "profitMargins": 0.2,
            "returnOnEquity": 0.2,
            "operatingMargins": 0.2,
            "ebitdaMargins": 0.2,
            "returnOnAssets": 0.1,
            "revenueGrowth": 0.1,
            "earningsGrowth": 0.1,
            "currentRatio": 3,
            "quickRatio": 2,
            "debtToEquity": 30,
            "freeCashflow": 1e9,
            "operatingCashflow": 2e9,
            "financialCurrency": "USD",
        },
        "key_stats": {
            "priceToBook": 2,
            "enterpriseToEbitda": 12,
            "pegRatio": 1,
            "sharesOutstanding": 1e9,
            "mostRecentQuarter": "2026-09-30",
        },
        "price": {"regularMarketPrice": 100, "regularMarketTime": NOW.isoformat(), "currency": "USD"},
        "buybacks": True,
    }


def test_automatic_allocation_requires_no_manual_business_case():
    rows, evidence = assess_watchlist({"A": rich_data()}, budget=5000, now=NOW)
    assert rows[0]["Rank"] == 1
    assert rows[0]["Data coverage %"] == 100
    assert rows[0]["Suggested USD"] == 5000
    assert rows[0]["Purchase blockers"] == ""
    assert sum(e["Points"] for e in evidence) == pytest.approx(rows[0]["Score"], abs=0.1)


def test_priorities_change_relative_ranking():
    cheap = rich_data()
    cheap["financial_data"].update(
        profitMargins=0.01, returnOnEquity=0.01, operatingMargins=0.01, ebitdaMargins=0.01, returnOnAssets=0.01
    )
    expensive = rich_data()
    expensive["summary_detail"].update(trailingPE=100, priceToSalesTrailing12Months=20)
    expensive["key_stats"].update(priceToBook=20, enterpriseToEbitda=100, pegRatio=10)
    weights = {g: 0.0 for g in GROUPS}
    weights["Valuation"] = 100
    rows, _ = assess_watchlist({"CHEAP": cheap, "QUALITY": expensive}, weights, now=NOW)
    assert rows[0]["Ticker"] == "CHEAP"
    weights["Valuation"], weights["Profitability"] = 0, 100
    rows, _ = assess_watchlist({"CHEAP": cheap, "QUALITY": expensive}, weights, now=NOW)
    assert rows[0]["Ticker"] == "QUALITY"


def test_missing_data_never_improves_score_and_ranks_stay_visible():
    data = rich_data()
    full, _ = assess_watchlist({"A": data}, now=NOW)
    data["financial_data"] = {}
    partial, _ = assess_watchlist({"A": data}, now=NOW)
    assert partial[0]["Score"] < full[0]["Score"]
    assert partial[0]["Data coverage %"] < 70
    assert partial[0]["Rank"] == 1
    assert partial[0]["Suggested USD"] == 0
    empty, _ = assess_watchlist({"A": {}}, now=NOW)
    assert empty[0]["Rank"] is None


@pytest.mark.parametrize("metric", ["P/E Ratio", "P/B Ratio", "EV / EBITDA", "PEG Ratio"])
def test_negative_multiple_is_not_a_bargain(metric):
    assert metric_score(metric, -5) == 0
    assert metric_score(metric, 0) == 0
    assert metric_score(metric, float("nan")) is None


@pytest.mark.parametrize("change", ["error", "stale_quote", "stale_quarter", "currency"])
def test_provider_data_problems_block_cash_without_hiding_ranking(change):
    data = rich_data()
    if change == "error":
        data["error"] = {"status_code": 429}
    elif change == "stale_quote":
        data["price"]["regularMarketTime"] = "2025-01-01"
    elif change == "stale_quarter":
        data["key_stats"]["mostRecentQuarter"] = "2025-01-01"
    else:
        data["price"]["currency"] = "EUR"
    rows, _ = assess_watchlist({"A": data}, now=NOW)
    assert rows[0]["Rank"] == 1
    assert rows[0]["Suggested USD"] == 0
    assert rows[0]["Purchase blockers"]


def test_allocation_respects_budget_and_number_of_businesses():
    rows, _ = assess_watchlist(
        {t: deepcopy(rich_data()) for t in ["C", "A", "B"]}, budget=10.01, max_businesses=2, now=NOW
    )
    assert [r["Ticker"] for r in rows] == ["A", "B", "C"]
    assert [r["Suggested USD"] for r in rows] == [5.01, 5, 0]
    data = rich_data()
    data["financial_data"]["returnOnEquity"] = float("nan")
    rows, evidence = assess_watchlist({"A": data}, now=NOW)
    json.dumps({"rows": rows, "evidence": evidence}, allow_nan=False)


def test_automatic_preferences_roundtrip_and_bad_import_rejected():
    profile = new_profile()
    profile["automatic"] = {"budget": 5000, "weights": DEFAULT_WEIGHTS, "max_businesses": 2}
    assert decode_profile(encode_profile(profile)) == profile
    profile["automatic"]["budget"] = -1
    with pytest.raises(ValueError):
        decode_profile(encode_profile(profile))


def test_default_ui_scores_reported_metrics_and_funds_without_approvals(monkeypatch):
    monkeypatch.delenv("VALUATION_PROFILE_PATH", raising=False)
    data = rich_data()
    data["price"]["regularMarketTime"] = datetime.now(timezone.utc).isoformat()
    data["key_stats"]["mostRecentQuarter"] = datetime.now(timezone.utc).date().isoformat()
    source = f"""
from unittest.mock import patch
from stock_dashboard import data_access, deployment_ui
from stock_dashboard.deployment_profile import new_profile
import streamlit as st
st.session_state.deployment_profile = new_profile()
with patch.object(data_access, "get_batched_ticker_client", return_value=None), patch.object(
    data_access, "fetch_ticker_sections", return_value={data!r}):
    deployment_ui.render(["A"])
"""
    app = AppTest.from_string(source).run(timeout=15)
    assert not app.exception
    assert app.radio[0].value == "Automatic financial ranking"
    assert any("Automatic allocation: A $5,000.00" in message.value for message in app.success)
    assert not any(x.label == "Latest results support the thesis" for x in app.checkbox)
    assert not any(x.label == "Business reviewed on (YYYY-MM-DD)" for x in app.text_input)
    ranking = app.dataframe[0].value
    assert ranking["Ticker"].tolist() == ["A"]
    assert ranking["Suggested USD"].tolist() == [5000]


def test_strong_quality_cannot_hide_failing_every_valuation_check():
    data = rich_data()
    data["summary_detail"].update(trailingPE=100, priceToSalesTrailing12Months=30)
    data["key_stats"].update(priceToBook=30, enterpriseToEbitda=100, pegRatio=10)
    rows, _ = assess_watchlist({"A": data}, now=NOW)
    assert rows[0]["Score"] > 60
    assert rows[0]["Valuation score"] < 50
    assert rows[0]["Rank"] == 1
    assert rows[0]["Suggested USD"] == 0
    assert "Valuation metrics" in rows[0]["Purchase blockers"]
