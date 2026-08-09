import datetime
import unittest
from unittest.mock import patch

from core.evidence_providers.race import (
    RaceCandidate,
    _generic_elevation_penalty_seconds,
    _is_training_intent,
    _recency_signal,
)
from core.adaptive_weekly_plan import _completed_family_today


class LiveDataReconciliationTests(unittest.TestCase):
    def test_recency_has_no_30_day_cliff(self):
        day30 = _recency_signal(30)
        day31 = _recency_signal(31)
        self.assertLess(day30 - day31, 0.02)

    def test_recency_still_declines(self):
        self.assertGreater(
            _recency_signal(30),
            _recency_signal(120),
        )

    def test_threshold_title_is_training_intent(self):
        candidate = RaceCandidate(
            activity_id=1,
            activity_date=datetime.date(2026,8,8),
            title="Nostell parkrun - Threshold",
            distance_km=5.0,
            elapsed_time_s=1200.0,
            moving_time_s=1200.0,
            avg_hr=None,
            max_hr=None,
            athlete_lt2_hr=None,
            athlete_max_hr=None,
            elevation_up_m=55.0,
            elevation_down_m=55.0,
            temperature_c=None,
            humidity=None,
            wind_speed=None,
            route_name="Nostell",
            official_race_name=None,
            official_distance_m=None,
            official_time_s=None,
            officially_measured=False,
            raw_json={},
        )
        self.assertTrue(_is_training_intent(candidate))
        self.assertGreater(
            _generic_elevation_penalty_seconds(candidate),
            0.0,
        )


if __name__ == "__main__":
    unittest.main()
