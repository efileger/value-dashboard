from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd
from yahooquery import Ticker

DEFAULT_WATCHLIST_PATH = Path(__file__).resolve().parent.parent / "watchlist.txt"
DEFAULT_TICKERS_FALLBACK = "AAPL,MSFT,META"


def validate_tickers(
    tickers: Iterable[str], ticker_cls: type[Ticker] = Ticker
) -> list[str]:
    """Return a list of valid, uppercase ticker symbols.

    The function asks Yahoo Finance for quote metadata to filter out unknown
    tickers and to surface canonical symbols when they differ from user input.
    """

    normalized: list[str] = []
    seen_inputs: set[str] = set()
    for ticker in tickers:
        if not ticker:
            continue
        ticker_upper = ticker.upper()
        if ticker_upper not in seen_inputs:
            normalized.append(ticker_upper)
            seen_inputs.add(ticker_upper)

    if not normalized:
        return []

    try:
        ticker_client = ticker_cls(normalized)
        quote_type_section = getattr(ticker_client, "quote_type", {})
        symbols_attr = getattr(ticker_client, "symbols", [])
    except Exception:
        return normalized

    available_symbols: list[str] = []
    if isinstance(symbols_attr, Iterable) and not isinstance(symbols_attr, (str, bytes)):
        available_symbols = [s.upper() for s in symbols_attr if isinstance(s, str)]

    validated: list[str] = []
    seen_validated: set[str] = set()

    def _add_symbol(symbol: str) -> None:
        symbol_upper = symbol.upper()
        if symbol_upper not in seen_validated:
            validated.append(symbol_upper)
            seen_validated.add(symbol_upper)

    for ticker in normalized:
        section = _safe_section(quote_type_section, ticker)
        if section:
            canonical = (
                section.get("symbol")
                or section.get("underlyingSymbol")
                or ticker
            )
            _add_symbol(canonical)
        elif ticker in available_symbols:
            _add_symbol(ticker)

    if available_symbols and len(validated) < len(available_symbols):
        for symbol in available_symbols:
            if symbol not in seen_validated and (
                symbol in normalized or not validated
            ):
                _add_symbol(symbol)

    return validated


def load_watchlist(path: Path | None = None) -> list[str]:
    """Load the default watchlist from disk.

    Returns
    -------
    list[str]
        A list of uppercase ticker symbols.
    """

    watchlist_path = path or DEFAULT_WATCHLIST_PATH

    try:
        content = watchlist_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []

    symbols = []
    for part in content.replace("\n", ",").split(","):
        symbol = part.strip()
        if symbol:
            symbols.append(symbol.upper())

    return validate_tickers(symbols)


def get_default_watchlist_string(path: Path | None = None) -> str:
    """Return the default comma-separated tickers for the UI input."""

    watchlist = load_watchlist(path)
    if watchlist:
        return ",".join(watchlist)

    return DEFAULT_TICKERS_FALLBACK


def _safe_section(section: Any, ticker: str) -> Mapping[str, Any]:
    """Return ticker-specific data when the yahooquery section is a mapping."""

    if isinstance(section, pd.DataFrame):
        if ticker in section.index:
            row = section.loc[ticker]
            if isinstance(row, pd.Series):
                return row.to_dict()
        return {}

    if isinstance(section, pd.Series):
        return section.to_dict() if section.name == ticker else {}

    if hasattr(section, "get"):
        value = section.get(ticker, {})
        return value if isinstance(value, dict) else {}

    return {}


def resolve_company_name(ticker: str, quote_type=None, price=None, profile=None) -> str:
    """Return the most descriptive company name available for the ticker.

    Fallback order: quote_type longName -> price longName -> price shortName
    -> profile longName -> ticker symbol.
    """

    quote_type = quote_type or {}
    price = price or {}
    profile = profile or {}

    return (
        quote_type.get("longName")
        or price.get("longName")
        or price.get("shortName")
        or profile.get("longName")
        or ticker
    )


def _detect_buybacks(ticker_client: Any, key_stats: Mapping[str, Any]) -> bool | None:
    """Return True when historical share counts indicate buybacks."""

    try:
        hist_data = ticker_client.history(period="5y")
        if not hist_data.empty and "close" in hist_data.columns:
            share_counts = key_stats.get("sharesOutstanding")
            if isinstance(share_counts, list) and len(share_counts) > 1:
                return share_counts[-1] < share_counts[0]
    except Exception:
        return None

    return None


def fetch_ticker_sections(ticker: str, ticker_cls: type[Ticker] = Ticker) -> dict[str, Mapping[str, Any]]:
    """Load all ticker sections used by the dashboard."""

    ticker_client = ticker_cls(ticker)
    summary = _safe_section(ticker_client.summary_detail, ticker)
    financial = _safe_section(ticker_client.financial_data, ticker)
    profile = _safe_section(ticker_client.asset_profile, ticker)
    key_stats = _safe_section(ticker_client.key_stats, ticker)
    quote_type = _safe_section(ticker_client.quote_type, ticker)
    price = _safe_section(ticker_client.price, ticker)

    buybacks = _detect_buybacks(ticker_client, key_stats)

    return {
        "summary_detail": summary,
        "financial_data": financial,
        "asset_profile": profile,
        "key_stats": key_stats,
        "quote_type": quote_type,
        "price": price,
        "buybacks": buybacks,
    }
