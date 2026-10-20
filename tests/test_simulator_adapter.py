import unittest

from src.simulator_adapter import describe_space, inspect_environment


class FakeSpace:
    shape = (4, 8)


class FakeDiscreteSpace:
    n = 12


class FakeEnv:
    observation_space = FakeSpace()
    action_space = FakeDiscreteSpace()

    def reset(self, seed=None):
        return ([0, 1, 2], {"seed": seed})


class OldStyleFakeEnv(FakeEnv):
    def reset(self):
        return [1, 2]


class SimulatorAdapterTests(unittest.TestCase):
    def test_describes_spaces(self):
        self.assertEqual(describe_space(FakeDiscreteSpace())["n"], 12)
        self.assertEqual(describe_space(FakeSpace())["shape"], [4, 8])
        self.assertIsNone(describe_space(None))

    def test_inspects_reset_without_executing_actions(self):
        result = inspect_environment(FakeEnv(), seed=42)
        self.assertEqual(result["observation_type"], "list")
        self.assertEqual(result["action_space"]["n"], 12)
        self.assertEqual(result["actions_executed"], 0)

    def test_supports_reset_without_seed_argument(self):
        result = inspect_environment(OldStyleFakeEnv())
        self.assertEqual(result["observation_type"], "list")
        self.assertIsNone(result["observation_shape"])


if __name__ == "__main__":
    unittest.main()
