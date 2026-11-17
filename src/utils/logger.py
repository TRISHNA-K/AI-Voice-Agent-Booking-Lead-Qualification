"""Structured and colorized logger for the Voice AI Agent platform."""

import logging
import sys
from rich.console import Console
from rich.logging import RichHandler

console = Console()


def get_logger(name: str = "voice_agent") -> logging.Logger:
    """Return a configured logger with Rich formatting."""
    logger = logging.getLogger(name)

    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        handler = RichHandler(
            console=console,
            show_time=True,
            show_path=False,
            markup=True,
            rich_tracebacks=True,
        )
        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.propagate = False

    return logger
