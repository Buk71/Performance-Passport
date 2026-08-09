import unittest
from core.performance_backtracking import (
    PreparationWindow,
    _bucket,
    _contrast,
    _family_components,
    _signature_lifts,
)

class PerformanceBacktrackingTests(unittest.TestCase):
    def test_standard_distance_bucket(self):
        self.assertEqual(_bucket(5.01),5.0)
        self.assertEqual(_bucket(10.04),10.0)
        self.assertIsNone(_bucket(7.0))

    def test_mixed_quality_counts_both_stimuli(self):
        import json
        phases=json.dumps([
            {"phase_type":"threshold"},
            {"phase_type":"short_intervals"},
        ])
        self.assertEqual(
            _family_components(phases),
            {"threshold","short_intervals"},
        )

    def test_successful_vs_normal_contrast(self):
        successful = (
            PreparationWindow(
                42, 36, 270.0, 45.0, 10, 5, 4, 1, 0, 5, 90.0, ()
            ),
            PreparationWindow(
                42, 36, 282.0, 47.0, 10, 5, 4, 1, 0, 5, 91.0, ()
            ),
        )
        normal = (
            PreparationWindow(
                42, 30, 240.0, 40.0, 7, 2, 3, 1, 0, 4, 87.0, ()
            ),
            PreparationWindow(
                42, 31, 246.0, 41.0, 7, 2, 3, 1, 0, 4, 88.0, ()
            ),
        )

        contrast = _contrast(
            "threshold_session_count",
            "Threshold",
            successful,
            normal,
        )

        self.assertIsNotNone(contrast)
        self.assertGreater(
            contrast.relative_difference,
            1.0,
        )

    def test_signature_lift_finds_disproportionate_workout(self):
        successful = (
            PreparationWindow(
                42, 30, 250, 41.7, 8, 3, 3, 0, 0, 4, 90,
                (("threshold_3x10", 1),)
            ),
            PreparationWindow(
                42, 30, 250, 41.7, 8, 3, 3, 0, 0, 4, 90,
                (("threshold_3x10", 1),)
            ),
        )
        normal = (
            PreparationWindow(
                42, 30, 250, 41.7, 8, 3, 3, 0, 0, 4, 90,
                (("10x400", 1),)
            ),
            PreparationWindow(
                42, 30, 250, 41.7, 8, 3, 3, 0, 0, 4, 90,
                (("threshold_3x10", 1),)
            ),
            PreparationWindow(
                42, 30, 250, 41.7, 8, 3, 3, 0, 0, 4, 90,
                (("10x400", 1),)
            ),
            PreparationWindow(
                42, 30, 250, 41.7, 8, 3, 3, 0, 0, 4, 90,
                (("10x400", 1),)
            ),
        )

        lifts = _signature_lifts(
            successful,
            normal,
        )

        self.assertEqual(
            lifts[0].workout_signature,
            "threshold_3x10",
        )
        self.assertGreater(
            lifts[0].lift,
            1.0,
        )


if __name__=="__main__":
    unittest.main()
