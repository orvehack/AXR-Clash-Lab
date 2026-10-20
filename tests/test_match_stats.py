import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.match_stats import load_summary, summarize_rows


class MatchStatsTests(unittest.TestCase):
    def test_summarizes_results_and_trophies(self):
        summary = summarize_rows([
            {"result": "win", "opponent_deck": "Hog cycle", "trophy_delta": "28"},
            {"result": "loss", "opponent_deck": "LavaLoon", "trophy_delta": "-27"},
            {"result": "draw", "opponent_deck": "Hog cycle", "trophy_delta": "0"},
        ])
        self.assertEqual(summary.total, 3)
        self.assertEqual(summary.wins, 1)
        self.assertEqual(summary.losses, 1)
        self.assertEqual(summary.undecided, 1)
        self.assertEqual(summary.trophy_delta, 1)
        self.assertEqual(summary.win_rate, 50.0)
        self.assertEqual(summary.opponent_counts["Hog cycle"], 2)

    def test_accepts_spanish_result_labels(self):
        summary = summarize_rows([
            {"result": "Victoria", "opponent_deck": "", "trophy_delta": "5"},
            {"result": "derrota", "opponent_deck": "Ciclo", "trophy_delta": "-3"},
        ])
        self.assertEqual(summary.wins, 1)
        self.assertEqual(summary.losses, 1)
        self.assertEqual(summary.trophy_delta, 2)
        self.assertEqual(summary.opponent_counts["Sin especificar"], 1)

    def test_empty_data_has_no_win_rate(self):
        summary = summarize_rows([])
        self.assertEqual(summary.total, 0)
        self.assertIsNone(summary.win_rate)

    def test_invalid_trophy_delta_reports_row(self):
        with self.assertRaisesRegex(ValueError, "fila 2"):
            summarize_rows([
                {"result": "win", "opponent_deck": "Test", "trophy_delta": "muchos"}
            ])

    def test_loads_csv_and_checks_required_columns(self):
        with TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "matches.csv"
            csv_path.write_text(
                "result,opponent_deck,trophy_delta\nwin,Test,12\n",
                encoding="utf-8",
            )
            self.assertEqual(load_summary(csv_path).trophy_delta, 12)

            csv_path.write_text("result,notes\nwin,ok\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Faltan columnas"):
                load_summary(csv_path)


if __name__ == "__main__":
    unittest.main()
