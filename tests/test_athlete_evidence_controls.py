"""Real-athlete regressions for athlete-first coaching evidence controls."""

from __future__ import annotations

import json
import unittest

from core.athlete_passport import build_athlete_passport
from core.database import (
    clear_activity_override,
    clear_personal_best_override,
    get_effective_activity_heart_rate,
    get_personal_best_overrides,
    save_activity_override,
    save_personal_best_override,
)
from core.session import SessionType
from core.session_intelligence import ActivityFacts, classify_session
from core.splits import parse_splits, recognise_workout


class AthleteEvidenceControlsTests(unittest.TestCase):
    def test_real_jo_twenty_short_repetitions_are_work_not_connectors(self):
        work = "-".join("U0.200|0:47-U0.100|1:00" for _ in range(20))
        result = recognise_workout(parse_splits(f"U0.400|2:16-{work}-U0.433|2:30"))
        self.assertEqual(result.rep_count, 20)
        self.assertAlmostEqual(result.average_rep_distance_km, 0.2, places=3)
        self.assertAlmostEqual(result.average_rep_pace_s_per_km, 235, delta=1)

    def test_real_jo_six_kilometre_repetitions_exclude_cooldown(self):
        splits = (
            "U0.400|2:27-U1.000|4:27-U0.165|2:00-"
            "U1.000|4:21-U0.163|2:00-U1.000|4:17-U0.165|2:00-"
            "U1.000|4:20-U0.174|2:00-U1.000|4:23-U0.177|2:00-"
            "U1.000|4:31-U0.149|2:00-U1.150|6:39"
        )
        result = recognise_workout(parse_splits(splits))
        self.assertEqual(result.rep_count, 6)
        self.assertAlmostEqual(result.average_rep_distance_km, 1, places=3)
        self.assertAlmostEqual(result.average_rep_pace_s_per_km, 263.2, delta=0.2)

    def test_separately_saved_strides_never_become_a_workout(self):
        splits = "-".join("U0.083|0:20-U0.060|1:00" for _ in range(6))
        facts = ActivityFacts(
            activity_id=10656, athlete_id=3, activity_date="2026-08-20",
            title="Activity", sport_id="966023", distance_km=0.88,
            moving_time_s=480, elapsed_time_s=480, avg_hr=145, max_hr=165,
            elevation_up_m=0, temperature_c=15, humidity=60, wind_speed=0,
            route_name=None, raw_json_text=json.dumps({"splits": splits}),
            athlete_lt2_hr=183, athlete_lt1_hr=171,
        )
        result = classify_session(facts)
        self.assertEqual(result.session_type, SessionType.CONTINUOUS_RUN)
        self.assertEqual(result.metadata.get("activity_intent"), "standalone_strides")

    def test_heart_rate_correction_preserves_and_restores_source_value(self):
        try:
            save_activity_override(3, 5577, heart_rate_reliable=False)
            self.assertIsNone(get_effective_activity_heart_rate(3, 5577, 141))
            save_activity_override(
                3, 5577, heart_rate_reliable=False, corrected_avg_hr=155
            )
            self.assertEqual(get_effective_activity_heart_rate(3, 5577, 141), 155)
        finally:
            clear_activity_override(3, 5577)
        self.assertEqual(get_effective_activity_heart_rate(3, 5577, 141), 141)

    def test_activity_corrections_cannot_cross_athletes(self):
        with self.assertRaises(ValueError):
            save_activity_override(1, 5577, session_intent="workout")

    def test_manual_classification_takes_priority_and_can_be_removed(self):
        facts = ActivityFacts(
            activity_id=5577, athlete_id=3, activity_date="2026-08-09",
            title="Easy run", sport_id="966023", distance_km=9.94,
            moving_time_s=3122, elapsed_time_s=3122, avg_hr=145,
            max_hr=170, elevation_up_m=0, temperature_c=15, humidity=60,
            wind_speed=0, route_name=None, raw_json_text=None,
            athlete_lt2_hr=183, athlete_lt1_hr=171,
        )
        try:
            save_activity_override(3, 5577, session_intent="workout")
            corrected = classify_session(facts)
            self.assertEqual(corrected.session_type, SessionType.STRUCTURED_WORKOUT)
            self.assertEqual(corrected.metadata.get("manual_override"), "workout")
        finally:
            clear_activity_override(3, 5577)

    def test_official_pb_takes_priority_over_watch_distance(self):
        prior = get_personal_best_overrides(3).get("5k")
        try:
            save_personal_best_override(3, "5k", 1359)
            passport = build_athlete_passport(3)
            five_k = next(item for item in passport.personal_bests if item.key == "5k")
            self.assertEqual(five_k.all_time_seconds, 1359)
            self.assertEqual(five_k.last_12_months_seconds, 1359)
        finally:
            if prior:
                save_personal_best_override(
                    3, "5k", prior["official_time_s"],
                    event_date=prior.get("event_date"), notes=prior.get("notes"),
                )
            else:
                clear_personal_best_override(3, "5k")


if __name__ == "__main__":
    unittest.main()
