"""Shared logging configuration for the stock dashboard."""

from __future__ import annotations

import logging
import os
from typing import Any

DEFAULT_LOG_LEVEL_ENV = "LOG_LEVEL"
DEFAULT_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def _resolve_level(level: str | int | None) -> int:
    if level is None:
        level = os.getenv(DEFAULT_LOG_LEVEL_ENV, "INFO")

    if isinstance(level, str):
        numeric_level: Any = logging.getLevelName(level.upper())
        if isinstance(numeric_level, int):
            return numeric_level
        try:
            return int(level)
        except ValueError:
            return logging.INFO

    if isinstance(level, int):
        return level

    return logging.INFO


def configure_logging(level: str | int | None = None, format_string: str | None = None) -> None:
    """Configure global logging with a default format and level.

    When ``level`` is not provided, ``LOG_LEVEL`` environment variable is used with
    ``INFO`` as a fallback.
    """

    resolved_level = _resolve_level(level)
    logging.basicConfig(
        level=resolved_level,
        format=format_string or DEFAULT_FORMAT,
        force=True,
    )

