
import unittest
from core.training_blueprint import BlueprintCategory, _apply_rep_metrics

class SpeedCoachMetricsTests(unittest.TestCase):
    def test_rep_metrics_are_connected(self):
        category = BlueprintCategory(
            key="speed",
            label="Speed Development",
            coach="Speed Coach",
            icon="",
            sample_size=4,
            benchmark_size=3,
            confidence=0.48,
            hr_low=130,
            hr_high=145,
            hr_typical=138,
            pace_low_s_per_km=None,
            pace_high_s_per_km=None,
            typical_distance_km=8.0,
            show_pace=False,
            source="Athlete history",
            summary="Old",
        )
        result = _apply_rep_metrics(
            category,
            {
                "sample_size": 10,
                "benchmark_size": 5,
                "pace_low": 205.0,
                "pace_high": 215.0,
                "pace_typical": 210.0,
                "distance_low": 0.35,
                "distance_high": 0.45,
                "distance_typical": 0.40,
                "recovery_typical": 90.0,
                "rep_count_typical": 8.0,
                "quality_volume_typical": 3.2,
            },
        )
        self.assertEqual(result.rep_distance_typical_km, 0.40)
        self.assertEqual(result.rep_pace_typical_s_per_km, 210.0)
        self.assertEqual(result.recovery_typical_s, 90.0)
        self.assertEqual(result.rep_count_typical, 8.0)

if __name__ == "__main__":
    unittest.main()
