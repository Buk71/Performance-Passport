"""Compose existing coaching services into one auditable Training Coach view.

This module does not decide the next run. Adaptive Coach remains responsible
for that decision, Session Designer remains responsible for the prescription,
and Fuel Planner remains responsible for nutrition guidance.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime

from core.adaptive_coach_live import LiveCoachDecision, build_live_coach_decision
from core.fuel_planner import fuel_guidance_for_demand, training_demand
from core.session_designer import DesignedSession, build_designed_session


@dataclass(frozen=True)
class TrainingAdjustment:
    key: str
    label: str
    direction: str


@dataclass(frozen=True)
class TrainingCoachDetail:
    athlete_id: int
    decision: LiveCoachDecision
    session: DesignedSession | None
    fuel_demand: str
    fuel_focus: str
    fuel_before: str
    fuel_during: str
    fuel_after: str
    adjustments: tuple[TrainingAdjustment, ...]
    model_version: int = 1


def _designer_family(decision: LiveCoachDecision) -> str | None:
    """Translate live-week family names into Session Designer vocabulary."""
    family = str(decision.key_family or "").strip().lower()
    if family in {
        "recovery", "easy", "threshold", "vo2", "speed", "endurance",
        "race_pace",
    }:
        return family
    if family == "long":
        return "endurance"
    if family == "race":
        return "race_pace"

    evidence = " ".join(
        str(value or "")
        for value in (
            decision.key_label,
            decision.key_prescription,
            decision.immediate_label,
        )
    ).lower()
    if "threshold" in evidence or "tempo" in evidence:
        return "threshold"
    if "vo2" in evidence or "vo₂" in evidence:
        return "vo2"
    if "speed" in evidence or "repetition" in evidence:
        return "speed"
    if "long" in evidence or "endurance" in evidence:
        return "endurance"
    if "race" in evidence:
        return "race_pace"
    return None


def _adjustments() -> tuple[TrainingAdjustment, ...]:
    return (
        TrainingAdjustment(
            key="fatigue",
            label="Unusually fatigued",
            direction=(
                "Move the demanding session and keep the day easy or rest. "
                "Do not repay it by placing two hard days together."
            ),
        ),
        TrainingAdjustment(
            key="pain",
            label="Pain or altered movement",
            direction=(
                "Do not substitute another workout. Stop if pain is sharp, "
                "worsening or changes your gait; seek professional advice if it persists."
            ),
        ),
        TrainingAdjustment(
            key="time",
            label="Short of time",
            direction=(
                "Keep the warm-up and cool-down. Reduce main-set volume rather "
                "than increasing pace or removing recovery."
            ),
        ),
    )


def build_training_coach_detail(
    athlete_id: int,
    *,
    today: datetime.date | None = None,
) -> TrainingCoachDetail | None:
    """Build one athlete's Training Coach page from established services."""
    decision = build_live_coach_decision(athlete_id, today=today)
    if decision is None:
        return None

    family = _designer_family(decision)
    main_set = (
        (decision.key_prescription,)
        if decision.key_prescription else None
    )
    session = build_designed_session(
        athlete_id,
        family_override=family,
        main_set_override=main_set,
        timing_override=decision.key_day,
        confidence_override=decision.confidence,
        confidence_label_override=decision.confidence_label,
        why_override=decision.why,
    )

    # Fuel advice belongs to the immediate run at the top of the page. The
    # detailed key session may be several days away and must not make an easy
    # or recovery day look like a quality-fuel day.
    demand_text = " ".join(
        value for value in (
            decision.immediate_label,
            decision.immediate_detail,
        ) if value
    )
    demand = training_demand(demand_text)
    focus, before, during, after = fuel_guidance_for_demand(demand)

    return TrainingCoachDetail(
        athlete_id=athlete_id,
        decision=decision,
        session=session,
        fuel_demand=demand,
        fuel_focus=focus,
        fuel_before=before,
        fuel_during=during,
        fuel_after=after,
        adjustments=_adjustments(),
    )
