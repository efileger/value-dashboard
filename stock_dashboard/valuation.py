"""Explicit scenario valuation and valuation-gated cash deployment.

Yahoo facts never imply reviewed assumptions. All monetary inputs are in the
listed security's quote currency and per listed share (per ADR where relevant).
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

import numpy_financial as npf


def number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def parse_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return None


def parse_timestamp(value: Any) -> datetime | None:
    try:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, timezone.utc)
        if isinstance(value, str):
            result = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return result if result.tzinfo else result.replace(tzinfo=timezone.utc)
    except (ValueError, OverflowError, OSError):
        pass
    return None


@dataclass
class Assumptions:
    eps: float = 0.0
    dividend: float = 0.0
    bear_growth: float = 0.0
    base_growth: float = 0.05
    bull_growth: float = 0.10
    bear_multiple: float = 15.0
    base_multiple: float = 20.0
    bull_multiple: float = 25.0
    hurdle: float = 0.10
    years: int = 5
    reviewed_on: str = ""
    financial_period: str = ""
    source: str = ""
    normalization: str = ""
    failure_condition: str = ""
    confidence: str = "Low"
    thesis_intact: bool = False
    units_verified: bool = False
    currency: str = "USD"
    holding_value: float = 0.0
    max_weight: float = 0.10
    addition_cap: float = 0.0


@dataclass
class Policy:
    requested: float = 5000.0
    available_cash: float = 35000.0
    protected_reserve: float = 0.0
    portfolio_value: float = 0.0
    holdings_as_of: str = ""
    account: str = "Taxable"
    max_businesses: int = 1
    review_days: int = 95
    cash_yield: float = 0.0383
    cash_spread: float = 0.04
    plan_started_on: str = ""


@dataclass
class Assessment:
    ticker: str
    price: float | None = None
    quote_as_of: str = ""
    reviewed_on: str = ""
    review_due: str = ""
    financial_period: str = ""
    bear_value: float | None = None
    base_value: float | None = None
    bull_value: float | None = None
    discount: float | None = None
    bear_return: float | None = None
    base_return: float | None = None
    bull_return: float | None = None
    entry_price: float | None = None
    headroom: float = 0.0
    tranche_limit: float = 0.0
    confidence: str = "Low"
    reasons: list[str] = field(default_factory=list)
    allocation: float = 0.0
    rank: int | None = None

    @property
    def eligible(self) -> bool:
        return not self.reasons


def validate_assumptions(a: Assumptions) -> list[str]:
    errors = []
    numeric = (
        a.eps,
        a.dividend,
        a.bear_growth,
        a.base_growth,
        a.bull_growth,
        a.bear_multiple,
        a.base_multiple,
        a.bull_multiple,
        a.hurdle,
        a.holding_value,
        a.max_weight,
        a.addition_cap,
    )
    if any(number(v) is None for v in numeric):
        return ["Assumptions must contain finite numbers"]
    if a.eps <= 0 or a.dividend < 0:
        errors.append("Positive normalized EPS and nonnegative dividend required")
    if not isinstance(a.years, int) or isinstance(a.years, bool) or not 1 <= a.years <= 20:
        errors.append("Holding period must be 1–20 whole years")
    if not -0.9 <= a.bear_growth <= a.base_growth <= a.bull_growth <= 1.0:
        errors.append("Growth scenarios must be ordered bear ≤ base ≤ bull, between -90% and 100%")
    if not 0 < a.bear_multiple <= a.base_multiple <= a.bull_multiple <= 100:
        errors.append("Exit multiples must be positive and ordered bear ≤ base ≤ bull (max 100)")
    if not 0 < a.hurdle <= 1:
        errors.append("Return hurdle must be above 0% and at most 100%")
    if a.holding_value < 0 or not 0 < a.max_weight <= 1 or a.addition_cap < 0:
        errors.append("Position, maximum weight or addition cap invalid")
    if a.confidence not in {"Low", "Medium", "High"}:
        errors.append("Confidence must be Low, Medium or High")
    return errors


def validate_policy(p: Policy) -> None:
    for value in (p.requested, p.available_cash, p.protected_reserve, p.portfolio_value, p.cash_yield, p.cash_spread):
        if number(value) is None or value < 0:
            raise ValueError("Budget, portfolio and cash rates must be finite and nonnegative")
    if type(p.max_businesses) is not int or not 1 <= p.max_businesses <= 100:
        raise ValueError("Select between 1 and 100 businesses")
    if type(p.review_days) is not int or not 1 <= p.review_days <= 95:
        raise ValueError("Business review interval must be between 1 and 95 days")


def scenario(a: Assumptions, growth: float, multiple: float, price: float) -> tuple[float, float]:
    terminal = a.eps * (1 + growth) ** a.years * multiple
    flows = [a.dividend] * a.years
    flows[-1] += terminal
    value = float(npf.npv(a.hurdle, [0.0, *flows]))
    annual_return = float(npf.irr([-price, *flows]))
    if not math.isfinite(value) or not math.isfinite(annual_return):
        raise ValueError("Scenario does not produce a finite value and annual return")
    return value, annual_return


def assess(
    ticker: str,
    a: Assumptions | None,
    sections: dict[str, Any],
    p: Policy,
    purchases: list[dict[str, Any]],
    now: datetime | None = None,
) -> Assessment:
    now = now or datetime.now(timezone.utc)
    today = now.date()
    r = Assessment(ticker=ticker)
    if sections.get("demo"):
        r.reasons.append("Demo data cannot qualify for cash deployment")
    price_data = sections.get("price") or {}
    r.price = number(price_data.get("regularMarketPrice"))
    quote_time = parse_timestamp(price_data.get("regularMarketTime"))
    r.quote_as_of = quote_time.isoformat() if quote_time else "Unknown"
    if r.price is None or r.price <= 0:
        r.reasons.append("Missing valid market price")
    if quote_time is None or not timedelta(0) <= now - quote_time <= timedelta(days=4):
        r.reasons.append("Quote timestamp missing, future or older than 4 days")
    if sections.get("error"):
        r.reasons.append("Market data request failed; refresh before buying")
    if not a:
        r.reasons.append("Business valuation not configured")
        return r
    r.reviewed_on, r.financial_period, r.confidence = a.reviewed_on, a.financial_period, a.confidence
    reviewed = parse_date(a.reviewed_on)
    period = parse_date(a.financial_period)
    r.review_due = (reviewed + timedelta(days=p.review_days)).isoformat() if reviewed else "Unknown"
    if reviewed is None or not 0 <= (today - reviewed).days < p.review_days:
        r.reasons.append("Business review missing, future or due; update quarterly")
    if period is None or period > today or (reviewed and period > reviewed):
        r.reasons.append("Financial period missing or inconsistent with review date")
    elif (today - period).days > 200:
        r.reasons.append("Financial period is older than 200 days; review current reports")
    latest_period = parse_timestamp((sections.get("key_stats") or {}).get("mostRecentQuarter"))
    if latest_period and period and latest_period.date() > period:
        r.reasons.append("A newer financial quarter is available; revise the business case")
    if not a.source.strip() or not a.normalization.strip() or not a.failure_condition.strip():
        r.reasons.append("Record source, normalization rationale and thesis failure condition")
    if not a.thesis_intact:
        r.reasons.append("Thesis has not been confirmed intact")
    if not a.units_verified:
        r.reasons.append("Verify currency, per-share/ADR units and normalized earnings")
    if not price_data.get("currency") or price_data.get("currency") != a.currency:
        r.reasons.append("Quote currency missing or differs from valuation currency")
    if a.currency != "USD":
        r.reasons.append("USD deployment requires a USD quote; FX conversion is not configured")
    if a.confidence == "Low":
        r.reasons.append("Low confidence: research before allocating")
    errors = validate_assumptions(a)
    r.reasons.extend(errors)
    if errors:
        return r
    # A valid price is needed for IRR, but scenario values remain useful without a quote.
    scenario_price = r.price if r.price is not None and r.price > 0 else 1.0
    try:
        r.bear_value, bear_return = scenario(a, a.bear_growth, a.bear_multiple, scenario_price)
        r.base_value, base_return = scenario(a, a.base_growth, a.base_multiple, scenario_price)
        r.bull_value, bull_return = scenario(a, a.bull_growth, a.bull_multiple, scenario_price)
    except ValueError as exc:
        r.reasons.append(str(exc))
        return r
    if r.price is not None and r.price > 0:
        r.bear_return, r.base_return, r.bull_return = bear_return, base_return, bull_return
        # Conservative bear value, never the optimistic bull scenario, sets the buy gate.
        r.discount = 1 - r.price / r.bear_value
    history = [item for item in purchases if item["ticker"] == ticker]
    stage = len(history)
    gate = (0.15, 0.25, 0.35, 0.15)[min(stage, 3)]
    r.entry_price = r.bear_value * (1 - gate)
    if r.discount is None or r.discount + 1e-10 < gate:
        r.reasons.append(f"Needs {gate:.0%} discount to conservative value")
    if r.bear_return is None or r.bear_return + 1e-10 < max(a.hurdle, p.cash_yield + p.cash_spread):
        r.reasons.append("Conservative annual return below equity/cash hurdle")
    if stage >= 4:
        r.reasons.append("Four-tranche addition complete; start a new plan deliberately")
    if any(item["reviewed_on"] == a.reviewed_on for item in history):
        r.reasons.append("A tranche was already recorded for this business review")
    if stage == 3 and period:
        first_period = parse_date(history[0]["financial_period"])
        if first_period is None or period <= first_period:
            r.reasons.append("Fourth tranche needs confirmation from a subsequent financial report")
    holdings_date = parse_date(p.holdings_as_of)
    if holdings_date is None or not 0 <= (today - holdings_date).days <= 30:
        r.reasons.append("Update portfolio snapshot (must be within 30 days)")
    if p.portfolio_value <= 0 or a.holding_value > p.portfolio_value:
        r.reasons.append("Portfolio value missing or smaller than this position")
    r.headroom = max(0.0, p.portfolio_value * a.max_weight - a.holding_value)
    spent = sum(item["amount"] for item in history)
    r.tranche_limit = max(0.0, min(a.addition_cap / 4, a.addition_cap - spent, r.headroom))
    if r.tranche_limit < 0.01:
        r.reasons.append("No portfolio headroom or remaining addition budget")
    return r


def deployment(
    tickers: list[str],
    assumptions: dict[str, Assumptions],
    sections: dict[str, dict[str, Any]],
    policy: Policy,
    purchases: list[dict[str, Any]],
    now: datetime | None = None,
) -> tuple[list[Assessment], float]:
    validate_policy(policy)
    results = [
        assess(t, assumptions.get(t), sections.get(t, {}), policy, purchases, now) for t in dict.fromkeys(tickers)
    ]
    if sum(a.holding_value for a in assumptions.values()) + policy.available_cash > policy.portfolio_value:
        for result in results:
            result.reasons.append("Entered positions plus cash exceed the portfolio value")

    # Lexicographic ordering avoids an opaque composite score. Unknowns remain unranked.
    def order(r: Assessment) -> tuple:
        return (
            -(r.bear_return if r.bear_return is not None else -math.inf),
            -(r.discount if r.discount is not None else -math.inf),
            -{"High": 2, "Medium": 1, "Low": 0}.get(r.confidence, 0),
            -r.headroom,
            r.ticker,
        )

    qualified = sorted((r for r in results if r.eligible), key=order)
    remaining = min(policy.requested, max(0.0, policy.available_cash - policy.protected_reserve))
    remaining = math.floor(remaining * 100 + 1e-8) / 100
    for rank, result in enumerate(qualified, 1):
        result.rank = rank
        if rank <= policy.max_businesses:
            result.allocation = math.floor(min(remaining, result.tranche_limit) * 100 + 1e-8) / 100
            remaining = round(remaining - result.allocation, 2)
    blocked = sorted((r for r in results if not r.eligible), key=order)
    retained = round(policy.requested - sum(r.allocation for r in qualified), 2)
    return [*qualified, *blocked], retained


def conversation_seeds() -> dict[str, Assumptions]:
    """Unverified working examples from the supplied conversation, never live facts."""
    result = {}
    for ticker, eps, dividend, low, high, pe, hurdle, cap in (
        ("PEP", 8.38, 5.92, 0.03, 0.05, 18, 0.10, 7500),
        ("MSFT", 17.75, 3.92, 0.10, 0.15, 25, 0.10, 10000),
        ("TSM", 15.0, 4.32, 0.10, 0.15, 20, 0.12, 10000),
    ):
        result[ticker] = Assumptions(
            eps=eps,
            dividend=dividend,
            bear_growth=low,
            base_growth=(low + high) / 2,
            bull_growth=high,
            bear_multiple=float(pe),
            base_multiple=float(pe),
            bull_multiple=float(pe),
            hurdle=hurdle,
            addition_cap=float(cap),
            source="User-supplied conversation, November 2026; working scenario, unverified",
            normalization="Conversation working EPS; reconcile latest filings before approval",
        )
    context = {
        "PEP": (
            "Use recurring core EPS and realistic recovery growth, not a prior price high.",
            "Results no longer support the modeled recurring earnings recovery.",
        ),
        "MSFT": (
            "Reconcile investment gains and test cash returns on infrastructure spending.",
            "Infrastructure investment fails to support modeled earnings and cash returns.",
        ),
        "TSM": (
            (
                "Normalize semiconductor cycle, investment gains and insurance; reconcile TWD/USD "
                "and five ordinary shares per US ADR; reflect geographic risk in hurdle."
            ),
            "Cycle, margins or geographic risk invalidate normalized ADR earnings.",
        ),
        "ADYEY": (
            (
                "Reconcile EUR/USD, ADR units, acquisition spending and merchant-settlement cash; "
                "do not subtract the entire displayed cash balance from enterprise value."
            ),
            "Growth or cash available to shareholders no longer supports the thesis.",
        ),
        "T": (
            "Reconcile company-defined FCF and debt; evaluate existing portfolio exposure.",
            "Debt service or capital needs undermine sustainable shareholder cash generation.",
        ),
        "QCOM": (
            (
                "Remove the reported one-off tax benefit; rebuild normalized earnings and FCF "
                "after deterioration in cash generation."
            ),
            "Updated operating earnings and cash flow fail to support normalized EPS.",
        ),
        "AMZN": (
            (
                "Model future returns from infrastructure capex; negative reported FCF does not "
                "establish normalized cash generation."
            ),
            "Investment spending fails to earn the modeled return.",
        ),
        "NVDA": (
            "Reconcile earnings with operating cash conversion, receivables and extended terms.",
            "Cash collections or demand fail to support modeled earnings.",
        ),
        "GOOGL": (
            (
                "Normalize investment gains/losses and exceptional items; test capex returns; "
                "refresh household concentration before additions."
            ),
            "Investment returns and recurring cash generation fail to support growth.",
        ),
        "META": (
            (
                "Normalize exceptional charges; test cash conversion and returns from capex; "
                "refresh household concentration."
            ),
            "Capex and recurring operating economics invalidate modeled cash returns.",
        ),
        "AAPL": (
            "Test growth needed to justify current valuation and existing portfolio concentration.",
            "Recurring earnings growth falls below the modeled business case.",
        ),
        "KO": (
            "Test growth and cash generation at today's valuation; dividends alone are not a bonus.",
            "Cash generation and growth fail to support the modeled valuation.",
        ),
        "WDC": (
            (
                "Normalize across the storage cycle, remove Sandisk-related gains and refresh "
                "existing portfolio concentration."
            ),
            "Normalized cycle earnings and cash conversion fail to support the thesis.",
        ),
    }
    for ticker, (note, failure) in context.items():
        a = result.setdefault(
            ticker, Assumptions(source="User-supplied conversation, November 2026; unverified research notes")
        )
        a.normalization += (". " if a.normalization else "") + note
        a.failure_condition = failure
    return result


def to_dict(result: Assessment) -> dict[str, Any]:
    return {**asdict(result), "eligible": result.eligible}
