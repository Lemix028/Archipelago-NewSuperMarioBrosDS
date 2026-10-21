"""Check NSMBDS file formatting and shared debug-level inheritance in isolation."""

from __future__ import annotations

import importlib.util
from contextlib import closing
import io
import logging
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch


spec = importlib.util.spec_from_file_location(
    "nsmbds_logging_config", Path(__file__).parents[1] / "client" / "logging_config.py"
)
logging_config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(logging_config)


class TestClientLogging(unittest.TestCase):
    def test_dedicated_launch_uses_own_log_name_and_restores_core(self):
        original = Mock()
        utils = types.SimpleNamespace(init_logging=original)

        def launch(*args):
            self.assertEqual(args, ("seed.apnds",))
            utils.init_logging("BizHawkClient", exception_logger="Client")
            utils.init_logging("OtherClient", "debug")

        with patch.dict(sys.modules, {"Utils": utils}):
            logging_config.launch_with_client_logging(launch, "seed.apnds")
        self.assertIs(utils.init_logging, original)
        self.assertEqual(original.call_args_list[0].args, ("NsmbdsClient",))
        self.assertEqual(original.call_args_list[0].kwargs, {"exception_logger": "Client"})
        self.assertEqual(original.call_args_list[1].args, ("OtherClient", "debug"))

    def test_failed_launch_restores_core_logging(self):
        original = Mock()
        utils = types.SimpleNamespace(init_logging=original)

        def launch():
            utils.init_logging("BizHawkClient", exception_logger="Client")
            raise RuntimeError("Startup failed")

        with patch.dict(sys.modules, {"Utils": utils}):
            with self.assertRaisesRegex(RuntimeError, "Startup failed"):
                logging_config.launch_with_client_logging(launch)
        self.assertIs(utils.init_logging, original)

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
