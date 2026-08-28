"""Explainable Recovery Coach traffic light for Lead Coach Home.

The signal summarises existing Recovery Coach evidence.  It is deliberately
not a physiological readiness score and never changes an approved session.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime

from core.recovery_coach import RecoveryCoachDetail, build_recovery_coach_detail


@dataclass(frozen=True)
class HomeRecoverySignal:
    athlete_id: int
    level: str
    label: str
    headline: str
    guidance: str
    reasons: tuple[str, ...]
    confidence: str
    checkin_required: bool
    latest_health_date: str | None
    explanation: str


def empty_home_recovery_signal(athlete_id: int) -> HomeRecoverySignal:
    return HomeRecoverySignal(
        athlete_id=int(athlete_id),
        level="grey",
        label="Baseline building",
        headline="Recovery evidence is still building.",
        guidance=(
            "Follow the plan conservatively and use how you feel while Recovery "
            "Coach builds a current personal baseline."
        ),
        reasons=(
            "No current personal health baseline is available",
            "Today’s athlete check-in is missing",
        ),
        confidence="Limited",
        checkin_required=True,
        latest_health_date=None,
        explanation=(
            "Grey means insufficient or stale evidence; it is never treated as green."
        ),
    )


def _reported_flags(detail: RecoveryCoachDetail) -> tuple[str, ...]:
    checkin = detail.checkin
    if checkin is None:
        return ()
    flags = []
    if checkin.sleep_quality <= 2:
        flags.append("Sleep quality is reported as low")
    if checkin.fatigue >= 4:
        flags.append("Fatigue is reported as high")
    if checkin.soreness >= 4:
        flags.append("Soreness is reported as high")
    if checkin.motivation <= 2:
        flags.append("Motivation is reported as low")
    return tuple(flags)


def _health_flags(detail: RecoveryCoachDetail) -> tuple[str, ...]:
    health = detail.health
    flags = []
    if health.hrv_status == "Below recent HRV baseline":
        flags.append("Seven-day HRV is below the personal baseline")
    if health.resting_hr_status == "Resting HR is above baseline":
        flags.append("Seven-day resting HR is above the personal baseline")
    if health.sleep_status == "Sleep duration is below baseline":
        flags.append("Seven-day sleep duration is below the personal baseline")
    return tuple(flags)


def _training_flags(detail: RecoveryCoachDetail) -> tuple[str, ...]:
    flags = []
    if detail.load.change_percent is not None and detail.load.change_percent >= 20:
        flags.append("Rolling seven-day mileage rose sharply")
    if detail.schedule.status == "Recovery review suggested":
        flags.append("The approved week already suggests a recovery review")
    return tuple(flags)


def _positive_reasons(detail: RecoveryCoachDetail) -> tuple[str, ...]:
    health = detail.health
    reasons = []
    if health.hrv_status == "Within recent HRV range":
        reasons.append("HRV is within the personal range")
    if health.resting_hr_status == "Resting HR is broadly stable":
        reasons.append("Resting HR is broadly stable")
    if health.sleep_status == "Sleep duration is broadly stable":
        reasons.append("Sleep duration is broadly stable")
    if detail.checkin is not None:
        reasons.append("No recovery concern is reported today")
    return tuple(reasons[:3])


def compose_home_recovery_signal(
    detail: RecoveryCoachDetail | None,
    *,
    athlete_id: int | None = None,
) -> HomeRecoverySignal:
    """Classify existing evidence without allowing HRV alone to turn red."""
    if detail is None:
        return empty_home_recovery_signal(int(athlete_id or 0))

    reported = _reported_flags(detail)
    health_flags = _health_flags(detail)
    training_flags = _training_flags(detail)
    checkin_required = detail.checkin is None
    health_ready = (
        detail.health.available
        and detail.health.confidence in {"Strong", "Moderate"}
        and any(
            "building" not in status.lower()
            for status in (
                detail.health.hrv_status,
                detail.health.resting_hr_status,
                detail.health.sleep_status,
            )
        )
    )
    severe_report = bool(
        detail.checkin
        and (detail.checkin.soreness == 5 or len(reported) >= 2)
    )
    combined_red = bool(reported and len(health_flags) >= 2)

    if severe_report or combined_red:
        level = "red"
        label = "Recovery warning"
        headline = "Pause hard training today."
        guidance = (
            "Rest or use gentle recovery work. Persistent, focal or worsening "
            "pain—and symptoms of illness—need appropriate assessment."
        )
        reasons = (*reported, *health_flags, *training_flags)[:3]
    elif reported or health_flags or training_flags or (health_ready and checkin_required):
        level = "amber"
        label = "Check in"
        headline = "How do you feel today?"
        guidance = (
            "Use the evidence as context. Keep easy work easy and adjust or rest "
            "if the concern persists."
        )
        reasons_list = [*reported, *health_flags, *training_flags]
        if checkin_required:
            reasons_list.append("Today’s athlete check-in is missing")
        reasons = tuple(reasons_list[:3])
    elif not health_ready:
        return HomeRecoverySignal(
            athlete_id=detail.athlete_id,
            level="grey",
            label="Baseline building",
            headline="Recovery evidence is still building.",
            guidance=(
                "Follow the plan conservatively and use how you feel while "
                "Recovery Coach builds a current personal baseline."
            ),
            reasons=tuple(
                reason
                for reason in (
                    "Personal health evidence is unavailable or still building",
                    "Today’s athlete check-in is missing" if checkin_required else None,
                )
                if reason is not None
            ),
            confidence="Limited",
            checkin_required=checkin_required,
            latest_health_date=detail.health.latest_date,
            explanation=(
                "Grey means insufficient or stale evidence; it is never treated as green."
            ),
        )
    else:
        level = "green"
        label = "On track"
        headline = "Follow today’s plan."
        guidance = (
            "Current recovery evidence supports the planned session. Continue to "
            "respect unusual fatigue, illness or pain."
        )
        reasons = _positive_reasons(detail)

    confidence = (
        "Strong"
        if detail.health.confidence == "Strong" and detail.checkin is not None
        else "Moderate"
        if detail.health.confidence in {"Strong", "Moderate"} or detail.checkin is not None
        else "Limited"
    )
    return HomeRecoverySignal(
        athlete_id=detail.athlete_id,
        level=level,
        label=label,
        headline=headline,
        guidance=guidance,
        reasons=tuple(reasons),
        confidence=confidence,
        checkin_required=checkin_required,
        latest_health_date=detail.health.latest_date,
        explanation=(
            "The signal combines personal health trends, today’s athlete report, "
            "completed load and the approved week. No single HRV reading can turn it red."
        ),
    )


def build_home_recovery_signal(
    athlete_id: int,
    *,
    today: datetime.date | None = None,
) -> HomeRecoverySignal:
    today = today or datetime.date.today()
    return compose_home_recovery_signal(
        build_recovery_coach_detail(int(athlete_id), today=today),
        athlete_id=int(athlete_id),
    )
