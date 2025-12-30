"""Command-line interface for fetching ticker data and computing metrics."""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Iterable, Sequence

from . import data_access, metrics
from .logging import configure_logging


LOGGER = logging.getLogger(__name__)


_DEF_EXCLUDED_SECTION_KEYS = {"buybacks", "error", "cache_info"}


def _parse_tickers(raw: str) -> list[str]:
    tickers = [ticker.strip() for ticker in raw.split(",") if ticker.strip()]
    return tickers


def _normalized_sections(
    sections: dict[str, dict[str, object]]
) -> dict[str, dict[str, object]]:
    return {k: v for k, v in sections.items() if k not in _DEF_EXCLUDED_SECTION_KEYS}


def _process_ticker(ticker: str, ticker_client: object | None = None) -> bool:
    try:
        LOGGER.info("Fetching sections for %s", ticker)
        sections = data_access.fetch_ticker_sections(
            ticker, ticker_client=ticker_client
        )

        computed_metrics = metrics.compute_metrics(ticker, sections)
        warnings = metrics.ensure_data_available(
            ticker, _normalized_sections(sections), computed_metrics
        )
    except ValueError as exc:  # noqa: BLE001
        LOGGER.error("%s", exc)
        return False

    for category, missing_items in warnings.items():
        LOGGER.warning("%s: %s", category, ", ".join(sorted(missing_items)))

    LOGGER.info("Computed %d metrics for %s", len(computed_metrics), ticker)
    return True


def run(tickers: Iterable[str]) -> int:
    normalized = [ticker for ticker in tickers if ticker]
    validated = data_access.validate_tickers(normalized)

    if not validated:
        LOGGER.error("No valid tickers supplied after validation")
        return 1

    shared_client = data_access.get_batched_ticker_client(validated)

    failures = 0
    for ticker in validated:
        ok = _process_ticker(ticker, ticker_client=shared_client)
        failures += int(not ok)

    if failures:
        LOGGER.error("Completed with %d validation failure(s)", failures)
        return 1

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compute value-investing metrics for tickers",
    )
    parser.add_argument(
        "--tickers",
        required=True,
        help="Comma-separated ticker symbols (e.g., AAPL,MSFT)",
        type=_parse_tickers,
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    configure_logging(logging.DEBUG if args.verbose else None)
    exit_code = run(args.tickers)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
