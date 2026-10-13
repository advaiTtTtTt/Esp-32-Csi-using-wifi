import unittest

import numpy as np

from src.signal_processing import calculate_baseline, filter_signal


class SignalProcessingTests(unittest.TestCase):
    def test_median_filter_removes_one_sample_spike(self):
        filtered = filter_signal([10, 10, 100, 10, 10], window=3)
        np.testing.assert_allclose(filtered, [10, 10, 10, 10, 10])

    def test_baseline_uses_robust_median_and_spread(self):
        baseline = calculate_baseline([10, 10, 10, 10, 10, 1000])
        self.assertEqual(baseline.center, 10.0)
        self.assertEqual(baseline.spread, 0.0)
        self.assertEqual(baseline.samples, 6)

    def test_baseline_requires_five_valid_values(self):
        with self.assertRaises(ValueError):
            calculate_baseline([1, 2, np.nan, 3, 4])


if __name__ == "__main__":
    unittest.main()
