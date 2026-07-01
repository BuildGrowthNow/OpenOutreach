# openoutreach/core/logging.py
"""Centralized logging configuration with colored output and startup banner."""

from __future__ import annotations

import logging
import os
import sys

from termcolor import colored

# ── Banner ──────────────────────────────────────────────────────────

BANNER = r"""
   ___                   ___        _                      _
  / _ \ _ __   ___ _ __ / _ \ _   _| |_ _ __ ___  __ _  ___| |__
 | | | | '_ \ / _ \ '_ \ | | | | | | __| '__/ _ \/ _` |/ __| '_ \
 | |_| | |_) |  __/ | | | |_| | |_| | |_| | |  __/ (_| | (__| | | |
  \___/| .__/ \___|_| |_|\___/ \__,_|\__|_|  \___|\__,_|\___|_| |_|
       |_|
"""


def print_banner() -> None:
    """Print the OpenOutreach startup banner in bold cyan."""
    sys.stdout.write(colored(BANNER, "cyan", attrs=["bold"]))
    sys.stdout.write("\n")
    sys.stdout.flush()


# ── Colored formatter ───────────────────────────────────────────────

_LEVEL_COLORS = {
    logging.DEBUG: ("dark_grey", []),
    logging.INFO: (None, []),
    logging.WARNING: ("yellow", ["bold"]),
    logging.ERROR: ("red", ["bold"]),
    logging.CRITICAL: ("red", ["bold", "underline"]),
}

_LEVEL_LABELS = {
    logging.DEBUG: "DBG",
    logging.INFO: "INF",
    logging.WARNING: "WRN",
    logging.ERROR: "ERR",
    logging.CRITICAL: "CRT",
}


class ColoredFormatter(logging.Formatter):
    """Compact colored formatter: ``[LVL] message``."""

    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        color, attrs = _LEVEL_COLORS.get(record.levelno, (None, []))
        label = _LEVEL_LABELS.get(record.levelno, "???")
        prefix = colored(f"[{label}]", color, attrs=attrs) if color else f"[{label}]"
        return f"{prefix} {msg}"


# ── Public API ──────────────────────────────────────────────────────

_BRANDS = {
    "bettercontact": ("BetterContact", (155, 81, 224)),  # bettercontact.rocks #9b51e0
    "icemail": ("IceMail", (34, 197, 94)),  # icemail.ai --brand #22c55e
}


def _color_enabled() -> bool:
    """Mirror termcolor's gating: NO_COLOR off, FORCE_COLOR on, else TTY-only."""
    if "NO_COLOR" in os.environ:
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return sys.stdout.isatty()


def brand(service: str, text: str | None = None) -> str:
    """Render a service name (or `text`) in that vendor's brand colour."""
    label, (r, g, b) = _BRANDS[service]
    label = text if text is not None else label
    if not _color_enabled():
        return label
    return f"\033[38;2;{r};{g};{b}m{label}\033[0m"


SILENCED_LOGGERS = (
    "urllib3",
    "urllib3.connectionpool",
    "httpx",
    "pydantic_ai",
    "openai",
    "playwright",
    "httpcore",
    "fastembed",
    "huggingface_hub",
    "filelock",
    "asyncio",
    "requests",
    "pymongo",
    "pymongo.command",
    "pymongo.monitor",
    "pymongo.network",
    "pymongo.topology",
    "bson",
)


def configure_logging(level: int | None = None) -> None:
    """Configure root logger with colored output and silence noisy libraries."""
    if level is None:
        configured_level = os.environ.get("OPENOUTREACH_LOG_LEVEL", "INFO").upper()
        level = getattr(logging, configured_level, logging.INFO)

    root = logging.getLogger()
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(ColoredFormatter("%(message)s"))
    handler.setLevel(level)

    root.addHandler(handler)
    root.setLevel(level)

    for name in SILENCED_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
