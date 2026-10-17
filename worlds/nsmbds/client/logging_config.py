"""File-log formatting for NSMBDS without changing other clients' records."""

from __future__ import annotations

import logging


class NSMBDSLogFormatter(logging.Formatter):
    def __init__(self, fallback: logging.Formatter | None) -> None:
        super().__init__("[%(name)s %(levelname)s at %(asctime)s]: %(message)s")
        self.fallback = fallback or logging.Formatter()

    def format(self, record: logging.LogRecord) -> str:
        if record.name == "NSMBDS" or record.name.startswith("NSMBDS."):
            return super().format(record)
        return self.fallback.format(record)


def configure_file_logging() -> None:
    """Add severity to NSMBDS file records after Core initializes its handlers."""
    for handler in logging.getLogger().handlers:
        if isinstance(handler, logging.FileHandler) and not isinstance(handler.formatter, NSMBDSLogFormatter):
            handler.setFormatter(NSMBDSLogFormatter(handler.formatter))
