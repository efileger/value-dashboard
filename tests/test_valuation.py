from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from stock_dashboard.valuation import (
    Assumptions,
    Policy,
    conversation_seeds,
    deployment,
    parse_timestamp,
    scenario,
)

NOW = datetime(2026, 11, 8, 18, tzinfo=timezone.utc)


@pytest.fixture
def business():
    return Assumptions(
        eps=10,
        dividend=0,
        bear_growth=0,
        base_growth=0.05,
        bull_growth=0.10,
        bear_multiple=20,
        base_multiple=22,
        bull_multiple=25,
        reviewed_on="2026-11-07",
        financial_period="2026-09-30",
        source="Latest 10-Q",
        normalization="Exclude one-off tax credit; reconcile capex and dilution",
        failure_condition="Cash return on invested capital falls",
        confidence="High",
        thesis_intact=True,
        units_verified=True,
        addition_cap=20000,
    )


@pytest.fixture
def policy():
    return Policy(portfolio_value=100000, holdings_as_of="2026-11-07", max_businesses=10)


def quote(price=70, **kwargs):
    return {"price": {"regularMarketPrice": price, "regularMarketTime": NOW.timestamp(), "currency": "USD", **kwargs}}


def run(a, p, data=None, purchases=None):
    return deployment(["TEST"], {"TEST": a}, {"TEST": data or quote()}, p, purchases or [], NOW)[0][0]


def test_present_value_and_irr_include_dividends(business):
    a = replace(business, eps=8.38, dividend=5.92, bear_growth=0.03, bear_multiple=18)
    value, annual_return = scenario(a, 0.03, 18, 143)
    expected = sum(5.92 / 1.10**year for year in range(1, 6)) + 8.38 * 1.03**5 * 18 / 1.10**5
    assert value == pytest.approx(expected)
    assert 130 < value < 132
    assert annual_return < 0.10
    assert scenario(a, 0.03, 18, value)[1] == pytest.approx(0.10)


def test_five_thousand_goes_to_best_qualifying_business(business, policy):
    results, retained = deployment(
        ["WEAKER", "BEST"],
        {"WEAKER": business, "BEST": business},
        {"WEAKER": quote(80), "BEST": quote(60)},
        replace(policy, max_businesses=1),
        [],
        NOW,
    )
    assert [r.ticker for r in results] == ["BEST", "WEAKER"]
    assert [r.rank for r in results] == [1, 2]
    assert [r.allocation for r in results] == [5000, 0]
    assert retained == 0


def test_cash_reserve_tranches_and_weights_limit_spread(business, policy):
    assumptions = {
        "A": replace(business, addition_cap=10000),
        "B": replace(business, holding_value=9400),
        "C": business,
    }
    results, retained = deployment(
        ["A", "B", "C"],
        assumptions,
        {"A": quote(50), "B": quote(60), "C": quote(70)},
        replace(policy, requested=15000, available_cash=10000, protected_reserve=6000),
        [],
        NOW,
    )
    assert [r.allocation for r in results] == [2500, 600, 900]
    assert retained == 11000
    assert sum(r.allocation for r in results) <= 4000


def test_no_candidate_means_hold_all_cash(business, policy):
    result = run(business, policy, quote(200))
    assert not result.eligible
    assert result.rank is None
    assert result.allocation == 0
    assert any("discount" in reason for reason in result.reasons)


def test_optimistic_bull_cannot_make_conservative_case_qualify(business, policy):
    result = run(replace(business, bull_growth=0.8, bull_multiple=80), policy, quote(150))
    assert result.bull_value > 1000
    assert not result.eligible
    assert result.discount < 0


def test_falling_value_with_falling_price_does_not_create_bargain(business, policy):
    initial = run(business, policy, quote(70))
    revised = run(replace(business, eps=3), policy, quote(60))
    assert initial.eligible
    assert not revised.eligible


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"reviewed_on": "2026-08-01"}, "review"),
        ({"reviewed_on": "2026-11-09"}, "review"),
        ({"financial_period": "2025-12-31"}, "200 days"),
        ({"units_verified": False}, "units"),
        ({"thesis_intact": False}, "Thesis"),
        ({"source": ""}, "source"),
        ({"normalization": ""}, "normalization"),
        ({"failure_condition": ""}, "failure"),
        ({"confidence": "Low"}, "confidence"),
        ({"eps": -1}, "Positive"),
        ({"eps": float("nan")}, "finite"),
        ({"bear_multiple": -2}, "multiples"),
        ({"bear_growth": 0.50}, "ordered"),
        ({"holding_value": 10000}, "headroom"),
        ({"currency": "EUR"}, "currency"),
    ],
)
def test_unreliable_or_full_positions_never_allocate(business, policy, change, reason):
    result = run(replace(business, **change), policy)
    assert not result.eligible
    assert result.allocation == 0
    assert any(reason.lower() in message.lower() for message in result.reasons)


@pytest.mark.parametrize(
    "data,reason",
    [
        (quote(0), "price"),
        (quote(float("inf")), "price"),
        (quote(regularMarketTime=None), "timestamp"),
        (quote(regularMarketTime=(NOW - timedelta(days=5)).timestamp()), "timestamp"),
        (quote(regularMarketTime=(NOW + timedelta(seconds=1)).timestamp()), "timestamp"),
        (quote(currency="TWD"), "currency"),
        ({**quote(), "error": {"message": "429"}}, "failed"),
        ({**quote(), "key_stats": {"mostRecentQuarter": "2026-10-31"}}, "newer"),
        ({**quote(), "demo": True}, "Demo"),
    ],
)
def test_bad_or_outdated_provider_data_blocks(business, policy, data, reason):
    result = run(business, policy, data)
    assert not result.eligible
    assert any(reason.lower() in message.lower() for message in result.reasons)


def test_friday_quote_works_on_sunday_and_timestamp_formats(business, policy):
    assert run(business, policy, quote(regularMarketTime=(NOW - timedelta(days=2)).timestamp())).eligible
    assert parse_timestamp(NOW) == NOW
    assert parse_timestamp("2026-11-08 18:00:00") == NOW


def test_portfolio_and_cash_hurdle_gates(business, policy):
    assert not run(business, replace(policy, holdings_as_of="2026-09-01")).eligible
    assert not run(business, replace(policy, portfolio_value=0)).eligible
    assert not run(business, replace(policy, cash_yield=0.50, cash_spread=0.50)).eligible
    assert not run(business, replace(policy, available_cash=110000)).eligible


def purchase(review="2026-11-01", period="2026-09-30", amount=5000):
    return {
        "ticker": "TEST",
        "amount": amount,
        "reviewed_on": review,
        "financial_period": period,
        "recorded_on": review,
    }


def test_one_tranche_per_review_not_per_rerun(business, policy):
    history = [purchase(review=business.reviewed_on)]
    for _ in range(2):
        result = run(business, policy, purchases=history)
        assert not result.eligible
        assert any("already recorded" in s for s in result.reasons)
    assert len(history) == 1


def test_progressive_gates_and_fourth_report_confirmation(business, policy):
    # Conservative value is ~124; 100 clears 15%, but not 25%.
    assert run(business, policy, quote(100)).eligible
    assert not run(business, policy, quote(100), [purchase()]).eligible
    history = [purchase(review=f"2026-11-0{i}") for i in range(1, 4)]
    fourth = run(business, policy, quote(70), history)
    assert not fourth.eligible
    assert any("subsequent" in s for s in fourth.reasons)
    confirmed = run(replace(business, financial_period="2026-10-31"), policy, quote(70), history)
    assert confirmed.eligible
    assert confirmed.allocation == 5000
    assert not run(business, policy, quote(50), history + [purchase(review="2026-11-04")]).eligible


def test_remaining_cap_limits_final_tranche(business, policy):
    result = run(business, policy, purchases=[purchase(amount=19000)])
    assert result.allocation == 1000


def test_missing_assumptions_stay_visible_without_rank(policy):
    results, retained = deployment(["UNKNOWN", "UNKNOWN"], {}, {}, policy, [], NOW)
    assert len(results) == 1
    assert results[0].rank is None
    assert retained == 5000


def test_conversation_seeds_cannot_allocate_until_reviewed(policy):
    seeds = conversation_seeds()
    results, retained = deployment(list(seeds), seeds, {t: quote(10) for t in seeds}, policy, [], NOW)
    assert all(not r.eligible for r in results)
    assert retained == 5000


@pytest.mark.parametrize(
    "change", [{"requested": -1}, {"requested": float("nan")}, {"max_businesses": 0}, {"review_days": 100}]
)
def test_invalid_policy_rejected(policy, change):
    with pytest.raises(ValueError):
        deployment([], {}, {}, replace(policy, **change), [], NOW)
