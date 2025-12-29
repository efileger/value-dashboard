"""Convenience exports for the stock dashboard package.

The module avoids eager submodule imports so a transient import failure does not
leave ``stock_dashboard.data_access`` or siblings missing from ``sys.modules``.
Heavy dependencies are imported lazily on first use, and any failures surface a
Streamlit-friendly error instead of an opaque ``KeyError``.
"""
import importlib
import sys
from types import ModuleType
from typing import Any

import pandas as pd
import streamlit as st
from yahooquery import Ticker


_LAZY_MODULES: dict[str, str] = {
    "data_access": "stock_dashboard.data_access",
    "metrics": "stock_dashboard.metrics",
    "ui": "stock_dashboard.ui",
}

_ATTR_TO_MODULE: dict[str, str] = {
    "DEFAULT_TICKERS_FALLBACK": "data_access",
    "DEFAULT_WATCHLIST_PATH": "data_access",
    "_safe_section": "data_access",
    "fetch_ticker_sections": "data_access",
    "get_default_watchlist_string": "data_access",
    "load_watchlist": "data_access",
    "RateLimitError": "data_access",
    "resolve_company_name": "data_access",
    "compute_metrics": "metrics",
    "ensure_data_available": "metrics",
    "format_billions": "metrics",
    "thresholds": "metrics",
    "tooltips": "metrics",
    "validate_metrics": "metrics",
    "display_stock": "ui",
    "main": "ui",
}

__all__ = [
    "DEFAULT_TICKERS_FALLBACK",
    "DEFAULT_WATCHLIST_PATH",
    "Ticker",
    "_safe_section",
    "compute_metrics",
    "data_access",
    "display_stock",
    "ensure_data_available",
    "fetch_ticker_sections",
    "format_billions",
    "get_default_watchlist_string",
    "load_watchlist",
    "main",
    "metrics",
    "pd",
    "RateLimitError",
    "resolve_company_name",
    "st",
    "thresholds",
    "tooltips",
    "ui",
    "validate_metrics",
]


def _handle_import_error(module_name: str, exc: Exception) -> RuntimeError:
    """Return a descriptive error while surfacing a Streamlit-friendly message."""

    message = (
        f"Unable to load stock_dashboard.{module_name}. "
        "Please refresh or try again later."
    )
    try:
        st.error(message)
    except Exception:
        # Streamlit is not available or configured; fall back to raising.
        pass
    return RuntimeError(f"{message}\nOriginal error: {exc!r}")


def _load_module(module_name: str) -> ModuleType:
    fq_name = _LAZY_MODULES[module_name]
    if fq_name in sys.modules:
        return sys.modules[fq_name]

    try:
        module = importlib.import_module(fq_name)
    except Exception as exc:  # noqa: BLE001 - propagate wrapped error
        raise _handle_import_error(module_name, exc) from exc

    sys.modules.setdefault(fq_name, module)
    return module


def _resolve_from_module(module_name: str, attr: str) -> Any:
    module = _load_module(module_name)
    try:
        return getattr(module, attr)
    except AttributeError as exc:
        raise _handle_import_error(module_name, exc) from exc


def __getattr__(name: str) -> Any:
    if name in _LAZY_MODULES:
        return _load_module(name)

    module_name = _ATTR_TO_MODULE.get(name)
    if module_name:
        return _resolve_from_module(module_name, name)

    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


# Provide module aliases in sys.modules to avoid KeyError lookups when a
# submodule import fails midway through startup. Modules will be populated on
# first access via ``__getattr__``.
for alias, fq_name in _LAZY_MODULES.items():
    sys.modules.setdefault(fq_name, sys.modules.get(f"{__name__}.{alias}"))
