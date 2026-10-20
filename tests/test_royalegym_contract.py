import unittest

from src.royalegym_contract import (
    _finite_scalar,
    _require_two_seat_mapping,
    _shape,
    summarize_space,
)


class FakeSpace:
    shape = (4, 8)
    dtype = "float32"


class FakeDiscreteSpace:
    n = 2305
    start = 0


class RoyaleGymContractUnitTests(unittest.TestCase):
    def test_summarizes_spaces_without_serializing_objects(self):
        self.assertEqual(summarize_space(FakeSpace()), {
            "type": "FakeSpace",
            "shape": [4, 8],
            "dtype": "float32",
        })
        self.assertEqual(summarize_space(FakeDiscreteSpace()), {
            "type": "FakeDiscreteSpace",
            "n": 2305,
            "start": 0,
        })

    def test_shape_is_none_when_missing(self):
        self.assertIsNone(_shape(object()))

    def test_requires_both_seats(self):
        self.assertEqual(_require_two_seat_mapping({"blue": 1, "red": 2}, "test")["red"], 2)
        with self.assertRaises(ValueError):
            _require_two_seat_mapping({"blue": 1}, "test")

    def test_finite_scalar(self):
        self.assertEqual(_finite_scalar(0.25, "reward"), 0.25)
        with self.assertRaises(ValueError):
            _finite_scalar(float("nan"), "reward")
        with self.assertRaises(TypeError):
            _finite_scalar("not a number", "reward")


if __name__ == "__main__":
    unittest.main()
