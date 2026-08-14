from __future__ import annotations

from dataclasses import dataclass, replace
import datetime

from core.coaching_arbitration import build_coaching_arbitration
from core.live_integration import build_adaptive_coach_proposal
from core.next_run import build_next_run_recommendation
from core.operational_block import OperationalWeek, build_operational_block_week


@dataclass(frozen=True)
class LiveCoachDecision:
    athlete_id: int
    immediate_label: str
    immediate_timing: str
    immediate_detail: str
    key_family: str | None
    key_label: str | None
    key_prescription: str | None
    key_day: str | None
    confidence: float
    confidence_label: str
    headline: str
    why: tuple[str, ...]
    safety_notes: tuple[str, ...]
    readiness_required: bool
    source: str
    model_version: int = 1
    operational_week_number: int | None = None
    operational_status: str | None = None
    operational_completed_miles: float | None = None
    operational_planned_miles: float | None = None


def family_label(family: str | None) -> str | None:
    return {
        "threshold": "Threshold Development",
        "vo2": "VO₂ / Speed Development",
        "speed": "Speed Development",
        "race_pace": "Race-Pace / Sharpening",
        "endurance": "Long Easy / Endurance",
        "recovery": "Recovery Run",
        "easy": "Easy Aerobic",
    }.get(family)



def _day_timing(day_name: str | None, today: datetime.date) -> str:
    if not day_name:
        return "Timing building"

    names = (
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    )

    try:
        target_index = names.index(day_name)
    except ValueError:
        return day_name

    offset = (target_index - today.weekday()) % 7

    if offset == 0:
        return "Today"
    if offset == 1:
        return "Tomorrow"

    return day_name


def _operational_only(
    athlete_id: int,
    operational: OperationalWeek,
) -> LiveCoachDecision:
    next_run = operational.next_run
    confidence = 0.84 if operational.state == "Active" else 0.76
    return LiveCoachDecision(
        athlete_id=athlete_id,
        immediate_label=next_run.session_type,
        immediate_timing=next_run.timing,
        immediate_detail=next_run.detail,
        key_family=(
            next_run.family
            if next_run.family in {"threshold", "quality", "race", "long"}
            else None
        ),
        key_label=(
            next_run.planned_type
            if next_run.family in {"threshold", "quality", "race", "long"}
            else None
        ),
        key_prescription=(
            next_run.detail
            if next_run.family in {"threshold", "quality", "race", "long"}
            else None
        ),
        key_day=next_run.day,
        confidence=confidence,
        confidence_label="Good" if confidence >= 0.80 else "Moderate",
        headline=f"{operational.status}: {operational.headline}.",
        why=(operational.summary, next_run.reason),
        safety_notes=tuple(
            suggestion.detail for suggestion in operational.suggestions
            if suggestion.kind in {"protect", "review", "recover"}
        ),
        readiness_required=next_run.family in {
            "threshold", "quality", "race", "long"
        },
        source=operational.source,
        operational_week_number=operational.week_number,
        operational_status=operational.status,
        operational_completed_miles=operational.completed_miles,
        operational_planned_miles=operational.planned_miles,
    )


def _apply_operational(
    decision: LiveCoachDecision,
    operational: OperationalWeek | None,
) -> LiveCoachDecision:
    if operational is None:
        return decision
    if operational.state != "Active":
        return replace(
            decision,
            why=(
                f"Saved Week {operational.week_number} is {operational.state.lower()}: "
                f"{operational.headline}.",
            ) + decision.why,
            operational_week_number=operational.week_number,
            operational_status=operational.status,
            operational_completed_miles=operational.completed_miles,
            operational_planned_miles=operational.planned_miles,
        )
    next_run = operational.next_run
    hard = next_run.family in {"threshold", "quality", "race", "long"}
    safety = tuple(dict.fromkeys(
        decision.safety_notes + tuple(
            suggestion.detail for suggestion in operational.suggestions
            if suggestion.kind in {"protect", "review", "recover"}
        )
    ))
    headline = (
        f"{next_run.session_type} protects the saved week; "
        f"{next_run.planned_type} remains for review."
        if next_run.adapted
        else f"{next_run.session_type} is next in saved Week {operational.week_number}."
    )
    return replace(
        decision,
        immediate_label=next_run.session_type,
        immediate_timing=next_run.timing,
        immediate_detail=next_run.detail,
        key_family=next_run.family if hard else decision.key_family,
        key_label=next_run.planned_type if hard else decision.key_label,
        key_prescription=next_run.detail if hard else decision.key_prescription,
        key_day=next_run.day if hard else decision.key_day,
        headline=headline,
        why=(operational.summary, next_run.reason) + decision.why,
        safety_notes=safety,
        readiness_required=hard or decision.readiness_required,
        source=f"{operational.source} + Adaptive Coach",
        operational_week_number=operational.week_number,
        operational_status=operational.status,
        operational_completed_miles=operational.completed_miles,
        operational_planned_miles=operational.planned_miles,
    )



def build_live_coach_decision(
    athlete_id: int,
    *,
    today: datetime.date | None = None,
) -> LiveCoachDecision | None:
    today = today or datetime.date.today()

    established = build_next_run_recommendation(
        athlete_id,
        today=today,
    )
    operational = build_operational_block_week(athlete_id, today=today)
    if established is None:
        return (
            _operational_only(athlete_id, operational)
            if operational is not None else None
        )

    established_label = (
        established.next_key_session_family
        or established.session_family
    )

    proposal = build_adaptive_coach_proposal(
        athlete_id,
        today=today,
        existing_label=established_label,
    )

    arbitration = build_coaching_arbitration(
        athlete_id,
        today=today,
        existing_recommendation=established,
    )

    if arbitration is None or not arbitration.ready_for_live:
        key_label = (
            established.next_key_session_family
            or established.session_family
        )
        return _apply_operational(LiveCoachDecision(
            athlete_id=athlete_id,
            immediate_label=established.session_family,
            immediate_timing=established.earliest_timing,
            immediate_detail=established.timing_detail,
            key_family=None,
            key_label=key_label,
            key_prescription=None,
            key_day=established.next_key_session_timing,
            confidence=established.confidence,
            confidence_label=established.confidence_label,
            headline=established.headline,
            why=established.why,
            safety_notes=(
                "Adaptive Coach retained the established recommendation because the arbitration safety gate did not clear.",
            ),
            readiness_required=established.readiness_required,
            source="Established Coach fallback",
        ), operational)

    selected_label = family_label(
        arbitration.selected_family
    )

    immediate_label = (
        family_label(proposal.immediate_family)
        if proposal is not None
        else established.session_family
    )
    immediate_timing = (
        _day_timing(proposal.immediate_day, today)
        if proposal is not None
        else established.earliest_timing
    )
    immediate_detail = (
        proposal.immediate_prescription
        if proposal is not None
        else established.timing_detail
    )

    immediate_headline = (
        (
            f"{proposal.immediate_title} now; "
            f"{selected_label} is the next key workout."
        )
        if (
            proposal is not None
            and selected_label
            and proposal.immediate_family != arbitration.selected_family
        )
        else arbitration.headline
    )

    why = list(arbitration.evidence)

    if proposal is not None:
        why.insert(
            0,
            (
                f"Immediate run from the live adaptive week: "
                f"{proposal.immediate_day} · "
                f"{proposal.immediate_prescription}."
            ),
        )

    return _apply_operational(LiveCoachDecision(
        athlete_id=athlete_id,
        immediate_label=immediate_label or established.session_family,
        immediate_timing=immediate_timing,
        immediate_detail=immediate_detail,
        key_family=arbitration.selected_family,
        key_label=selected_label,
        key_prescription=arbitration.selected_prescription,
        key_day=arbitration.selected_day,
        confidence=arbitration.confidence,
        confidence_label=arbitration.confidence_label,
        headline=immediate_headline,
        why=tuple(why),
        safety_notes=arbitration.safety_notes,
        readiness_required=established.readiness_required,
        source="Adaptive Coach + Arbitration",
    ), operational)
