import json
from dataclasses import replace
from datetime import datetime, timezone

from stock_dashboard.diagnostics import build_report
from stock_dashboard.valuation import Assessment, Assumptions

NOW = datetime(2026, 11, 8, 22, tzinfo=timezone.utc)


def facts():
    return {
        "price": {"regularMarketPrice": 141.34, "regularMarketTime": NOW.timestamp(), "currency": "USD"},
        "key_stats": {"trailingEps": 9.2, "mostRecentQuarter": "2026-09-30"},
        "financial_data": {"financialCurrency": "USD"},
        "cache_info": {"served_from_cache": True, "section_fetched_at": {"price": NOW.isoformat()}},
    }


def test_quotes_arrive_but_manual_inputs_prevent_scenarios():
    report = build_report(["AAPL"], {"AAPL": facts()}, {"AAPL": Assumptions()}, [], NOW)
    assert report["summary"] == {
        "tickers": 1,
        "quotes_available": 1,
        "provider_errors": 0,
        "scenarios_calculated": 0,
        "normalized_eps_entered": 0,
    }
    row = report["rows"][0]
    assert row["Provider status"] == "Data received"
    assert row["Reported EPS"] == 9.2
    assert "Normalized EPS" in row["Business review needed"]
    assert "Financial period reviewed" in row["Business review needed"]
    assert row["Cache"] == "Full"
    assert row["Section receipt times"]["price"] == NOW.isoformat()


def test_provider_failure_distinct_from_assumptions_and_sanitized():
    data = {"error": {"status_code": 429, "message": "apikey=SECRET", "headers": {"Authorization": "SECRET"}}}
    report = build_report(["MSFT"], {"MSFT": data}, {"MSFT": Assumptions(eps=17.75)}, [], NOW)
    assert report["rows"][0]["Provider status"] == "Throttled / cooldown"
    assert report["summary"]["provider_errors"] == 1
    assert not report["rows"][0]["Quote available"]
    assert report["rows"][0]["Normalized EPS entered"]
    assert "SECRET" not in json.dumps(report)
    assert "price.regularMarketPrice" in report["rows"][0]["Missing provider fields"]


def test_complete_business_inputs_and_stale_quotes_are_separate():
    a = Assumptions(
        eps=10,
        reviewed_on="2026-11-08",
        financial_period="2026-09-30",
        thesis_intact=True,
        units_verified=True,
        confidence="High",
    )
    data = facts()
    data["price"]["regularMarketTime"] = "2026-10-01"
    report = build_report(["A"], {"A": data}, {"A": a}, [Assessment(ticker="A", bear_value=100)], NOW)
    assert report["summary"]["scenarios_calculated"] == 1
    assert report["rows"][0]["Quote freshness"] == "Missing / stale / future"
    assert report["rows"][0]["Business review needed"].startswith("Required inputs entered")
    assert report["rows"][0]["Missing provider fields"] == "None"
    unconfigured = build_report(["A"], {}, {}, [], NOW)["rows"][0]
    assert unconfigured["Business review needed"] == "Business case not configured"
    assert unconfigured["Provider status"] == "No data received"


def test_authentication_error_is_not_reported_as_rate_limit():
    report = build_report(
        ["A"], {"A": {"error": {"status_code": 401}}}, {"A": replace(Assumptions(), confidence="Medium")}, [], NOW
    )
    assert report["rows"][0]["Provider status"] == "Authentication / access failure"
