"""
Recent-race evidence provider.

Version 1:
- detects likely running races from activity titles;
- ignores races older than 18 months;
- uses elapsed time for race evidence where available;
- scores recency, distance certainty, effort certainty and data quality;
- converts a race result to the active goal distance with the Riegel model;
- returns one transparent EvidenceItem.

The provider is deliberately conservative. It does not claim that a
title-matched activity is a certified race.
"""

from __future__ import annotations

import datetime
import math
from dataclasses import dataclass

from core.database import get_connection
from core.evidence import EvidenceItem, EvidenceStatus
from core.evidence_providers.base import EvidenceContext, EvidenceProvider


RUNNING_SPORT_ID = "965611"
RIEGEL_EXPONENT = 1.06
MAX_AGE_DAYS = 548

RACE_KEYWORDS = (
    "race",
    "parkrun",
    "5k",
    "10k",
    "10 km",
    "10 mile",
    "half marathon",
    "half",
    "marathon",
    "cross country",
    "xc",
    "handicap",
    "road race",
    "trail race",
    "fell race",
    "time trial",
)

TRAINING_KEYWORDS = (
    "interval",
    "intervals",
    "threshold",
    "tempo",
    "reps",
    "fartlek",
    "session",
    "easy",
    "recovery",
    "warm up",
    "warm-up",
    "cool down",
    "cool-down",
)

STANDARD_DISTANCES_KM = (
    5.0,
    10.0,
    16.09344,
    21.0975,
    42.195,
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
    temperature_c: float | None
    humidity: float | None


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(value, upper))


def _title_score(title: str) -> float:
    normalised = (title or "").strip().lower()

    if not normalised:
        return 0.0

    if any(keyword in normalised for keyword in TRAINING_KEYWORDS):
        return 0.0

    matches = sum(
        1 for keyword in RACE_KEYWORDS
        if keyword in normalised
    )

    if matches >= 2:
        return 1.0

    if matches == 1:
        return 0.82

    return 0.0


def _distance_certainty(distance_km: float) -> tuple[float, float | None]:
    if distance_km <= 0:
        return 0.0, None

    closest = min(
        STANDARD_DISTANCES_KM,
        key=lambda standard: abs(standard - distance_km),
    )
    relative_error = abs(distance_km - closest) / closest

    if relative_error <= 0.015:
        return 1.0, closest

    if relative_error <= 0.03:
        return 0.85, closest

    if relative_error <= 0.06:
        return 0.65, closest

    return 0.45, None


def _recency_score(age_days: int) -> float:
    if age_days < 0:
        return 0.0

    if age_days <= 30:
        return 1.0

    if age_days <= 90:
        return 0.90

    if age_days <= 183:
        return 0.75

    if age_days <= 365:
        return 0.50

    if age_days <= MAX_AGE_DAYS:
        return 0.25

    return 0.0


def _effort_score(candidate: RaceCandidate) -> float:
    scores = []

    if (
        candidate.max_hr is not None
        and candidate.athlete_max_hr is not None
        and candidate.athlete_max_hr > 0
    ):
        scores.append(
            _clamp(
                (candidate.max_hr / candidate.athlete_max_hr - 0.82)
                / 0.14
            )
        )

    if (
        candidate.avg_hr is not None
        and candidate.athlete_lt2_hr is not None
        and candidate.athlete_lt2_hr > 0
    ):
        scores.append(
            _clamp(
                candidate.avg_hr / candidate.athlete_lt2_hr
            )
        )

    if scores:
        return sum(scores) / len(scores)

    return 0.60


def _data_quality_score(candidate: RaceCandidate) -> float:
    score = 0.45

    if candidate.elapsed_time_s > 0:
        score += 0.25

    if candidate.distance_km > 0:
        score += 0.20

    if candidate.avg_hr is not None or candidate.max_hr is not None:
        score += 0.10

    return _clamp(score)


def _race_confidence(
    candidate: RaceCandidate,
    reference_date: datetime.date,
) -> tuple[float, dict]:
    age_days = (reference_date - candidate.activity_date).days
    title = _title_score(candidate.title)
    distance, matched_distance = _distance_certainty(
        candidate.distance_km
    )
    recency = _recency_score(age_days)
    effort = _effort_score(candidate)
    data_quality = _data_quality_score(candidate)

    confidence = (
        title * 0.28
        + distance * 0.24
        + recency * 0.24
        + effort * 0.14
        + data_quality * 0.10
    )

    details = {
        "age_days": age_days,
        "title_score": title,
        "distance_score": distance,
        "matched_standard_distance_km": matched_distance,
        "recency_score": recency,
        "effort_score": effort,
        "data_quality_score": data_quality,
    }

    return _clamp(confidence), details


def _riegel_prediction(
    race_time_s: float,
    race_distance_km: float,
    target_distance_km: float,
) -> float | None:
    if (
        race_time_s <= 0
        or race_distance_km <= 0
        or target_distance_km <= 0
    ):
        return None

    return race_time_s * math.pow(
        target_distance_km / race_distance_km,
        RIEGEL_EXPONENT,
    )


class RaceEvidenceProvider(EvidenceProvider):
    key = "recent_race"
    title = "Recent race"

    def build(self, context: EvidenceContext) -> EvidenceItem:
        candidates, latest_activity_date = self._load_candidates(
            context.athlete_id
        )

        if not candidates:
            return EvidenceItem(
                key=self.key,
                title=self.title,
                summary=(
                    "No recent running activity was confidently identified "
                    "as a race effort."
                ),
                status=EvidenceStatus.UNAVAILABLE,
                confidence=0.0,
                sample_size=0,
                predicted_seconds=None,
                weight=1.0,
                metadata={
                    "limitations": [
                        "Race detection currently relies partly on titles.",
                        "Only the last 18 months are considered.",
                    ],
                },
            )

        reference_date = latest_activity_date or datetime.date.today()
        scored = []

        for candidate in candidates:
            confidence, details = _race_confidence(
                candidate,
                reference_date,
            )

            if details["age_days"] > MAX_AGE_DAYS:
                continue

            if confidence < 0.45:
                continue

            scored.append((confidence, candidate, details))

        if not scored:
            return EvidenceItem(
                key=self.key,
                title=self.title,
                summary=(
                    "Possible races were found, but none reached the minimum "
                    "confidence required for coaching evidence."
                ),
                status=EvidenceStatus.BUILDING,
                confidence=0.30,
                sample_size=len(candidates),
                predicted_seconds=None,
                weight=1.0,
                metadata={
                    "limitations": [
                        "Race classification remains uncertain.",
                    ],
                },
            )

        confidence, best, details = max(
            scored,
            key=lambda item: (
                item[0],
                item[1].activity_date,
            ),
        )

        goal_distance_km = None
        goal = context.goal or {}

        if goal.get("distance_m"):
            goal_distance_km = float(goal["distance_m"]) / 1000.0

        predicted_seconds = None

        if goal_distance_km:
            predicted_seconds = _riegel_prediction(
                best.elapsed_time_s,
                best.distance_km,
                goal_distance_km,
            )

        matched_distance = details[
            "matched_standard_distance_km"
        ]
        distance_label = (
            f"{matched_distance:g} km"
            if matched_distance is not None
            else f"{best.distance_km:.2f} km"
        )

        age_days = details["age_days"]
        age_text = (
            "on the latest imported activity date"
            if age_days == 0
            else f"{age_days} days before the latest imported activity"
        )

        summary = (
            f"{best.title or 'Race effort'}: {distance_label} in "
            f"{_format_duration(best.elapsed_time_s)}, {age_text}. "
            "Elapsed time is used for race evidence."
        )

        strengths = [
            "Race-like title detected",
            "Elapsed time available",
            f"Recency score {details['recency_score']:.0%}",
            f"Distance certainty {details['distance_score']:.0%}",
        ]

        limitations = [
            "Certification and course accuracy are not yet verified.",
            "The initial goal-distance conversion uses the generic "
            "Riegel model.",
        ]

        if best.temperature_c is not None:
            limitations.append(
                "Weather is recorded but race-time weather adjustment "
                "is not yet applied."
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
                "activity_id": best.activity_id,
                "activity_date": best.activity_date.isoformat(),
                "title": best.title,
                "distance_km": best.distance_km,
                "elapsed_time_s": best.elapsed_time_s,
                "moving_time_s": best.moving_time_s,
                "temperature_c": best.temperature_c,
                "humidity": best.humidity,
                "strengths": strengths,
                "limitations": limitations,
                "score_breakdown": details,
            },
        )

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
                a.temperature_c,
                a.humidity
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
                temperature_c,
                humidity,
            ) = row

            if _title_score(title or "") <= 0:
                continue

            elapsed = elapsed_time_s or moving_time_s

            if not distance_km or not elapsed or elapsed <= 0:
                continue

            try:
                activity_date = datetime.date.fromisoformat(
                    activity_date_text[:10]
                )
            except (TypeError, ValueError):
                continue

            candidates.append(
                RaceCandidate(
                    activity_id=activity_id,
                    activity_date=activity_date,
                    title=title or "Race effort",
                    distance_km=float(distance_km),
                    elapsed_time_s=float(elapsed),
                    moving_time_s=(
                        float(moving_time_s)
                        if moving_time_s is not None
                        else None
                    ),
                    avg_hr=(
                        float(avg_hr)
                        if avg_hr is not None
                        else None
                    ),
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
                )
            )

        conn.close()
        return candidates, latest_date


def _format_duration(seconds: float) -> str:
    total = int(round(seconds))
    hours = total // 3600
    minutes = (total % 3600) // 60
    remaining = total % 60

    if hours:
        return f"{hours}:{minutes:02d}:{remaining:02d}"

    return f"{minutes}:{remaining:02d}"
