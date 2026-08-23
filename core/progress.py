"""Longitudinal Progress Foundation built from real athlete evidence.

Progress keeps distinct questions distinct:
- aerobic efficiency is conditions-adjusted and heart-rate relative;
- training rhythm describes consistency, not fitness;
- race results remain factual elapsed-time evidence;
- threshold and durability only claim a trend with comparable samples.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime
import json
import math
import statistics
from typing import Any

from core.activity_reliability import has_reliable_distance_and_pace
from core.coaching import RunProfile, is_easy_baseline_candidate
from core.database import (
    get_athlete_sport_roles,
    get_connection,
    get_effective_activity_heart_rate,
    get_effective_athlete_thresholds,
)
from core.environment_profile import build_personal_environment_profile
from core.performance_backtracking import build_performance_anchors
from core.performance_recognition import (
    build_recognition_index,
    environment_adjusted_pace,
    recognition_key,
)


@dataclass(frozen=True)
class TrendPoint:
    label: str
    value: float | None
    sample_size: int


@dataclass(frozen=True)
class AerobicProgress:
    available: bool
    status: str
    trend_percent: float | None
    confidence: str
    sample_size: int
    recent_sample_size: int
    comparison_sample_size: int
    adjusted_run_count: int
    personalised_run_count: int
    points: tuple[TrendPoint, ...]
    summary: str


@dataclass(frozen=True)
class RhythmPoint:
    label: str
    active_days: int
    moving_hours: float
    reliable_miles: float
    easy_miles: float
    long_miles: float
    quality_miles: float
    other_miles: float


@dataclass(frozen=True)
class TrainingRhythm:
    status: str
    confidence: str
    active_days_per_week: float
    moving_hours_per_week: float
    reliable_miles_per_week: float
    prior_reliable_miles_per_week: float
    change_percent: float | None
    unreliable_activity_count: int
    points: tuple[RhythmPoint, ...]
    summary: str


@dataclass(frozen=True)
class RaceEventProgress:
    key: str
    label: str
    all_time_best_s: float | None
    last_12m_best_s: float | None
    recent_best_s: float | None
    prior_best_s: float | None
    change_s: float | None
    evidence_count: int


@dataclass(frozen=True)
class RaceProgress:
    available: bool
    status: str
    confidence: str
    events: tuple[RaceEventProgress, ...]
    evidence_count: int
    summary: str


@dataclass(frozen=True)
class ThresholdProgress:
    available: bool
    status: str
    confidence: str
    current_pace_s_per_km: float | None
    standard_equivalent_fast_s_per_km: float | None
    standard_equivalent_slow_s_per_km: float | None
    current_conditions: str | None
    current_date: str | None
    trend_seconds_per_km: float | None
    recent_sample_size: int
    comparison_sample_size: int
    total_sample_size: int
    summary: str


@dataclass(frozen=True)
class DurabilityProgress:
    available: bool
    status: str
    confidence: str
    recent_decoupling_percent: float | None
    prior_decoupling_percent: float | None
    change_percent: float | None
    recent_sample_size: int
    comparison_sample_size: int
    total_sample_size: int
    interrupted_exclusion_count: int
    summary: str


@dataclass(frozen=True)
class ProgressSummary:
    athlete_id: int
    athlete_name: str
    reference_date: str
    verdict: str
    headline: str
    confidence: str
    summary: str
    aerobic: AerobicProgress
    rhythm: TrainingRhythm
    race: RaceProgress
    threshold: ThresholdProgress
    durability: DurabilityProgress
    evidence_notes: tuple[str, ...]
    model_version: int = 1


@dataclass(frozen=True)
class _ProgressRun:
    activity_id: int
    date: datetime.date
    profile: RunProfile
    elapsed_time_s: float | None
    wind_speed: float | None
    raw_json: str | None
    pace_reliable: bool


def _safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _date(value: Any) -> datetime.date | None:
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _distance_km(value: Any) -> float | None:
    distance = _safe_float(value)
    if distance is None or distance <= 0:
        return None
    return distance / 1000.0 if distance > 250.0 else distance


def _trimmed_mean(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) >= 10:
        trim = max(int(len(ordered) * 0.10), 1)
        ordered = ordered[trim:-trim]
    return statistics.fmean(ordered) if ordered else None


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _month_start(value: datetime.date) -> datetime.date:
    return value.replace(day=1)


def _add_months(value: datetime.date, months: int) -> datetime.date:
    index = value.year * 12 + value.month - 1 + months
    return datetime.date(index // 12, index % 12 + 1, 1)


def _load_runs(athlete_id: int) -> tuple[str, list[_ProgressRun]]:
    thresholds = get_effective_athlete_thresholds(athlete_id)
    running_ids = {
        str(sport_id)
        for sport_id, role in get_athlete_sport_roles(athlete_id).items()
        if role == "running"
    }
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        "SELECT first_name, last_name FROM athletes WHERE id = ?",
        (athlete_id,),
    )
    athlete = cursor.fetchone()
    cursor.execute(
        """
        SELECT id, activity_date, title, sport_id, distance_m,
               moving_time_s, elapsed_time_s, avg_hr, max_hr,
               elevation_up_m, temperature_c, humidity, wind_speed,
               route_name, raw_json
        FROM activities
        WHERE athlete_id = ?
        ORDER BY activity_date, id
        """,
        (athlete_id,),
    )
    rows = cursor.fetchall()
    connection.close()

    name = (
        f"{athlete[0] or ''} {athlete[1] or ''}".strip()
        if athlete is not None
        else "Athlete"
    )
    results = []
    for row in rows:
        if str(row[3] or "") not in running_ids:
            continue
        run_date = _date(row[1])
        distance = _distance_km(row[4])
        moving = _safe_float(row[5])
        if run_date is None or distance is None or moving is None or moving <= 0:
            continue
        profile = RunProfile(
            athlete_id=athlete_id,
            activity_date=run_date.isoformat(),
            title=row[2],
            sport_id=row[3],
            distance_km=distance,
            moving_time_seconds=moving,
            avg_hr=_safe_float(get_effective_activity_heart_rate(athlete_id, row[0], row[7])),
            run_max_hr=_safe_float(row[8]),
            elevation_m=_safe_float(row[9]),
            temperature_c=_safe_float(row[10]),
            humidity=_safe_float(row[11]),
            lt1_hr=thresholds.get("lt1_hr"),
            lt2_hr=thresholds.get("lt2_hr"),
            athlete_max_hr=thresholds.get("athlete_max_hr"),
        )
        results.append(
            _ProgressRun(
                activity_id=int(row[0]),
                date=run_date,
                profile=profile,
                elapsed_time_s=_safe_float(row[6]),
                wind_speed=_safe_float(row[12]),
                raw_json=row[14],
                pace_reliable=has_reliable_distance_and_pace(
                    title=row[2],
                    sport_id=str(row[3] or ""),
                    route_name=row[13],
                    raw_json_text=row[14],
                ),
            )
        )
    return name, results


def _aerobic_progress(
    runs: list[_ProgressRun],
    reference_date: datetime.date,
    personal_profile,
) -> AerobicProgress:
    cutoff = reference_date - datetime.timedelta(days=365)
    scored: list[tuple[datetime.date, float]] = []
    adjusted_count = 0
    personalised_count = 0

    for item in runs:
        run = item.profile
        if not cutoff <= item.date <= reference_date or not item.pace_reliable:
            continue
        if not is_easy_baseline_candidate(run):
            continue
        if not run.distance_km or run.distance_km < 4.0 or not run.avg_hr:
            continue
        adjustment = environment_adjusted_pace(
            run,
            wind_speed=item.wind_speed,
            personal_profile=personal_profile,
        )
        if adjustment.adjusted_pace_s_per_km <= 0:
            continue
        efficiency = (
            (1000.0 / adjustment.adjusted_pace_s_per_km)
            / float(run.avg_hr)
        )
        scored.append((item.date, efficiency))
        adjusted_count += adjustment.total_penalty_s_per_km > 0.5
        personalised_count += bool(adjustment.personalised_factors)

    recent = [
        value for date, value in scored
        if 0 <= (reference_date - date).days <= 90
    ]
    opening = [
        value for date, value in scored
        if 275 <= (reference_date - date).days <= 365
    ]
    recent_mean = _trimmed_mean(recent)
    opening_mean = _trimmed_mean(opening)
    trend = None
    if (
        recent_mean is not None
        and opening_mean is not None
        and opening_mean > 0
        and len(recent) >= 4
        and len(opening) >= 4
    ):
        trend = ((recent_mean / opening_mean) - 1.0) * 100.0

    current_month = _month_start(reference_date)
    month_starts = [_add_months(current_month, offset) for offset in range(-11, 1)]
    raw_months: list[tuple[str, float | None, int]] = []
    for month in month_starts:
        next_month = _add_months(month, 1)
        values = [value for date, value in scored if month <= date < next_month]
        raw_months.append((month.strftime("%b"), _trimmed_mean(values), len(values)))
    baseline = next((value for _label, value, _count in raw_months if value), None)
    points = tuple(
        TrendPoint(
            label=label,
            value=round(value / baseline * 100.0, 2)
            if value is not None and baseline
            else None,
            sample_size=count,
        )
        for label, value, count in raw_months
    )

    if trend is None:
        status = "Trend building"
    elif trend >= 2.0:
        status = "Improving strongly"
    elif trend >= 0.5:
        status = "Improving"
    elif trend <= -2.0:
        status = "Below the opening period"
    elif trend <= -0.5:
        status = "Slightly softer"
    else:
        status = "Stable"
    confidence = (
        "Strong"
        if len(scored) >= 40 and len(recent) >= 8 and len(opening) >= 8
        else "Moderate"
        if len(scored) >= 16 and len(recent) >= 4 and len(opening) >= 4
        else "Limited"
    )
    summary = (
        f"Recent adjusted easy-run efficiency is {trend:+.1f}% versus the "
        "opening 90 days of the last year."
        if trend is not None
        else "More comparable easy runs are needed at both ends of the year."
    )
    return AerobicProgress(
        available=bool(scored),
        status=status,
        trend_percent=round(trend, 2) if trend is not None else None,
        confidence=confidence,
        sample_size=len(scored),
        recent_sample_size=len(recent),
        comparison_sample_size=len(opening),
        adjusted_run_count=adjusted_count,
        personalised_run_count=personalised_count,
        points=points,
        summary=summary,
    )


def _training_rhythm(
    runs: list[_ProgressRun],
    reference_date: datetime.date,
    recognition: dict,
) -> TrainingRhythm:
    points = []
    for offset in range(11, -1, -1):
        end = reference_date - datetime.timedelta(days=offset * 7)
        start = end - datetime.timedelta(days=6)
        selected = [item for item in runs if start <= item.date <= end]
        category_miles = {
            "easy": 0.0,
            "long": 0.0,
            "quality": 0.0,
            "other": 0.0,
        }
        for item in selected:
            if not item.pace_reliable:
                continue
            miles = (item.profile.distance_km or 0.0) / 1.609344
            result = recognition.get(recognition_key(item.profile))
            category = result.category_key if result is not None else None
            if category in {"easy", "recovery", "steady"}:
                category_miles["easy"] += miles
            elif category == "long_easy":
                category_miles["long"] += miles
            elif category in {
                "threshold", "workout", "vo2", "speed", "race"
            }:
                category_miles["quality"] += miles
            else:
                category_miles["other"] += miles
        points.append(
            RhythmPoint(
                label=end.strftime("%-d %b"),
                active_days=len({item.date for item in selected}),
                moving_hours=round(
                    sum(item.profile.moving_time_seconds or 0 for item in selected)
                    / 3600.0,
                    2,
                ),
                reliable_miles=round(
                    sum(
                        item.profile.distance_km or 0
                        for item in selected
                        if item.pace_reliable
                    ) / 1.609344,
                    2,
                ),
                easy_miles=round(category_miles["easy"], 2),
                long_miles=round(category_miles["long"], 2),
                quality_miles=round(category_miles["quality"], 2),
                other_miles=round(category_miles["other"], 2),
            )
        )
    prior = points[:6]
    recent = points[6:]
    average = lambda values: statistics.fmean(values) if values else 0.0
    recent_miles = average([point.reliable_miles for point in recent])
    prior_miles = average([point.reliable_miles for point in prior])
    change = (
        ((recent_miles / prior_miles) - 1.0) * 100.0
        if prior_miles > 0
        else None
    )
    if change is None:
        status = "Rhythm building"
    elif change >= 10:
        status = "Building volume"
    elif change <= -15:
        status = "Reduced volume"
    else:
        status = "Consistent base"
    cutoff = reference_date - datetime.timedelta(days=83)
    unreliable_count = sum(
        not item.pace_reliable
        for item in runs
        if cutoff <= item.date <= reference_date
    )
    active = average([point.active_days for point in recent])
    hours = average([point.moving_hours for point in recent])
    confidence = "Strong" if sum(point.active_days > 0 for point in points) >= 10 else "Moderate"
    return TrainingRhythm(
        status=status,
        confidence=confidence,
        active_days_per_week=round(active, 1),
        moving_hours_per_week=round(hours, 1),
        reliable_miles_per_week=round(recent_miles, 1),
        prior_reliable_miles_per_week=round(prior_miles, 1),
        change_percent=round(change, 1) if change is not None else None,
        unreliable_activity_count=unreliable_count,
        points=tuple(points),
        summary=(
            f"The latest six weeks average {active:.1f} running days, "
            f"{hours:.1f} hours and {recent_miles:.1f} reliable miles per week."
        ),
    )


def _race_progress(
    athlete_id: int,
    reference_date: datetime.date,
) -> RaceProgress:
    anchors = [
        item for item in build_performance_anchors(athlete_id)
        if item.confidence >= 0.70
    ]
    definitions = (("5k", "5K"), ("10k", "10K"), ("half", "Half Marathon"))
    events = []
    for key, label in definitions:
        matching = [item for item in anchors if item.distance_label == label]
        within_year = [
            item for item in matching
            if 0 <= (reference_date - _date(item.activity_date)).days <= 365
        ]
        recent = [
            item for item in within_year
            if (reference_date - _date(item.activity_date)).days <= 180
        ]
        prior = [
            item for item in within_year
            if 181 <= (reference_date - _date(item.activity_date)).days <= 365
        ]
        recent_best = min((item.time_s for item in recent), default=None)
        prior_best = min((item.time_s for item in prior), default=None)
        events.append(
            RaceEventProgress(
                key=key,
                label=label,
                all_time_best_s=min((item.time_s for item in matching), default=None),
                last_12m_best_s=min((item.time_s for item in within_year), default=None),
                recent_best_s=recent_best,
                prior_best_s=prior_best,
                change_s=(prior_best - recent_best)
                if recent_best is not None and prior_best is not None
                else None,
                evidence_count=len(within_year),
            )
        )
    supported = [event for event in events if event.change_s is not None]
    changes = [event.change_s for event in supported]
    improving = any(change >= 5 for change in changes)
    softer = any(change <= -10 for change in changes)
    if not changes:
        status = "Race trend building"
    elif improving and softer:
        status = "Mixed recent results"
    elif improving:
        status = "Race performance improving"
    elif softer:
        status = "Recent results softer"
    else:
        status = "Race performance stable"
    evidence_count = sum(event.evidence_count for event in events)
    confidence = "Strong" if evidence_count >= 8 and supported else "Moderate" if evidence_count >= 3 else "Limited"
    return RaceProgress(
        available=evidence_count > 0,
        status=status,
        confidence=confidence,
        events=tuple(events),
        evidence_count=evidence_count,
        summary=(
            "Elapsed race and race-quality times remain factual; conditions "
            "are context and never rewrite a PB."
        ),
    )


def _threshold_progress(
    athlete_id: int,
    runs_by_id: dict[int, _ProgressRun],
    reference_date: datetime.date,
    personal_profile,
) -> ThresholdProgress:
    recent_easy_paces = [
        item.profile.moving_time_seconds / item.profile.distance_km
        for item in runs_by_id.values()
        if item.date <= reference_date
        and (reference_date - item.date).days <= 365
        and item.pace_reliable
        and item.profile.distance_km
        and item.profile.moving_time_seconds
        and is_easy_baseline_candidate(item.profile)
    ]
    easy_pace_anchor = (
        statistics.median(recent_easy_paces)
        if len(recent_easy_paces) >= 8
        else None
    )

    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT activity_id, activity_date, phase_json
        FROM workout_library
        WHERE athlete_id = ? AND activity_date >= ? AND activity_date <= ?
          AND recognition_confidence >= 0.65 AND phase_confidence >= 0.70
        ORDER BY activity_date DESC
        """,
        (
            athlete_id,
            (reference_date - datetime.timedelta(days=365)).isoformat(),
            reference_date.isoformat(),
        ),
    )
    rows = cursor.fetchall()
    connection.close()
    threshold_types = {
        "threshold", "continuous_threshold", "long_threshold", "sustained_quality"
    }
    evidence = []
    for activity_id, activity_date, phase_json in rows:
        try:
            phases = json.loads(phase_json or "[]")
        except (TypeError, json.JSONDecodeError):
            continue
        phases = [
            phase for phase in phases
            if str(phase.get("phase_type") or "").lower() in threshold_types
            and _safe_float(phase.get("pace_s_per_km")) is not None
            and _safe_float(phase.get("distance_km")) is not None
            and (_safe_float(phase.get("confidence")) or 0) >= 0.80
        ]
        total_distance = sum(float(phase["distance_km"]) for phase in phases)
        if total_distance < 3.0:
            continue
        raw_pace = sum(
            float(phase["pace_s_per_km"]) * float(phase["distance_km"])
            for phase in phases
        ) / total_distance
        if easy_pace_anchor is not None and raw_pace > easy_pace_anchor * 0.90:
            # A slightly quicker kilometre within an otherwise easy run can
            # resemble an alternating float workout. It is not physiological
            # threshold work if its pace still overlaps the athlete's normal
            # easy-running history.
            continue
        item = runs_by_id.get(int(activity_id))
        if item is None or not item.pace_reliable:
            continue
        adjustment = environment_adjusted_pace(
            item.profile,
            wind_speed=item.wind_speed,
            personal_profile=personal_profile,
        )
        adjusted_pace = max(raw_pace - adjustment.total_penalty_s_per_km, 150.0)
        # A single workout cannot justify awarding every estimated second of
        # environmental cost. Preserve the observed work pace as the headline
        # and expose a broad standard-conditions range using only 25–75% of
        # the supported allowance. This is especially important for wind,
        # where direction and exposure are not available historically.
        equivalent_fast = max(
            raw_pace - adjustment.total_penalty_s_per_km * 0.75,
            150.0,
        )
        equivalent_slow = max(
            raw_pace - adjustment.total_penalty_s_per_km * 0.25,
            equivalent_fast,
        )
        run_date = _date(activity_date)
        if run_date is not None:
            evidence.append(
                (
                    run_date,
                    raw_pace,
                    adjusted_pace,
                    equivalent_fast,
                    equivalent_slow,
                    ", ".join(adjustment.factors) or "standard conditions",
                )
            )
    recent = [
        adjusted for date, _raw, adjusted, _fast, _slow, _conditions in evidence
        if (reference_date - date).days <= 90
    ]
    comparison = [
        adjusted for date, _raw, adjusted, _fast, _slow, _conditions in evidence
        if 91 <= (reference_date - date).days <= 365
    ]
    trend = None
    if len(recent) >= 2 and len(comparison) >= 2:
        trend = _trimmed_mean(comparison) - _trimmed_mean(recent)
    if evidence:
        (
            current_date,
            current_pace,
            _current_adjusted,
            standard_fast,
            standard_slow,
            current_conditions,
        ) = evidence[0]
    else:
        current_date = current_pace = standard_fast = standard_slow = None
        current_conditions = None
    status = (
        "Improving" if trend is not None and trend >= 4
        else "Softer" if trend is not None and trend <= -4
        else "Stable" if trend is not None
        else "Trend building"
    )
    confidence = "Strong" if len(recent) >= 3 and len(comparison) >= 3 else "Moderate" if trend is not None else "Limited"
    return ThresholdProgress(
        available=bool(evidence),
        status=status,
        confidence=confidence,
        current_pace_s_per_km=round(current_pace, 1) if current_pace is not None else None,
        standard_equivalent_fast_s_per_km=(
            round(standard_fast, 1) if standard_fast is not None else None
        ),
        standard_equivalent_slow_s_per_km=(
            round(standard_slow, 1) if standard_slow is not None else None
        ),
        current_conditions=current_conditions,
        current_date=current_date.isoformat() if current_date else None,
        trend_seconds_per_km=round(trend, 1) if trend is not None else None,
        recent_sample_size=len(recent),
        comparison_sample_size=len(comparison),
        total_sample_size=len(evidence),
        summary=(
            "Observed work pace comes from trusted threshold phases. A trend "
            "needs at least two recent and two earlier comparable sessions."
        ),
    )


def _durability_progress(
    runs: list[_ProgressRun],
    reference_date: datetime.date,
    recognition: dict,
) -> DurabilityProgress:
    values = []
    interrupted = 0
    for item in runs:
        if not 0 <= (reference_date - item.date).days <= 365:
            continue
        result = recognition.get(recognition_key(item.profile))
        if result is None or result.category_key != "long_easy":
            continue
        if result.moving_percent is not None and result.moving_percent < 90:
            interrupted += 1
            continue
        try:
            raw = json.loads(item.raw_json or "{}")
            decoupling = float(raw.get("aerobicDecouplingPace"))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if math.isfinite(decoupling) and -10 <= decoupling <= 25:
            values.append((item.date, decoupling))
    recent = [value for date, value in values if (reference_date - date).days <= 90]
    comparison = [value for date, value in values if 91 <= (reference_date - date).days <= 180]
    recent_median = _median(recent)
    prior_median = _median(comparison)
    change = None
    if len(recent) >= 3 and len(comparison) >= 3:
        change = prior_median - recent_median
    if recent_median is None:
        status = "Recent evidence needed"
    elif recent_median <= 5:
        status = "Controlled"
    else:
        status = "Drift visible"
    confidence = "Strong" if len(recent) >= 6 and len(comparison) >= 6 else "Moderate" if change is not None else "Limited"
    return DurabilityProgress(
        available=bool(values),
        status=status,
        confidence=confidence,
        recent_decoupling_percent=round(recent_median, 1) if recent_median is not None else None,
        prior_decoupling_percent=round(prior_median, 1) if prior_median is not None else None,
        change_percent=round(change, 1) if change is not None else None,
        recent_sample_size=len(recent),
        comparison_sample_size=len(comparison),
        total_sample_size=len(values),
        interrupted_exclusion_count=interrupted,
        summary=(
            "Lower pace decoupling is better. Only continuous Long Easy runs "
            "with at least 90% moving time enter this evidence."
        ),
    )


def build_progress_summary(
    athlete_id: int,
    *,
    reference_date: datetime.date | None = None,
) -> ProgressSummary | None:
    athlete_name, runs = _load_runs(athlete_id)
    if not runs:
        return None
    reference_date = reference_date or max(item.date for item in runs)
    eligible_profiles = [
        item.profile
        for item in runs
        if item.pace_reliable and item.date <= reference_date
    ]
    personal_profile = build_personal_environment_profile(
        eligible_profiles,
        athlete_id=athlete_id,
    )
    aerobic = _aerobic_progress(runs, reference_date, personal_profile)
    profiles = [item.profile for item in runs]
    recognition = build_recognition_index(
        profiles,
        athlete_id=athlete_id,
        reference_date=reference_date,
    )
    rhythm = _training_rhythm(runs, reference_date, recognition)
    race = _race_progress(athlete_id, reference_date)
    runs_by_id = {item.activity_id: item for item in runs}
    threshold = _threshold_progress(
        athlete_id,
        runs_by_id,
        reference_date,
        personal_profile,
    )
    durability = _durability_progress(runs, reference_date, recognition)

    trend = aerobic.trend_percent
    if trend is None:
        verdict = "Still learning"
        headline = "Progress evidence is building"
    elif trend >= 2.0:
        verdict = "Improving"
        headline = "Aerobic fitness is moving forward"
    elif trend >= 0.5:
        verdict = "Improving"
        headline = "Progress is building"
    elif trend <= -2.0:
        verdict = "Review"
        headline = "Recent aerobic efficiency is below the opening period"
    else:
        verdict = "Stable"
        headline = "Fitness is holding steady"
    confidence = aerobic.confidence if aerobic.available else "Limited"
    summary = (
        f"{aerobic.summary} {rhythm.summary}"
        if aerobic.available
        else rhythm.summary
    )
    notes = (
        "Aerobic and threshold pace are normalised for supported heat, humidity, climbing, wind and trail effects.",
        "High-confidence personal heat, hill and trail responses scale the generic model.",
        "Race times remain factual elapsed results and are never environmentally rewritten.",
        "Treadmill time can support training rhythm; unreliable treadmill pace and distance cannot support performance trends.",
        "Durability uses within-run decoupling and excludes interrupted long runs.",
    )
    return ProgressSummary(
        athlete_id=athlete_id,
        athlete_name=athlete_name,
        reference_date=reference_date.isoformat(),
        verdict=verdict,
        headline=headline,
        confidence=confidence,
        summary=summary,
        aerobic=aerobic,
        rhythm=rhythm,
        race=race,
        threshold=threshold,
        durability=durability,
        evidence_notes=notes,
    )
