"""Offline tests for AXR's emulator discovery and launcher contracts."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src import emulator_manager as manager


class EmulatorDiscoveryTests(unittest.TestCase):
    def test_dedupe_paths_is_case_insensitive(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            exe = Path(folder) / "MEmu.exe"
            exe.write_text("stub", encoding="utf-8")
            duplicate = Path(folder) / "." / "MEmu.exe"
            self.assertEqual(len(manager._dedupe_paths([exe, duplicate])), 1)

    def test_find_candidate_rejects_unknown_emulator(self) -> None:
        with self.assertRaises(ValueError):
            manager.find_candidate("unknown")

    def test_find_candidate_errors_when_not_installed(self) -> None:
        with patch.object(manager, "discover_emulators", return_value={"memu": [], "bluestacks": []}):
            with self.assertRaises(FileNotFoundError):
                manager.find_candidate("memu")

    def test_launch_uses_popen_without_shell(self) -> None:
        candidate = manager.EmulatorCandidate("memu", Path("C:/test/MEmu.exe"))
        fake_process = type("Process", (), {"pid": 1234})()
        with patch.object(manager, "find_candidate", return_value=candidate), patch.object(
            manager.subprocess, "Popen", return_value=fake_process
        ) as popen:
            result = manager.launch_emulator("memu")
        self.assertTrue(result.started)
        self.assertEqual(result.pid, 1234)
        self.assertFalse(popen.call_args.kwargs["shell"])

    def test_process_status_reports_errors_without_crashing(self) -> None:
        with patch.object(manager.subprocess, "run", side_effect=OSError("missing")):
            result = manager.process_status()
        self.assertFalse(result["available"])
        self.assertEqual(result["running"], [])

    def test_diagnostics_discloses_scope(self) -> None:
        with patch.object(manager, "discover_emulators", return_value={"memu": [], "bluestacks": []}), patch.object(
            manager, "process_status", return_value={"available": True, "running": []}
        ):
            result = manager.diagnostics()
        self.assertIn("no game input", result["scope"])


if __name__ == "__main__":
    unittest.main()
