"""Automatic assessment UI: only budget and preference inputs, no business approvals."""

from __future__ import annotations

import json
import logging
from typing import Any

import pandas as pd
import streamlit as st

from . import data_access
from . import deployment_profile as profiles
from .automatic import DEFAULT_WEIGHTS, GROUPS, assess_watchlist


def render(tickers: list[str], profile: dict[str, Any], save, load_market: bool = True) -> None:
    st.caption(
        "Automatic ranking from reported financial metrics. No normalized EPS forecasts, thesis approvals, "
        "review dates or manual confidence ratings are required."
    )
    with st.expander("Load saved preferences"):
        uploaded = st.file_uploader("Preferences JSON", type=["json"], key="automatic_profile_upload")
        if st.button("Load automatic preferences", disabled=uploaded is None) and uploaded is not None:
            try:
                save(profiles.decode_profile(uploaded.getvalue().decode("utf-8")))
                st.rerun()
            except (ValueError, UnicodeError) as exc:
                st.error(f"Preferences not loaded: {exc}")
    settings = profile.get("automatic", {})
    weights = dict(settings.get("weights", DEFAULT_WEIGHTS))
    with st.form("automatic_preferences"):
        cols = st.columns(2)
        with cols[0]:
            budget = st.number_input(
                "Cash to deploy today (USD)",
                min_value=0.0,
                value=float(settings.get("budget", profile["policy"]["requested"])),
                step=1000.0,
            )
        with cols[1]:
            count = st.number_input(
                "Maximum businesses to fund", min_value=1, max_value=100, value=int(settings.get("max_businesses", 1))
            )
        with st.expander("Your ranking priorities and automatic purchase rules"):
            st.caption(
                "Defaults are starting preferences, not learned personal priorities. Weights are normalized "
                "to 100%; each category divides its weight equally across its metrics."
            )
            for group in GROUPS:
                weights[group] = st.number_input(
                    f"{group} weight", min_value=0.0, max_value=100.0, value=float(weights[group])
                )
            minimum_score = st.number_input(
                "Minimum score for suggested cash",
                min_value=0.0,
                max_value=100.0,
                value=float(settings.get("minimum_score", 60.0)),
            )
            minimum_coverage = st.number_input(
                "Minimum data coverage for suggested cash (%)",
                min_value=0.0,
                max_value=100.0,
                value=float(settings.get("minimum_coverage", 70.0)),
            )
        if st.form_submit_button("Run automatic assessment", type="primary"):
            if sum(weights.values()) <= 0:
                st.error("At least one category needs a positive weight.")
            else:
                profile["automatic"] = {
                    "budget": budget,
                    "max_businesses": count,
                    "weights": weights,
                    "minimum_score": minimum_score,
                    "minimum_coverage": minimum_coverage,
                }
                save(profile)
    settings = profile.get("automatic", {})
    client = data_access.get_batched_ticker_client(tickers) if load_market else None
    data = {}
    for ticker in tickers:
        try:
            data[ticker] = (
                data_access.fetch_ticker_sections(ticker, ticker_client=client)
                if load_market
                else {"error": {"message": "Provider unavailable"}}
            )
        except Exception:
            logging.getLogger(__name__).exception("Automatic assessment fetch failed for %s", ticker)
            data[ticker] = {"error": {"message": "Provider fetch failed"}}
    budget = float(settings.get("budget", profile["policy"]["requested"]))
    rows, evidence = assess_watchlist(
        data,
        settings.get("weights", DEFAULT_WEIGHTS),
        budget,
        int(settings.get("max_businesses", 1)),
        float(settings.get("minimum_score", 60.0)),
        float(settings.get("minimum_coverage", 70.0)) / 100,
    )
    ranked = [r for r in rows if r["Rank"] is not None]
    availability = {
        "tickers": len(rows),
        "ranked": len(ranked),
        "provider_errors": sum(r["Provider error"] for r in rows),
    }
    st.caption(
        f"Automatic data check: {len(ranked)}/{len(rows)} stocks have scored metrics · "
        f"{availability['provider_errors']} provider errors. Missing metrics are listed in the ranking."
    )
    logging.getLogger(__name__).info("Automatic availability summary: %s", json.dumps(availability))
    funded = [r for r in rows if r["Suggested USD"] > 0]
    if ranked:
        first = ranked[0]
        st.markdown(
            f"**Strongest automatic target: {first['Ticker']}** · Score {first['Score']:.1f}/100 · "
            f"Data coverage {first['Data coverage %']:.0f}%"
        )
    deployed = sum(r["Suggested USD"] for r in rows)
    st.markdown(f"**Suggested today: ${deployed:,.2f} · Unallocated: ${budget - deployed:,.2f}**")
    if funded:
        st.success("Automatic allocation: " + ", ".join(f"{r['Ticker']} ${r['Suggested USD']:,.2f}" for r in funded))
    else:
        st.info("No stock clears the automatic score/data rules today. The full ranking remains visible below.")
    st.caption(
        "Enter only cash already available after your reserves. No brokerage holdings feed is connected: "
        "these suggestions do not account for existing portfolio concentration, taxes or account restrictions. "
        "With multiple funded businesses, cash is split equally among the highest-ranked qualifying names."
    )
    if any(d.get("demo") for d in data.values()):
        st.warning("Demo market data: not a live investment assessment.")
    st.markdown("### Automatic watchlist ranking — strongest to weakest")
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    with st.expander("Explain the score and missing data"):
        st.markdown(
            "This is a weighted financial screen, not intrinsic value or a forecast of investment returns. "
            "For positive ratio targets, meeting the original threshold scores 50; better values increase toward 100. "
            "Negative valuation multiples score zero. Positive cash flow and net share reduction score 100, otherwise zero. "
            "Missing weighted metrics contribute zero and lower coverage, so missing data cannot improve a score. "
            "When valuation has a positive weight, its category must also score at least 50 before suggesting cash; "
            "quality alone cannot compensate for failing every valuation check. "
            "Reported growth is not a forecast. A known financial period older than 200 days blocks suggested cash; "
            "unknown periods are shown explicitly and cannot establish freshness. Absolute sales per share is context, not a ranking factor. Sector differences and accounting one-offs can distort these metrics. "
            "Income/ownership signals have zero weight by default; dividends alone do not increase allocation priority. "
            "Stocks remain ranked when score or coverage rules block suggested cash. Only absent financial data leaves a stock unranked."
        )
        st.dataframe(pd.DataFrame(evidence), hide_index=True, width="stretch")
    st.download_button(
        "Download automatic assessment (JSON)",
        json.dumps(
            {
                "settings": {
                    "budget": budget,
                    "max_businesses": settings.get("max_businesses", 1),
                    "minimum_score": settings.get("minimum_score", 60.0),
                    "minimum_coverage": settings.get("minimum_coverage", 70.0),
                },
                "effective_weights": settings.get("weights", DEFAULT_WEIGHTS),
                "results": rows,
                "metric_evidence": evidence,
            },
            indent=2,
            allow_nan=False,
        ),
        "automatic-assessment.json",
        "application/json",
    )
    st.download_button(
        "Export automatic ranking (CSV)", pd.DataFrame(rows).to_csv(index=False), "automatic-ranking.csv", "text/csv"
    )
    st.download_button(
        "Download preferences for next session",
        json.dumps(profile, indent=2, allow_nan=False),
        "deployment-profile.json",
        "application/json",
    )
