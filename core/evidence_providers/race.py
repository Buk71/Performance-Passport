"""
Smarter recent-race evidence provider.

Selection is based primarily on what the activity looked like:
- recency;
- standard race distance;
- moving time close to elapsed time;
- high effort;
- official race metadata;
- race-like title as supporting evidence only.

Time adjustment currently supports temperature and humidity/dew point using
the existing conservative Performance Passport coaching functions.

Elevation, surface and wind are inspected and reported, but are not yet used
to alter race time unless sufficient information exists. This avoids
pretending that unsupported adjustments are precise.
"""

from __future__ import annotations

import datetime
import json
import math
import statistics
from dataclasses import dataclass

from core.activity_reliability import has_reliable_distance_and_pace
from core.coaching import (
    humidity_adjustment_seconds_per_km,
    temperature_adjustment_seconds_per_km,
)
from core.database import get_athlete_sport_roles, get_connection
from core.evidence import EvidenceItem, EvidenceStatus
from core.evidence_providers.base import EvidenceContext, EvidenceProvider
from core.race_detection import score_race_evidence


RIEGEL_EXPONENT = 1.06
MAX_AGE_DAYS = 548
MINIMUM_SELECTION_SCORE = 45.0
MIXED_WIND_EXPOSURE = 0.55

STANDARD_DISTANCES_KM = (
    5.0,
    10.0,
    16.09344,
    21.0975,
    42.195,
)

RACE_WORDS = (
    "race",
    "parkrun",
    "5k",
    "10k",
    "10 km",
    "10 mile",
    "half marathon",
    "marathon",
    "cross country",
    "xc",
    "handicap",
    "road race",
    "trail race",
    "fell race",
    "time trial",
)

TRAINING_WORDS = (
    "interval",
    "intervals",
    "threshold",
    "tempo",
    "reps",
    "fartlek",
    "easy",
    "recovery",
    "warm up",
    "warm-up",
    "cool down",
    "cool-down",
)


@dataclass(frozen=True)
class RaceCandidate:
    activity_id: int
    activity_date: datetime.date
    title: str
    distance_km: float
    elapsed_time_s: float
    moving_time_s: float | None
    avg_hr: float | None
    max_hr: float | None
    athlete_lt2_hr: float | None
    athlete_max_hr: float | None
    elevation_up_m: float | None
    elevation_down_m: float | None
    temperature_c: float | None
    humidity: float | None
    wind_speed: float | None
    route_name: str | None
    official_race_name: str | None
    official_distance_m: float | None
    official_time_s: float | None
    officially_measured: bool
    raw_json: dict


@dataclass(frozen=True)
class CandidateScore:
    candidate: RaceCandidate
    total: float
    recency: float
    distance: float
    continuity: float
    effort: float
    official: float
    title: float
    training_penalty: float
    matched_distance_km: float | None
    age_days: int
    moving_ratio: float | None


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(value, high))


def _normalise_title(title: str) -> str:
    return (title or "").strip().lower()


def _title_signal(title: str) -> float:
    normalised = _normalise_title(title)
    if not normalised:
        return 0.0

    matches = sum(word in normalised for word in RACE_WORDS)
    if matches >= 2:
        return 1.0
    if matches == 1:
        return 0.7
    return 0.0


def _training_penalty(title: str) -> float:
    normalised = _normalise_title(title)
    if not normalised:
        return 0.0
    return 1.0 if any(word in normalised for word in TRAINING_WORDS) else 0.0


def _distance_signal(distance_km: float) -> tuple[float, float | None]:
    if distance_km <= 0:
        return 0.0, None

    closest = min(
        STANDARD_DISTANCES_KM,
        key=lambda standard: abs(standard - distance_km),
    )
    relative_error = abs(distance_km - closest) / closest

    if relative_error <= 0.012:
        return 1.0, closest
    if relative_error <= 0.025:
        return 0.88, closest
    if relative_error <= 0.05:
        return 0.65, closest
    if relative_error <= 0.08:
        return 0.40, closest
    return 0.10, None


def _recency_signal(age_days: int) -> float:
    """
    Smooth decay rather than hard 30/60/90-day cliffs.

    A good race does not suddenly become much weaker evidence because one new
    upload moved it from day 30 to day 31.
    """
    if age_days < 0:
        return 0.0
    if age_days > MAX_AGE_DAYS:
        return 0.0

    # Half-life ~120 days, with a small floor for older but still useful races.
    return max(
        0.10,
        math.pow(0.5, age_days / 120.0),
    )


def _continuity_signal(
    moving_time_s: float | None,
    elapsed_time_s: float,
) -> tuple[float, float | None]:
    if elapsed_time_s <= 0 or moving_time_s is None:
        return 0.45, None

    ratio = _clamp(moving_time_s / elapsed_time_s)

    if ratio >= 0.995:
        return 1.0, ratio
    if ratio >= 0.985:
        return 0.90, ratio
    if ratio >= 0.97:
        return 0.72, ratio
    if ratio >= 0.94:
        return 0.45, ratio
    return 0.10, ratio


def _effort_signal(candidate: RaceCandidate) -> float:
    signals = []

    if (
        candidate.max_hr is not None
        and candidate.athlete_max_hr is not None
        and candidate.athlete_max_hr > 0
    ):
        max_ratio = candidate.max_hr / candidate.athlete_max_hr
        signals.append(_clamp((max_ratio - 0.84) / 0.13))

    if (
        candidate.avg_hr is not None
        and candidate.athlete_lt2_hr is not None
        and candidate.athlete_lt2_hr > 0
    ):
        avg_ratio = candidate.avg_hr / candidate.athlete_lt2_hr
        signals.append(_clamp((avg_ratio - 0.88) / 0.15))

    if not signals:
        return 0.45

    return sum(signals) / len(signals)


def _official_signal(candidate: RaceCandidate) -> float:
    score = 0.0
    if candidate.official_race_name:
        score += 0.35
    if candidate.official_distance_m:
        score += 0.25
    if candidate.official_time_s:
        score += 0.25
    if candidate.officially_measured:
        score += 0.15
    return _clamp(score)


def _display_title(candidate: RaceCandidate) -> str:
    if candidate.official_race_name:
        return candidate.official_race_name
    if candidate.title:
        return candidate.title
    if candidate.route_name:
        return candidate.route_name
    return "Race-quality effort"



def _is_training_intent(candidate: RaceCandidate) -> bool:
    title = _normalise_title(candidate.title)

    return any(
        word in title
        for word in (
            "threshold",
            "tempo",
            "interval",
            "reps",
            "session",
            "steady",
            "training",
        )
    )


def _route_course_penalty_seconds(
    athlete_id: int,
    candidate: RaceCandidate,
) -> tuple[float, dict]:
    """
    Learn a repeated-course penalty from the athlete's own history.

    For a repeatedly-run hilly 5K route, compare the athlete's best route
    performances with their best low-elevation standard-distance performances
    in the same broad period. This captures course shape/surface effects that
    raw metres climbed alone cannot explain.
    """
    route = (candidate.route_name or "").strip()

    if not route:
        return 0.0, {
            "route_calibration_applied": False,
            "route_penalty_seconds": 0.0,
        }

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT distance_m, elapsed_time_s, elevation_up_m, route_name,
               activity_date, title, sport_id, raw_json
        FROM activities
        WHERE athlete_id = ?
          AND activity_date >= date(?, '-240 day')
          AND activity_date <= date(?, '+60 day')
          AND distance_m BETWEEN ? AND ?
          AND elapsed_time_s IS NOT NULL
        """,
        (
            athlete_id,
            candidate.activity_date.isoformat(),
            candidate.activity_date.isoformat(),
            candidate.distance_km * 0.94,
            candidate.distance_km * 1.06,
        ),
    )
    rows = cursor.fetchall()
    conn.close()

    route_paces = []
    route_elevations = []
    benchmark_paces = []

    for (
        distance,
        elapsed,
        elevation,
        route_name,
        _date,
        title,
        sport_id,
        raw_json_text,
    ) in rows:
        if not has_reliable_distance_and_pace(
            title=title,
            sport_id=str(sport_id or ""),
            route_name=route_name,
            raw_json_text=raw_json_text,
        ):
            continue

        try:
            distance = float(distance)
            elapsed = float(elapsed)
            elevation = float(elevation or 0.0)
        except (TypeError, ValueError):
            continue

        if distance <= 0 or elapsed <= 0:
            continue

        pace = elapsed / distance

        if (route_name or "").strip().lower() == route.lower():
            route_paces.append(pace)
            route_elevations.append(elevation)

        # A low-elevation comparator approximates a fast/neutral course.
        if elevation <= 20.0:
            benchmark_paces.append(pace)

    median_route_elevation = (
        statistics.median(route_elevations)
        if route_elevations
        else 0.0
    )

    if (
        len(route_paces) < 3
        or len(benchmark_paces) < 2
        or median_route_elevation < 30.0
    ):
        return 0.0, {
            "route_calibration_applied": False,
            "route_penalty_seconds": 0.0,
            "route_sample_size": len(route_paces),
            "benchmark_sample_size": len(benchmark_paces),
            "median_route_elevation_m": median_route_elevation,
        }

    # Best-vs-best estimates the athlete's course ceiling. This is especially
    # useful for repeatedly-raced/parkrun routes such as Nostell, where the
    # same athlete provides their own calibration.
    route_reference = min(route_paces)
    benchmark_reference = min(benchmark_paces)

    penalty_per_km = max(
        0.0,
        route_reference - benchmark_reference,
    )

    # Conservative cap: no more than 18 sec/km from empirical route learning.
    penalty_per_km = min(
        penalty_per_km,
        18.0,
    )
    total = penalty_per_km * candidate.distance_km

    return total, {
        "route_calibration_applied": total >= 5.0,
        "route_penalty_seconds": total,
        "route_penalty_seconds_per_km": penalty_per_km,
        "route_sample_size": len(route_paces),
        "benchmark_sample_size": len(benchmark_paces),
        "median_route_elevation_m": median_route_elevation,
        "route_name": route,
    }


def _generic_elevation_penalty_seconds(
    candidate: RaceCandidate,
) -> float:
    """
    Conservative generic fallback when no repeated-course calibration exists.

    Net climbing alone underestimates rolling courses because descents do not
    repay all uphill cost. For short race-quality efforts, use 0.45 sec per
    metre climbed, capped at 15 sec/km.
    """
    gain = float(candidate.elevation_up_m or 0.0)

    if gain <= 0 or candidate.distance_km <= 0:
        return 0.0

    return min(
        gain * 0.45,
        candidate.distance_km * 15.0,
    )


def _performance_quality_signal(
    athlete_id: int,
    candidate: RaceCandidate,
    equivalent_time_s: float,
) -> float:
    """
    Athlete-relative quality at the same standard distance.

    A controlled threshold 5K can be valid fitness evidence, but it should not
    outrank a substantially faster genuine race merely because it is newer.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT distance_m, elapsed_time_s, title, sport_id, route_name,
               raw_json
        FROM activities
        WHERE athlete_id = ?
          AND activity_date <= ?
          AND distance_m BETWEEN ? AND ?
          AND elapsed_time_s IS NOT NULL
        """,
        (
            athlete_id,
            candidate.activity_date.isoformat(),
            candidate.distance_km * 0.94,
            candidate.distance_km * 1.06,
        ),
    )
    rows = cursor.fetchall()
    conn.close()

    paces = []

    for distance, elapsed, title, sport_id, route_name, raw_json_text in rows:
        if not has_reliable_distance_and_pace(
            title=title,
            sport_id=str(sport_id or ""),
            route_name=route_name,
            raw_json_text=raw_json_text,
        ):
            continue

        try:
            distance = float(distance)
            elapsed = float(elapsed)
        except (TypeError, ValueError):
            continue

        if distance > 0 and elapsed > 0:
            paces.append(elapsed / distance)

    if len(paces) < 6:
        return 0.50

    candidate_pace = equivalent_time_s / candidate.distance_km
    percentile = sum(
        pace <= candidate_pace
        for pace in paces
    ) / len(paces)

    # Top 10% => near 1.0; median => ~0.5; poor efforts trend to 0.
    return _clamp(
        1.10 - percentile * 1.20
    )



def _score_candidate(
    candidate: RaceCandidate,
    reference_date: datetime.date,
    athlete_id: int,
) -> CandidateScore:
    age_days = (reference_date - candidate.activity_date).days
    recency = _recency_signal(age_days)

    shared = score_race_evidence(
        title=candidate.title,
        distance_km=candidate.distance_km,
        moving_time_s=candidate.moving_time_s,
        elapsed_time_s=candidate.elapsed_time_s,
        avg_hr=candidate.avg_hr,
        max_hr=candidate.max_hr,
        athlete_lt2_hr=candidate.athlete_lt2_hr,
        athlete_max_hr=candidate.athlete_max_hr,
        official_race_name=candidate.official_race_name,
        official_distance_m=candidate.official_distance_m,
        official_time_s=candidate.official_time_s,
        officially_measured=candidate.officially_measured,
    )

    equivalent_time, _ = _equivalent_race_time(
        candidate,
        athlete_id=athlete_id,
    )
    performance_quality = _performance_quality_signal(
        athlete_id,
        candidate,
        equivalent_time,
    )

    # Current-race selection should favour actual performance quality over a
    # tiny recency edge. Explicit training intent is allowed as evidence but
    # is materially demoted.
    training_intent_penalty = (
        18.0
        if _is_training_intent(candidate)
        else 0.0
    )

    total = (
        shared.total * 0.58
        + recency * 16.0
        + performance_quality * 26.0
        - training_intent_penalty
    )

    return CandidateScore(
        candidate=candidate,
        total=total,
        recency=recency,
        distance=shared.distance,
        continuity=shared.continuity,
        effort=shared.effort,
        official=shared.official,
        title=shared.title,
        training_penalty=shared.training_penalty,
        matched_distance_km=shared.matched_distance_km,
        age_days=age_days,
        moving_ratio=shared.moving_ratio,
    )


def _weather_adjustment_seconds(
    candidate: RaceCandidate,
) -> tuple[float, dict]:
    temp_penalty_per_km = temperature_adjustment_seconds_per_km(
        candidate.temperature_c
    )
    humidity_penalty_per_km = humidity_adjustment_seconds_per_km(
        candidate.temperature_c,
        candidate.humidity,
    )

    total_per_km = temp_penalty_per_km + humidity_penalty_per_km
    total_seconds = max(total_per_km, 0.0) * candidate.distance_km

    return total_seconds, {
        "temperature_penalty_seconds_per_km": temp_penalty_per_km,
        "humidity_penalty_seconds_per_km": humidity_penalty_per_km,
        "total_weather_adjustment_seconds": total_seconds,
    }


def _wind_adjustment_seconds(
    candidate: RaceCandidate,
) -> tuple[float, dict]:
    """Return the product's existing conservative mixed-exposure allowance.

    Runalyze stores wind speed in km/h. Direction and course exposure are not
    reliable enough to model precisely, so Race Coach mirrors the Race
    Outlook's generic mixed-exposure rule and reports the assumption. This is
    intentionally modest: a 29 km/h reading contributes about 1.9 sec/km.
    """
    wind = max(float(candidate.wind_speed or 0.0), 0.0)
    penalty_per_km = (
        min(max(wind - 10.0, 0.0) * 0.18, 8.0)
        * MIXED_WIND_EXPOSURE
    )
    total = penalty_per_km * max(candidate.distance_km, 0.0)
    return total, {
        "wind_adjustment_applied": total >= 1.0,
        "wind_adjustment_seconds": total,
        "wind_penalty_seconds_per_km": penalty_per_km,
        "wind_exposure_assumption": "mixed",
        "wind_adjustment_confidence": 0.45 if total >= 1.0 else 0.75,
    }


def _equivalent_race_time(
    candidate: RaceCandidate,
    *,
    athlete_id: int | None = None,
) -> tuple[float, dict]:
    observed = (
        candidate.official_time_s
        if candidate.official_time_s
        else candidate.elapsed_time_s
    )

    weather_seconds, weather_details = _weather_adjustment_seconds(candidate)
    wind_seconds, wind_details = _wind_adjustment_seconds(candidate)

    route_seconds = 0.0
    route_details = {
        "route_calibration_applied": False,
        "route_penalty_seconds": 0.0,
    }

    if athlete_id is not None:
        route_seconds, route_details = _route_course_penalty_seconds(
            athlete_id,
            candidate,
        )

    elevation_seconds = 0.0

    if route_seconds < 5.0:
        elevation_seconds = _generic_elevation_penalty_seconds(
            candidate
        )

    total_adjustment = (
        weather_seconds
        + route_seconds
        + elevation_seconds
        + wind_seconds
    )

    # Keep environmental correction conservative.
    adjusted = max(
        observed - total_adjustment,
        observed * 0.82,
    )

    details = {
        "observed_time_seconds": observed,
        "weather_adjusted_time_seconds": adjusted,
        **weather_details,
        **route_details,
        "elevation_adjustment_applied": elevation_seconds > 0,
        "elevation_adjustment_seconds": elevation_seconds,
        "surface_adjustment_applied": bool(
            route_details.get("route_calibration_applied")
        ),
        **wind_details,
        "heart_rate_time_adjustment_applied": False,
    }

    return adjusted, details


def _riegel_prediction(
    race_time_s: float,
    race_distance_km: float,
    target_distance_km: float,
) -> float | None:
    if race_time_s <= 0 or race_distance_km <= 0 or target_distance_km <= 0:
        return None

    return race_time_s * math.pow(
        target_distance_km / race_distance_km,
        RIEGEL_EXPONENT,
    )


def _projection_distance_km(
    selected: CandidateScore,
) -> tuple[float, bool]:
    """Normalise a GPS-short standard event without inventing a faster time.

    A continuous, race-quality 4.96 km effort is normally a GPS measurement
    of a 5K event, not a 4.96 km race that needs extrapolating. Race Coach
    already records the matched standard distance in its evidence score. Use
    that distance only inside the strict 1.2% standard-distance window; keep
    the observed elapsed time and all confidence limitations unchanged.
    """
    candidate = selected.candidate
    matched = selected.matched_distance_km
    if matched is None or matched <= 0:
        return candidate.distance_km, False
    relative_error = abs(candidate.distance_km - matched) / matched
    if relative_error > 0.012 or selected.distance < 0.95:
        return candidate.distance_km, False
    return float(matched), abs(candidate.distance_km - matched) > 0.001


def _format_duration(seconds: float) -> str:
    total = int(round(seconds))
    hours = total // 3600
    minutes = (total % 3600) // 60
    remaining = total % 60

    if hours:
        return f"{hours}:{minutes:02d}:{remaining:02d}"
    return f"{minutes}:{remaining:02d}"


def _select_goal_representative_race(
    scored: list[CandidateScore],
    goal_distance_km: float | None,
    athlete_id: int,
) -> CandidateScore:
    """Reject a recent-race outlier when direct goal-distance evidence exists.

    A marginal recency advantage must not make one much slower 5K outweigh a
    cluster of similarly trusted faster races and a recent actual 10K. Existing
    selections remain unchanged unless the leading projection is a meaningful
    outlier and direct evidence is comparably well supported.
    """
    selected = scored[0]
    if goal_distance_km is None or goal_distance_km <= 0:
        return selected

    # For endurance goals, a recent high-quality performance at the actual
    # distance is more representative than extrapolating a shorter race. The
    # quality floor prevents ordinary long runs from being promoted merely
    # because their distance happens to match the goal.
    if goal_distance_km >= 15.0:
        direct_quality_floor = (
            55.0 if goal_distance_km >= 30.0 else 65.0
        )
        direct_age_limit = (
            365 if goal_distance_km >= 30.0 else 210
        )
        recent_direct = [
            item
            for item in scored
            if item.age_days <= direct_age_limit
            and item.total >= direct_quality_floor
            and not _is_training_intent(item.candidate)
            and abs(item.candidate.distance_km - goal_distance_km)
            / goal_distance_km <= 0.035
        ]
        if recent_direct:
            return max(
                recent_direct,
                key=lambda item: (
                    item.total,
                    item.candidate.activity_date,
                ),
            )

    comparable = [
        item for item in scored
        if item.total >= selected.total - 2.5
        and item.age_days <= 120
    ]
    if len(comparable) < 3:
        return selected

    predictions: dict[int, float] = {}
    for item in comparable:
        equivalent, _ = _equivalent_race_time(
            item.candidate,
            athlete_id=athlete_id,
        )
        predicted = _riegel_prediction(
            equivalent,
            item.candidate.distance_km,
            goal_distance_km,
        )
        if predicted is not None:
            predictions[item.candidate.activity_id] = predicted

    leading = predictions.get(selected.candidate.activity_id)
    alternatives = [
        prediction for activity_id, prediction in predictions.items()
        if activity_id != selected.candidate.activity_id
    ]
    if leading is None or len(alternatives) < 2:
        return selected
    if leading <= statistics.median(alternatives) * 1.06:
        return selected

    direct = [
        item for item in comparable
        if abs(item.candidate.distance_km - goal_distance_km)
        / goal_distance_km <= 0.035
    ]
    if not direct:
        return selected

    return max(
        direct,
        key=lambda item: (item.total, item.candidate.activity_date),
    )


class RaceEvidenceProvider(EvidenceProvider):
    key = "recent_race"
    title = "Race Coach"

    def build(self, context: EvidenceContext) -> EvidenceItem:
        candidates, latest_date = self._load_candidates(context.athlete_id)

        if not candidates:
            return EvidenceItem(
                key=self.key,
                title=self.title,
                summary="No suitable recent race-quality running effort was found.",
                status=EvidenceStatus.UNAVAILABLE,
                confidence=0.0,
                sample_size=0,
                predicted_seconds=None,
                weight=1.0,
                metadata={
                    "limitations": [
                        "No activity met the minimum race-quality criteria.",
                    ],
                    "candidate_debug": [],
                },
            )

        reference_date = latest_date or datetime.date.today()
        scored = [
            _score_candidate(candidate, reference_date, context.athlete_id)
            for candidate in candidates
        ]
        scored = [
            item
            for item in scored
            if item.age_days <= MAX_AGE_DAYS
            and item.total >= MINIMUM_SELECTION_SCORE
        ]

        scored.sort(
            key=lambda item: (
                item.total,
                item.candidate.activity_date,
            ),
            reverse=True,
        )

        if not scored:
            return EvidenceItem(
                key=self.key,
                title=self.title,
                summary=(
                    "Possible race efforts were found, but none reached the "
                    "minimum evidence score."
                ),
                status=EvidenceStatus.BUILDING,
                confidence=0.25,
                sample_size=len(candidates),
                predicted_seconds=None,
                weight=1.0,
                metadata={
                    "limitations": [
                        "Candidate quality is currently too uncertain.",
                    ],
                    "candidate_debug": self._candidate_debug(
                        [_score_candidate(c, reference_date, context.athlete_id) for c in candidates]
                    ),
                },
            )

        goal = context.goal or {}
        goal_distance_km = (
            float(goal["distance_m"]) / 1000.0
            if goal.get("distance_m")
            else None
        )
        selected = _select_goal_representative_race(
            scored,
            goal_distance_km,
            context.athlete_id,
        )
        candidate = selected.candidate
        equivalent_time, adjustment_details = _equivalent_race_time(
            candidate,
            athlete_id=context.athlete_id,
        )
        projection_distance_km, standard_distance_normalised = (
            _projection_distance_km(selected)
        )

        predicted_seconds = None
        if goal_distance_km:
            predicted_seconds = _riegel_prediction(
                equivalent_time,
                projection_distance_km,
                goal_distance_km,
            )

        confidence = _clamp(selected.total / 100.0)
        moving_text = (
            f"{selected.moving_ratio:.1%} moving"
            if selected.moving_ratio is not None
            else "moving ratio unavailable"
        )
        display_title = _display_title(candidate)

        summary = (
            f"Selected {display_title} on "
            f"{candidate.activity_date.strftime('%d %b %Y')}: "
            f"{candidate.distance_km:.2f} km in "
            f"{_format_duration(candidate.elapsed_time_s)} "
            f"({moving_text})."
        )

        strengths = [
            f"Selection score {selected.total:.1f}/100",
            f"Recency contribution {selected.recency:.0%}",
            f"Distance certainty {selected.distance:.0%}",
            f"Continuity {selected.continuity:.0%}",
            f"Effort evidence {selected.effort:.0%}",
        ]

        if selected.official > 0:
            strengths.append(
                f"Official race metadata {selected.official:.0%}"
            )

        weather_adjustment = adjustment_details[
            "total_weather_adjustment_seconds"
        ]
        if weather_adjustment > 0:
            strengths.append(
                "Temperature and humidity adjustment applied: "
                f"{weather_adjustment:.0f} seconds"
            )

        wind_adjustment = adjustment_details[
            "wind_adjustment_seconds"
        ]
        if wind_adjustment > 0:
            strengths.append(
                "Conservative mixed-exposure wind allowance applied: "
                f"{wind_adjustment:.0f} seconds"
            )

        if standard_distance_normalised:
            strengths.append(
                f"GPS distance {candidate.distance_km:.2f} km recognised "
                f"as a {projection_distance_km:.2f} km standard event"
            )

        direct_goal_distance = bool(
            goal_distance_km
            and abs(projection_distance_km - goal_distance_km)
            / goal_distance_km <= 0.035
        )
        limitations = [
            (
                "This is direct goal-distance evidence; no material "
                "cross-distance conversion was required."
                if direct_goal_distance
                else "Goal-distance conversion still uses the generic Riegel model."
            ),
            "Heart rate affects evidence confidence, not race-time correction.",
        ]

        if candidate.elevation_up_m:
            limitations.append(
                f"Elevation recorded ({candidate.elevation_up_m:.0f} m); "
                "PP now applies athlete-specific repeated-course calibration "
                "where possible, otherwise a conservative elevation fallback."
            )

        if candidate.wind_speed:
            limitations.append(
                f"Wind recorded ({candidate.wind_speed:g} km/h). Direction "
                "and exact exposure are unknown, so only the product's "
                "conservative mixed-exposure allowance is used."
            )

        limitations.append(
            "Surface is not reliably labelled in all imports; repeated-route "
            "calibration can capture some combined hill/surface/course difficulty."
        )

        return EvidenceItem(
            key=self.key,
            title=self.title,
            summary=summary,
            status=EvidenceStatus.AVAILABLE,
            confidence=confidence,
            sample_size=len(scored),
            predicted_seconds=predicted_seconds,
            weight=1.0,
            metadata={
                "activity_id": candidate.activity_id,
                "activity_date": candidate.activity_date.isoformat(),
                "selected_title": display_title,
                "distance_km": candidate.distance_km,
                "projection_distance_km": projection_distance_km,
                "standard_distance_normalised": standard_distance_normalised,
                "direct_goal_distance": direct_goal_distance,
                "elapsed_time_s": candidate.elapsed_time_s,
                "moving_time_s": candidate.moving_time_s,
                "moving_ratio": selected.moving_ratio,
                "avg_hr": candidate.avg_hr,
                "max_hr": candidate.max_hr,
                "temperature_c": candidate.temperature_c,
                "humidity": candidate.humidity,
                "elevation_up_m": candidate.elevation_up_m,
                "wind_speed": candidate.wind_speed,
                "route_name": candidate.route_name,
                "equivalent_time_seconds": equivalent_time,
                "selection_basis": (
                    "recent_direct_goal_distance"
                    if direct_goal_distance and goal_distance_km >= 15.0
                    else "best_supported_race_projection"
                ),
                "strengths": strengths,
                "limitations": limitations,
                "adjustments": adjustment_details,
                "score_breakdown": {
                    "total": selected.total,
                    "recency": selected.recency,
                    "distance": selected.distance,
                    "continuity": selected.continuity,
                    "effort": selected.effort,
                    "official": selected.official,
                    "title": selected.title,
                    "training_penalty": selected.training_penalty,
                },
                "candidate_debug": self._candidate_debug(scored[:10]),
            },
        )

    def _candidate_debug(
        self,
        scored: list[CandidateScore],
    ) -> list[dict]:
        ranked = sorted(
            scored,
            key=lambda item: (
                item.total,
                item.candidate.activity_date,
            ),
            reverse=True,
        )

        return [
            {
                "activity_id": item.candidate.activity_id,
                "date": item.candidate.activity_date.isoformat(),
                "title": _display_title(item.candidate),
                "distance_km": round(item.candidate.distance_km, 3),
                "elapsed": _format_duration(item.candidate.elapsed_time_s),
                "moving_ratio": (
                    round(item.moving_ratio, 4)
                    if item.moving_ratio is not None
                    else None
                ),
                "avg_hr": item.candidate.avg_hr,
                "max_hr": item.candidate.max_hr,
                "temperature_c": item.candidate.temperature_c,
                "humidity": item.candidate.humidity,
                "score": round(item.total, 2),
                "recency": round(item.recency, 3),
                "distance": round(item.distance, 3),
                "continuity": round(item.continuity, 3),
                "effort": round(item.effort, 3),
                "official": round(item.official, 3),
                "title_signal": round(item.title, 3),
                "training_penalty": round(item.training_penalty, 3),
            }
            for item in ranked[:10]
        ]

    def _load_candidates(
        self,
        athlete_id: int,
    ) -> tuple[list[RaceCandidate], datetime.date | None]:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT MAX(date(activity_date))
            FROM activities
            WHERE athlete_id = ?
              AND activity_date IS NOT NULL
            """,
            (athlete_id,),
        )
        row = cursor.fetchone()
        latest_date = (
            datetime.date.fromisoformat(row[0])
            if row and row[0]
            else None
        )

        sport_roles = get_athlete_sport_roles(athlete_id)
        running_sport_ids = [
            sport_id
            for sport_id, role in sport_roles.items()
            if role == "running"
        ]

        if not running_sport_ids:
            conn.close()
            return [], latest_date

        placeholders = ",".join("?" for _ in running_sport_ids)

        cursor.execute(
            f"""
            SELECT
                a.id,
                a.activity_date,
                a.title,
                a.distance_m,
                a.elapsed_time_s,
                a.moving_time_s,
                a.avg_hr,
                a.max_hr,
                at.lt2_hr,
                at.max_hr,
                a.elevation_up_m,
                a.elevation_down_m,
                a.temperature_c,
                a.humidity,
                a.wind_speed,
                a.route_name,
                a.raw_json
            FROM activities a
            JOIN athletes at ON at.id = a.athlete_id
            WHERE a.athlete_id = ?
              AND CAST(a.sport_id AS TEXT) IN ({placeholders})
              AND a.activity_date IS NOT NULL
              AND a.distance_m IS NOT NULL
              AND COALESCE(a.elapsed_time_s, a.moving_time_s) IS NOT NULL
            ORDER BY a.activity_datetime DESC
            """,
            (athlete_id, *running_sport_ids),
        )

        candidates = []

        for row in cursor.fetchall():
            (
                activity_id,
                activity_date_text,
                title,
                distance_km,
                elapsed_time_s,
                moving_time_s,
                avg_hr,
                run_max_hr,
                athlete_lt2_hr,
                athlete_max_hr,
                elevation_up_m,
                elevation_down_m,
                temperature_c,
                humidity,
                wind_speed,
                route_name,
                raw_json_text,
            ) = row

            elapsed = elapsed_time_s or moving_time_s
            if not distance_km or not elapsed or elapsed <= 0:
                continue

            if not has_reliable_distance_and_pace(
                title=title,
                route_name=route_name,
                raw_json_text=raw_json_text,
            ):
                continue

            try:
                activity_date = datetime.date.fromisoformat(
                    activity_date_text[:10]
                )
            except (TypeError, ValueError):
                continue

            raw = {}
            if raw_json_text:
                try:
                    raw = json.loads(raw_json_text)
                except (TypeError, json.JSONDecodeError):
                    raw = {}

            official_name = raw.get("race_name")
            official_distance = raw.get("race_officialDistance")
            official_time = raw.get("race_officialTime")
            officially_measured = bool(raw.get("race_officiallyMeasured"))

            candidates.append(
                RaceCandidate(
                    activity_id=int(activity_id),
                    activity_date=activity_date,
                    title=title or "",
                    distance_km=float(distance_km),
                    elapsed_time_s=float(elapsed),
                    moving_time_s=(
                        float(moving_time_s)
                        if moving_time_s is not None
                        else None
                    ),
                    avg_hr=float(avg_hr) if avg_hr is not None else None,
                    max_hr=(
                        float(run_max_hr)
                        if run_max_hr is not None
                        else None
                    ),
                    athlete_lt2_hr=(
                        float(athlete_lt2_hr)
                        if athlete_lt2_hr is not None
                        else None
                    ),
                    athlete_max_hr=(
                        float(athlete_max_hr)
                        if athlete_max_hr is not None
                        else None
                    ),
                    elevation_up_m=(
                        float(elevation_up_m)
                        if elevation_up_m is not None
                        else None
                    ),
                    elevation_down_m=(
                        float(elevation_down_m)
                        if elevation_down_m is not None
                        else None
                    ),
                    temperature_c=(
                        float(temperature_c)
                        if temperature_c is not None
                        else None
                    ),
                    humidity=(
                        float(humidity)
                        if humidity is not None
                        else None
                    ),
                    wind_speed=(
                        float(wind_speed)
                        if wind_speed is not None
                        else None
                    ),
                    route_name=route_name,
                    official_race_name=official_name,
                    official_distance_m=(
                        float(official_distance)
                        if official_distance is not None
                        else None
                    ),
                    official_time_s=(
                        float(official_time)
                        if official_time is not None
                        else None
                    ),
                    officially_measured=officially_measured,
                    raw_json=raw,
                )
            )

        conn.close()
        return candidates, latest_date
