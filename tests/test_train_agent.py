from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.train_agent import (
    append_jsonl_event,
    estimate_training_resources,
    make_plan,
    parse_args,
    read_jsonl_events,
    summarize_progress_events,
    write_experiment_card,
    write_run_manifest,
)


class TrainAgentHelperTests(unittest.TestCase):
    def test_plan_only_arguments_are_validated_without_optional_packages(self) -> None:
        args = parse_args([
            "--plan-only",
            "--steps", "12000",
            "--n-envs", "2",
            "--warm-start", "runs/teacher_actor",
        ])
        plan = make_plan(args)
        self.assertEqual(plan.total_steps, 12000)
        self.assertEqual(plan.n_envs, 2)
        self.assertEqual(plan.warm_start, "runs/teacher_actor")
        estimate = estimate_training_resources(plan)
        self.assertEqual(estimate.env_count, 2)
        self.assertGreater(estimate.estimated_updates, 0)

    def test_manifest_is_valid_json_with_real_line_ending(self) -> None:
        args = parse_args(["--plan-only", "--save-dir", "unused"])
        plan = make_plan(args)
        with tempfile.TemporaryDirectory() as temporary:
            path = write_run_manifest(plan, Path(temporary))
            raw = path.read_text(encoding="utf-8")
            payload = json.loads(raw)
            self.assertEqual(payload["status"], "planned")
            self.assertIn("experiment_fingerprint", payload)
            self.assertTrue(raw.endswith("\n"))
            self.assertNotIn("\\n", raw)

    def test_jsonl_events_round_trip_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "logs" / "events.jsonl"
            append_jsonl_event(path, {"step": 10, "reward": 0.5, "loss": 1.25})
            append_jsonl_event(path, {"step": 20, "reward": 1.5, "loss": 0.75})
            events = read_jsonl_events(path)
            summary = summarize_progress_events(events)
            self.assertEqual(summary["event_count"], 2)
            self.assertEqual(summary["last_step"], 20)
            self.assertAlmostEqual(summary["mean_reward"], 1.0)
            self.assertAlmostEqual(summary["mean_loss"], 1.0)

    def test_experiment_card_contains_evaluation_gates(self) -> None:
        plan = make_plan(parse_args(["--plan-only", "--steps", "1000"]))
        with tempfile.TemporaryDirectory() as temporary:
            path = write_experiment_card(plan, Path(temporary))
            content = path.read_text(encoding="utf-8")
            self.assertIn("Evaluation checklist", content)
            self.assertIn("held-out seeds", content)
            self.assertTrue(content.endswith("\n"))


if __name__ == "__main__":
    unittest.main()
