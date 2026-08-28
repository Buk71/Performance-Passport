import datetime
from types import SimpleNamespace

from core.recovery_coach import RecoveryCheckIn, compose_recovery_coach


TODAY = datetime.date(2026, 8, 27)


def _point(miles, *, days=6, easy=30.0, long=8.0, quality=2.0):
    return SimpleNamespace(
        reliable_miles=float(miles),
        active_days=days,
        easy_miles=easy,
        long_miles=long,
        quality_miles=quality,
    )


def _progress(current=44.0):
    rhythm = SimpleNamespace(
        points=tuple(
            [_point(40.0) for _ in range(11)]
            + [_point(current, easy=30.0, long=9.0, quality=5.0)]
        )
    )
    durability = SimpleNamespace(
        available=True,
        status="Controlled",
        recent_decoupling_percent=3.2,
        change_percent=-.8,
        total_sample_size=18,
        confidence="Strong",
        summary="Lower pace decoupling is better.",
    )
    return SimpleNamespace(rhythm=rhythm, durability=durability)


def _week(status="On track"):
    definitions = (
        ("Monday", "2026-08-24", "rest", "Rest", "Rest"),
        ("Tuesday", "2026-08-25", "quality", "Intervals", "Complete"),
        ("Wednesday", "2026-08-26", "easy", "Easy", "Complete"),
        ("Thursday", "2026-08-27", "recovery", "Recovery", "Today"),
        ("Friday", "2026-08-28", "threshold", "Threshold", "Planned"),
        ("Saturday", "2026-08-29", "easy", "Easy", "Planned"),
        ("Sunday", "2026-08-30", "long", "Long run", "Planned"),
    )
    days = tuple(
        SimpleNamespace(
            day=day,
            date=date,
            planned_family=family,
            planned_type=session_type,
            status=day_status,
        )
        for day, date, family, session_type, day_status in definitions
    )
    return SimpleNamespace(
        block_name="10K Development",
        week_number=4,
        total_weeks=12,
        status=status,
        days=days,
    )


def test_recovery_coach_keeps_training_balance_separate_from_unreported_feelings():
    detail = compose_recovery_coach(
        athlete_id=1,
        athlete_name="Richard Burke",
        progress=_progress(),
        week=_week(),
        checkin=None,
        today=TODAY,
    )

    assert detail.checkin_status == "Not reported today"
    assert detail.load.current_miles == 44.0
    assert detail.load.change_percent == 10.0
    assert detail.schedule.next_demand == "Threshold"
    assert detail.schedule.next_demand_timing == "Tomorrow"
    assert detail.schedule.protected_days_before_next_demand == 1
    assert "how you feel is still unreported" in detail.headline
    assert any("no hidden" in item.lower() for item in detail.limitations)


def test_multiple_athlete_reported_flags_call_for_adjustment_without_a_score():
    checkin = RecoveryCheckIn(
        athlete_id=3,
        checkin_date=TODAY.isoformat(),
        sleep_quality=1,
        fatigue=5,
        soreness=4,
        motivation=2,
        notes="Heavy legs and poor sleep",
    )
    detail = compose_recovery_coach(
        athlete_id=3,
        athlete_name="Joanne Burke",
        progress=_progress(),
        week=_week(),
        checkin=checkin,
        today=TODAY,
    )

    assert detail.checkin_status == "Several recovery flags reported"
    assert detail.headline == "Today calls for a recovery adjustment."
    assert len(detail.cautions) == 4
    assert "keep today easy or rest" in detail.direction.lower()


def test_sharp_rolling_load_is_a_transparent_caution_not_invented_readiness():
    detail = compose_recovery_coach(
        athlete_id=4,
        athlete_name="Paul Farrell",
        progress=_progress(current=60.0),
        week=None,
        checkin=None,
        today=TODAY,
    )

    assert detail.load.change_percent == 50.0
    assert detail.load.status == "Load rose sharply"
    assert any("rose sharply" in item for item in detail.cautions)
    assert detail.schedule.available is False
    assert detail.evidence_confidence == "Moderate"
