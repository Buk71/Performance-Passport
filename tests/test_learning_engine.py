import unittest

from core.learning_engine import (
    LearningObservation,
    _build_pattern,
    _phase_family,
)


class LearningEngineTests(unittest.TestCase):
    def test_threshold_phase_maps_to_threshold(self):
        self.assertEqual(
            _phase_family(
                [
                    {"phase_type": "warmup"},
                    {"phase_type": "threshold"},
                    {"phase_type": "cooldown"},
                ]
            ),
            "threshold",
        )

    def test_mixed_threshold_and_short_intervals_is_mixed(self):
        self.assertEqual(
            _phase_family(
                [
                    {"phase_type": "threshold"},
                    {"phase_type": "short_intervals"},
                ]
            ),
            "mixed_quality",
        )

    def test_positive_history_builds_positive_pattern(self):
        observations = []
        for index, delta in enumerate((2.0, 2.5, 1.8, 2.2), start=1):
            observations.append(
                LearningObservation(
                    workout_id=index,
                    activity_id=index,
                    activity_date=f"2026-01-{index:02d}",
                    activity_title="Threshold",
                    family="threshold",
                    workout_signature="threshold_3x10min",
                    execution_score=90.0,
                    phase_confidence=0.9,
                    recognition_confidence=0.9,
                    pre_execution_avg=85.0,
                    post_execution_avg=85.0 + delta,
                    response_delta=delta,
                    response_direction="positive",
                    pre_sample_count=3,
                    post_sample_count=3,
                    race_link_count=0,
                    best_race_link_confidence=None,
                )
            )

        pattern = _build_pattern(
            "threshold",
            observations,
        )

        self.assertEqual(pattern.direction, "strong_positive")
        self.assertGreater(pattern.average_response_delta, 2.0)
        self.assertEqual(pattern.best_associated_signature, "threshold_3x10min")


if __name__ == "__main__":
    unittest.main()
