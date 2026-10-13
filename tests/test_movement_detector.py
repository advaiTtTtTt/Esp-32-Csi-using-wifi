import unittest

from src.movement_detector import MovementDetector


class MovementDetectorTests(unittest.TestCase):
    def test_requires_persistent_deviation_and_emits_one_event(self):
        detector = MovementDetector(filter_window=1, persistence=3, release_samples=2)
        detector.calibrate([10, 10, 10, 10, 10])
        results = [detector.update(12) for _ in range(3)]
        self.assertEqual(sum(result.event_started for result in results), 1)
        self.assertTrue(results[-1].moving)
        self.assertFalse(detector.update(12).event_started)

    def test_releases_after_quiet_samples(self):
        detector = MovementDetector(filter_window=1, persistence=1, release_samples=2)
        detector.calibrate([10, 10, 10, 10, 10])
        self.assertTrue(detector.update(12).moving)
        self.assertTrue(detector.update(10).moving)
        self.assertFalse(detector.update(10).moving)

    def test_requires_baseline(self):
        result = MovementDetector().update(10)
        self.assertFalse(result.baseline_ready)
        self.assertIsNone(result.threshold)


if __name__ == "__main__":
    unittest.main()
