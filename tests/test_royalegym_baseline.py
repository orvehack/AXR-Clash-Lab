import json
import tempfile
import unittest
from pathlib import Path

from src.royalegym_baseline import (
    LanePressureAgent,
    RandomLegalAgent,
    evaluate,
    legal_actions,
    make_agent,
    play_episode,
    save_evaluation_bundle,
)


class FakeEnv:
    """Tiny deterministic parallel environment for testing the evaluator contract."""

    def __init__(self):
        self.closed = False
        self.steps = 0

    def reset(self, seed=None):
        self.steps = 0
        obs = {
            "blue": {"action_mask": [1, 1, 0, 0]},
            "red": {"action_mask": [1, 0, 1, 0]},
        }
        return obs, {}

    def step(self, actions):
        self.steps += 1
        self.last_actions = actions
        obs = {
            "blue": {"action_mask": [1, 1, 0, 0]},
            "red": {"action_mask": [1, 0, 1, 0]},
        }
        rewards = {"blue": 1.0, "red": -1.0}
        done = self.steps >= 2
        terminated = {"blue": done, "red": done}
        truncated = {"blue": False, "red": False}
        info = {
            "blue": {"own_crowns": 2, "enemy_crowns": 0},
            "red": {"own_crowns": 0, "enemy_crowns": 2},
        }
        return obs, rewards, terminated, truncated, info

    def close(self):
        self.closed = True


class BaselineAgentTests(unittest.TestCase):
    def test_reads_legal_action_mask(self):
        self.assertEqual(legal_actions({"action_mask": [0, 1, 0, 1]}), [1, 3])

    def test_missing_or_empty_mask_is_rejected(self):
        with self.assertRaises(KeyError):
            legal_actions({})
        with self.assertRaises(ValueError):
            legal_actions({"action_mask": [0, 0, 0]})

    def test_random_agent_never_selects_illegal_action(self):
        agent = RandomLegalAgent(seed=42)
        observation = {"action_mask": [0, 0, 1, 0, 1]}
        for _ in range(50):
            self.assertIn(agent.act(observation), [2, 4])

    def test_lane_policy_decodes_default_tile_action_ids(self):
        self.assertIsNone(LanePressureAgent.decode(0))
        self.assertEqual(LanePressureAgent.decode(1), (0, 0, 0))
        self.assertEqual(LanePressureAgent.decode(1342), (2, 9, 10))
        self.assertIsNone(LanePressureAgent.decode(2305))

    def test_lane_policy_chooses_only_legal_actions(self):
        agent = LanePressureAgent(seed=5, wait_probability=0)
        observation = {"action_mask": [1] + [0] * 100 + [1]}
        self.assertEqual(agent.act(observation), 101)

    def test_factory_rejects_unknown_agent(self):
        with self.assertRaises(ValueError):
            make_agent("super-bot")

    def test_play_episode_returns_metrics_and_respects_done(self):
        env = FakeEnv()
        result = play_episode(env, LanePressureAgent(wait_probability=0), RandomLegalAgent(), 99)
        self.assertEqual(result.seed, 99)
        self.assertEqual(result.winner, "blue")
        self.assertEqual(result.decisions, 2)
        self.assertEqual(result.blue_crowns, 2)
        self.assertGreaterEqual(result.duration_seconds, 0)

    def test_terminal_shaped_reward_is_not_misreported_as_a_win(self):
        class NoCrownInfoEnv(FakeEnv):
            def step(self, actions):
                self.steps += 1
                obs = {
                    "blue": {"action_mask": [1, 1, 0, 0]},
                    "red": {"action_mask": [1, 0, 1, 0]},
                }
                rewards = {"blue": 100.0, "red": -100.0}
                done = self.steps >= 1
                terminated = {"blue": done, "red": done}
                truncated = {"blue": False, "red": False}
                return obs, rewards, terminated, truncated, {}

        result = play_episode(
            NoCrownInfoEnv(), RandomLegalAgent(seed=1), RandomLegalAgent(seed=2), 77
        )
        self.assertEqual(result.winner, "unknown")

    def test_evaluation_bundle_writes_real_newlines_and_valid_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            summary = evaluate(lambda: FakeEnv(), episodes=2, seed_start=200)
            paths = save_evaluation_bundle(summary, Path(temporary))
            payload = Path(paths["json"]).read_text(encoding="utf-8")
            markdown = Path(paths["markdown"]).read_text(encoding="utf-8")
            self.assertEqual(json.loads(payload)["episodes"], 2)
            self.assertTrue(payload.endswith("\n"))
            self.assertNotIn("\\n", payload)
            self.assertTrue(markdown.endswith("\n"))
            self.assertNotIn("\\n", markdown)

    def test_episode_limit_is_reported(self):
        env = FakeEnv()
        result = play_episode(env, RandomLegalAgent(), RandomLegalAgent(), 10, max_decisions=1)
        self.assertEqual(result.decisions, 1)
        self.assertEqual(result.winner, "limit")

    def test_evaluate_closes_environment_and_summarizes(self):
        created = []

        def factory():
            env = FakeEnv()
            created.append(env)
            return env

        summary = evaluate(factory, episodes=3, seed_start=20)
        self.assertEqual(summary.episodes, 3)
        self.assertEqual(summary.wins, 3)
        self.assertEqual(summary.losses, 0)
        self.assertEqual(summary.win_rate, 100.0)
        self.assertEqual([r.seed for r in summary.results], [20, 21, 22])
        self.assertTrue(created[0].closed)
        self.assertEqual(len(summary.to_dict()["results"]), 3)


if __name__ == "__main__":
    unittest.main()
