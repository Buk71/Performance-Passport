"""
Easy Run Coach.

Easy Run Coach answers four questions:

1. Was the latest suitable run genuinely easy?
2. How aerobically efficient was it relative to this athlete's history?
3. Is recent easy-run efficiency improving?
4. Was it notable after allowing for heat and terrain context?

The coach compares the athlete only with their own running history. It does
not reward raw pace alone and does not yet claim that one run changed race
capability by a precise number of seconds.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime
import math
import statistics
from typing import Any, Iterable

from core.coaching import RunProfile, equivalent_performance


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


@dataclass(frozen=True)
class EasyRunAssessment:
    activity_date: str | None
    title: str
    distance_km: float
    actual_pace_s_per_km: float
    equivalent_pace_s_per_km: float
    avg_hr: float
    efficiency_score: float
    percentile: float
    rank: int
    comparison_count: int
    temperature_c: float | None
    elevation_m: float | None
    verdict: str
    comment: str
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
    model_version: int = 1


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


def _is_easy_candidate(run: RunProfile) -> bool:
    title = str(run.title or "").lower()

    if any(word in title for word in EXCLUDED_TITLE_WORDS):
        return False

    distance = _safe_float(run.distance_km)
    avg_hr = _safe_float(run.avg_hr)
    lt1 = _safe_float(run.lt1_hr)
    pace = _pace(run)

    if (
        distance is None
        or avg_hr is None
        or pace is None
        or distance < 4.0
        or distance > 22.0
        or avg_hr < 80
    ):
        return False

    # LT1 is the preferred personal boundary. A small allowance avoids
    # rejecting genuine easy runs because of cardiac drift or wrist-HR noise.
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
    """
    Higher is better.

    Speed per heartbeat is calculated from environmentally adjusted pace.
    This remains a within-athlete comparison and is not a population VO2
    estimate.
    """
    equivalent_pace = _equivalent_pace(run)
    avg_hr = float(run.avg_hr)
    speed_m_per_s = 1000.0 / equivalent_pace
    return speed_m_per_s / avg_hr


def _percentile(value: float, values: list[float]) -> float:
    if not values:
        return 0.0

    below_or_equal = sum(item <= value for item in values)
    return below_or_equal / len(values)


def _trimmed_mean(values: list[float]) -> float | None:
    if not values:
        return None

    ordered = sorted(values)

    if len(ordered) >= 10:
        trim = max(int(len(ordered) * 0.10), 1)
        ordered = ordered[trim:-trim]

    return statistics.fmean(ordered) if ordered else None


def _verdict(percentile: float) -> str:
    if percentile >= 0.98:
        return "Outstanding"
    if percentile >= 0.90:
        return "Excellent"
    if percentile >= 0.75:
        return "Strong"
    if percentile >= 0.45:
        return "Solid"
    return "Easy fitness still building"


def build_easy_run_coach(
    runs: Iterable[RunProfile],
    *,
    reference_date: datetime.date | None = None,
) -> EasyRunCoachResult:
    reference_date = reference_date or datetime.date.today()
    candidates = [
        run for run in runs
        if _is_easy_candidate(run)
    ]
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
        )

    scored = [
        (run, _efficiency(run))
        for run in candidates
    ]
    latest_run, latest_score = scored[0]
    all_scores = [score for _, score in scored]
    ordered_scores = sorted(all_scores, reverse=True)
    rank = ordered_scores.index(latest_score) + 1
    percentile = _percentile(latest_score, all_scores)

    latest_date = _as_date(latest_run.activity_date)
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
        trend_percent = (
            (recent_mean / prior_mean) - 1.0
        ) * 100.0

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
            and _as_date(run.activity_date).year
            == reference_date.year
        )
    ]

    best_ever = rank == 1 and len(scored) >= 5
    best_this_year = (
        latest_score == max(year_scores)
        if year_scores
        else False
    )

    actual_pace = _pace(latest_run)
    equivalent_pace = _equivalent_pace(latest_run)
    pace_gain = max(actual_pace - equivalent_pace, 0.0)

    reasons = [
        (
            f"Aerobic efficiency ranked {rank} of "
            f"{len(scored)} comparable easy runs."
        ),
        (
            "Average heart rate stayed within the athlete's personal "
            "easy-run boundary."
        ),
    ]

    if pace_gain >= 3:
        reasons.append(
            f"Conditions cost approximately {pace_gain:.0f} sec/km, "
            "so raw pace understated the run."
        )

    if best_ever:
        comment = (
            "This is your strongest recorded easy run by adjusted aerobic "
            "efficiency."
        )
    elif percentile >= 0.90:
        comment = (
            "This was one of your best easy runs. It delivered strong "
            "aerobic work without relying on raw pace."
        )
    elif percentile >= 0.60:
        comment = (
            "This easy run did exactly what it needed to do: controlled "
            "effort with useful aerobic stimulus."
        )
    else:
        comment = (
            "The run was genuinely easy, although aerobic efficiency was "
            "below your stronger historical examples."
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
        efficiency_score=round(latest_score, 6),
        percentile=round(percentile, 4),
        rank=rank,
        comparison_count=len(scored),
        temperature_c=_safe_float(latest_run.temperature_c),
        elevation_m=_safe_float(latest_run.elevation_m),
        verdict=_verdict(percentile),
        comment=comment,
        reasons=tuple(reasons),
    )

    strengths = [
        f"{len(scored)} personal easy runs available for comparison",
        f"Latest run sits in the top {(1.0 - percentile) * 100:.0f}% "
        "of comparable history",
    ]

    if trend_percent is not None:
        strengths.append(
            f"90-day aerobic-efficiency trend: {trend_percent:+.1f}%"
        )

    headline = (
        "Best easy run ever"
        if best_ever
        else "One of your strongest easy runs"
        if percentile >= 0.90
        else "A well-controlled easy run"
        if percentile >= 0.45
        else "Easy effort confirmed"
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
            "Wind and exact surface are not yet measured directly.",
            "Easy Run Coach does not yet change race capability by a fixed "
            "number of seconds.",
        ),
    )
