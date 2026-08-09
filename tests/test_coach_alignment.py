import datetime
import unittest
from unittest.mock import patch

from core.adaptive_coach_live import (
    _day_timing,
    family_label,
)
from core.evidence_providers.workout import (
    _is_race_quality_session,
)
from core.session_intelligence import ActivityFacts


class CoachAlignmentTests(unittest.TestCase):
    def test_day_timing(self):
        sunday = datetime.date(2026, 8, 9)
        self.assertEqual(
            _day_timing("Monday", sunday),
            "Tomorrow",
        )
        self.assertEqual(
            _day_timing("Wednesday", sunday),
            "Wednesday",
        )

    def test_family_label_matches_vo2(self):
        self.assertEqual(
            family_label("vo2"),
            "VO₂ / Speed Development",
        )

    def test_jo_race_quality_is_excluded_from_workout_coach(self):
        facts = ActivityFacts(
            activity_id=1,
            athlete_id=3,
            activity_date="2026-08-09",
            title="Activity",
            sport_id="running",
            distance_km=9.94,
            moving_time_s=3122.0,
            elapsed_time_s=3122.0,
            avg_hr=161.0,
            max_hr=181.0,
            elevation_up_m=126.0,
            temperature_c=None,
            humidity=None,
            wind_speed=None,
            route_name="Halton",
            raw_json_text="{}",
            athlete_lt2_hr=170.0,
            athlete_max_hr=190.0,
        )

        self.assertTrue(
            _is_race_quality_session(facts)
        )


if __name__ == "__main__":
    unittest.main()
