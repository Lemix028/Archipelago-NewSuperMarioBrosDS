"""Run the legacy client regression harness without polluting Core modules."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest import TestCase


class TestClientRegressionHarness(TestCase):
    def test_client_regressions(self) -> None:
        script = Path(__file__).with_name("client_regression.py")
        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=Path(__file__).parents[3],
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"Client regression harness failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}",
        )
