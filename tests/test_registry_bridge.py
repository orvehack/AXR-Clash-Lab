from __future__ import annotations

import unittest

from src.registry_bridge import convert_baseline_report


class RegistryBridgeTests(unittest.TestCase):
    def test_imports_only_verifiable_terminal_outcomes(self) -> None:
        payload = {
            "agent": "lane-pressure",
            "opponent": "random",
            "results": [
                {"seed": 10, "winner": "blue", "blue_crowns": 2, "red_crowns": 0, "duration_seconds": 10.5},
                {"seed": 11, "winner": "red", "blue_crowns": 0, "red_crowns": 1, "duration_seconds": 11.0},
                {"seed": 12, "winner": "draw", "blue_crowns": 1, "red_crowns": 1, "duration_seconds": 12.0},
                {"seed": 13, "winner": "unknown", "blue_crowns": None, "red_crowns": None},
                {"seed": 14, "winner": "limit", "blue_crowns": None, "red_crowns": None},
            ],
        }
        records, report = convert_baseline_report(payload, "axr-v1", "random-v1")
        self.assertEqual([row.outcome for row in records], ["win", "loss", "draw"])
        self.assertEqual([row.seed for row in records], [10, 11, 12])
        self.assertEqual(report["records_imported"], 3)
        self.assertEqual(report["episodes_skipped_by_outcome"], {"unknown": 1, "limit": 1})

    def test_rejects_duplicate_seeds(self) -> None:
        payload = {"results": [
            {"seed": 1, "winner": "blue"},
            {"seed": 1, "winner": "red"},
        ]}
        with self.assertRaisesRegex(ValueError, "Semilla duplicada"):
            convert_baseline_report(payload, "axr-v1", "opponent-v1")

    def test_rejects_missing_episode_results(self) -> None:
        with self.assertRaisesRegex(ValueError, "lista 'results'"):
            convert_baseline_report({}, "axr-v1", "opponent-v1")


if __name__ == "__main__":
    unittest.main()
