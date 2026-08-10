
import unittest

from core.training_blueprint import (
    BlueprintCategory,
    _apply_rep_metrics,
    _distance_family,
)


class RecentComparableWorkoutTests(unittest.TestCase):
    def test_400m_family_tolerates_gps_drift(self):
        self.assertEqual(_distance_family(0.399)[0], "400m")
        self.assertEqual(_distance_family(0.421)[0], "400m")

    def test_current_and_historical_profiles_are_preserved(self):
        category = BlueprintCategory(
            key="speed",
            label="Speed Development",
            coach="Speed Coach",
            icon="",
            sample_size=10,
            benchmark_size=5,
            confidence=0.60,
            hr_low=130,
            hr_high=145,
            hr_typical=138,
            pace_low_s_per_km=None,
            pace_high_s_per_km=None,
            typical_distance_km=8.0,
            show_pace=False,
            source="old",
            summary="old",
        )

        result = _apply_rep_metrics(
            category,
            {
                "sample_size": 20,
                "benchmark_size": 4,
                "pace_low": 205.0,
                "pace_high": 215.0,
                "pace_typical": 210.0,
                "distance_low": 0.395,
                "distance_high": 0.405,
                "distance_typical": 0.400,
                "recovery_typical": 75.0,
                "rep_count_typical": 20.0,
                "quality_volume_typical": 8.0,
                "recent_rep_count_typical": 20.0,
                "recent_quality_volume_typical": 8.0,
                "historical_rep_count_typical": 12.0,
                "historical_quality_volume_typical": 4.8,
                "comparable_distance_label": "400m",
                "current_profile_sample_size": 4,
                "historical_profile_sample_size": 12,
            },
        )

        self.assertEqual(result.recent_rep_count_typical, 20.0)
        self.assertEqual(result.historical_rep_count_typical, 12.0)
        self.assertEqual(result.comparable_distance_label, "400m")
        self.assertIn("Current 400m pattern", result.summary)


if __name__ == "__main__":
    unittest.main()
