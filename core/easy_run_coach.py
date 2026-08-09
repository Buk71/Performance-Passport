"""
Easy Run Coach V2.

Easy Run Coach now judges whether an easy run achieved its likely purpose,
not simply whether it was fast.

The coach scores five dimensions:
- Aerobic Control
- Efficiency
- Effort Stability
- Recovery Value
- Execution

It also identifies likely easy-run intent and meaningful achievements:
- Recovery
- Aerobic Builder
- Long Easy
- Heat Adaptation
- Trail Conditioning
- Base Builder

The model remains athlete-relative and transparent. It does not claim that a
single easy run changed race capability by an exact number of seconds.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime
import math
import statistics
from typing import Any, Iterable

from core.actionable_coaching import (
    ActionableRecommendation,
    build_easy_run_opportunities,
    choose_actionable_recommendation,
)
from core.coaching import RunProfile, equivalent_performance
from core.evidence_engine import AthleteEvidenceProfile
from core.race_detection import score_athlete_relative_race_effort


EXCLUDED_TITLE_WORDS = (
    "race",
    "parkrun",
    "threshold",
    "tempo",
    "interval",
    "reps",
    "fartlek",
    "track",
    "vo2",
    "hill rep",
    "time trial",
    "progression",
)

TRAIL_WORDS = (
    "trail",
    "forest",
    "off road",
    "off-road",
    "xc",
    "cross country",
)


@dataclass(frozen=True)
class EasyRunDimensions:
    aerobic_control: float
    efficiency: float
    effort_stability: float
    recovery_value: float
    execution: float

    @property
    def overall(self) -> float:
        return round(
            self.aerobic_control * 0.28
            + self.efficiency * 0.25
            + self.effort_stability * 0.15
            + self.recovery_value * 0.17
            + self.execution * 0.15,
            1,
        )


@dataclass(frozen=True)
class EasyRunAssessment:
    activity_date: str | None
    title: str
    distance_km: float
    actual_pace_s_per_km: float
    equivalent_pace_s_per_km: float
    avg_hr: float
    max_hr: float | None
    efficiency_score: float
    percentile: float
    rank: int
    comparison_count: int
    temperature_c: float | None
    elevation_m: float | None
    run_type: str
    secondary_effect: str | None
    verdict: str
    comment: str
    takeaway: str
    dimensions: EasyRunDimensions
    achievements: tuple[str, ...]
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class EasyRunCoachResult:
    available: bool
    confidence: float
    status: str
    headline: str
    summary: str
    latest: EasyRunAssessment | None
    recent_easy_run_count: int
    historical_easy_run_count: int
    trend_percent: float | None
    trend_label: str
    best_ever: bool
    best_this_year: bool
    strengths: tuple[str, ...]
    limitations: tuple[str, ...]
    actionable_recommendation: ActionableRecommendation | None
    model_version: int = 3


def _safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(number):
        return None

    return number


def _as_date(value: str | None) -> datetime.date | None:
    if not value:
        return None

    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _pace(run: RunProfile) -> float | None:
    distance = _safe_float(run.distance_km)
    moving_time = _safe_float(run.moving_time_seconds)

    if (
        distance is None
        or moving_time is None
        or distance <= 0
        or moving_time <= 0
    ):
        return None

    return moving_time / distance


def _is_trail(run: RunProfile) -> bool:
    title = str(run.title or "").lower()
    return any(word in title for word in TRAIL_WORDS)


def _is_easy_candidate(run: RunProfile) -> bool:
    title = str(run.title or "").lower()

    if any(word in title for word in EXCLUDED_TITLE_WORDS):
        return False

    distance = _safe_float(run.distance_km)

    relative_race = score_athlete_relative_race_effort(
        athlete_id=run.athlete_id,
        title=title,
        distance_km=distance,
        moving_time_s=run.moving_time_seconds,
    )

    if relative_race.is_race_quality:
        return False
    avg_hr = _safe_float(run.avg_hr)
    lt1 = _safe_float(run.lt1_hr)
    pace = _pace(run)

    if (
        distance is None
        or avg_hr is None
        or pace is None
        or distance < 4.0
        or distance > 24.0
        or avg_hr < 80
    ):
        return False

    if lt1 is not None and avg_hr > lt1 * 1.03:
        return False

    return True


def _equivalent_pace(run: RunProfile) -> float:
    pace = _pace(run)

    if pace is None:
        raise ValueError("Run has no usable pace.")

    try:
        result = equivalent_performance(run)
        value = _safe_float(result.equivalent_pace_seconds_per_km)
        return value if value is not None else pace
    except Exception:
        return pace


def _efficiency(run: RunProfile) -> float:
    equivalent_pace = _equivalent_pace(run)
    avg_hr = float(run.avg_hr)
    speed_m_per_s = 1000.0 / equivalent_pace
    return speed_m_per_s / avg_hr


def _percentile(value: float, values: list[float]) -> float:
    if not values:
        return 0.0

    return sum(item <= value for item in values) / len(values)


def _trimmed_mean(values: list[float]) -> float | None:
    if not values:
        return None

    ordered = sorted(values)

    if len(ordered) >= 10:
        trim = max(int(len(ordered) * 0.10), 1)
        ordered = ordered[trim:-trim]

    return statistics.fmean(ordered) if ordered else None


def _score_aerobic_control(run: RunProfile) -> float:
    avg_hr = float(run.avg_hr)
    lt1 = _safe_float(run.lt1_hr)

    if lt1 is None or lt1 <= 0:
        return 70.0

    ratio = avg_hr / lt1

    if ratio <= 0.88:
        return 96.0
    if ratio <= 0.94:
        return 90.0
    if ratio <= 0.98:
        return 82.0
    if ratio <= 1.00:
        return 74.0
    if ratio <= 1.03:
        return 62.0
    return 45.0


def _score_efficiency(percentile: float) -> float:
    return max(35.0, min(55.0 + percentile * 45.0, 100.0))


def _score_effort_stability(run: RunProfile) -> float:
    """
    V2 uses HR reserve within the activity as a cautious stability proxy.

    This is not true cardiac drift because split-level HR is not yet loaded
    into RunProfile. The UI states this limitation clearly.
    """
    avg_hr = _safe_float(run.avg_hr)
    max_hr = _safe_float(run.run_max_hr)

    if avg_hr is None or max_hr is None or max_hr <= 0:
        return 68.0

    spread = max_hr - avg_hr

    if spread <= 8:
        return 94.0
    if spread <= 14:
        return 86.0
    if spread <= 20:
        return 76.0
    if spread <= 28:
        return 64.0
    return 50.0


def _score_recovery_value(run: RunProfile) -> float:
    distance = float(run.distance_km)
    control = _score_aerobic_control(run)

    if distance <= 8:
        duration_factor = 94.0
    elif distance <= 12:
        duration_factor = 84.0
    elif distance <= 16:
        duration_factor = 70.0
    else:
        duration_factor = 58.0

    return round(control * 0.65 + duration_factor * 0.35, 1)


def _score_execution(
    *,
    aerobic_control: float,
    efficiency: float,
    effort_stability: float,
) -> float:
    return round(
        aerobic_control * 0.45
        + effort_stability * 0.30
        + efficiency * 0.25,
        1,
    )


def _run_type(run: RunProfile) -> tuple[str, str | None]:
    distance = float(run.distance_km)
    temperature = _safe_float(run.temperature_c)
    trail = _is_trail(run)
    avg_hr = float(run.avg_hr)
    lt1 = _safe_float(run.lt1_hr)
    hr_ratio = avg_hr / lt1 if lt1 else None

    if distance >= 15:
        primary = "Long Easy"
    elif trail:
        primary = "Trail Conditioning"
    elif temperature is not None and temperature >= 20:
        primary = "Heat Adaptation"
    elif distance <= 8 and hr_ratio is not None and hr_ratio <= 0.91:
        primary = "Recovery"
    elif distance >= 10:
        primary = "Aerobic Builder"
    else:
        primary = "Base Builder"

    secondary = None

    if primary != "Heat Adaptation" and temperature is not None and temperature >= 20:
        secondary = "Heat Adaptation"
    elif primary != "Trail Conditioning" and trail:
        secondary = "Trail Conditioning"
    elif primary not in {"Aerobic Builder", "Long Easy"}:
        secondary = "Aerobic Builder"

    return primary, secondary


def _verdict(score: float) -> str:
    if score >= 92:
        return "Outstanding"
    if score >= 84:
        return "Excellent"
    if score >= 74:
        return "Strong"
    if score >= 62:
        return "Solid"
    return "Developing"


def _category_rank(
    latest_run: RunProfile,
    latest_score: float,
    scored: list[tuple[RunProfile, float]],
    predicate,
) -> tuple[int | None, int]:
    category = [
        score
        for run, score in scored
        if predicate(run)
    ]

    if not predicate(latest_run) or not category:
        return None, len(category)

    ordered = sorted(category, reverse=True)
    return ordered.index(latest_score) + 1, len(category)


def build_easy_run_coach(
    runs: Iterable[RunProfile],
    *,
    reference_date: datetime.date | None = None,
    evidence_profile: AthleteEvidenceProfile | None = None,
) -> EasyRunCoachResult:
    reference_date = reference_date or datetime.date.today()
    candidates = [run for run in runs if _is_easy_candidate(run)]
    candidates.sort(
        key=lambda run: str(run.activity_date or ""),
        reverse=True,
    )

    if not candidates:
        return EasyRunCoachResult(
            available=False,
            confidence=0.0,
            status="building",
            headline="Easy Run Coach is still learning.",
            summary=(
                "No suitable easy runs with usable pace and heart-rate data "
                "were found."
            ),
            latest=None,
            recent_easy_run_count=0,
            historical_easy_run_count=0,
            trend_percent=None,
            trend_label="Still learning",
            best_ever=False,
            best_this_year=False,
            strengths=(),
            limitations=(
                "Easy Run Coach requires genuine easy runs with heart rate.",
            ),
            actionable_recommendation=None,
        )

    scored = [(run, _efficiency(run)) for run in candidates]
    latest_run, latest_score = scored[0]
    all_scores = [score for _, score in scored]
    ordered_scores = sorted(all_scores, reverse=True)
    rank = ordered_scores.index(latest_score) + 1
    percentile = _percentile(latest_score, all_scores)

    recent_scores = []
    prior_scores = []

    for run, score in scored:
        run_date = _as_date(run.activity_date)

        if run_date is None:
            continue

        age_days = (reference_date - run_date).days

        if 0 <= age_days <= 90:
            recent_scores.append(score)
        elif 91 <= age_days <= 180:
            prior_scores.append(score)

    recent_mean = _trimmed_mean(recent_scores)
    prior_mean = _trimmed_mean(prior_scores)
    trend_percent = None

    if (
        recent_mean is not None
        and prior_mean is not None
        and prior_mean > 0
        and len(recent_scores) >= 4
        and len(prior_scores) >= 4
    ):
        trend_percent = ((recent_mean / prior_mean) - 1.0) * 100.0

    if trend_percent is None:
        trend_label = "Building trend"
    elif trend_percent >= 2.0:
        trend_label = "Improving strongly"
    elif trend_percent >= 0.5:
        trend_label = "Improving"
    elif trend_percent <= -2.0:
        trend_label = "Below the previous period"
    elif trend_percent <= -0.5:
        trend_label = "Slightly softer"
    else:
        trend_label = "Stable"

    year_scores = [
        score
        for run, score in scored
        if (
            _as_date(run.activity_date) is not None
            and _as_date(run.activity_date).year == reference_date.year
        )
    ]

    best_ever = rank == 1 and len(scored) >= 5
    best_this_year = (
        latest_score == max(year_scores)
        if year_scores
        else False
    )

    aerobic_control = _score_aerobic_control(latest_run)
    efficiency = _score_efficiency(percentile)
    effort_stability = _score_effort_stability(latest_run)
    recovery_value = _score_recovery_value(latest_run)
    execution = _score_execution(
        aerobic_control=aerobic_control,
        efficiency=efficiency,
        effort_stability=effort_stability,
    )

    dimensions = EasyRunDimensions(
        aerobic_control=round(aerobic_control, 1),
        efficiency=round(efficiency, 1),
        effort_stability=round(effort_stability, 1),
        recovery_value=round(recovery_value, 1),
        execution=round(execution, 1),
    )

    run_type, secondary_effect = _run_type(latest_run)
    actual_pace = _pace(latest_run)
    equivalent_pace = _equivalent_pace(latest_run)
    pace_gain = max(actual_pace - equivalent_pace, 0.0)

    achievements = []

    if best_ever:
        achievements.append("🏆 Best Easy Run Ever")
    elif best_this_year:
        achievements.append("🏆 Best Easy Run This Year")

    heat_rank, heat_count = _category_rank(
        latest_run,
        latest_score,
        scored,
        lambda run: (
            _safe_float(run.temperature_c) is not None
            and float(run.temperature_c) >= 20
        ),
    )
    trail_rank, trail_count = _category_rank(
        latest_run,
        latest_score,
        scored,
        _is_trail,
    )
    recovery_rank, recovery_count = _category_rank(
        latest_run,
        latest_score,
        scored,
        lambda run: _run_type(run)[0] == "Recovery",
    )
    long_rank, long_count = _category_rank(
        latest_run,
        latest_score,
        scored,
        lambda run: float(run.distance_km) >= 15,
    )

    if heat_rank == 1 and heat_count >= 3:
        achievements.append("🔥 Best Hot Easy Run")
    if trail_rank == 1 and trail_count >= 3:
        achievements.append("🌲 Best Trail Easy Run")
    if recovery_rank == 1 and recovery_count >= 3:
        achievements.append("🔋 Best Recovery Run")
    if long_rank == 1 and long_count >= 3:
        achievements.append("🧱 Best Long Easy Run")

    reasons = [
        (
            f"Adjusted aerobic efficiency ranked {rank} of "
            f"{len(scored)} comparable easy runs."
        ),
        (
            "Average heart rate stayed within the athlete's personal "
            "easy-run boundary."
        ),
        (
            f"The likely training purpose was {run_type}."
        ),
    ]

    if pace_gain >= 3:
        reasons.append(
            f"Conditions cost approximately {pace_gain:.0f} sec/km, "
            "so raw pace understated the run."
        )

    overall_score = dimensions.overall
    verdict = _verdict(overall_score)

    if overall_score >= 90:
        comment = (
            f"An outstanding {run_type.lower()} session: controlled, "
            "efficient and low-cost."
        )
        takeaway = (
            "You gained more from restraint than speed today."
        )
    elif overall_score >= 82:
        comment = (
            f"An excellent {run_type.lower()} session that moved the aerobic "
            "system forward without unnecessary fatigue."
        )
        takeaway = (
            "This run quietly strengthened your aerobic profile."
        )
    elif overall_score >= 70:
        comment = (
            f"A strong {run_type.lower()} session that achieved its likely "
            "purpose."
        )
        takeaway = (
            "This was exactly the sort of easy run that supports quality work."
        )
    elif aerobic_control < 65:
        comment = (
            "The run was still classified as easy, but effort drifted close "
            "to the top of the intended range."
        )
        takeaway = (
            "Start a little slower next time and protect the easy-day purpose."
        )
    else:
        comment = (
            "The run was genuinely easy, although it was less efficient than "
            "your stronger historical examples."
        )
        takeaway = (
            "The effort was appropriate; fitness benefit comes from repeating "
            "this consistently."
        )

    confidence = min(
        0.45
        + min(len(scored) / 40.0, 0.35)
        + (0.15 if latest_run.lt1_hr is not None else 0.0),
        0.95,
    )

    assessment = EasyRunAssessment(
        activity_date=latest_run.activity_date,
        title=latest_run.title or "Easy run",
        distance_km=round(float(latest_run.distance_km), 2),
        actual_pace_s_per_km=round(float(actual_pace), 1),
        equivalent_pace_s_per_km=round(float(equivalent_pace), 1),
        avg_hr=round(float(latest_run.avg_hr), 1),
        max_hr=_safe_float(latest_run.run_max_hr),
        efficiency_score=round(latest_score, 6),
        percentile=round(percentile, 4),
        rank=rank,
        comparison_count=len(scored),
        temperature_c=_safe_float(latest_run.temperature_c),
        elevation_m=_safe_float(latest_run.elevation_m),
        run_type=run_type,
        secondary_effect=secondary_effect,
        verdict=verdict,
        comment=comment,
        takeaway=takeaway,
        dimensions=dimensions,
        achievements=tuple(achievements),
        reasons=tuple(reasons),
    )

    strengths = [
        f"{len(scored)} personal easy runs available for comparison",
        f"Latest run sits in the top {(1.0 - percentile) * 100:.0f}% "
        "of comparable history",
        f"Overall easy-run quality score: {overall_score:.0f}/100",
    ]

    if trend_percent is not None:
        strengths.append(
            f"90-day aerobic-efficiency trend: {trend_percent:+.1f}%"
        )

    headline = (
        "Best easy run ever"
        if best_ever
        else f"{verdict} {run_type}"
    )

    opportunities = build_easy_run_opportunities(
        dimensions=dimensions,
        avg_hr=float(latest_run.avg_hr),
        lt1_hr=_safe_float(latest_run.lt1_hr),
        comparison_count=len(scored),
        evidence_profile=evidence_profile,
    )
    actionable_recommendation = choose_actionable_recommendation(
        opportunities,
        overall_current=dimensions.overall,
        source="Easy Run Coach",
    )

    return EasyRunCoachResult(
        available=True,
        confidence=round(confidence, 4),
        status="strong" if confidence >= 0.75 else "steady",
        headline=headline,
        summary=comment,
        latest=assessment,
        recent_easy_run_count=len(recent_scores),
        historical_easy_run_count=len(scored),
        trend_percent=(
            round(trend_percent, 2)
            if trend_percent is not None
            else None
        ),
        trend_label=trend_label,
        best_ever=best_ever,
        best_this_year=best_this_year,
        strengths=tuple(strengths),
        limitations=(
            "Efficiency is a within-athlete pace-to-heart-rate comparison.",
            "Effort Stability currently uses HR spread as a proxy; true "
            "split-level cardiac drift comes next.",
            "Easy Run Coach does not change race capability by a fixed number "
            "of seconds.",
        ),
        actionable_recommendation=actionable_recommendation,
    )
