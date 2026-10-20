from __future__ import annotations

import unittest

from src.imitate_agent import parse_args, validate_args


class ImitationPipelineTests(unittest.TestCase):
    def test_plan_only_has_architecture_matching_ppo_defaults(self) -> None:
        args = parse_args(["--plan-only", "--matches", "25"])
        self.assertEqual(args.matches, 25)
        self.assertEqual(args.trunk_channels, 64)
        self.assertEqual(args.trunk_blocks, 4)
        self.assertEqual(validate_args(args), [])

    def test_rejects_invalid_training_parameters(self) -> None:
        args = parse_args(["--matches", "0", "--epochs", "0", "--batch-size", "0"])
        errors = validate_args(args)
        self.assertTrue(any("--matches" in item for item in errors))
        self.assertTrue(any("--epochs" in item for item in errors))
        self.assertTrue(any("--batch-size" in item for item in errors))

    def test_rejects_missing_local_replay_directory(self) -> None:
        args = parse_args(["--data-dir", "this-folder-should-not-exist-axr"])
        errors = validate_args(args)
        self.assertTrue(any("--data-dir" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
