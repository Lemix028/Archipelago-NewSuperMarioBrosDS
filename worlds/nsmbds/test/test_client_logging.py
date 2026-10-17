"""Check NSMBDS file formatting and shared debug-level inheritance in isolation."""

from __future__ import annotations

import importlib.util
from contextlib import closing
import io
import logging
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    "nsmbds_logging_config", Path(__file__).parents[1] / "client" / "logging_config.py"
)
logging_config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(logging_config)


class TestClientLogging(unittest.TestCase):
    def test_file_severity_preserves_other_records_and_stream_format(self):
        with tempfile.TemporaryDirectory() as directory:
            with closing(logging.FileHandler(Path(directory) / "client.log", encoding="utf-8")) as handler:
                original = logging.Formatter("[%(name)s]: %(message)s")
                handler.setFormatter(original)
                stream = logging.StreamHandler(io.StringIO())
                stream.setFormatter(original)
                with patch.object(logging.getLogger(), "handlers", [handler, stream]):
                    logging_config.configure_file_logging()
                    formatter = handler.formatter
                    logging_config.configure_file_logging()
                    self.assertIs(handler.formatter, formatter)
                    self.assertIs(stream.formatter, original)
                    handler.handle(logging.makeLogRecord({
                        "name": "NSMBDS.Blocks", "levelno": logging.DEBUG,
                        "levelname": "DEBUG", "msg": "Ignored already checked Blocksanity: %s.",
                        "args": ("World 8-1 Blocksanity Block 7",),
                    }))
                    handler.handle(logging.makeLogRecord({
                        "name": "Client", "levelno": logging.INFO,
                        "levelname": "INFO", "msg": "Connected", "args": (),
                    }))
                handler.flush()
                output = (Path(directory) / "client.log").read_text(encoding="utf-8")
                self.assertIn("[NSMBDS.Blocks DEBUG at ", output)
                self.assertIn("Ignored already checked Blocksanity: World 8-1 Blocksanity Block 7.", output)
                self.assertIn("[Client]: Connected\n", output)

    def test_parent_debug_switch_controls_all_feature_loggers(self):
        parent = logging.getLogger("NSMBDS")
        previous_level = parent.level
        names = (
            "Client", "Network", "Bridge", "Items", "Reserve", "Locations", "Blocks",
            "RedCoins", "Overworld", "Trap", "Buffs", "DeathLink", "DeathCounter",
            "Goal", "Performance", "Launch", "Diag",
        )
        try:
            for level in (logging.DEBUG, logging.INFO):
                parent.setLevel(level)
                for name in names:
                    with self.subTest(level=level, logger=name):
                        child = parent.getChild(name)
                        self.assertEqual(child.getEffectiveLevel(), level)
                        self.assertEqual(child.isEnabledFor(logging.DEBUG), level == logging.DEBUG)
        finally:
            parent.setLevel(previous_level)


if __name__ == "__main__":
    unittest.main()
