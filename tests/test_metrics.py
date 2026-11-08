import pytest

from stock_dashboard import metrics


def test_ensure_data_available_detects_missing_sections():
    sections = {
        "summary_detail": {},
        "financial_data": {},
        "asset_profile": {},
        "key_stats": {},
        "price": {},
    }

    with pytest.raises(ValueError) as exc:
        metrics.ensure_data_available("AAPL", sections, {"P/E Ratio": None})

    assert "missing sections" in str(exc.value)


def test_ensure_data_available_requires_metrics_and_critical_fields():
    sections = {
        "summary_detail": {"trailingPE": 20},
        "financial_data": {"totalRevenue": None, "totalDebt": None},
        "asset_profile": {"industry": "Tech"},
        "key_stats": {"marketCap": None},
        "price": {"shortName": "Test"},
    }
    test_metrics = {"P/E Ratio": 15.0, "Current Ratio": None}

    with pytest.raises(ValueError) as exc:
        metrics.ensure_data_available("AAPL", sections, test_metrics)

    assert "Missing required fields" in str(exc.value)


def test_ensure_data_available_detects_missing_metrics():
    sections = {
        "summary_detail": {"trailingPE": 20},
        "financial_data": {"totalRevenue": 1, "totalDebt": 1},
        "asset_profile": {"industry": "Tech"},
        "key_stats": {"marketCap": 10},
        "price": {"shortName": "Test"},
    }

    with pytest.raises(ValueError) as exc:
        metrics.ensure_data_available("AAPL", sections, {"P/E Ratio": None})

    assert "No metrics available" in str(exc.value)


@pytest.mark.parametrize(
    "market_cap_section, fallback_value",
    [
        ("price", {"price": {"marketCap": 1_500_000_000}}),
        ("summary_detail", {"summary_detail": {"marketCap": 2_250_000_000}}),
    ],
)
def test_ensure_data_available_accepts_market_cap_fallback(market_cap_section, fallback_value):
    base_sections = {
        "summary_detail": {"trailingPE": 21.0},
        "financial_data": {"totalRevenue": 10_000_000_000, "totalDebt": 5_000_000_000},
        "asset_profile": {"industry": "Tech"},
        "key_stats": {"marketCap": None},
        "price": {"shortName": "Test"},
    }
    base_sections[market_cap_section].update(fallback_value.get(market_cap_section, {}))

    warnings = metrics.ensure_data_available("AAPL", base_sections, {"P/E Ratio": 20.0})

    assert not warnings.get("missing_fields")


def test_correct_growth_labels_and_pb_module():
    computed = metrics.compute_metrics(
        "TEST",
        {
            "financial_data": {"revenueGrowth": 0.10, "earningsGrowth": 0.20},
            "key_stats": {"priceToBook": 3.5},
            "summary_detail": {"priceToBook": 9},
        },
    )
    assert computed["P/B Ratio"] == 3.5
    assert computed["Reported Sales Growth (%)"] == 0.10
    assert computed["Reported EPS Growth (%)"] == 0.20
    assert not any("4 Yr" in name for name in computed)


@pytest.mark.parametrize("financial_currency", [None, "TWD", "USD"])
def test_derived_per_share_fields_require_matching_known_currencies(financial_currency):
    computed = metrics.compute_metrics(
        "ADR",
        {
            "financial_data": {
                "financialCurrency": financial_currency,
                "operatingCashflow": 1000,
                "totalRevenue": 2000,
            },
            "price": {"currency": "USD"},
            "key_stats": {"sharesOutstanding": 10},
            "summary_detail": {"trailingPE": 20},
        },
    )
    assert computed["Cash Flow/Share"] == (100 if financial_currency == "USD" else None)
    assert computed["Sales/Share"] == (200 if financial_currency == "USD" else None)
