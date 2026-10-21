from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.model_registry import (
    Evaluation,
    append_evaluations,
    load_evaluations,
    paired_comparison,
    summarize,
    write_model_manifest,
)


class ModelRegistryTests(unittest.TestCase):
    def test_evaluation_jsonl_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "metrics" / "evaluations.jsonl"
            rows = [
                Evaluation("candidate", 1, "baseline", "win", 2, 1, 90.0),
                Evaluation("candidate", 2, "baseline", "draw", 1, 1, 120.0),
            ]
            self.assertEqual(append_evaluations(path, rows), 2)
            self.assertEqual(load_evaluations(path), rows)
            summary = summarize(rows, "candidate", "baseline")
            self.assertEqual(summary["games"], 2)
            self.assertEqual(summary["wins"], 1)
            self.assertEqual(summary["draws"], 1)
            self.assertEqual(summary["mean_own_crowns"], 1.5)

    def test_promotion_requires_enough_paired_seeds(self) -> None:
        rows = [
            Evaluation("candidate", 1, "opponent", "win"),
            Evaluation("baseline", 1, "opponent", "loss"),
        ]
        result = paired_comparison(rows, "candidate", "baseline", "opponent", minimum_pairs=2)
        self.assertFalse(result["promote"])
        self.assertEqual(result["reason"], "insufficient_paired_evaluations")

    def test_promotion_passes_only_when_both_gates_pass(self) -> None:
        rows = []
        for seed in range(1, 31):
            rows.append(Evaluation("candidate", seed, "opponent", "win"))
            rows.append(Evaluation("baseline", seed, "opponent", "loss"))
        result = paired_comparison(rows, "candidate", "baseline", "opponent", minimum_pairs=30)
        self.assertTrue(result["promote"])
        self.assertEqual(result["paired_games"], 30)
        self.assertAlmostEqual(result["delta"], 1.0)

    def test_promotion_rejected_when_paired_evidence_is_uncertain(self) -> None:
        rows = []
        for seed in range(1, 31):
            rows.append(Evaluation(
                "candidate", seed, "opponent",
                "win" if seed <= 18 else "loss",
            ))
            rows.append(Evaluation(
                "baseline", seed, "opponent",
                "win" if seed <= 15 else "loss",
            ))
        result = paired_comparison(
            rows, "candidate", "baseline", "opponent",
            minimum_pairs=30, required_win_rate=0.55, required_delta=0.05,
        )
        self.assertAlmostEqual(result["candidate_win_rate"], 0.6)
        self.assertAlmostEqual(result["delta"], 0.1)
        self.assertFalse(result["promote"])
        self.assertEqual(result["reason"], "paired_uncertainty_too_high")
        self.assertEqual(set(result["paired_delta_ci_95"]), {"lower", "upper"})

    def test_rejects_duplicate_seed_for_same_model(self) -> None:
        rows = [
            Evaluation("candidate", 1, "opponent", "win"),
            Evaluation("candidate", 1, "opponent", "loss"),
            Evaluation("baseline", 1, "opponent", "loss"),
        ]
        with self.assertRaisesRegex(ValueError, "Semilla duplicada"):
            paired_comparison(rows, "candidate", "baseline", "opponent", minimum_pairs=1)

    def test_manifest_hashes_artifact_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "actor"
            artifact.mkdir()
            (artifact / "weights.bin").write_bytes(b"axr-test-weights")
            target = Path(tmp) / "registry" / "candidate.json"
            manifest = write_model_manifest("candidate-v1", artifact, target, "imitation")
            self.assertEqual(manifest["promotion_status"], "unverified")
            self.assertEqual(len(manifest["files"]), 1)
            self.assertEqual(len(manifest["files"][0]["sha256"]), 64)
            saved = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(saved["model_id"], "candidate-v1")


if __name__ == "__main__":
    unittest.main()
