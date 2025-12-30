import logging

import pandas as pd
import streamlit as st

from . import data_access
from .logging import configure_logging
from .metrics import (
    compute_metrics,
    ensure_data_available,
    format_billions,
    resolve_critical_fields,
    thresholds,
    tooltips,
)


def _render_metric_rows(metrics: dict[str, object]) -> tuple[pd.DataFrame, int, int]:
    rows = []
    pass_count = 0
    red_count = 0
    for metric, value in metrics.items():
        threshold = thresholds.get(metric)
        tooltip = tooltips.get(metric, "")

        display_val = "N/A"
        if isinstance(value, (int, float)):
            if "Margin" in metric or "%" in metric or "Growth" in metric or "Yield" in metric:
                value *= 100
            display_val = f"{value:.2f}"

        status = "ℹ️"
        if isinstance(value, (int, float)):
            if isinstance(threshold, bool):
                status = "✅" if value == threshold else "❌"
            elif "Debt/Equity" in metric or "P/E" in metric or "PEG" in metric or "P/B" in metric or "P/S" in metric or "EV / EBITDA" in metric:
                status = "✅" if value <= threshold else "❌"
            else:
                status = "✅" if value >= threshold else "❌"
        elif isinstance(value, bool):
            status = "✅" if value else "❌"

        if status == "✅":
            pass_count += 1
        elif status == "❌":
            red_count += 1

        label = f"{metric}"
        if tooltip:
            label += " ⓘ"
            st.markdown(f"<span title='{tooltip}' style='cursor: help;'>{label}</span>", unsafe_allow_html=True)

        rows.append((metric, display_val, status))

    df = pd.DataFrame(rows, columns=["Metric", "Value", "Status"])
    return df, pass_count, red_count


def _format_error_details(error_info: dict[str, object]) -> str | None:
    if not error_info:
        return None

    rate_limit = error_info.get("rate_limit")
    status_code = error_info.get("status_code") or getattr(rate_limit, "status_code", None)
    host = error_info.get("host") or getattr(rate_limit, "host", None)
    retry_after = (
        error_info.get("retry_after")
        or getattr(rate_limit, "retry_after", None)
        or getattr(rate_limit, "remaining", None)
    )
    headers = error_info.get("headers") or getattr(rate_limit, "headers", None)
    message = error_info.get("message") or getattr(rate_limit, "message", None)

    parts: list[str] = []
    if status_code is not None:
        parts.append(f"HTTP {status_code}")
    if host:
        parts.append(f"host={host}")
    if retry_after:
        parts.append(f"retry_after={retry_after}s")
    if headers:
        parts.append(f"headers={headers}")
    if message:
        parts.append(str(message))

    return "; ".join(parts) if parts else None


def _sanitize_error_info(error_info: dict[str, object]) -> dict[str, object]:
    if not error_info:
        return {}

    sanitized = dict(error_info)
    rate_limit = sanitized.get("rate_limit")
    if isinstance(rate_limit, data_access.RateLimitError):
        sanitized["rate_limit"] = {
            "status_code": rate_limit.status_code,
            "message": rate_limit.message,
            "retry_after": rate_limit.retry_after,
            "headers": dict(rate_limit.headers),
            "host": rate_limit.host,
            "payload": rate_limit.payload,
            "remaining": rate_limit.remaining,
        }

    return sanitized


def _render_error_diagnostics(ticker: str, error_info: dict[str, object]) -> None:
    if not error_info:
        return

    with st.expander(f"Diagnostics for {ticker}"):
        st.json(_sanitize_error_info(error_info))


def display_stock(ticker: str, ticker_cls=None, ticker_client=None):
    ticker_cls = ticker_cls or data_access.Ticker
    sections = data_access.fetch_ticker_sections(
        ticker, ticker_cls=ticker_cls, ticker_client=ticker_client
    )

    error_info = sections.get("error") or {}
    rate_limit = error_info.get("rate_limit")
    if isinstance(rate_limit, data_access.RateLimitError):
        retry_after = rate_limit.retry_after or rate_limit.remaining or 0
        remaining_seconds = rate_limit.remaining or rate_limit.retry_after or 0
        host = rate_limit.host or "Yahoo Finance"
        details = _format_error_details(error_info) or "Rate limit detected"
        message = (
            f"Rate limit detected from {host}. Please wait {remaining_seconds} seconds before retrying."
        )
        if retry_after:
            message += f" Retry-After header indicates {retry_after} seconds."
        if details and details not in message:
            message += f" Details: {details}."
        st.info(message)
        _render_error_diagnostics(ticker, error_info)
        try:
            st.toast(message)
        except Exception:
            # Toast not available in some Streamlit versions; banner is sufficient.
            pass
        return

    core_sections = {
        k: v for k, v in sections.items() if k not in {"buybacks", "error"}
    }

    if all(not section for section in core_sections.values()):
        message_parts: list[str] = []
        detailed_reason = _format_error_details(error_info)
        if detailed_reason:
            message_parts.append(detailed_reason)

        reason = "; ".join(message_parts) if message_parts else None
        if not reason:
            reason = (
                "No response returned from Yahoo Finance. This may indicate a "
                "temporary data-source outage or rate limit."
            )

        st.warning(reason)
        _render_error_diagnostics(ticker, error_info)
        raise ValueError(f"No data available for {ticker} (reason: {reason})")

    cache_info = sections.get("cache_info", {})
    cache_sections = cache_info.get("sections_cached") or []
    if cache_info.get("served_from_cache"):
        st.caption("💾 Served fully from cache")
    elif cache_sections:
        st.caption(
            "💾 Partially served from cache: "
            + ", ".join(sorted(cache_sections))
        )
    elif cache_info.get("cache_disabled"):
        st.caption("💾 Cache disabled for this request")

    try:
        metrics = compute_metrics(ticker, sections)
        warnings = ensure_data_available(ticker, core_sections, metrics)
    except ValueError as exc:  # noqa: BLE001
        fallback_message = (
            "No response returned from Yahoo Finance. This may indicate a "
            "temporary data-source outage or rate limit."
        )
        warning_message = _format_error_details(error_info) or str(exc)
        if not error_info and fallback_message not in warning_message:
            warning_message = (
                f"{warning_message}. {fallback_message}" if warning_message else fallback_message
            )
        st.warning(warning_message)
        _render_error_diagnostics(ticker, error_info)
        raise ValueError(
            f"No data available for {ticker} (reason: {warning_message})"
        ) from exc

    profile = core_sections.get("asset_profile", {})
    key_stats = core_sections.get("key_stats", {})
    financial = core_sections.get("financial_data", {})
    quote_type = core_sections.get("quote_type", {})
    price = core_sections.get("price", {})

    critical_fields = resolve_critical_fields(core_sections)

    industry = profile.get("industry", "—")
    sector = profile.get("sector", "—")
    market_cap = format_billions(critical_fields.get("market cap", "—"))
    total_revenue = format_billions(critical_fields.get("total revenue", "—"))
    total_cash = format_billions(financial.get("totalCash", "—"))
    total_debt = format_billions(critical_fields.get("total debt", "—"))
    shares_outstanding = format_billions(key_stats.get("sharesOutstanding", "—"))

    company_name = data_access.resolve_company_name(ticker, quote_type, price, profile)

    if warnings:
        warning_messages: list[str] = []
        missing_fields = warnings.get("missing_fields", [])
        missing_metrics = warnings.get("missing_metrics", [])

        if missing_fields:
            warning_messages.append(
                f"Missing required fields for {ticker}: {', '.join(missing_fields)}"
            )

        if missing_metrics:
            warning_messages.append(
                f"Missing metrics for {ticker}: {', '.join(missing_metrics)}"
            )

        for message in warning_messages:
            st.warning(message)

    st.subheader(f"{ticker} - {company_name}")
    st.markdown(f"**Industry**: {industry}")
    st.markdown(f"**Sector**: {sector}")
    st.markdown(f"**Market Cap**: {market_cap}")
    st.markdown(f"**Total Revenue**: {total_revenue}")
    st.markdown(f"**Total Cash**: {total_cash}")
    st.markdown(f"**Total Debt**: {total_debt}")
    st.markdown(f"**Shares Outstanding**: {shares_outstanding}")

    df, pass_count, red_count = _render_metric_rows(metrics)
    st.dataframe(df, width="stretch")

    score = f"{pass_count} ✅ / {red_count} ❌"
    st.markdown(f"### Snapshot Score: {score}")

    decision = "Hold"
    if pass_count >= 12:
        decision = "Buy"
    elif red_count >= 10:
        decision = "Sell"

    st.markdown(f"### 📌 Suggested Action: **{decision}**")


def main():
    configure_logging()
    logging.getLogger(__name__).info("Initializing Streamlit dashboard")
    st.set_page_config(page_title="Value Investing Dashboard", layout="wide")
    st.title("📊 Value Investing Dashboard")

    default_watchlist = data_access.get_default_watchlist_string()

    if data_access.is_smoke_mode():
        st.info(
            "Smoke test mode enabled. Skipping live ticker validation and data fetches."
        )
        st.markdown(
            "This lightweight page confirms the server is running without reaching "
            "out to Yahoo Finance. Disable `SMOKE_TEST` to load live ticker data."
        )

    st.markdown(f"Default watchlist: `{default_watchlist}`")
    ticker_input = st.text_input(
        "Enter comma-separated stock tickers (e.g. AAPL,MSFT,META):",
        default_watchlist,
    )
    raw_tickers = [t.strip().upper() for t in ticker_input.split(",") if t.strip()]
    tickers = data_access.validate_tickers(raw_tickers)
    batched_client = data_access.get_batched_ticker_client(tickers)

    for ticker in tickers:
        try:
            display_stock(ticker, ticker_client=batched_client)
        except Exception as e:
            st.error(f"Error loading {ticker}: {e}")


if __name__ == "__main__":
    main()
