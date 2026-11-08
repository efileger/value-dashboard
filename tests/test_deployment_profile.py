import json

import pytest

from stock_dashboard.deployment_profile import (
    configured_path,
    decode_profile,
    encode_profile,
    new_profile,
    save_profile,
)


def test_round_trip_and_atomic_private_save(tmp_path, monkeypatch):
    monkeypatch.delenv("VALUATION_PROFILE_PATH", raising=False)
    assert configured_path() is None
    profile = new_profile()
    path = tmp_path / "private" / "deployment-profile.json"
    save_profile(profile, path)
    assert decode_profile(path.read_text()) == profile
    assert decode_profile(encode_profile(profile)) == profile
    monkeypatch.setenv("VALUATION_PROFILE_PATH", str(path))
    assert configured_path() == path
    assert path.stat().st_mode & 0o077 == 0


@pytest.mark.parametrize("raw", ["null", "[]", "{", '{"version": 99}', '{"version": 1}'])
def test_invalid_profiles_rejected(raw):
    with pytest.raises(ValueError):
        decode_profile(raw)


@pytest.mark.parametrize(
    "field,value",
    [
        ("eps", float("nan")),
        ("years", 100),
        ("units_verified", "yes"),
        ("source", []),
        ("bear_growth", 2),
        ("confidence", "Certain"),
    ],
)
def test_bad_assumptions_rejected(field, value):
    profile = new_profile()
    profile["assumptions"]["PEP"][field] = value
    with pytest.raises(ValueError):
        decode_profile(json.dumps(profile))


def test_invalid_purchase_records_rejected():
    profile = new_profile()
    profile["purchases"] = [{"ticker": "PEP", "amount": -1}]
    with pytest.raises(ValueError):
        decode_profile(encode_profile(profile))
    profile["purchases"] = [{"ticker": "PEP", "amount": 100, "recorded_on": "bad"}]
    with pytest.raises(ValueError):
        decode_profile(encode_profile(profile))


def test_profile_keeps_execution_history():
    profile = new_profile()
    profile["purchases"].append(
        {
            "ticker": "PEP",
            "amount": 1000,
            "recorded_on": "2026-11-08",
            "reviewed_on": "2026-11-07",
            "financial_period": "2026-09-30",
        }
    )
    assert decode_profile(encode_profile(profile))["purchases"] == profile["purchases"]
