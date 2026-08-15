import datetime

import pytest

from core.coaching import RunProfile
from core.environment_profile import PersonalEnvironmentProfile
from core.performance_recognition import environment_adjusted_pace
from core.progress import build_progress_summary


REFERENCE_DATE = datetime.date(2026, 8, 9)


def test_richard_progress_uses_real_independent_evidence():
    progress = build_progress_summary(1, reference_date=REFERENCE_DATE)

    assert progress.athlete_name == "Richard Burke"
    assert progress.verdict == "Improving"
    assert progress.aerobic.confidence == "Strong"
    assert progress.aerobic.sample_size == 124
    assert progress.aerobic.trend_percent == 4.42
    assert progress.aerobic.adjusted_run_count == 116
    assert progress.aerobic.personalised_run_count == 105
    assert progress.rhythm.active_days_per_week == 5.8
    assert progress.rhythm.reliable_miles_per_week == 39.7
    assert all(
        round(
            point.easy_miles
            + point.long_miles
            + point.quality_miles
            + point.other_miles,
            1,
        ) == round(point.reliable_miles, 1)
        for point in progress.rhythm.points
    )
    assert progress.race.status == "Mixed recent results"
    assert progress.threshold.status == "Trend building"
    assert progress.threshold.recent_sample_size == 1
    assert progress.threshold.current_pace_s_per_km == 235.7
    assert progress.threshold.standard_equivalent_fast_s_per_km == 230.5
    assert progress.threshold.standard_equivalent_slow_s_per_km == pytest.approx(
        234.0,
        abs=0.11,
    )
    assert progress.threshold.current_conditions == "20°C heat, 27 km/h wind"
    assert progress.durability.recent_sample_size == 1


def test_jo_progress_uses_her_own_evidence():
    progress = build_progress_summary(3, reference_date=REFERENCE_DATE)

    assert progress.athlete_name == "Joanne Burke"
    assert progress.verdict == "Improving"
    assert progress.aerobic.sample_size == 86
    assert progress.aerobic.trend_percent == 2.22
    assert progress.rhythm.active_days_per_week == 4.8
    assert progress.rhythm.reliable_miles_per_week == 27.5
    assert progress.race.status == "Race performance improving"
    assert progress.threshold.total_sample_size == 2
    assert progress.threshold.current_pace_s_per_km == 257.2
    assert progress.durability.confidence == "Moderate"
    assert progress.durability.change_percent == 0.7


def test_progress_keeps_race_results_raw_and_threshold_cautious():
    richard = build_progress_summary(1, reference_date=REFERENCE_DATE)
    events = {event.key: event for event in richard.race.events}

    assert events["5k"].all_time_best_s == 1148
    assert events["10k"].all_time_best_s == 2380
    assert events["5k"].change_s == 18
    assert events["10k"].change_s == -40
    assert richard.threshold.trend_seconds_per_km is None
    assert "never rewrite a PB" in richard.race.summary


def test_environment_adjustment_is_auditable_and_personalised():
    run = RunProfile(
        athlete_id=1,
        activity_date="2026-07-01",
        title="Warm hilly trail run",
        sport_id="trail_running",
        distance_km=10,
        moving_time_seconds=3000,
        avg_hr=140,
        run_max_hr=160,
        elevation_m=250,
        temperature_c=24,
        humidity=70,
        lt1_hr=145,
        lt2_hr=165,
        athlete_max_hr=185,
    )
    profile = PersonalEnvironmentProfile(
        athlete_id=1,
        heat_multiplier=1.2,
        hill_multiplier=0.8,
        trail_multiplier=0.7,
        heat_sample_size=20,
        hill_sample_size=20,
        trail_sample_size=20,
        heat_confidence=0.8,
        hill_confidence=0.8,
        trail_confidence=0.8,
        overall_confidence=0.8,
        reasons=(),
        limitations=(),
    )

    result = environment_adjusted_pace(
        run,
        wind_speed=22,
        personal_profile=profile,
    )

    assert result.adjusted_pace_s_per_km < result.actual_pace_s_per_km
    assert result.total_penalty_s_per_km > 0
    assert result.heat_humidity_penalty_s_per_km > 0
    assert result.elevation_penalty_s_per_km > 0
    assert result.wind_penalty_s_per_km > 0
    assert result.surface_penalty_s_per_km > 0
    assert set(result.personalised_factors) == {"heat", "hills", "trail"}


def test_progress_excludes_unreliable_treadmill_pace_but_counts_time():
    richard = build_progress_summary(1, reference_date=REFERENCE_DATE)

    assert richard.rhythm.moving_hours_per_week == 5.2
    assert any(
        "Treadmill time can support training rhythm" in note
        for note in richard.evidence_notes
    )
