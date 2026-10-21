"""File-log formatting for NSMBDS without changing other clients' records."""

from __future__ import annotations

import logging


def launch_with_client_logging(launch, *args: str) -> None:
    """Choose the dedicated client's filename using Core's existing initializer."""
    import Utils

    original_init_logging = Utils.init_logging

    def init_logging(name, *logging_args, **logging_kwargs):
        if name == "BizHawkClient":
            name = "NsmbdsClient"
        return original_init_logging(name, *logging_args, **logging_kwargs)

    # Only the dedicated NSMBDS process calls this launcher. Keep Core itself
    # compatible with installed Archipelago versions and restore it on exit.
    Utils.init_logging = init_logging
    try:
        launch(*args)
    finally:
        Utils.init_logging = original_init_logging


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
