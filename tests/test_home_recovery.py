import datetime

from core.home_recovery import compose_home_recovery_signal
from core.recovery_coach import RecoveryCheckIn, compose_recovery_coach
from tests.test_recovery_coach import _progress, _week
from tests.test_recovery_health import _health


TODAY = datetime.date(2026, 8, 27)
DEFAULT_WEEK = object()


def _checkin(*, sleep=4, fatigue=2, soreness=1, motivation=4):
    return RecoveryCheckIn(
        athlete_id=1,
        checkin_date=TODAY.isoformat(),
        sleep_quality=sleep,
        fatigue=fatigue,
        soreness=soreness,
        motivation=motivation,
        notes=None,
    )


def _detail(*, checkin=None, health=None, progress=None, week=DEFAULT_WEEK):
    return compose_recovery_coach(
        athlete_id=1,
        athlete_name="Richard Burke",
        progress=progress or _progress(),
        week=_week() if week is DEFAULT_WEEK else week,
        checkin=checkin,
        today=TODAY,
        health=health,
    )


def test_home_recovery_is_grey_when_baseline_and_checkin_are_missing():
    signal = compose_home_recovery_signal(_detail())

    assert signal.level == "grey"
    assert signal.label == "Baseline building"
    assert signal.confidence == "Limited"
    assert "never treated as green" in signal.explanation


def test_stable_health_without_today_checkin_is_amber_not_green():
    signal = compose_home_recovery_signal(_detail(health=_health()))

    assert signal.level == "amber"
    assert signal.headline == "How do you feel today?"
    assert signal.checkin_required is True
    assert any("check-in is missing" in reason for reason in signal.reasons)


def test_stable_health_and_clear_athlete_report_are_green():
    signal = compose_home_recovery_signal(
        _detail(health=_health(), checkin=_checkin())
    )

    assert signal.level == "green"
    assert signal.headline == "Follow today’s plan."
    assert signal.confidence == "Strong"
    assert any("HRV is within" in reason for reason in signal.reasons)


def test_multiple_athlete_reported_flags_are_red_without_a_readiness_score():
    signal = compose_home_recovery_signal(
        _detail(checkin=_checkin(sleep=1, fatigue=5, soreness=4, motivation=2))
    )

    assert signal.level == "red"
    assert signal.headline == "Pause hard training today."
    assert "No single HRV reading" in signal.explanation


def test_two_health_warnings_without_athlete_report_remain_amber():
    signal = compose_home_recovery_signal(
        _detail(
            health=_health(
                hrv_status="Below recent HRV baseline",
                rhr_status="Resting HR is above baseline",
            )
        )
    )

    assert signal.level == "amber"
    assert signal.level != "red"
    assert signal.checkin_required is True


def test_health_warnings_plus_an_athlete_concern_can_turn_red():
    signal = compose_home_recovery_signal(
        _detail(
            checkin=_checkin(fatigue=4),
            health=_health(
                hrv_status="Below recent HRV baseline",
                rhr_status="Resting HR is above baseline",
            ),
        )
    )

    assert signal.level == "red"
    assert any("Fatigue" in reason for reason in signal.reasons)


def test_sharp_training_load_is_an_explainable_amber_signal():
    signal = compose_home_recovery_signal(
        _detail(progress=_progress(current=60.0), week=None)
    )

    assert signal.level == "amber"
    assert any("mileage rose sharply" in reason for reason in signal.reasons)
