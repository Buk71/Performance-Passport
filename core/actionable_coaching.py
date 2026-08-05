"""
Actionable Coaching Engine.

This shared engine converts coach scores and athlete evidence into one clear,
defensible recommendation.

Principles:
- one recommendation, not a checklist;
- evidence before opinion;
- athlete-specific where data supports it;
- no advice from unavailable metrics;
- improvement is expressed as training-quality potential, not guaranteed
  race-time gain;
- strong sessions may correctly produce "change very little".

Easy Run Coach is the first client. Threshold, Endurance, Speed and Race
coaches can later submit opportunities using the same contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from core.evidence_engine import AthleteEvidenceProfile


@dataclass(frozen=True)
class CoachingOpportunity:
    key: str
    label: str
    current_score: float
    potential_score: float
    confidence: float
    recommendation: str
    reason: str
    evidence: tuple[str, ...]
    required_metrics: tuple[str, ...]
    impact_label: str

    @property
    def gain(self) -> float:
        return round(
            max(self.potential_score - self.current_score, 0.0),
            1,
        )


@dataclass(frozen=True)
class ActionableRecommendation:
    available: bool
    category: str
    headline: str
    recommendation: str
    reason: str
    current_score: float
    potential_score: float
    overall_current: float
    overall_potential: float
    expected_gain: float
    confidence: float
    confidence_label: str
    impact_label: str
    evidence: tuple[str, ...]
    limitations: tuple[str, ...]
    source: str
    model_version: int = 1


def _metric_status(
    profile: AthleteEvidenceProfile | None,
    key: str,
) -> str:
    if profile is None:
        return "unavailable"

    for metric in profile.metrics:
        if metric.key == key:
            return metric.status

    return "unavailable"


def _metric_ready(
    profile: AthleteEvidenceProfile | None,
    key: str,
    *,
    allow_developing: bool = True,
) -> bool:
    status = _metric_status(profile, key)

    if status == "available":
        return True

    return allow_developing and status == "developing"


def _confidence_label(confidence: float) -> str:
    if confidence >= 0.85:
        return "Very strong evidence"
    if confidence >= 0.70:
        return "Strong evidence"
    if confidence >= 0.50:
        return "Moderate evidence"
    if confidence > 0:
        return "Early evidence"
    return "Insufficient evidence"


def _impact_label(gain: float) -> str:
    if gain >= 15:
        return "Major opportunity"
    if gain >= 8:
        return "Meaningful gain"
    if gain >= 4:
        return "Small improvement"
    return "Fine tuning"


def _potential(current: float) -> float:
    """
    Improvement potential is deliberately capped.

    The engine should not imply that one execution change can turn every
    dimension into a perfect 100.
    """
    gap = 100.0 - current

    if current >= 92:
        improvement = min(gap, 3.0)
    elif current >= 84:
        improvement = min(gap, 6.0)
    elif current >= 72:
        improvement = min(gap, 10.0)
    else:
        improvement = min(gap, 14.0)

    return round(current + improvement, 1)


def build_easy_run_opportunities(
    *,
    dimensions: Any,
    avg_hr: float,
    lt1_hr: float | None,
    comparison_count: int,
    evidence_profile: AthleteEvidenceProfile | None,
) -> tuple[CoachingOpportunity, ...]:
    opportunities = []

    base_confidence = min(
        0.45 + comparison_count / 80.0,
        0.90,
    )

    aerobic_score = float(dimensions.aerobic_control)
    efficiency_score = float(dimensions.efficiency)
    stability_score = float(dimensions.effort_stability)
    recovery_score = float(dimensions.recovery_value)
    execution_score = float(dimensions.execution)

    if lt1_hr is not None and lt1_hr > 0:
        hr_difference = avg_hr - lt1_hr
        if hr_difference > 0:
            recommendation = (
                f"Keep average heart rate around "
                f"{max(int(round(lt1_hr - 2)), 1)}–"
                f"{int(round(lt1_hr))} bpm next time."
            )
            reason = (
                "The run sat at or above the top of your personal easy range, "
                "which reduced aerobic control and recovery value."
            )
        elif avg_hr < lt1_hr * 0.84 and aerobic_score >= 90:
            recommendation = (
                f"If the aim is an aerobic builder rather than recovery, "
                f"allow heart rate to rise gradually towards "
                f"{int(round(lt1_hr * 0.88))}–"
                f"{int(round(lt1_hr * 0.94))} bpm."
            )
            reason = (
                "The effort was exceptionally controlled. A slightly fuller "
                "aerobic stimulus may add benefit when recovery is not the "
                "primary purpose."
            )
        else:
            recommendation = (
                "Keep the opening effort patient and stay within the same "
                "personal easy-heart-rate range."
            )
            reason = (
                "Aerobic control was already good; the opportunity is mainly "
                "to reproduce it consistently."
            )

        opportunities.append(
            CoachingOpportunity(
                key="aerobic_control",
                label="Aerobic control",
                current_score=aerobic_score,
                potential_score=_potential(aerobic_score),
                confidence=min(base_confidence + 0.05, 0.95),
                recommendation=recommendation,
                reason=reason,
                evidence=(
                    f"Average heart rate: {avg_hr:.0f} bpm",
                    f"Personal LT1 boundary: {lt1_hr:.0f} bpm",
                    f"Aerobic-control score: {aerobic_score:.0f}/100",
                ),
                required_metrics=("average_hr",),
                impact_label=_impact_label(
                    _potential(aerobic_score) - aerobic_score
                ),
            )
        )

    if _metric_ready(evidence_profile, "temperature"):
        efficiency_reason = (
            "Adjusted aerobic efficiency was the clearest remaining area "
            "with room to improve after allowing for available conditions."
        )
        efficiency_evidence = (
            f"Efficiency score: {efficiency_score:.0f}/100",
            f"Compared with {comparison_count} personal easy runs",
            "Temperature and elevation context available",
        )
    else:
        efficiency_reason = (
            "Aerobic efficiency has room to improve, although environmental "
            "evidence is incomplete."
        )
        efficiency_evidence = (
            f"Efficiency score: {efficiency_score:.0f}/100",
            f"Compared with {comparison_count} personal easy runs",
        )

    opportunities.append(
        CoachingOpportunity(
            key="efficiency",
            label="Aerobic efficiency",
            current_score=efficiency_score,
            potential_score=_potential(efficiency_score),
            confidence=base_confidence,
            recommendation=(
                "Run by relaxed effort rather than chasing pace, especially "
                "on climbs and into changing conditions."
            ),
            reason=efficiency_reason,
            evidence=efficiency_evidence,
            required_metrics=(
                "average_hr",
                "moving_time",
                "temperature",
                "elevation",
            ),
            impact_label=_impact_label(
                _potential(efficiency_score) - efficiency_score
            ),
        )
    )

    # V1 cannot honestly claim true pace consistency or stop analysis without
    # the relevant evidence. HR spread is allowed only as cautious support.
    stability_metrics = []

    if _metric_ready(evidence_profile, "pace_variability"):
        stability_metrics.append("pace_variability")

    if _metric_ready(evidence_profile, "stop_count"):
        stability_metrics.append("stop_count")

    if stability_metrics:
        recommendation = (
            "Keep effort smoother and minimise unnecessary interruptions "
            "where safe."
        )
        reason = (
            "Pace or continuity evidence shows more variation than would be "
            "ideal for this run's purpose."
        )
        evidence = (
            f"Effort-stability score: {stability_score:.0f}/100",
            "Direct pace/continuity evidence is available",
        )
        confidence = min(base_confidence + 0.05, 0.92)
    else:
        recommendation = (
            "Aim for the same calm effort throughout and let pace change "
            "naturally with the terrain."
        )
        reason = (
            "Effort stability is the opportunity, but direct pace-variation "
            "and stop evidence are not yet available, so the advice remains "
            "cautious."
        )
        evidence = (
            f"Effort-stability proxy: {stability_score:.0f}/100",
            "Direct pace variability and stop metrics are still building",
        )
        confidence = min(base_confidence, 0.62)

    opportunities.append(
        CoachingOpportunity(
            key="effort_stability",
            label="Effort stability",
            current_score=stability_score,
            potential_score=_potential(stability_score),
            confidence=confidence,
            recommendation=recommendation,
            reason=reason,
            evidence=evidence,
            required_metrics=tuple(stability_metrics),
            impact_label=_impact_label(
                _potential(stability_score) - stability_score
            ),
        )
    )

    opportunities.append(
        CoachingOpportunity(
            key="recovery_value",
            label="Recovery value",
            current_score=recovery_score,
            potential_score=_potential(recovery_score),
            confidence=min(base_confidence, 0.78),
            recommendation=(
                "Protect the easy-day purpose: finish feeling that you could "
                "comfortably continue rather than adding pace late."
            ),
            reason=(
                "Lower physiological cost would improve recovery value without "
                "removing the aerobic benefit."
            ),
            evidence=(
                f"Recovery-value score: {recovery_score:.0f}/100",
                f"Average heart rate: {avg_hr:.0f} bpm",
            ),
            required_metrics=("average_hr", "moving_time"),
            impact_label=_impact_label(
                _potential(recovery_score) - recovery_score
            ),
        )
    )

    execution_direct = (
        _metric_ready(evidence_profile, "pace_variability")
        or _metric_ready(evidence_profile, "stop_count")
        or _metric_ready(evidence_profile, "moving_percent")
    )

    opportunities.append(
        CoachingOpportunity(
            key="execution",
            label="Session execution",
            current_score=execution_score,
            potential_score=_potential(execution_score),
            confidence=(
                min(base_confidence + 0.05, 0.90)
                if execution_direct
                else min(base_confidence, 0.65)
            ),
            recommendation=(
                "Repeat the run with one simple target: keep the purpose easy "
                "from the first minute to the last."
            ),
            reason=(
                "Session execution summarises how well control, efficiency and "
                "stability combined."
            ),
            evidence=(
                f"Session-execution score: {execution_score:.0f}/100",
                (
                    "Direct continuity evidence available"
                    if execution_direct
                    else "Direct continuity evidence still building"
                ),
            ),
            required_metrics=("average_hr",),
            impact_label=_impact_label(
                _potential(execution_score) - execution_score
            ),
        )
    )

    return tuple(opportunities)


def choose_actionable_recommendation(
    opportunities: Iterable[CoachingOpportunity],
    *,
    overall_current: float,
    source: str,
) -> ActionableRecommendation:
    candidates = [
        opportunity
        for opportunity in opportunities
        if opportunity.confidence >= 0.40
    ]

    if not candidates:
        return ActionableRecommendation(
            available=False,
            category="Still learning",
            headline="No evidence-backed change yet",
            recommendation=(
                "Repeat the session as planned while the coach gathers more "
                "evidence."
            ),
            reason=(
                "No opportunity met the minimum evidence threshold."
            ),
            current_score=overall_current,
            potential_score=overall_current,
            overall_current=overall_current,
            overall_potential=overall_current,
            expected_gain=0.0,
            confidence=0.0,
            confidence_label="Insufficient evidence",
            impact_label="Still learning",
            evidence=(),
            limitations=(
                "The coach will not invent advice from unavailable metrics.",
            ),
            source=source,
        )

    # Rank by expected gain tempered by evidence confidence.
    chosen = max(
        candidates,
        key=lambda item: (
            item.gain * item.confidence,
            item.confidence,
        ),
    )

    weighted_gain = chosen.gain * 0.35
    overall_potential = min(
        overall_current + weighted_gain,
        100.0,
    )

    if overall_current >= 92 and chosen.gain <= 4:
        headline = "Very little needs changing"
        recommendation = (
            "Keep the same approach. The best improvement is consistency: "
            "repeat this execution rather than trying to make the run faster."
        )
        reason = (
            "All major easy-run dimensions were already close to their useful "
            "ceiling."
        )
        impact_label = "Fine tuning"
    else:
        headline = f"Biggest opportunity: {chosen.label}"
        recommendation = chosen.recommendation
        reason = chosen.reason
        impact_label = chosen.impact_label

    return ActionableRecommendation(
        available=True,
        category=chosen.label,
        headline=headline,
        recommendation=recommendation,
        reason=reason,
        current_score=chosen.current_score,
        potential_score=chosen.potential_score,
        overall_current=round(overall_current, 1),
        overall_potential=round(overall_potential, 1),
        expected_gain=chosen.gain,
        confidence=round(chosen.confidence, 4),
        confidence_label=_confidence_label(chosen.confidence),
        impact_label=impact_label,
        evidence=chosen.evidence,
        limitations=(
            "Expected gains refer to modelled training quality, not guaranteed "
            "race performance.",
            "The recommendation is limited to evidence currently available "
            "for this athlete.",
        ),
        source=source,
    )
