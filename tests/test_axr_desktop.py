import csv
import json
import tempfile
import unittest
from pathlib import Path

from src.axr_desktop import (
    DecisionRecord,
    MatchRecord,
    list_runs,
    load_decisions,
    load_matches,
    normalize_result,
    read_csv_rows,
    summarize_decisions,
    summarize_matches,
    write_json,
)


class ResultNormalizationTests(unittest.TestCase):
    def test_english_and_spanish_win_labels(self):
        for value in ("win", "Won", "victoria", "GANADA", "gané"):
            with self.subTest(value=value):
                self.assertEqual(normalize_result(value), "win")

    def test_loss_labels(self):
        for value in ("loss", "lost", "derrota", "perdida", "perdí"):
            with self.subTest(value=value):
                self.assertEqual(normalize_result(value), "loss")

    def test_draw_and_unknown_labels(self):
        self.assertEqual(normalize_result("empate"), "draw")
        self.assertEqual(normalize_result("tie"), "draw")
        self.assertEqual(normalize_result(""), "unknown")
        self.assertEqual(normalize_result("maybe"), "unknown")


class MatchSummaryTests(unittest.TestCase):
    def test_metrics_include_win_rate_and_trophies(self):
        records = [
            MatchRecord("2026-10-01", "win", "Giant", "Hog", 28, ""),
            MatchRecord("2026-10-02", "loss", "Giant", "LavaLoon", -27, ""),
            MatchRecord("2026-10-03", "draw", "Giant", "Hog", 0, ""),
            MatchRecord("2026-10-04", "unknown", "Giant", "Unknown", 3, ""),
        ]
        summary = summarize_matches(records)
        self.assertEqual(summary["total"], 4)
        self.assertEqual(summary["wins"], 1)
        self.assertEqual(summary["losses"], 1)
        self.assertEqual(summary["draws"], 1)
        self.assertEqual(summary["undecided"], 1)
        self.assertAlmostEqual(summary["win_rate"], 100 / 3)
        self.assertEqual(summary["trophy_delta"], 4)
        self.assertEqual(summary["opponents"][0], ("Hog", 2))

    def test_empty_history_is_safe(self):
        summary = summarize_matches([])
        self.assertEqual(summary["total"], 0)
        self.assertEqual(summary["win_rate"], 0)
        self.assertEqual(summary["average_trophy_delta"], 0)


class CsvLoadingTests(unittest.TestCase):
    def test_missing_file_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(read_csv_rows(Path(directory) / "missing.csv"), [])

    def test_load_match_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "matches.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=("date", "result", "own_deck", "opponent_deck", "trophy_delta", "notes"),
                )
                writer.writeheader()
                writer.writerow({
                    "date": "2026-10-20",
                    "result": "victoria",
                    "own_deck": "Giant",
                    "opponent_deck": "Hog",
                    "trophy_delta": "28",
                    "notes": "offline",
                })
            rows = load_matches(path)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].result, "win")
            self.assertEqual(rows[0].trophy_delta, 28)

    def test_load_decisions_skips_template_header(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "decisions.csv"
            path.write_text(
                "match_id,timestamp_seconds,phase,event_type,own_elixir,opponent_elixir,"
                "own_card,own_lane,opponent_card,decision_label,outcome_label,notes\n",
                encoding="utf-8",
            )
            self.assertEqual(load_decisions(path), [])

    def test_load_decisions_reports_bad_timestamp(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "decisions.csv"
            path.write_text(
                "match_id,timestamp_seconds,phase,event_type,own_elixir,opponent_elixir,"
                "own_card,own_lane,opponent_card,decision_label,outcome_label,notes\n"
                "m1,not-a-number,opening,play,5,4,Giant,left,,play_giant,positive,\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "no es numérico"):
                load_decisions(path)

    def test_load_decisions_bad_timestamp_is_a_value_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "decisions.csv"
            path.write_text(
                "match_id,timestamp_seconds,phase,event_type,own_elixir,opponent_elixir,"
                "own_card,own_lane,opponent_card,decision_label,outcome_label,notes\\n"
                "m1,invalid,opening,play,5,4,Giant,left,,play_giant,positive,\\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                load_decisions(path)


class DecisionSummaryTests(unittest.TestCase):
    def test_counts_matches_phases_labels_and_notes(self):
        records = [
            DecisionRecord("m1", 5, "opening", "play", 5, 4, "Giant", "left", "", "play_giant", "positive", "good"),
            DecisionRecord("m1", 12, "opening", "defend", 3, 6, "Cannon", "center", "Hog", "defend_hog", "positive", ""),
            DecisionRecord("m2", 70, "overtime", "wait", 4, 4, "", "", "", "", "", ""),
        ]
        summary = summarize_decisions(records)
        self.assertEqual(summary["rows"], 3)
        self.assertEqual(summary["matches"], 2)
        self.assertEqual(summary["labeled"], 2)
        self.assertEqual(summary["notes"], 1)
        self.assertEqual(dict(summary["phases"])["opening"], 2)


class JsonAndRunTests(unittest.TestCase):
    def test_write_json_creates_parent_and_round_trips(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "report.json"
            write_json(path, {"status": "planned", "count": 3})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"status": "planned", "count": 3})
            self.assertFalse(path.with_suffix(".json.tmp").exists())

    def test_list_runs_ignores_unrecognized_json(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_json(root / "unrelated.json", {"hello": "world"})
            write_json(root / "experiment" / "axr_run_manifest.json", {
                "status": "planned",
                "training_plan": {"total_steps": 1000},
            })
            runs = list_runs(root)
            self.assertEqual(len(runs), 1)
            self.assertEqual(runs[0].name, "experiment")
            self.assertEqual(runs[0].status, "planned")
            self.assertIn("1000", runs[0].details)


if __name__ == "__main__":
    unittest.main()
