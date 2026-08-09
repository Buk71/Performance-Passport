import unittest

from core.session_designer import _preserve_recovery_instruction


class AdaptiveRecoveryDetailTests(unittest.TestCase):
    def test_keeps_time_recovery_when_reps_are_overridden(self):
        result = _preserve_recovery_instruction(
            (
                "6 × 3 min strong and controlled",
                "90 sec easy jog between reps",
            ),
            ("8 × 500m controlled intervals",),
        )

        self.assertEqual(
            result,
            (
                "8 × 500m controlled intervals",
                "90 sec easy jog between reps",
            ),
        )

    def test_keeps_distance_recovery(self):
        result = _preserve_recovery_instruction(
            (
                "8 × 400 m fast but relaxed",
                "200 m very easy jog between reps",
            ),
            ("10 × 400m controlled intervals",),
        )

        self.assertIn(
            "200 m very easy jog between reps",
            result,
        )

    def test_does_not_invent_recovery_for_continuous_session(self):
        result = _preserve_recovery_instruction(
            ("90 min comfortable continuous running",),
            ("95 min comfortable continuous running",),
        )

        self.assertEqual(
            result,
            ("95 min comfortable continuous running",),
        )


if __name__ == "__main__":
    unittest.main()
