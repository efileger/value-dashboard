"""Automatic, explainable ranking of reported fundamentals; no analyst approvals."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

from .metrics import compute_metrics, thresholds
from .valuation import number, parse_timestamp

GROUPS = {
    "Valuation": ["P/E Ratio", "P/B Ratio", "P/S Ratio", "EV / EBITDA", "PEG Ratio"],
    "Profitability": [
        "Net Profit Margin (%)",
        "ROE (%)",
        "Operating Margin (%)",
        "EBITDA Margin (%)",
        "Return on Assets (%)",
    ],
    "Growth": ["Reported Sales Growth (%)", "Reported EPS Growth (%)"],
    "Balance sheet": ["Current Ratio", "Quick Ratio", "Debt/Equity"],
    "Cash generation": ["Free Cash Flow", "Cash Flow/Share", "Buybacks"],
    "Income / ownership": ["Dividend Yield (%)", "Insider Ownership (%)"],
}
DEFAULT_WEIGHTS = {
    "Valuation": 35.0,
    "Profitability": 25.0,
    "Growth": 15.0,
    "Balance sheet": 15.0,
    "Cash generation": 10.0,
    "Income / ownership": 0.0,
}
LOWER = {"P/E Ratio", "P/B Ratio", "P/S Ratio", "EV / EBITDA", "PEG Ratio", "Debt/Equity"}


def metric_score(metric: str, raw: Any) -> float | None:
    if metric == "Buybacks":
        return 100.0 if raw is True else 0.0 if raw is False else None
    value = number(raw)
    if value is None:
        return None
    if "%" in metric:
        value *= 100
    target = thresholds[metric]
    if metric in LOWER:
        if value <= 0:
            return 100.0 if metric == "Debt/Equity" and value == 0 else 0.0
        return min(100.0, 50.0 * target / value)
    if target == 0:
        return 100.0 if value > 0 else 0.0
    return max(0.0, min(100.0, 50.0 * value / target))


def assess_watchlist(
    sections: dict[str, dict[str, Any]],
    weights: dict[str, float] | None = None,
    budget: float = 5000.0,
    max_businesses: int = 1,
    minimum_score: float = 60.0,
    minimum_coverage: float = 0.70,
    now: datetime | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    weights = weights if weights is not None else DEFAULT_WEIGHTS
    if (
        set(weights) != set(GROUPS)
        or any(number(w) is None or w < 0 for w in weights.values())
        or sum(weights.values()) <= 0
    ):
        raise ValueError("Choose finite nonnegative category weights with at least one positive weight")
    if number(budget) is None or budget < 0 or type(max_businesses) is not int or max_businesses < 1:
        raise ValueError("Budget must be nonnegative and business count positive")
    if (
        number(minimum_score) is None
        or not 0 <= minimum_score <= 100
        or number(minimum_coverage) is None
        or not 0 <= minimum_coverage <= 1
    ):
        raise ValueError("Score and coverage limits are outside their valid ranges")
    now = now or datetime.now(timezone.utc)
    total = sum(weights.values())
    rows: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    for ticker, data in sections.items():
        try:
            metrics = compute_metrics(ticker, data)
        except ValueError:
            metrics = {}
        points, available = 0.0, 0.0
        valuation_points = 0.0
        strengths: list[str] = []
        weaknesses: list[str] = []
        missing: list[str] = []
        for group, names in GROUPS.items():
            weight = weights[group] / len(names)
            for name in names:
                raw = metrics.get(name)
                score = metric_score(name, raw)
                clean = number(raw)
                display = raw if isinstance(raw, bool) else clean * 100 if clean is not None and "%" in name else clean
                contribution = (score or 0.0) * weight / total
                evidence.append(
                    {
                        "Ticker": ticker,
                        "Category": group,
                        "Metric": name,
                        "Reported value": display,
                        "Reference threshold": thresholds[name],
                        "Weight %": round(weight / total * 100, 2),
                        "Metric score": score,
                        "Points": round(contribution, 2),
                        "Available": score is not None,
                    }
                )
                if group == "Valuation":
                    valuation_points += (score or 0.0) / len(names)
                if weight == 0:
                    continue
                if score is None:
                    missing.append(name)
                else:
                    available += weight
                    points += contribution
                    (strengths if score >= 50 else weaknesses).append(name)
        coverage = available / total
        price = data.get("price") or {}
        quote = number(price.get("regularMarketPrice"))
        timestamp = parse_timestamp(price.get("regularMarketTime"))
        blockers = []
        if available == 0:
            blockers.append("No scored financial metrics available")
        if coverage + 1e-10 < minimum_coverage:
            blockers.append("Insufficient provider-data coverage")
        if weights["Valuation"] > 0 and valuation_points + 1e-10 < 50:
            blockers.append("Valuation metrics below reference thresholds")
        if points + 1e-10 < minimum_score:
            blockers.append("Below automatic score threshold")
        if data.get("error"):
            blockers.append("Provider request error / cooldown")
        if quote is None or quote <= 0 or price.get("currency") != "USD":
            blockers.append("Missing valid USD quote")
        if timestamp is None or not timedelta(0) <= now - timestamp <= timedelta(days=4):
            blockers.append("Quote timestamp missing, stale or future")
        quarter = parse_timestamp((data.get("key_stats") or {}).get("mostRecentQuarter"))
        if quarter is not None and not timedelta(0) <= now - quarter <= timedelta(days=200):
            blockers.append("Reported financial period is stale or future")
        if data.get("demo"):
            blockers.append("Demo data")
        rows.append(
            {
                "Rank": None,
                "Ticker": ticker,
                "Score": round(points, 2) if available else None,
                "Data coverage %": round(coverage * 100, 1),
                "Valuation score": round(valuation_points, 2),
                "Price USD": quote,
                "Quote as of": timestamp.isoformat() if timestamp else "Unknown",
                "Reported financial period": quarter.date().isoformat() if quarter else "Not supplied",
                "Provider error": bool(data.get("error")),
                "Cache": "Full"
                if (data.get("cache_info") or {}).get("served_from_cache")
                else "Partial"
                if (data.get("cache_info") or {}).get("sections_cached")
                else "None",
                "Suggested USD": 0.0,
                "Status": "Qualifies" if not blockers else "Review / wait",
                "Strengths": "; ".join(strengths),
                "Weaknesses": "; ".join(weaknesses),
                "Missing provider metrics": "; ".join(missing),
                "Purchase blockers": "; ".join(blockers),
                "_score": points,
                "_coverage": coverage,
            }
        )
    rows.sort(key=lambda r: (r["Score"] is None, -r["_score"], -r["_coverage"], r["Ticker"]))
    rank = 0
    for row in rows:
        if row["Score"] is not None:
            rank += 1
            row["Rank"] = rank
        del row["_score"], row["_coverage"]
    selected = [r for r in rows if r["Status"] == "Qualifies"][:max_businesses]
    # Equal caps across the chosen top N; allocate cents deterministically.
    cents = math.floor(budget * 100 + 1e-8)
    for index, row in enumerate(selected):
        row["Suggested USD"] = (cents // len(selected) + (index < cents % len(selected))) / 100
    return rows, evidence
