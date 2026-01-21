"""Logging utilities for SEO Agent."""

import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler


def setup_logging(
    level: int = logging.INFO,
    log_file: Path | None = None,
) -> logging.Logger:
    """Configure logging with Rich handler for console output."""
    # Create logger
    logger = logging.getLogger("seo_agent")
    logger.setLevel(level)

    # Remove existing handlers
    logger.handlers.clear()

    # Console handler with Rich
    console_handler = RichHandler(
        console=Console(stderr=True),
        show_time=True,
        show_path=False,
        markup=True,
    )
    console_handler.setLevel(level)
    console_formatter = logging.Formatter("%(message)s")
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler if specified
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str = "seo_agent") -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)


class LogContext:
    """Context manager for logging with extra context."""

    def __init__(self, logger: logging.Logger, context: str):
        self.logger = logger
        self.context = context

    def __enter__(self):
        self.logger.info(f"Starting: {self.context}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.logger.error(f"Failed: {self.context} - {exc_val}")
        else:
            self.logger.info(f"Completed: {self.context}")
        return False
