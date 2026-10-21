from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.doctor import REQUIRED_PATHS, diagnose


class DoctorTests(unittest.TestCase):
    def test_reports_missing_project_paths_without_installing_anything(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = diagnose(Path(temporary))
        self.assertFalse(report["core_ready"])
        self.assertEqual(set(report["missing_required_paths"]), set(REQUIRED_PATHS))
        self.assertIn("optional_ml_modules", report)
        self.assertIn("notes", report)

    def test_repository_root_has_expected_core_files(self) -> None:
        root = Path(__file__).resolve().parents[1]
        report = diagnose(root)
        self.assertEqual(report["missing_required_paths"], [])
        self.assertTrue(report["python_supported_for_core"])
        self.assertIn("royalegym", report["optional_ml_modules"])


if __name__ == "__main__":
    unittest.main()
