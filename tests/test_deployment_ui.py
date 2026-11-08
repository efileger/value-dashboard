from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from streamlit.testing.v1 import AppTest

from stock_dashboard.deployment_profile import decode_profile, encode_profile, new_profile
from stock_dashboard.valuation import Assumptions, Policy


def widget(elements, label):
    return next(element for element in elements if element.label == label)


def test_full_app_smoke_has_planner_without_buy_labels(monkeypatch):
    monkeypatch.setenv("SMOKE_TEST", "1")
    monkeypatch.delenv("VALUATION_PROFILE_PATH", raising=False)
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "stock_dashboard.py").run(timeout=20)
    assert not app.exception
    assert any("No stock clears the automatic" in message.value for message in app.info)
    assert not any("Suggested Action" in message.value for message in app.markdown)
    assert widget(app.number_input, "Cash to deploy today (USD)").value == 5000
    assert len(app.get("download_button")) == 3


def planner_app(profile):
    source = f"""
import streamlit as st
from datetime import datetime, timezone
from stock_dashboard import data_access, deployment_ui
from stock_dashboard.deployment_profile import decode_profile
from unittest.mock import patch
st.session_state["assessment_mode"] = "Scenario valuation (advanced)"
st.session_state.setdefault("deployment_profile", decode_profile({encode_profile(profile)!r}))
def fetch(ticker, **kwargs):
    return {{"price": {{
    "regularMarketPrice": 60 if ticker == "BEST" else 70,
    "regularMarketTime": datetime.now(timezone.utc).isoformat(), "currency": "USD"}}}}
with patch.object(data_access, "is_smoke_mode", return_value=False), \
     patch.object(data_access, "get_batched_ticker_client", return_value=None), \
     patch.object(data_access, "fetch_ticker_sections", side_effect=fetch):
    deployment_ui.render(["BEST", "OTHER"])
"""
    return AppTest.from_string(source).run(timeout=20)


def ready_profile():
    today = datetime.now(timezone.utc).date().isoformat()
    profile = new_profile()
    profile["policy"] = asdict(Policy(portfolio_value=100000, holdings_as_of=today))
    a = Assumptions(
        eps=10,
        bear_multiple=20,
        base_multiple=20,
        bull_multiple=20,
        reviewed_on=today,
        financial_period=today,
        source="Latest quarterly report",
        normalization="Recurring EPS, capex and dilution reviewed",
        failure_condition="Margin deterioration",
        confidence="High",
        units_verified=True,
        thesis_intact=True,
        addition_cap=20000,
    )
    profile["assumptions"] = {"BEST": asdict(a), "OTHER": asdict(a)}
    return profile


def test_change_budget_spread_record_and_persist_purchase(tmp_path, monkeypatch):
    path = tmp_path / "profile.json"
    monkeypatch.setenv("VALUATION_PROFILE_PATH", str(path))
    app = planner_app(ready_profile())
    assert not app.exception
    assert "Best qualifying candidate: BEST" in app.success[0].value
    assert "$5,000.00" in app.success[0].value
    # A new requested budget can be spread, with one capped tranche per business.
    widget(app.number_input, "Cash to deploy today (USD)").set_value(15000)
    widget(app.number_input, "Maximum businesses this review").set_value(10)
    widget(app.button, "Rank deployment opportunities").click().run()
    assert not app.exception
    assert any("Proposed today: $10,000.00" in m.value for m in app.markdown)
    widget(app.button, "Record executed purchase").click().run()
    assert not app.exception
    saved = decode_profile(path.read_text())
    assert len(saved["purchases"]) == 1
    assert saved["purchases"][0]["ticker"] == "BEST"
    assert saved["policy"]["available_cash"] == 30000
    assert saved["assumptions"]["BEST"]["holding_value"] == 5000
    assert "Best qualifying candidate: OTHER" in app.success[0].value
    # Passive reruns do not record purchases or consume more capital.
    app.run()
    assert not app.exception
    assert len(app.session_state["deployment_profile"]["purchases"]) == 1
    widget(app.button, "Archive plan and begin a fresh review").click().run()
    assert not app.exception
    fresh = decode_profile(path.read_text())
    assert fresh["purchases"] == []
    assert len(fresh["archives"][0]["purchases"]) == 1
    assert fresh["archives"][0]["assumptions"]["BEST"]["thesis_intact"]
    assert not fresh["assumptions"]["BEST"]["thesis_intact"]
    assert fresh["policy"]["available_cash"] == 30000
    assert fresh["assumptions"]["BEST"]["holding_value"] == 5000
    assert any("No watchlist business clears" in m.value for m in app.info)


def test_edit_business_case_invalid_then_valid(monkeypatch):
    monkeypatch.delenv("VALUATION_PROFILE_PATH", raising=False)
    profile = ready_profile()
    profile["assumptions"]["BEST"]["thesis_intact"] = False
    app = planner_app(profile)
    assert "Best qualifying candidate: OTHER" in app.success[0].value
    widget(app.checkbox, "Latest results support the thesis").check()
    widget(app.number_input, "Base annual EPS growth (%)").set_value(-5)
    widget(app.button, "Save business case").click().run()
    assert any("ordered" in error.value for error in app.error)
    assert not app.session_state["deployment_profile"]["assumptions"]["BEST"]["thesis_intact"]
    widget(app.number_input, "Base annual EPS growth (%)").set_value(5)
    widget(app.button, "Save business case").click().run()
    assert not app.exception
    assert app.session_state["deployment_profile"]["assumptions"]["BEST"]["thesis_intact"]
    assert "Best qualifying candidate: BEST" in app.success[0].value


def test_profile_load_error_is_visible_and_cannot_allocate(tmp_path, monkeypatch):
    path = tmp_path / "profile.json"
    path.write_text("broken")
    monkeypatch.setenv("VALUATION_PROFILE_PATH", str(path))
    app = AppTest.from_string("""
import streamlit as st
from stock_dashboard.deployment_ui import render
st.session_state["assessment_mode"] = "Scenario valuation (advanced)"
render([], load_market=False)
""").run()
    assert not app.exception
    assert any("Cannot load saved" in e.value for e in app.error)
    assert any("No watchlist business clears" in m.value for m in app.info)


def test_blocked_targets_remain_ranked_in_default_view(monkeypatch):
    monkeypatch.delenv("VALUATION_PROFILE_PATH", raising=False)
    profile = ready_profile()
    for case in profile["assumptions"].values():
        case["thesis_intact"] = False
    app = planner_app(profile)
    assert not app.exception
    assert any("No watchlist business clears" in message.value for message in app.info)
    assert any("Strongest modeled target: BEST" in message.value for message in app.markdown)
    top = next(d.value for d in app.dataframe if "Rank" in d.value.columns)
    assert top["Ticker"].tolist() == ["BEST", "OTHER"]
    assert top["Rank"].tolist() == [1, 2]
    assert (top["Suggested USD"] == 0).all()
    assert top["Why / blockers"].str.contains("Thesis").all()
    full = next(e for e in app.expander if e.label.startswith("Full watchlist: strongest to weakest"))
    assert full.proto.expanded


def test_diagnostics_explains_missing_business_inputs_without_provider_error(monkeypatch):
    monkeypatch.delenv("VALUATION_PROFILE_PATH", raising=False)
    profile = ready_profile()
    profile["assumptions"]["BEST"]["eps"] = 0
    app = planner_app(profile)
    assert not app.exception
    assert any(
        "2/2 quotes available" in caption.value and "0 provider errors" in caption.value for caption in app.caption
    )
    diagnostics = next(d.value for d in app.dataframe if "Provider status" in d.value.columns)
    row = diagnostics[diagnostics["Ticker"] == "BEST"].iloc[0]
    assert row["Provider status"] == "Data received"
    assert "Normalized EPS" in row["Business review needed"]
    assert not row["Scenario calculated"]
    assert any(b.label == "Download data diagnostics (JSON)" for b in app.get("download_button"))
