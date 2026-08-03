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
from dataclasses import dataclass

from core.coaching import (
    humidity_adjustment_seconds_per_km,
    temperature_adjustment_seconds_per_km,
)
from core.database import get_connection
from core.evidence import EvidenceItem, EvidenceStatus
from core.evidence_providers.base import EvidenceContext, EvidenceProvider


RUNNING_SPORT_ID = "965611"
RIEGEL_EXPONENT = 1.06
MAX_AGE_DAYS = 548
MINIMUM_SELECTION_SCORE = 45.0

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
    if age_days < 0:
        return 0.0
    if age_days <= 30:
        return 1.0
    if age_days <= 60:
        return 0.92
    if age_days <= 90:
        return 0.82
    if age_days <= 183:
        return 0.62
    if age_days <= 365:
        return 0.35
    if age_days <= MAX_AGE_DAYS:
        return 0.15
    return 0.0


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


def _score_candidate(
    candidate: RaceCandidate,
    reference_date: datetime.date,
) -> CandidateScore:
    age_days = (reference_date - candidate.activity_date).days
    recency = _recency_signal(age_days)
    distance, matched_distance = _distance_signal(candidate.distance_km)
    continuity, moving_ratio = _continuity_signal(
        candidate.moving_time_s,
        candidate.elapsed_time_s,
    )
    effort = _effort_signal(candidate)
    official = _official_signal(candidate)
    title = _title_signal(candidate.title)
    training_penalty = _training_penalty(candidate.title)

    total = (
        recency * 30.0
        + distance * 20.0
        + continuity * 20.0
        + effort * 20.0
        + official * 8.0
        + title * 5.0
        - training_penalty * 28.0
    )

    return CandidateScore(
        candidate=candidate,
        total=total,
        recency=recency,
        distance=distance,
        continuity=continuity,
        effort=effort,
        official=official,
        title=title,
        training_penalty=training_penalty,
        matched_distance_km=matched_distance,
        age_days=age_days,
        moving_ratio=moving_ratio,
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


def _equivalent_race_time(
    candidate: RaceCandidate,
) -> tuple[float, dict]:
    observed = (
        candidate.official_time_s
        if candidate.official_time_s
        else candidate.elapsed_time_s
    )

    weather_seconds, weather_details = _weather_adjustment_seconds(candidate)
    adjusted = max(observed - weather_seconds, observed * 0.85)

    details = {
        "observed_time_seconds": observed,
        "weather_adjusted_time_seconds": adjusted,
        **weather_details,
        "elevation_adjustment_applied": False,
        "surface_adjustment_applied": False,
        "wind_adjustment_applied": False,
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


def _format_duration(seconds: float) -> str:
    total = int(round(seconds))
    hours = total // 3600
    minutes = (total % 3600) // 60
    remaining = total % 60

    if hours:
        return f"{hours}:{minutes:02d}:{remaining:02d}"
    return f"{minutes}:{remaining:02d}"


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
            _score_candidate(candidate, reference_date)
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
                        [_score_candidate(c, reference_date) for c in candidates]
                    ),
                },
            )

        selected = scored[0]
        candidate = selected.candidate
        equivalent_time, adjustment_details = _equivalent_race_time(candidate)

        goal = context.goal or {}
        goal_distance_km = (
            float(goal["distance_m"]) / 1000.0
            if goal.get("distance_m")
            else None
        )

        predicted_seconds = None
        if goal_distance_km:
            predicted_seconds = _riegel_prediction(
                equivalent_time,
                candidate.distance_km,
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

        limitations = [
            "Goal-distance conversion still uses the generic Riegel model.",
            "Heart rate affects evidence confidence, not race-time correction.",
        ]

        if candidate.elevation_up_m:
            limitations.append(
                f"Elevation recorded ({candidate.elevation_up_m:.0f} m), "
                "but no race-time elevation correction is applied yet."
            )

        if candidate.wind_speed:
            limitations.append(
                f"Wind recorded ({candidate.wind_speed:g}), but direction "
                "and exposure are insufficient for a defensible correction."
            )

        limitations.append(
            "Surface is not currently stored reliably enough for adjustment."
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

        cursor.execute(
            """
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
              AND CAST(a.sport_id AS TEXT) = ?
              AND a.activity_date IS NOT NULL
              AND a.distance_m IS NOT NULL
              AND COALESCE(a.elapsed_time_s, a.moving_time_s) IS NOT NULL
            ORDER BY a.activity_datetime DESC
            """,
            (athlete_id, RUNNING_SPORT_ID),
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
