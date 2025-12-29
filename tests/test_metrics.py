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
