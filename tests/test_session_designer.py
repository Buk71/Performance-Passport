import unittest

from core.session_designer import (
    _history_structure,
    _session_family_from_label,
    _structural_fit,
)


class FakeRecord:
    phases = (
        {
            "phase_type": "warmup",
            "duration_s": 900,
            "distance_km": 2.5,
            "rep_count": 1,
        },
        {
            "phase_type": "threshold",
            "duration_s": 1800,
            "distance_km": 7.5,
            "rep_count": 3,
            "average_rep_distance_km": 2.5,
            "recovery_duration_s": 120,
            "pace_s_per_km": 240,
        },
    )


class FakeEvidence:
    rep_count = 3
    average_rep_duration_s = 600
    average_rep_distance_km = 2.5
    recovery_duration_s = 120


class SessionDesignerTests(unittest.TestCase):
    def test_session_family_label_maps_to_threshold(self):
        self.assertEqual(
            _session_family_from_label("Threshold Development"),
            "threshold",
        )

    def test_matching_threshold_structure_scores_well(self):
        score = _structural_fit(
            FakeRecord(),
            "threshold",
        )
        self.assertGreater(score, 0.7)

    def test_personal_history_can_build_three_by_ten(self):
        result = _history_structure(
            "threshold",
            (FakeEvidence(),),
        )
        self.assertIsNotNone(result)
        self.assertIn("3 × 10 min threshold", result[0])


if __name__ == "__main__":
    unittest.main()
