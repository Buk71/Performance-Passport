import datetime

from tests.test_recovery_coach import _progress, _week
from core.recovery_coach import RecoveryCheckIn, compose_recovery_coach
from ui.recovery_coach import build_recovery_coach_html


TODAY = datetime.date(2026, 8, 27)


def _detail(athlete_id=1, name="Richard Burke", checkin=None):
    return compose_recovery_coach(
        athlete_id=athlete_id,
        athlete_name=name,
        progress=_progress(),
        week=_week(),
        checkin=checkin,
        today=TODAY,
    )


def test_recovery_coach_page_has_the_complete_evidence_backed_journey():
    markup = build_recovery_coach_html(_detail())
    for expected in (
        "Recovery Coach · Richard",
        "Today’s check-in",
        "Rolling seven-day load",
        "Recovery support",
        "Long-run durability",
        "How do you feel today?",
        "Recovery has a place in the plan.",
        "What supports recovery",
        "What to watch",
        "Recovery priorities",
        "Connect the athlete’s personal recovery baseline.",
        "Gentle mobility",
        "Post-run reset",
        "Lower-leg mobility",
        "Rest-day yoga flow",
        "Training balance, not invented physiology.",
        "No hidden readiness score",
    ):
        assert expected in markup
    assert "Threshold" in markup
    assert markup.count('class="rc-day') == 7
    assert markup.count('class="rc-mobility-card"') == 3
    assert "color:#fff!important" in markup


def test_recovery_coach_escapes_athlete_report_and_never_crosses_athletes():
    checkin = RecoveryCheckIn(
        athlete_id=3,
        checkin_date=TODAY.isoformat(),
        sleep_quality=2,
        fatigue=4,
        soreness=3,
        motivation=3,
        notes="<script>alert(1)</script>",
    )
    jo = build_recovery_coach_html(_detail(3, "Joanne Burke", checkin))
    richard = build_recovery_coach_html(_detail())

    assert "Joanne" in jo
    assert "Richard" not in jo
    assert "<script>" not in jo
    assert jo != richard
