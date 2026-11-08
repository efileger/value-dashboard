"""Portable, versioned personal assumptions; no shared server file by default."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any

from .valuation import (
    Assumptions,
    Policy,
    conversation_seeds,
    number,
    parse_date,
    validate_assumptions,
    validate_policy,
)


def new_profile() -> dict[str, Any]:
    return {
        "version": 1,
        "policy": asdict(Policy(plan_started_on=date.today().isoformat())),
        "assumptions": {t: asdict(a) for t, a in conversation_seeds().items()},
        "purchases": [],
        "archives": [],
    }


def decode_profile(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
        if not isinstance(value, dict) or value.get("version") != 1:
            raise ValueError("Unsupported deployment profile version")
        policy = Policy(**value["policy"])
        validate_policy(policy)
        assumptions = value["assumptions"]
        if not isinstance(assumptions, dict):
            raise TypeError("Assumptions must be keyed by ticker")
        for ticker, fields in assumptions.items():
            if not isinstance(ticker, str) or not ticker.strip():
                raise ValueError("Invalid ticker in profile")
            a = Assumptions(**fields)
            # Empty EPS is allowed for an unfinished draft, never for deployment.
            errors = validate_assumptions(a)
            if a.eps == 0:
                errors = [e for e in errors if not e.startswith("Positive normalized EPS")]
            if errors:
                raise ValueError("; ".join(errors))
            for text in (a.reviewed_on, a.financial_period, a.source, a.normalization, a.failure_condition, a.currency):
                if not isinstance(text, str):
                    raise TypeError("Assumption text fields must be strings")
            if not isinstance(a.thesis_intact, bool) or not isinstance(a.units_verified, bool):
                raise TypeError("Approval fields must be boolean")
        if any(not isinstance(v, str) for v in (policy.holdings_as_of, policy.account, policy.plan_started_on)):
            raise TypeError("Portfolio date and account must be text")
        purchases = value["purchases"]
        if not isinstance(value.get("archives", []), list):
            raise TypeError("Archived plans must be a list")
        if not isinstance(purchases, list):
            raise TypeError("Purchases must be a list")
        for purchase in purchases:
            if not isinstance(purchase, dict):
                raise TypeError("Invalid purchase record")
            if purchase["ticker"] not in assumptions:
                raise ValueError("Purchase ticker has no assumptions")
            amount = number(purchase["amount"])
            if amount is None or amount <= 0:
                raise ValueError("Recorded purchases need positive finite amounts")
            for key in ("recorded_on", "reviewed_on", "financial_period"):
                if parse_date(purchase[key]) is None:
                    raise ValueError("Recorded purchase dates must be ISO dates")
        return value
    except (TypeError, KeyError, AttributeError) as exc:
        raise ValueError(f"Invalid deployment profile: {exc}") from exc


def encode_profile(profile: dict[str, Any]) -> str:
    return json.dumps(profile, indent=2, allow_nan=False)


def configured_path() -> Path | None:
    configured = os.getenv("VALUATION_PROFILE_PATH")
    return Path(configured) if configured else None


def save_profile(profile: dict[str, Any], path: Path) -> None:
    """Atomic single-user save. Shared hosting should use browser import/export."""
    payload = encode_profile(profile)
    decode_profile(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".deployment-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(payload)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
