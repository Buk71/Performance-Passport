import datetime

from core.evidence_providers.race import (
    CandidateScore,
    RaceCandidate,
    _select_goal_representative_race,
)


def _candidate(activity_id, distance_km, title, date):
    return RaceCandidate(
        activity_id=activity_id,
        activity_date=date,
        title=title,
        distance_km=distance_km,
        elapsed_time_s=2400.0,
        moving_time_s=2400.0,
        avg_hr=158.0,
        max_hr=165.0,
        athlete_lt2_hr=162.0,
        athlete_max_hr=170.0,
        elevation_up_m=20.0,
        elevation_down_m=20.0,
        temperature_c=15.0,
        humidity=60.0,
        wind_speed=5.0,
        route_name=None,
        official_race_name=None,
        official_distance_m=None,
        official_time_s=None,
        officially_measured=False,
        raw_json={},
    )


def _score(candidate, total, age_days):
    return CandidateScore(
        candidate=candidate,
        total=total,
        recency=0.9,
        distance=1.0,
        continuity=1.0,
        effort=0.9,
        official=0.0,
        title=0.0,
        training_penalty=0.0,
        matched_distance_km=candidate.distance_km,
        age_days=age_days,
        moving_ratio=1.0,
    )


def test_recent_direct_10k_can_outrank_higher_scoring_5k_projection():
    direct = _score(
        _candidate(2, 10.02, "Running", datetime.date(2026, 9, 27)),
        total=75.0,
        age_days=20,
    )
    five_k = _score(
        _candidate(1, 5.0, "parkrun", datetime.date(2026, 8, 22)),
        total=90.0,
        age_days=55,
    )

    selected = _select_goal_representative_race(
        [five_k, direct],
        goal_distance_km=10.0,
        athlete_id=1,
    )

    assert selected.candidate.activity_id == 2
