
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


    def test_ordered_pyramid_title_parses_full_sequence(self):
        intent = parse_workout_title(
            "400 800 1200 1600 2000 1600 1200 800 400 off 60"
        )

        self.assertIsNotNone(intent)
        self.assertEqual(intent.total_reps, 9)
        self.assertEqual(intent.structure_shape, "pyramid")
        self.assertEqual(intent.recovery_s, 60)
        self.assertEqual(
            [round(value * 1000) for value in intent.distance_sequence_km],
            [400, 800, 1200, 1600, 2000, 1600, 1200, 800, 400],
        )
        self.assertIn("Pyramid", intent.summary)
        self.assertIn("2000", intent.summary)

    def test_ordered_pyramid_rolls_into_prediction_components(self):
        raw = {
            "splits": (
                "I0.400|1:24||0-I0.120|1:00||0-"
                "I0.800|2:52||0-I0.120|1:00||0-"
                "I1.200|4:20||0-I0.120|1:00||0-"
                "I1.600|5:50||0-I0.120|1:00||0-"
                "I2.000|7:20||0-I0.120|1:00||0-"
                "I1.600|5:48||0-I0.120|1:00||0-"
                "I1.200|4:18||0-I0.120|1:00||0-"
                "I0.800|2:48||0-I0.120|1:00||0-"
                "I0.400|1:20||0"
            )
        }

        result = build_title_intent_evidence(
            "Pyramid 400 800 1200 1600 2000 1600 1200 800 400 off 60",
            json.dumps(raw),
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["metadata"]["structure_shape"], "pyramid")
        self.assertEqual(result["metadata"]["total_reps"], 9)
        self.assertAlmostEqual(
            result["metadata"]["total_work_distance_km"],
            10.0,
            places=2,
        )
        self.assertGreaterEqual(result["metadata"]["match_ratio"], 0.95)

        by_type = {
            component["component_type"]: component
            for component in result["components"]
        }
        self.assertEqual(by_type["short_intervals"]["rep_count"], 2)
        self.assertEqual(by_type["long_intervals"]["rep_count"], 2)
        self.assertEqual(by_type["threshold"]["rep_count"], 5)
        self.assertAlmostEqual(
            sum(component["total_work_distance_km"] for component in result["components"]),
            10.0,
            places=2,
        )


    def test_slr_is_not_parsed_as_workout_intent(self):
        self.assertIsNone(
            parse_workout_title("SLR 12 miles")
        )


if __name__ == "__main__":
    unittest.main()
