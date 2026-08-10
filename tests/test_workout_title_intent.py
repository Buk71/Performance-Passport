
import json
import unittest

from core.workout_title_intent import (
    build_title_intent_evidence,
    parse_workout_title,
)


class WorkoutTitleIntentTests(unittest.TestCase):
    def test_blizard_title_parses_full_sequence(self):
        intent = parse_workout_title(
            "Blizard session: 2 x 800, 1 mile, 2 x 800, "
            "1 mile, 2 x 800, off 60"
        )

        self.assertIsNotNone(intent)
        self.assertEqual(intent.total_reps, 8)
        self.assertEqual(intent.recovery_s, 60)
        self.assertEqual(
            [block.reps for block in intent.blocks],
            [2, 1, 2, 1, 2],
        )

    def test_title_matches_real_split_structure(self):
        raw = {
            "splits": (
                "I0.787|3:04||0-I0.013|0:04||0-"
                "I0.780|2:57||0-I0.015|0:05||0-"
                "I1.573|6:11||0-I0.009|0:04||0-"
                "I0.781|2:59||0-I0.015|0:05||0-"
                "I0.778|2:58||0-I0.008|0:04||0-"
                "I1.571|6:10||0-I0.014|0:04||0-"
                "I0.783|3:00||0-I0.013|0:05||0-"
                "I0.782|2:56||0"
            )
        }

        result = build_title_intent_evidence(
            "Blizard session: 2 x 800, 1 mile, 2 x 800, "
            "1 mile, 2 x 800, off 60",
            json.dumps(raw),
        )

        self.assertIsNotNone(result)
        self.assertGreaterEqual(
            result["metadata"]["match_ratio"],
            0.95,
        )
        self.assertEqual(
            result["metadata"]["source"],
            "activity_title+runalyze_splits",
        )

    def test_slr_is_not_parsed_as_workout_intent(self):
        self.assertIsNone(
            parse_workout_title("SLR 12 miles")
        )


if __name__ == "__main__":
    unittest.main()
