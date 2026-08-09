from __future__ import annotations

from dataclasses import dataclass
import datetime

from core.coaching_arbitration import build_coaching_arbitration
from core.next_run import build_next_run_recommendation


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
    if established is None:
        return None

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
        return LiveCoachDecision(
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
        )

    selected_label = family_label(
        arbitration.selected_family
    )

    return LiveCoachDecision(
        athlete_id=athlete_id,
        immediate_label=established.session_family,
        immediate_timing=established.earliest_timing,
        immediate_detail=established.timing_detail,
        key_family=arbitration.selected_family,
        key_label=selected_label,
        key_prescription=arbitration.selected_prescription,
        key_day=arbitration.selected_day,
        confidence=arbitration.confidence,
        confidence_label=arbitration.confidence_label,
        headline=arbitration.headline,
        why=arbitration.evidence,
        safety_notes=arbitration.safety_notes,
        readiness_required=established.readiness_required,
        source="Adaptive Coach + Arbitration",
    )
