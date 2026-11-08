"""Streamlit presentation for saved business cases and ranked cash deployment."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import streamlit as st

from . import data_access
from . import deployment_profile as profiles
from .valuation import Assumptions, Policy, deployment, parse_date, to_dict


def _save(profile: dict[str, Any]) -> None:
    st.session_state.deployment_profile = profile
    path = profiles.configured_path()
    if path:
        try:
            profiles.save_profile(profile, path)
        except (OSError, ValueError) as exc:
            st.error(f"Profile remains in this session; disk save failed: {exc}")
    else:
        st.caption("Saved for this session. Download your profile to keep it for the next quarter.")


def _profile() -> dict[str, Any]:
    if "deployment_profile" not in st.session_state:
        profile = profiles.new_profile()
        path = profiles.configured_path()
        if path and path.exists():
            try:
                profile = profiles.decode_profile(path.read_text())
            except (OSError, ValueError) as exc:
                st.error(f"Cannot load saved deployment profile: {exc}")
        st.session_state.deployment_profile = profile
    return st.session_state.deployment_profile


def _assumption_editor(tickers: list[str], profile: dict[str, Any], sections: dict[str, dict[str, Any]]) -> None:
    if not tickers:
        return
    with st.expander("Review business valuations and position limits"):
        ticker = st.selectbox("Business to review", tickers, key="valuation_ticker")
        a = Assumptions(**profile["assumptions"].get(ticker, {}))
        facts = sections.get(ticker, {})
        price = facts.get("price") or {}
        stats = facts.get("key_stats") or {}
        st.caption(
            f"Yahoo reported trailing EPS: {stats.get('trailingEps', 'Unknown')}; "
            f"quote currency: {price.get('currency', 'Unknown')}; "
            f"financial currency: {(facts.get('financial_data') or {}).get('financialCurrency', 'Unknown')}. "
            "Reported EPS is a reference, not normalized earnings. Enter all per-share inputs "
            "in quote currency per listed share or ADR."
        )
        st.caption("Yahoo data receipt times (not financial report dates)")
        st.json(facts.get("cache_info", {}).get("section_fetched_at", {}))
        with st.form(f"valuation_{ticker}"):
            a.eps = st.number_input(
                "Normalized annual EPS per listed share / ADR", min_value=0.0, value=float(a.eps), step=0.10
            )
            a.dividend = st.number_input(
                "Annual dividend per listed share / ADR (held flat)", min_value=0.0, value=float(a.dividend), step=0.10
            )
            a.currency = st.text_input("Valuation currency", value=a.currency).strip().upper()
            for name, label in (("bear", "Conservative / bear"), ("base", "Base"), ("bull", "Bull")):
                cols = st.columns(2)
                with cols[0]:
                    growth = st.number_input(
                        f"{label} annual EPS growth (%)",
                        min_value=-90.0,
                        max_value=100.0,
                        value=float(getattr(a, f"{name}_growth") * 100),
                    )
                    setattr(a, f"{name}_growth", growth / 100)
                with cols[1]:
                    multiple = st.number_input(
                        f"{label} exit P/E", min_value=0.1, max_value=100.0, value=float(getattr(a, f"{name}_multiple"))
                    )
                    setattr(a, f"{name}_multiple", multiple)
            a.hurdle = (
                st.number_input(
                    "Required annual return (%)", min_value=0.1, max_value=100.0, value=float(a.hurdle * 100)
                )
                / 100
            )
            a.years = st.number_input("Holding period (years)", min_value=1, max_value=20, value=a.years)
            a.holding_value = st.number_input(
                "Current position value in USD", min_value=0.0, value=float(a.holding_value)
            )
            a.max_weight = (
                st.number_input(
                    "Maximum portfolio weight (%)", min_value=0.1, max_value=100.0, value=float(a.max_weight * 100)
                )
                / 100
            )
            a.addition_cap = st.number_input(
                "Maximum addition in this four-tranche plan (USD)",
                min_value=0.0,
                value=float(a.addition_cap),
                step=500.0,
            )
            a.reviewed_on = st.text_input("Business reviewed on (YYYY-MM-DD)", value=a.reviewed_on)
            a.financial_period = st.text_input(
                "Latest financial period reviewed (YYYY-MM-DD)", value=a.financial_period
            )
            a.source = st.text_area("Sources / filing links", value=a.source)
            a.normalization = st.text_area(
                "Normalization rationale (one-offs, capex, dilution, cash conversion, FX / ADR units)",
                value=a.normalization,
            )
            a.failure_condition = st.text_area("Thesis failure condition", value=a.failure_condition)
            a.confidence = st.selectbox(
                "Valuation confidence", ["Low", "Medium", "High"], index=["Low", "Medium", "High"].index(a.confidence)
            )
            a.thesis_intact = st.checkbox("Latest results support the thesis", value=a.thesis_intact)
            a.units_verified = st.checkbox(
                "Normalized earnings, currency and ADR units verified", value=a.units_verified
            )
            if st.form_submit_button("Save business case", type="primary"):
                candidate = {**profile, "assumptions": {**profile["assumptions"], ticker: asdict(a)}}
                try:
                    profiles.decode_profile(profiles.encode_profile(candidate))
                    profile.update(candidate)
                    _save(profile)
                except ValueError as exc:
                    st.error(str(exc))
        st.caption(
            "Changing a review date alone does not validate a thesis. Reconcile the latest report. "
            "Record executed purchases below; rerunning the dashboard does not consume a tranche."
        )


def render(tickers: list[str], load_market: bool = True) -> None:
    st.subheader("Where should today's cash go?")
    st.caption(
        "Five-year EPS + dividends scenario model by default; returns are nominal, before tax. "
        "Buy gates use the conservative value. Quality checks do not determine allocations."
    )
    profile = _profile()
    with st.expander("Load a saved deployment profile"):
        uploaded = st.file_uploader("Import your profile JSON", type=["json"], key="profile_upload")
        if st.button("Load profile", disabled=uploaded is None) and uploaded is not None:
            try:
                restored = profiles.decode_profile(uploaded.getvalue().decode("utf-8"))
                _save(restored)
                st.rerun()
            except (ValueError, UnicodeError) as exc:
                st.error(f"Profile not loaded: {exc}")
    policy = Policy(**profile["policy"])
    with st.form("deployment_policy"):
        cols = st.columns(2)
        with cols[0]:
            policy.requested = st.number_input(
                "Cash to deploy today (USD)", min_value=0.0, value=float(policy.requested), step=1000.0
            )
        with cols[1]:
            policy.max_businesses = st.number_input(
                "Maximum businesses this review", min_value=1, max_value=100, value=policy.max_businesses
            )
        with st.expander("Cash, portfolio and review settings"):
            settings_cols = st.columns(3)
            with settings_cols[0]:
                policy.account = st.text_input("Account / portfolio scope", value=policy.account)
                policy.available_cash = st.number_input(
                    "Available cash / SGOV pool (USD)", min_value=0.0, value=float(policy.available_cash), step=1000.0
                )
                policy.protected_reserve = st.number_input(
                    "Protected reserve in that pool (USD)",
                    min_value=0.0,
                    value=float(policy.protected_reserve),
                    step=1000.0,
                )
            with settings_cols[1]:
                policy.portfolio_value = st.number_input(
                    "Portfolio value including cash (USD)",
                    min_value=0.0,
                    value=float(policy.portfolio_value),
                    step=10000.0,
                )
                policy.holdings_as_of = st.text_input(
                    "Portfolio snapshot date (YYYY-MM-DD)", value=policy.holdings_as_of
                )
                policy.review_days = st.number_input(
                    "Business review interval (days)", min_value=1, max_value=95, value=policy.review_days
                )
            with settings_cols[2]:
                policy.cash_yield = (
                    st.number_input(
                        "Cash alternative annual yield (%)", min_value=0.0, value=float(policy.cash_yield * 100)
                    )
                    / 100
                )
                policy.cash_spread = (
                    st.number_input(
                        "Minimum return above cash (percentage points)",
                        min_value=0.0,
                        value=float(policy.cash_spread * 100),
                    )
                    / 100
                )
                policy.plan_started_on = st.text_input(
                    "Deployment plan started (YYYY-MM-DD)", value=policy.plan_started_on
                )
        if st.form_submit_button("Rank deployment opportunities", type="primary"):
            profile["policy"] = asdict(policy)
            _save(profile)
    # Only submitted policy values drive the plan.
    policy = Policy(**profile["policy"])
    batched = data_access.get_batched_ticker_client(tickers) if load_market else None
    sections: dict[str, dict[str, Any]] = {}
    for ticker in tickers:
        if not load_market:
            sections[ticker] = {"error": {"message": "Data source unavailable"}}
            continue
        try:
            sections[ticker] = data_access.fetch_ticker_sections(ticker, ticker_client=batched)
        except Exception as exc:
            logging.getLogger(__name__).exception("Deployment data fetch failed for %s", ticker)
            sections[ticker] = {"error": {"message": str(exc)}}
    _assumption_editor(tickers, profile, sections)
    assumptions = {t: Assumptions(**a) for t, a in profile["assumptions"].items()}
    results, retained = deployment(tickers, assumptions, sections, policy, profile["purchases"])
    eligible = [r for r in results if r.eligible]
    ranked = [r for r in results if r.rank is not None]
    proposed = sum(r.allocation for r in results)
    st.markdown(f"**{policy.account} · Proposed today: ${proposed:,.2f} · Unallocated request: ${retained:,.2f}**")
    started = parse_date(policy.plan_started_on)
    if started and (datetime.now(timezone.utc).date() - started).days >= 180:
        st.info(
            "This deployment plan is at least six months old. Reassess unused capital and "
            "deliberately choose continued valuation gates or ordinary DCA; there is no forced deployment."
        )
    if ranked:
        leader = ranked[0]
        st.markdown(
            f"**Strongest modeled target: {leader.ticker}** · "
            f"Conservative modeled annual return: {leader.bear_return:.1%}. "
            "Ranking includes businesses that fail purchase gates."
        )
    if eligible:
        best = eligible[0]
        st.success(
            f"Best qualifying candidate: {best.ticker}. Eligible amount today: "
            f"${best.allocation:,.2f}; conservative modeled return: {best.bear_return:.1%} annually."
        )
    else:
        st.info(
            "No watchlist business clears all purchase gates today. Retain the cash allocation "
            "in your cash alternative and review the blockers below."
        )
    if data_access.is_smoke_mode():
        st.warning("Demo market data: these results are not a live deployment assessment.")
    st.caption(
        "Rank all comparable business cases by conservative annual return, then discount, confidence and portfolio headroom. "
        "Purchase gates affect suggested cash, not ranking. Unreviewed or stale cases retain visible blockers; "
        "businesses without usable valuation inputs are listed as unranked. "
        "One tranche per business review; a drop through several price gates does not release several tranches."
    )

    def table(rows):
        return pd.DataFrame(
            [
                {
                    "Rank": r.rank,
                    "Ticker": r.ticker,
                    "Status": "Qualifies" if r.eligible else "Review / wait",
                    "Price USD": r.price,
                    "Bear value": r.bear_value,
                    "Base value": r.base_value,
                    "Bull value": r.bull_value,
                    "Conservative discount %": None if r.discount is None else round(r.discount * 100, 2),
                    "Bear return %": None if r.bear_return is None else round(r.bear_return * 100, 2),
                    "Base return %": None if r.base_return is None else round(r.base_return * 100, 2),
                    "Bull return %": None if r.bull_return is None else round(r.bull_return * 100, 2),
                    "Review entry price": r.entry_price,
                    "Headroom USD": r.headroom,
                    "Tranche limit USD": r.tranche_limit,
                    "Suggested USD": r.allocation,
                    "Confidence": r.confidence,
                    "Normalized EPS": assumptions[r.ticker].eps if r.ticker in assumptions else None,
                    "Current weight %": (
                        round(assumptions[r.ticker].holding_value / policy.portfolio_value * 100, 2)
                        if r.ticker in assumptions and policy.portfolio_value > 0
                        else None
                    ),
                    "Maximum weight %": (assumptions[r.ticker].max_weight * 100 if r.ticker in assumptions else None),
                    "Business reviewed": r.reviewed_on,
                    "Review due": r.review_due,
                    "Financial period": r.financial_period,
                    "Quote as of": r.quote_as_of,
                    "Why / blockers": "; ".join(r.reasons) or "All gates passed",
                }
                for r in rows
            ]
        )

    st.markdown("### Top five deployment targets — regardless of purchase gates")
    top = table(ranked[:5])
    if not top.empty:
        top = top[
            [
                "Rank",
                "Ticker",
                "Status",
                "Price USD",
                "Bear value",
                "Conservative discount %",
                "Bear return %",
                "Suggested USD",
                "Why / blockers",
            ]
        ]
    st.dataframe(top, hide_index=True, width="stretch")
    with st.expander("Full watchlist: strongest to weakest, with purchase blockers", expanded=True):
        st.dataframe(table(results), hide_index=True, width="stretch")
    # Render the record action before export so a purchase is included in the download.
    with st.expander("Record an executed purchase / review purchase history"):
        candidates = [r for r in results if r.allocation > 0]
        if candidates and not data_access.is_smoke_mode():
            chosen = st.selectbox("Executed purchase", [r.ticker for r in candidates])
            result = next(r for r in candidates if r.ticker == chosen)
            amount = st.number_input(
                "Executed amount (USD)",
                min_value=0.01,
                max_value=float(result.allocation),
                value=float(result.allocation),
            )
            if st.button("Record executed purchase"):
                a = assumptions[chosen]
                profile["purchases"].append(
                    {
                        "ticker": chosen,
                        "amount": amount,
                        "recorded_on": datetime.now(timezone.utc).date().isoformat(),
                        "reviewed_on": a.reviewed_on,
                        "financial_period": a.financial_period,
                    }
                )
                profile["assumptions"][chosen]["holding_value"] += amount
                profile["policy"]["available_cash"] -= amount
                _save(profile)
                st.rerun()
        st.dataframe(pd.DataFrame(profile["purchases"]), hide_index=True)
        st.caption(
            "Records track actual purchases you enter; this app does not place orders. "
            "A partial purchase consumes that review's tranche. Starting a fresh plan archives "
            "this plan's assumptions and purchases, preserves cash and holdings, and clears business approvals."
        )
        if st.button("Archive plan and begin a fresh review", disabled=not profile["purchases"]):
            today = datetime.now(timezone.utc).date().isoformat()
            profile.setdefault("archives", []).append(
                {
                    "closed_on": today,
                    "policy": dict(profile["policy"]),
                    "assumptions": {t: dict(a) for t, a in profile["assumptions"].items()},
                    "purchases": profile["purchases"],
                }
            )
            profile["purchases"] = []
            profile["policy"]["plan_started_on"] = today
            for business in profile["assumptions"].values():
                business.update(reviewed_on="", thesis_intact=False, units_verified=False, confidence="Low")
            _save(profile)
            st.rerun()
    st.download_button(
        "Download deployment profile for next quarter",
        profiles.encode_profile(profile),
        "deployment-profile.json",
        "application/json",
    )
    st.download_button(
        "Export today's assessment (CSV)", table(results).to_csv(index=False), "deployment-assessment.csv", "text/csv"
    )
    st.download_button(
        "Export today's assessment (JSON)",
        json.dumps(
            {
                "assessed_at": datetime.now(timezone.utc).isoformat(),
                "policy": asdict(policy),
                "assumptions": profile["assumptions"],
                "purchases": profile["purchases"],
                "archives": profile.get("archives", []),
                "results": [to_dict(r) for r in results],
                "unallocated_request": retained,
                "data_receipts": {t: s.get("cache_info", {}) for t, s in sections.items()},
            },
            indent=2,
            allow_nan=False,
        ),
        "deployment-assessment.json",
        "application/json",
    )
    st.caption(
        "No shared-server profile is saved by default. Download your private JSON after changes; "
        "session state alone will not survive a new session. Initial PEP/MSFT/TSM assumptions and "
        "3.83% cash yield come from the supplied conversation and require review. "
        "Portfolio weights use the scope above; do not mix taxable cash with IRA reserves."
    )
    with st.expander("How this assessment works"):
        st.markdown(
            "Value today = discounted flat annual dividends + discounted terminal EPS × exit P/E. "
            "Annual return is the IRR of buying at today's quote, receiving those dividends and selling "
            "at the terminal value. The conservative scenario sets the 15% / 25% / 35% / 15% discount "
            "gates. Tranche four requires a later financial period than the first purchase. "
            "Each suggestion is capped at 25% of the planned addition, the remaining addition cap, "
            "portfolio headroom and available unreserved cash.\n\n"
            "A business review expires after 95 days by default; a newer reported quarter blocks buying "
            "sooner. Unknown or stale quote timestamps block buying (four calendar days allow weekends). "
            "The portfolio snapshot must be within 30 days. Low-confidence or unverified cases can be ranked "
            "when model inputs are available, but remain ineligible for suggested purchases. "
            "Confirm material news between reviews; the app does not monitor thesis failures.\n\n"
            "This is a scenario estimate, not an independently established intrinsic value. EPS can obscure "
            "capex, debt, settlement cash, dilution and cycle effects; document their reconciliation or leave "
            "the case unapproved. Dividends are cash flows, not a standalone allocation bonus. Returns exclude "
            "investor taxes, withholding, fees and future FX changes. No automatic FX conversion is performed. "
            "Refresh the cash yield when reviewing the plan."
        )
