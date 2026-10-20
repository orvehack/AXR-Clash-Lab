import tempfile
import unittest
from pathlib import Path

from src.decision_dataset import REQUIRED, load_and_validate, validate_rows
from src.train_agent import make_plan, parse_args, write_run_manifest


def valid_row(**overrides):
    row = {column: "" for column in REQUIRED}
    row.update({
        "match_id": "m-001",
        "timestamp_seconds": "12.5",
        "phase": "opening",
        "event_type": "card_play",
        "own_elixir": "5",
        "opponent_elixir": "4.5",
        "own_card": "Giant",
        "own_lane": "left",
        "opponent_card": "",
        "decision_label": "play_giant",
        "outcome_label": "positive",
        "notes": "",
    })
    row.update(overrides)
    return row


class DecisionDatasetTests(unittest.TestCase):
    def test_valid_rows_are_summarized(self):
        report = validate_rows([valid_row(), valid_row(match_id="m-002", phase="overtime")])
        self.assertEqual(report.rows, 2)
        self.assertEqual(report.valid_rows, 2)
        self.assertEqual(report.unique_matches, 2)
        self.assertEqual(report.phase_counts["opening"], 1)
        self.assertEqual(report.decision_counts["play_giant"], 2)

    def test_invalid_numeric_and_phase_values_are_reported(self):
        report = validate_rows([valid_row(own_elixir="eleven", phase="super-phase")])
        self.assertEqual(report.invalid_rows, 1)
        self.assertTrue(any("own_elixir debe ser numérico" in issue for issue in report.issues))
        self.assertTrue(any("fase desconocida" in issue for issue in report.issues))

    def test_elixir_out_of_range_is_reported(self):
        report = validate_rows([valid_row(opponent_elixir="12")])
        self.assertEqual(report.invalid_rows, 1)
        self.assertTrue(any("fuera del rango" in issue for issue in report.issues))

    def test_load_template_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "decisions.csv"
            path.write_text(",".join(REQUIRED) + "\n", encoding="utf-8")
            report = load_and_validate(path)
            self.assertEqual(report.rows, 0)
            self.assertEqual(report.invalid_rows, 0)


class TrainingPlanTests(unittest.TestCase):
    def test_plan_validation_and_defaults(self):
        plan = make_plan(parse_args(["--plan-only", "--steps", "12000"]))
        self.assertEqual(plan.total_steps, 12000)
        self.assertEqual(plan.opponent, "random")
        with self.assertRaises(ValueError):
            make_plan(parse_args(["--steps", "0"]))

    def test_manifest_does_not_claim_training_completed(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = make_plan(parse_args(["--plan-only", "--save-dir", str(Path(directory) / "run")]))
            path = write_run_manifest(plan, Path(plan.save_dir))
            text = path.read_text(encoding="utf-8")
            self.assertIn('"status": "planned"', text)
            self.assertIn("not proof that training completed", text)


if __name__ == "__main__":
    unittest.main()
