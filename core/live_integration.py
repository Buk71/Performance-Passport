"""
Adaptive Coach Live Integration Rehearsal v0.19.6.

Builds one proposed Adaptive Coach answer for Next Run + the next key workout,
then compares it with the existing live answer supplied by the UI.

SAFETY: rehearsal only. Nothing here writes to the database or replaces the
existing live coaching engine.
"""
from __future__ import annotations

from dataclasses import dataclass
import datetime
import re
from functools import lru_cache

from core.adaptive_progression import evaluate_progression
from core.adaptive_weekly_plan import build_adaptive_weekly_plan
from core.coach_validation_suite import build_validation_suite


@dataclass(frozen=True)
class AdaptiveCoachProposal:
    athlete_id: int
    immediate_day: str
    immediate_title: str
    immediate_prescription: str
    immediate_family: str
    key_day: str | None
    key_prescription: str | None
    key_family: str | None
    progression_action: str | None
    progression_headline: str | None
    adaptive_confidence: float
    adaptive_confidence_label: str
    existing_family: str | None
    family_agreement: bool | None
    comparison: str
    release_gate_ready: bool
    takeover_recommended: bool
    safety_status: str
    why: tuple[str, ...]
    model_version: int = 1


def _normalise_family(label: str | None) -> str | None:
    text = str(label or "").lower()
    if "recovery" in text: return "recovery"
    if "easy" in text: return "easy"
    if "threshold" in text: return "threshold"
    if "vo₂" in text or "vo2" in text or "speed" in text: return "vo2"
    if "long" in text or "endurance" in text: return "endurance"
    if "race" in text or "sharpen" in text: return "race_pace"
    return None


def _families_agree(adaptive: str | None, existing: str | None) -> tuple[bool | None, str]:
    if adaptive is None or existing is None:
        return None, "Not enough comparable information yet."
    if adaptive == existing:
        return True, "Same training stimulus."
    if {adaptive, existing} <= {"vo2", "speed", "race_pace"}:
        return True, "Compatible faster/race-specific stimulus."
    return False, "Different training stimulus — review before takeover."


def _next_non_rest(days, today_index: int):
    for offset in range(7):
        day = days[(today_index + offset) % 7]
        if day.session_family not in {"rest", "completed"}:
            return day
    return days[today_index]


def _next_key(days, today_index: int):
    quality = {"threshold", "vo2", "speed", "race_pace"}
    for offset in range(7):
        day = days[(today_index + offset) % 7]
        if day.session_family in quality:
            return day
    return None


def _adjust_for_gate(prescription: str, action: str | None) -> tuple[str, str]:
    if action == "reduce":
        match = re.search(r"(\d+)\s*×\s*(\d+)\s*m", prescription, flags=re.I)
        if match:
            reps = max(3, int(match.group(1)) - 1)
            metres = match.group(2)
            adjusted = re.sub(
                r"\d+\s*×\s*\d+\s*m",
                f"{reps} × {metres}m",
                prescription,
                count=1,
                flags=re.I,
            )
            return adjusted, "Recent execution reduces the proposed session by one repetition."
        return prescription, "Recent execution says do not increase this session."
    if action == "repeat":
        return prescription, "Repeat this stimulus before progressing."
    if action == "small_progress":
        return prescription, "Keep the planned progression modest."
    if action == "progress":
        return prescription, "Recent execution supports the planned progression."
    if action == "recover":
        return prescription, "A recent hard effort means freshness takes priority."
    return prescription, "No extra progression is being added."


@lru_cache(maxsize=1)
def _release_gate() -> bool:
    return bool(build_validation_suite().release_ready)


def build_adaptive_coach_proposal(
    athlete_id: int,
    *,
    today: datetime.date | None = None,
    existing_label: str | None = None,
) -> AdaptiveCoachProposal | None:
    today = today or datetime.date.today()
    plan = build_adaptive_weekly_plan(athlete_id, today=today)

    if not plan.available or not plan.weeks:
        return None

    week = plan.weeks[0]
    immediate = _next_non_rest(week.days, today.weekday())
    key = _next_key(week.days, today.weekday())

    gate = None
    key_prescription = None
    gate_note = None

    if key is not None:
        gate = evaluate_progression(
            athlete_id,
            key.session_family,
            as_of=today,
        )
        key_prescription, gate_note = _adjust_for_gate(
            key.prescription,
            gate.action,
        )

    existing_family = _normalise_family(existing_label)
    adaptive_compare_family = (
        key.session_family
        if key is not None
        else immediate.session_family
    )
    agreement, comparison = _families_agree(
        adaptive_compare_family,
        existing_family,
    )

    release_ready = _release_gate()
    confidence = 0.68
    if release_ready: confidence += 0.12
    if gate is not None:
        confidence += max(min((gate.confidence - 0.50) * 0.25, 0.10), -0.05)
    if agreement is True: confidence += 0.06
    elif agreement is False: confidence -= 0.12
    confidence = max(0.35, min(confidence, 0.92))

    confidence_label = (
        "High" if confidence >= 0.82
        else "Good" if confidence >= 0.68
        else "Developing"
    )

    takeover = (
        release_ready
        and agreement is not False
        and confidence >= 0.72
    )

    why = [
        f"Adaptive block immediate run: {immediate.day_name} · {immediate.prescription}.",
    ]
    if key is not None:
        why.append(
            f"Adaptive block next key workout: {key.day_name} · {key_prescription}."
        )
    if gate is not None:
        why.append(f"Progression gate: {gate.headline}.")
    if gate_note:
        why.append(gate_note)
    why.append(f"Existing/live comparison: {comparison}")
    why.append(
        "Retrospective release validation currently has no blocker."
        if release_ready
        else "Retrospective release validation still has a blocker."
    )

    return AdaptiveCoachProposal(
        athlete_id=athlete_id,
        immediate_day=immediate.day_name,
        immediate_title=immediate.title,
        immediate_prescription=immediate.prescription,
        immediate_family=immediate.session_family,
        key_day=key.day_name if key is not None else None,
        key_prescription=key_prescription,
        key_family=key.session_family if key is not None else None,
        progression_action=gate.action if gate is not None else None,
        progression_headline=gate.headline if gate is not None else None,
        adaptive_confidence=round(confidence, 4),
        adaptive_confidence_label=confidence_label,
        existing_family=existing_family,
        family_agreement=agreement,
        comparison=comparison,
        release_gate_ready=release_ready,
        takeover_recommended=takeover,
        safety_status=(
            "READY FOR LIVE INTEGRATION"
            if takeover
            else "REHEARSAL ONLY"
        ),
        why=tuple(why),
    )
