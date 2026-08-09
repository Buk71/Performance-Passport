from __future__ import annotations

from dataclasses import dataclass
import datetime

from core.adaptive_weekly_plan import build_adaptive_weekly_plan
from core.live_integration import build_adaptive_coach_proposal
from core.next_run import NextRunRecommendation, build_next_run_recommendation


QUALITY = {"threshold", "vo2", "speed", "race_pace"}


@dataclass(frozen=True)
class ArbitrationDecision:
    athlete_id: int
    existing_family: str | None
    adaptive_family: str | None
    selected_family: str | None
    selected_prescription: str | None
    selected_day: str | None
    decision_source: str
    disagreement_resolved: bool
    complementary_session_preserved: bool
    confidence: float
    confidence_label: str
    headline: str
    summary: str
    hierarchy: tuple[str, ...]
    evidence: tuple[str, ...]
    safety_notes: tuple[str, ...]
    ready_for_live: bool
    model_version: int = 1


def _normalise_family(label: str | None) -> str | None:
    text = str(label or "").lower()
    if "threshold" in text:
        return "threshold"
    if "vo₂" in text or "vo2" in text or "speed" in text:
        return "vo2"
    if "race" in text or "sharpen" in text:
        return "race_pace"
    if "long" in text or "endurance" in text:
        return "endurance"
    if "recovery" in text:
        return "recovery"
    if "easy" in text:
        return "easy"
    return None


def _family_label(family: str | None) -> str:
    return {
        "threshold": "Threshold",
        "vo2": "VO₂ / Speed",
        "speed": "Speed",
        "race_pace": "Race Specific",
        "endurance": "Endurance",
        "recovery": "Recovery",
        "easy": "Easy Aerobic",
    }.get(family, "Building")


def _quality_days(plan) -> list:
    if not plan.available or not plan.weeks:
        return []
    return [
        day
        for day in plan.weeks[0].days
        if day.session_family in QUALITY
    ]


def _complement_preserved(plan, selected_family, opportunity_family):
    if (
        selected_family is None
        or opportunity_family is None
        or selected_family == opportunity_family
    ):
        return False, None

    for day in _quality_days(plan):
        if day.session_family == opportunity_family:
            return True, (
                f"{_family_label(opportunity_family)} is not being ignored: "
                f"it is already scheduled on {day.day_name} "
                f"({day.prescription})."
            )

    return False, None


def _confidence_label(value: float) -> str:
    if value >= 0.84:
        return "High"
    if value >= 0.70:
        return "Good"
    if value >= 0.55:
        return "Developing"
    return "Low"


def build_coaching_arbitration(
    athlete_id: int,
    *,
    today: datetime.date | None = None,
    existing_recommendation: NextRunRecommendation | None = None,
) -> ArbitrationDecision | None:
    today = today or datetime.date.today()

    existing = existing_recommendation or build_next_run_recommendation(
        athlete_id,
        today=today,
    )

    if existing is None:
        return None

    existing_label = (
        existing.next_key_session_family
        or existing.session_family
    )
    existing_family = _normalise_family(existing_label)

    plan = build_adaptive_weekly_plan(
        athlete_id,
        today=today,
    )

    proposal = build_adaptive_coach_proposal(
        athlete_id,
        today=today,
        existing_label=existing_label,
    )

    if proposal is None:
        return None

    adaptive_family = proposal.key_family
    selected_family = adaptive_family
    selected_prescription = proposal.key_prescription
    selected_day = proposal.key_day
    source = "Adaptive block sequencing"
    evidence = []
    safety = []

    disagreement = (
        existing_family is not None
        and adaptive_family is not None
        and existing_family != adaptive_family
    )

    phase = str(existing.block_phase or "").strip().lower()

    if phase == "recovery":
        selected_family = "recovery"
        selected_prescription = "Recovery / easy running only"
        selected_day = None
        source = "Recovery phase override"
        evidence.append(
            "The block is in Recovery, so development opportunities do not override recovery."
        )
    elif phase == "taper":
        selected_family = "race_pace"
        source = "Taper / race-specific override"
        evidence.append(
            "Taper priorities are freshness and race specificity, not chasing the largest weakness."
        )

    preserved, preserved_text = _complement_preserved(
        plan,
        selected_family,
        existing_family,
    )

    if disagreement and phase not in {"recovery", "taper"}:
        if preserved:
            source = "Adaptive sequencing + preserved development opportunity"
            evidence.append(
                f"The existing engine identifies {_family_label(existing_family)} as the current development opportunity."
            )
            evidence.append(
                f"The adaptive block selects {_family_label(adaptive_family)} now because it fits the week's sequence and race build."
            )
            evidence.append(preserved_text)
        elif existing_family in QUALITY and adaptive_family in QUALITY:
            selected_family = existing_family
            selected_prescription = None
            selected_day = None
            source = "Development opportunity safeguard"
            evidence.append(
                f"The engines disagree and the adaptive week does not preserve {_family_label(existing_family)} elsewhere, so PP refuses to discard that weakness."
            )
    elif not disagreement:
        evidence.append(
            "The development-opportunity engine and adaptive block agree on the training stimulus."
        )

    if proposal.progression_headline:
        evidence.append(
            f"Progression gate: {proposal.progression_headline}."
        )

    if proposal.release_gate_ready:
        evidence.append(
            "Retrospective multi-scenario validation currently has no release blocker."
        )
    else:
        safety.append(
            "Retrospective validation still has a blocker."
        )

    if selected_family in QUALITY and existing.readiness_required:
        safety.append(
            "Dedicated Readiness/Fatigue is not connected; quality remains conditional on normal recovery, soreness and energy."
        )

    confidence = proposal.adaptive_confidence

    if not disagreement:
        confidence += 0.05
    elif preserved:
        confidence += 0.06
    else:
        confidence -= 0.08

    if source in {
        "Recovery phase override",
        "Taper / race-specific override",
    }:
        confidence += 0.04

    confidence = max(0.35, min(confidence, 0.94))

    ready = (
        proposal.release_gate_ready
        and confidence >= 0.72
        and source != "Development opportunity safeguard"
    )

    if selected_family is None:
        headline = "No key quality session needs forcing yet."
    elif disagreement and preserved:
        headline = (
            f"Use {_family_label(selected_family)} now — "
            f"preserve {_family_label(existing_family)} later in the week."
        )
    elif disagreement:
        headline = (
            f"Arbitration selects {_family_label(selected_family)}."
        )
    else:
        headline = (
            f"Both coaching systems support {_family_label(selected_family)}."
        )

    return ArbitrationDecision(
        athlete_id=athlete_id,
        existing_family=existing_family,
        adaptive_family=adaptive_family,
        selected_family=selected_family,
        selected_prescription=selected_prescription,
        selected_day=selected_day,
        decision_source=source,
        disagreement_resolved=(
            disagreement
            and source != "Development opportunity safeguard"
        ),
        complementary_session_preserved=preserved,
        confidence=round(confidence, 4),
        confidence_label=_confidence_label(confidence),
        headline=headline,
        summary=(
            "PP resolves coaching signals using the training block as a sequence, "
            "rather than assuming the biggest weakness must always be trained next."
        ),
        hierarchy=(
            "1 · Safety / recovery",
            "2 · Goal and block phase",
            "3 · Weekly stimulus sequencing",
            "4 · Current development opportunity",
            "5 · Personal historical learning",
            "6 · Progression evidence",
        ),
        evidence=tuple(evidence),
        safety_notes=tuple(safety),
        ready_for_live=ready,
    )
