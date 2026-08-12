"""Real-data and deterministic checks for the Athlete Passport."""

import datetime
import unittest

from core.athlete_passport import (
    age_grade_percent,
    build_athlete_passport,
)


REFERENCE_DATE = datetime.date(2026, 8, 11)


class AgeGradingTests(unittest.TestCase):
    def test_richard_5k_uses_2020_male_road_standard(self):
        result = age_grade_percent(
            sex="Male",
            age=54,
            event_key="5k",
            elapsed_seconds=1148,
        )
        self.assertAlmostEqual(result, 78.8327526, places=6)

    def test_jo_5k_uses_2020_female_road_standard(self):
        result = age_grade_percent(
            sex="Female",
            age=54,
            event_key="5k",
            elapsed_seconds=1371,
        )
        self.assertAlmostEqual(result, 75.4194019, places=6)


class RealPassportGoldenTests(unittest.TestCase):
    def test_richard_passport_from_real_history(self):
        passport = build_athlete_passport(
            1,
            reference_date=REFERENCE_DATE,
        )

        self.assertIsNotNone(passport)
        self.assertEqual(passport.full_name, "Richard Burke")
        self.assertEqual(passport.category, "M54 · Runner")
        self.assertAlmostEqual(passport.age_grade_all_time, 78.8327526, places=6)
        self.assertAlmostEqual(
            passport.age_grade_last_12_months,
            78.8327526,
            places=6,
        )
        self.assertEqual(
            [pb.all_time_seconds for pb in passport.personal_bests],
            [1148.0, 2380.0, 5360.0],
        )
        self.assertEqual(
            [pb.last_12_months_seconds for pb in passport.personal_bests],
            [1148.0, 2380.0, 5565.0],
        )
        self.assertAlmostEqual(passport.aerobic_trend_percent, 3.5254728, places=6)
        self.assertEqual(passport.aerobic_run_count, 124)
        self.assertEqual(len(passport.aerobic_chart_points), 12)

    def test_jo_passport_from_real_history(self):
        passport = build_athlete_passport(
            3,
            reference_date=REFERENCE_DATE,
        )

        self.assertIsNotNone(passport)
        self.assertEqual(passport.full_name, "Joanne Burke")
        self.assertEqual(passport.category, "W54 · Runner")
        self.assertAlmostEqual(passport.age_grade_all_time, 75.4194019, places=6)
        self.assertAlmostEqual(
            passport.age_grade_last_12_months,
            75.4194019,
            places=6,
        )
        self.assertEqual(
            [pb.all_time_seconds for pb in passport.personal_bests],
            [1371.0, 2803.0, 6248.0],
        )
        self.assertEqual(
            [pb.last_12_months_seconds for pb in passport.personal_bests],
            [1371.0, 2849.0, 6762.0],
        )
        self.assertAlmostEqual(passport.aerobic_trend_percent, 2.3370998, places=6)
        self.assertEqual(passport.aerobic_run_count, 86)
        self.assertEqual(len(passport.aerobic_chart_points), 12)


if __name__ == "__main__":
    unittest.main()
