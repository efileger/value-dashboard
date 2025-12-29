import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urlparse

import pandas as pd
from yahooquery import Ticker

DEFAULT_WATCHLIST_PATH = Path(__file__).resolve().parent.parent / "watchlist.txt"
DEFAULT_TICKERS_FALLBACK = "AAPL,MSFT,META"
_DEFAULT_RATE_LIMIT_SECONDS = 60

logger = logging.getLogger(__name__)


@dataclass
class RateLimitError:
    status_code: int | None
    message: str
    retry_after: int | None
    headers: Mapping[str, Any]
    host: str | None = None
    payload: Any | None = None
    remaining: int | None = None


RATE_LIMIT_COOLDOWNS: dict[str, datetime] = {}


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def is_smoke_mode() -> bool:
    """Return True when the smoke-test fast path is enabled."""

    value = os.getenv("SMOKE_TEST", "")
    return str(value).lower() not in {"", "0", "false", "no"}


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

    if is_smoke_mode():
        return normalized

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


def _extract_host(response: Any) -> str | None:
    url = getattr(response, "url", None) or getattr(getattr(response, "request", None), "url", None)
    if not url:
        return None

    parsed = urlparse(url)
    return parsed.hostname


def _normalize_headers(headers: Any) -> Mapping[str, Any]:
    if isinstance(headers, Mapping):
        return dict(headers)

    return {}


def _parse_retry_after(headers: Mapping[str, Any], payload: Any = None) -> int | None:
    header_value = None
    for key, value in headers.items():
        if str(key).lower() == "retry-after":
            header_value = value
            break

    if header_value is not None:
        try:
            return int(str(header_value))
        except (TypeError, ValueError):
            try:
                parsed_date = datetime.fromisoformat(str(header_value))
                return max(0, int((parsed_date - _utcnow()).total_seconds()))
            except Exception:
                return None

    if isinstance(payload, Mapping):
        retry_after = payload.get("retry_after") or payload.get("retryAfter")
        if retry_after:
            try:
                return int(retry_after)
            except (TypeError, ValueError):
                return None

    return None


def _record_rate_limit(rate_limit_error: RateLimitError) -> None:
    retry_after = rate_limit_error.retry_after or _DEFAULT_RATE_LIMIT_SECONDS
    host = rate_limit_error.host or "yahoo_finance"
    resume_at = _utcnow() + timedelta(seconds=retry_after)
    RATE_LIMIT_COOLDOWNS[host] = resume_at
    rate_limit_error.remaining = retry_after
    logger.info(
        "Rate limit detected for host %s; retry after %ss", host, retry_after
    )


def _active_rate_limit() -> RateLimitError | None:
    if not RATE_LIMIT_COOLDOWNS:
        return None

    now = _utcnow()
    active_host = None
    active_resume_at: datetime | None = None

    for host, resume_at in RATE_LIMIT_COOLDOWNS.items():
        if resume_at > now and (active_resume_at is None or resume_at < active_resume_at):
            active_host = host
            active_resume_at = resume_at

    if active_host is None or active_resume_at is None:
        return None

    remaining_seconds = max(0, int((active_resume_at - now).total_seconds()))
    logger.info(
        "Skipping fetch due to active rate limit for %s; %ss remaining",
        active_host,
        remaining_seconds,
    )
    return RateLimitError(
        status_code=None,
        message="Rate limit active",
        retry_after=remaining_seconds,
        headers={},
        host=active_host,
        remaining=remaining_seconds,
    )


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

    if is_smoke_mode():
        return {
            "summary_detail": {
                "trailingPE": 15.0,
                "priceToBook": 2.1,
                "priceToSalesTrailing12Months": 4.2,
                "dividendYield": 0.012,
                "pegRatio": 1.3,
            },
            "financial_data": {
                "profitMargins": 0.22,
                "returnOnEquity": 0.17,
                "currentRatio": 2.1,
                "quickRatio": 1.6,
                "revenueGrowth": 0.07,
                "earningsGrowth": 0.06,
                "operatingMargins": 0.14,
                "debtToEquity": 42.0,
                "freeCashflow": 3.2e10,
                "operatingCashflow": 4.5e10,
                "totalRevenue": 2.4e11,
                "totalDebt": 5.5e10,
            },
            "asset_profile": {"industry": "Demo Software", "sector": "Technology"},
            "key_stats": {
                "marketCap": 1.6e12,
                "sharesOutstanding": 1.6e10,
                "revenuePerShare": 14.5,
                "enterpriseToEbitda": 14.0,
                "heldPercentInsiders": 0.08,
            },
            "quote_type": {
                "symbol": ticker,
                "longName": f"{ticker} Demo Corp",
            },
            "price": {"shortName": f"{ticker} Demo"},
            "buybacks": True,
        }

    active_limit = _active_rate_limit()
    if active_limit:
        return {
            "summary_detail": {},
            "financial_data": {},
            "asset_profile": {},
            "key_stats": {},
            "quote_type": {},
            "price": {},
            "buybacks": None,
            "error": {"message": active_limit.message, "rate_limit": active_limit},
        }

    def _capture_error_details(exc: Exception) -> dict[str, Any]:
        details: dict[str, Any] = {"message": str(exc)}

        response = getattr(exc, "response", None)
        status_code = getattr(exc, "status_code", None)
        if response and not status_code:
            status_code = getattr(response, "status_code", None)

        headers = _normalize_headers(getattr(response, "headers", {}))
        payload = None
        if response is not None:
            try:
                payload = response.json()
            except Exception:
                payload = getattr(response, "text", None)

        if status_code is not None:
            details["status_code"] = status_code

        if headers:
            details["headers"] = headers

        host = _extract_host(response)
        retry_after = _parse_retry_after(headers, payload)
        if status_code in {429, 503} or retry_after:
            rate_limit_error = RateLimitError(
                status_code=status_code,
                message=str(exc),
                retry_after=retry_after,
                headers=headers,
                host=host,
                payload=payload,
                remaining=retry_after,
            )
            details["rate_limit"] = rate_limit_error

        return details

    def _fetch_section(client: Any, attr_name: str) -> tuple[Mapping[str, Any], dict[str, Any]]:
        try:
            section = getattr(client, attr_name)
            return _safe_section(section, ticker), {}
        except Exception as exc:  # noqa: BLE001
            details = _capture_error_details(exc)
            if rate_limit := details.get("rate_limit"):
                _record_rate_limit(rate_limit)
            return {}, details

    try:
        ticker_client = ticker_cls(ticker)
    except Exception as exc:  # noqa: BLE001
        error_details = _capture_error_details(exc)
        if rate_limit := error_details.get("rate_limit"):
            _record_rate_limit(rate_limit)
        return {
            "summary_detail": {},
            "financial_data": {},
            "asset_profile": {},
            "key_stats": {},
            "quote_type": {},
            "price": {},
            "buybacks": None,
            "error": error_details,
        }

    sections: dict[str, Mapping[str, Any]] = {}
    error_info: dict[str, Any] = {}

    for key, attr_name in (
        ("summary_detail", "summary_detail"),
        ("financial_data", "financial_data"),
        ("asset_profile", "asset_profile"),
        ("key_stats", "key_stats"),
        ("quote_type", "quote_type"),
        ("price", "price"),
    ):
        section, section_error = _fetch_section(ticker_client, attr_name)
        sections[key] = section
        if section_error and not error_info:
            error_info = section_error

    if rate_limit := error_info.get("rate_limit"):
        _record_rate_limit(rate_limit)

    buybacks = _detect_buybacks(ticker_client, sections.get("key_stats", {}))

    return {
        **sections,
        "buybacks": buybacks,
        "error": error_info,
    }
