import importlib


EXPECTED_ATTRIBUTES = [
    "data_access",
    "metrics",
    "ui",
    "main",
]


def test_package_exports_expected_members():
    module = importlib.import_module("stock_dashboard")

    for attr in EXPECTED_ATTRIBUTES:
        assert hasattr(module, attr), f"Missing attribute: {attr}"

    assert callable(module.main)
