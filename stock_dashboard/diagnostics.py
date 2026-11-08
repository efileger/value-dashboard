"""Small, allowlisted diagnostic snapshots: no API calls or raw provider payloads."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from .valuation import Assessment, Assumptions, number, parse_date, parse_timestamp

PROVIDER_FIELDS = {
    "price": ("regularMarketPrice", "regularMarketTime", "currency"),
    "key_stats": ("trailingEps", "mostRecentQuarter"),
    "financial_data": ("financialCurrency",),
}
SECTIONS = ("price", "key_stats", "financial_data", "summary_detail", "asset_profile", "quote_type")


def build_report(
    tickers: list[str],
    sections: dict[str, dict[str, Any]],
    assumptions: dict[str, Assumptions],
    results: list[Assessment],
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    modeled = {r.ticker for r in results if r.bear_value is not None}
    rows: list[dict[str, Any]] = []
    for ticker in dict.fromkeys(tickers):
        data = sections.get(ticker, {})
        price = data.get("price") or {}
        stats = data.get("key_stats") or {}
        error = data.get("error") or {}
        limit = error.get("rate_limit")
        status = error.get("status_code") or getattr(limit, "status_code", None)
        if limit or status == 429:
            state = "Throttled / cooldown"
        elif status in (401, 403):
            state = "Authentication / access failure"
        elif error:
            state = "Provider request failed"
        else:
            state = "Data received" if any(data.get(k) for k in SECTIONS) else "No data received"
        quote = number(price.get("regularMarketPrice"))
        has_quote = quote is not None and quote > 0
        quote_time = parse_timestamp(price.get("regularMarketTime"))
        fresh = quote_time is not None and timedelta(0) <= now - quote_time <= timedelta(days=4)
        a = assumptions.get(ticker)
        pending = []
        if not a:
            pending.append("Business case not configured")
        else:
            if number(a.eps) is None or a.eps <= 0:
                pending.append("Normalized EPS")
            if parse_date(a.reviewed_on) is None:
                pending.append("Business review date")
            if parse_date(a.financial_period) is None:
                pending.append("Financial period reviewed")
            if not a.thesis_intact:
                pending.append("Thesis confirmation")
            if not a.units_verified:
                pending.append("Currency / ADR / earnings verification")
            if a.confidence == "Low":
                pending.append("Valuation confidence")
        missing = [
            f"{section}.{field}"
            for section, fields in PROVIDER_FIELDS.items()
            for field in fields
            if (data.get(section) or {}).get(field) is None
        ]
        cached = data.get("cache_info") or {}
        receipts = {
            k: parsed.isoformat()
            for k in SECTIONS
            if (parsed := parse_timestamp(cached.get("section_fetched_at", {}).get(k))) is not None
        }
        rows.append(
            {
                "Ticker": ticker,
                "Provider status": state,
                "HTTP status": status if isinstance(status, int) else None,
                "Quote available": has_quote,
                "Quote freshness": "Fresh" if fresh else "Missing / stale / future",
                "Quote as of": quote_time.isoformat() if quote_time else "Unknown",
                "Reported EPS": number(stats.get("trailingEps")),
                "Normalized EPS entered": bool(a and number(a.eps) is not None and a.eps > 0),
                "Scenario calculated": ticker in modeled,
                "Business review needed": "; ".join(pending) or "Required inputs entered; see purchase blockers",
                "Missing provider fields": "; ".join(missing) or "None",
                "Missing provider sections": "; ".join(k for k in SECTIONS if not data.get(k)) or "None",
                "Cache": "Full"
                if cached.get("served_from_cache")
                else "Partial"
                if cached.get("sections_cached")
                else "None",
                "Section receipt times": receipts,
            }
        )
    return {
        "generated_at": now.isoformat(),
        "provider": "Yahoo Finance",
        "rows": rows,
        "summary": {
            "tickers": len(rows),
            "quotes_available": sum(r["Quote available"] for r in rows),
            "provider_errors": sum(bool(sections.get(r["Ticker"], {}).get("error")) for r in rows),
            "scenarios_calculated": sum(r["Scenario calculated"] for r in rows),
            "normalized_eps_entered": sum(r["Normalized EPS entered"] for r in rows),
        },
    }
