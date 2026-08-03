"""
Threshold Coach v1.

This provider identifies whole-activity threshold-like sessions using:
- heart rate relative to the athlete's LT2;
- sustained duration;
- continuity;
- recency;
- supporting title language.

It deliberately does not pretend to reconstruct individual intervals from
activity summaries. FIT-lap and split analysis will improve this later.
"""

from __future__ import annotations

import datetime
import math
from dataclasses import dataclass

from core.coaching import RunProfile, equivalent_performance
from core.database import get_connection
from core.evidence import EvidenceItem, EvidenceStatus
from core.evidence_providers.base import EvidenceContext, EvidenceProvider


RUNNING_SPORT_ID = "965611"
MAX_AGE_DAYS = 548
MIN_SCORE = 48.0

THRESHOLD_WORDS = (
    "threshold",
    "tempo",
    "cruise",
    "20 min",
    "20min",
    "30 min",
    "30min",
    "2 x 20",
    "2x20",
    "3 x 10",
    "3x10",
    "4 x 8",
    "4x8",
    "mile reps",
)

RACE_WORDS = (
    "race",
    "parkrun",
    "5k",
    "10k",
    "half marathon",
    "marathon",
    "handicap",
)

EASY_WORDS = (
    "easy",
    "recovery",
    "steady",
    "long run",
    "warm up",
    "warm-up",
    "cool down",
    "cool-down",
)

TARGET_PACE_FACTORS = {
    5.0: 0.94,
    10.0: 0.98,
    16.09344: 1.02,
    21.0975: 1.04,
    42.195: 1.12,
}


@dataclass(frozen=True)
class ThresholdCandidate:
    activity_id: int
    activity_date: datetime.date
    title: str
    distance_km: float
    moving_time_s: float
    elapsed_time_s: float | None
    avg_hr: float | None
    max_hr: float | None
    lt2_hr: float | None
    athlete_max_hr: float | None
    elevation_m: float | None
    temperature_c: float | None
    humidity: float | None


@dataclass(frozen=True)
class ScoredThreshold:
    candidate: ThresholdCandidate
    score: float
    recency: float
    heart_rate: float
    duration: float
    continuity: float
    title_signal: float
    race_penalty: float
    easy_penalty: float
    equivalent_pace_s_per_km: float
    actual_pace_s_per_km: float
    age_days: int
    moving_ratio: float | None


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(value, high))


def _contains(title: str, words: tuple[str, ...]) -> bool:
    normalised = (title or "").lower()
    return any(word in normalised for word in words)


def _recency(age_days: int) -> float:
    if age_days < 0:
        return 0.0
    if age_days <= 30:
        return 1.0
    if age_days <= 90:
        return 0.85
    if age_days <= 183:
        return 0.65
    if age_days <= 365:
        return 0.35
    if age_days <= MAX_AGE_DAYS:
        return 0.15
    return 0.0


def _duration_signal(seconds: float) -> float:
    minutes = seconds / 60.0

    if 25 <= minutes <= 60:
        return 1.0
    if 20 <= minutes < 25 or 60 < minutes <= 75:
        return 0.80
    if 15 <= minutes < 20 or 75 < minutes <= 90:
        return 0.50
    return 0.10


def _continuity(
    moving_time_s: float,
    elapsed_time_s: float | None,
) -> tuple[float, float | None]:
    if not elapsed_time_s or elapsed_time_s <= 0:
        return 0.55, None

    ratio = _clamp(moving_time_s / elapsed_time_s)

    if ratio >= 0.99:
        return 1.0, ratio
    if ratio >= 0.97:
        return 0.85, ratio
    if ratio >= 0.93:
        return 0.60, ratio
    return 0.20, ratio


def _heart_rate_signal(candidate: ThresholdCandidate) -> float:
    signals = []

    if candidate.avg_hr and candidate.lt2_hr and candidate.lt2_hr > 0:
        ratio = candidate.avg_hr / candidate.lt2_hr

        if 0.96 <= ratio <= 1.04:
            signals.append(1.0)
        elif 0.92 <= ratio < 0.96 or 1.04 < ratio <= 1.08:
            signals.append(0.75)
        elif 0.88 <= ratio < 0.92:
            signals.append(0.45)
        else:
            signals.append(0.15)

    if candidate.max_hr and candidate.athlete_max_hr:
        ratio = candidate.max_hr / candidate.athlete_max_hr
        signals.append(_clamp((ratio - 0.82) / 0.14))

    if not signals:
        return 0.35

    return sum(signals) / len(signals)


def _nearest_goal_factor(distance_km: float) -> float:
    nearest = min(
        TARGET_PACE_FACTORS,
        key=lambda standard: abs(standard - distance_km),
    )
    return TARGET_PACE_FACTORS[nearest]


def _weighted_average(values: list[tuple[float, float]]) -> float | None:
    total_weight = sum(weight for _, weight in values)

    if total_weight <= 0:
        return None

    return sum(value * weight for value, weight in values) / total_weight


def _format_pace(seconds_per_km: float) -> str:
    minutes = int(seconds_per_km // 60)
    seconds = int(round(seconds_per_km % 60))

    if seconds == 60:
        minutes += 1
        seconds = 0

    return f"{minutes}:{seconds:02d}/km"


class ThresholdEvidenceProvider(EvidenceProvider):
    key = "threshold"
    title = "Threshold Coach"

    def build(self, context: EvidenceContext) -> EvidenceItem:
        candidates, reference_date = self._load_candidates(context.athlete_id)

        if not candidates:
            return self._unavailable(
                "No running activities had enough data for threshold analysis."
            )

        scored = []

        for candidate in candidates:
            item = self._score(candidate, reference_date)
            if item is not None and item.score >= MIN_SCORE:
                scored.append(item)

        scored.sort(
            key=lambda item: (item.score, item.candidate.activity_date),
            reverse=True,
        )

        if not scored:
            return EvidenceItem(
                key=self.key,
                title=self.title,
                summary=(
                    "Threshold-like efforts were inspected, but none reached "
                    "the minimum evidence score."
                ),
                status=EvidenceStatus.BUILDING,
                confidence=0.30,
                sample_size=len(candidates),
                predicted_seconds=None,
                weight=0.9,
                metadata={
                    "limitations": [
                        "Whole-activity summaries cannot yet isolate intervals.",
                        "FIT lap and split analysis will improve recognition.",
                    ],
                    "candidate_debug": [],
                },
            )

        representative = scored[: min(5, len(scored))]
        pace_values = [
            (
                item.equivalent_pace_s_per_km,
                max(item.score, 1.0),
            )
            for item in representative
        ]
        threshold_pace = _weighted_average(pace_values)

        goal = context.goal or {}
        goal_distance_km = (
            float(goal["distance_m"]) / 1000.0
            if goal.get("distance_m")
            else None
        )

        predicted_seconds = None

        if threshold_pace is not None and goal_distance_km:
            race_pace = threshold_pace * _nearest_goal_factor(
                goal_distance_km
            )
            predicted_seconds = race_pace * goal_distance_km

        recent = [
            item
            for item in scored
            if item.age_days <= 90
        ]
        previous = [
            item
            for item in scored
            if 90 < item.age_days <= 270
        ]

        recent_pace = _weighted_average(
            [
                (item.equivalent_pace_s_per_km, item.score)
                for item in recent[:5]
            ]
        )
        previous_pace = _weighted_average(
            [
                (item.equivalent_pace_s_per_km, item.score)
                for item in previous[:5]
            ]
        )

        trend = "Stable"
        change_s_per_km = None

        if recent_pace is not None and previous_pace is not None:
            change_s_per_km = previous_pace - recent_pace

            if change_s_per_km >= 3:
                trend = "Improving"
            elif change_s_per_km <= -3:
                trend = "Declining"

        best = scored[0]
        sample_factor = min(len(scored) / 8.0, 1.0)
        confidence = _clamp(
            (best.score / 100.0) * 0.65
            + sample_factor * 0.35
        )

        summary = (
            f"Current threshold estimate: {_format_pace(threshold_pace)} "
            f"from {len(representative)} representative session(s). "
            f"Trend: {trend.lower()}."
        )

        recommendation = (
            "Maintain the current threshold pattern."
            if trend in ("Improving", "Stable")
            else "Consider reducing intensity and rebuilding consistency."
        )

        strengths = [
            f"{len(scored)} threshold-like sessions identified",
            f"Best session score {best.score:.1f}/100",
            "Pace adjusted for available temperature and humidity data",
            "Heart rate compared with the athlete's LT2 where available",
        ]

        limitations = [
            "Whole-activity summaries cannot separate work intervals from recoveries.",
            "Elevation is reported but not yet used as a precise pace correction.",
            "Surface and wind are not stored reliably enough for adjustment.",
            "Goal conversion uses transparent generic race-pace factors.",
        ]

        return EvidenceItem(
            key=self.key,
            title=self.title,
            summary=summary,
            status=EvidenceStatus.AVAILABLE,
            confidence=confidence,
            sample_size=len(scored),
            predicted_seconds=predicted_seconds,
            weight=0.9,
            metadata={
                "threshold_pace_seconds_per_km": threshold_pace,
                "threshold_pace_text": _format_pace(threshold_pace),
                "trend": trend,
                "change_seconds_per_km": change_s_per_km,
                "recommendation": recommendation,
                "selected_activity_id": best.candidate.activity_id,
                "selected_title": best.candidate.title,
                "selected_date": best.candidate.activity_date.isoformat(),
                "strengths": strengths,
                "limitations": limitations,
                "candidate_debug": self._debug(scored[:10]),
            },
        )

    def _score(
        self,
        candidate: ThresholdCandidate,
        reference_date: datetime.date,
    ) -> ScoredThreshold | None:
        run = RunProfile(
            title=candidate.title,
            sport_id=RUNNING_SPORT_ID,
            distance_km=candidate.distance_km,
            moving_time_seconds=candidate.moving_time_s,
            avg_hr=candidate.avg_hr,
            run_max_hr=candidate.max_hr,
            activity_date=candidate.activity_date.isoformat(),
            elevation_m=candidate.elevation_m,
            temperature_c=candidate.temperature_c,
            humidity=candidate.humidity,
            lt2_hr=candidate.lt2_hr,
            athlete_max_hr=candidate.athlete_max_hr,
        )
        performance = equivalent_performance(run)

        if performance is None:
            return None

        age_days = (reference_date - candidate.activity_date).days
        recency = _recency(age_days)
        heart_rate = _heart_rate_signal(candidate)
        duration = _duration_signal(candidate.moving_time_s)
        continuity, moving_ratio = _continuity(
            candidate.moving_time_s,
            candidate.elapsed_time_s,
        )
        title_signal = 1.0 if _contains(
            candidate.title,
            THRESHOLD_WORDS,
        ) else 0.0
        race_penalty = 1.0 if _contains(
            candidate.title,
            RACE_WORDS,
        ) else 0.0
        easy_penalty = 1.0 if _contains(
            candidate.title,
            EASY_WORDS,
        ) else 0.0

        score = (
            recency * 20.0
            + heart_rate * 32.0
            + duration * 20.0
            + continuity * 15.0
            + title_signal * 10.0
            + 3.0
            - race_penalty * 25.0
            - easy_penalty * 35.0
        )

        return ScoredThreshold(
            candidate=candidate,
            score=score,
            recency=recency,
            heart_rate=heart_rate,
            duration=duration,
            continuity=continuity,
            title_signal=title_signal,
            race_penalty=race_penalty,
            easy_penalty=easy_penalty,
            equivalent_pace_s_per_km=(
                performance.equivalent_pace_seconds_per_km
            ),
            actual_pace_s_per_km=(
                performance.actual_pace_seconds_per_km
            ),
            age_days=age_days,
            moving_ratio=moving_ratio,
        )

    def _load_candidates(
        self,
        athlete_id: int,
    ) -> tuple[list[ThresholdCandidate], datetime.date]:
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
        reference_date = (
            datetime.date.fromisoformat(row[0])
            if row and row[0]
            else datetime.date.today()
        )

        cursor.execute(
            """
            SELECT
                a.id,
                a.activity_date,
                a.title,
                a.distance_m,
                a.moving_time_s,
                a.elapsed_time_s,
                a.avg_hr,
                a.max_hr,
                at.lt2_hr,
                at.max_hr,
                a.elevation_up_m,
                a.temperature_c,
                a.humidity
            FROM activities a
            JOIN athletes at ON at.id = a.athlete_id
            WHERE a.athlete_id = ?
              AND CAST(a.sport_id AS TEXT) = ?
              AND a.activity_date IS NOT NULL
              AND a.distance_m BETWEEN 3.0 AND 20.0
              AND a.moving_time_s BETWEEN 900 AND 5400
              AND (
                    a.avg_hr IS NOT NULL
                    OR lower(COALESCE(a.title, '')) LIKE '%threshold%'
                    OR lower(COALESCE(a.title, '')) LIKE '%tempo%'
                  )
            ORDER BY a.activity_datetime DESC
            """,
            (athlete_id, RUNNING_SPORT_ID),
        )

        result = []

        for row in cursor.fetchall():
            try:
                activity_date = datetime.date.fromisoformat(row[1][:10])
            except (TypeError, ValueError):
                continue

            result.append(
                ThresholdCandidate(
                    activity_id=int(row[0]),
                    activity_date=activity_date,
                    title=row[2] or "Threshold-like session",
                    distance_km=float(row[3]),
                    moving_time_s=float(row[4]),
                    elapsed_time_s=(
                        float(row[5]) if row[5] is not None else None
                    ),
                    avg_hr=float(row[6]) if row[6] is not None else None,
                    max_hr=float(row[7]) if row[7] is not None else None,
                    lt2_hr=float(row[8]) if row[8] is not None else None,
                    athlete_max_hr=(
                        float(row[9]) if row[9] is not None else None
                    ),
                    elevation_m=(
                        float(row[10]) if row[10] is not None else None
                    ),
                    temperature_c=(
                        float(row[11]) if row[11] is not None else None
                    ),
                    humidity=(
                        float(row[12]) if row[12] is not None else None
                    ),
                )
            )

        conn.close()
        return result, reference_date

    def _debug(self, scored: list[ScoredThreshold]) -> list[dict]:
        return [
            {
                "date": item.candidate.activity_date.isoformat(),
                "title": item.candidate.title,
                "distance_km": round(item.candidate.distance_km, 2),
                "actual_pace": _format_pace(item.actual_pace_s_per_km),
                "equivalent_pace": _format_pace(
                    item.equivalent_pace_s_per_km
                ),
                "avg_hr": item.candidate.avg_hr,
                "moving_ratio": (
                    round(item.moving_ratio, 4)
                    if item.moving_ratio is not None
                    else None
                ),
                "score": round(item.score, 1),
                "recency": round(item.recency, 3),
                "heart_rate": round(item.heart_rate, 3),
                "duration": round(item.duration, 3),
                "continuity": round(item.continuity, 3),
            }
            for item in scored
        ]

    def _unavailable(self, message: str) -> EvidenceItem:
        return EvidenceItem(
            key=self.key,
            title=self.title,
            summary=message,
            status=EvidenceStatus.UNAVAILABLE,
            confidence=0.0,
            sample_size=0,
            predicted_seconds=None,
            weight=0.9,
            metadata={
                "limitations": [
                    "More threshold-like sessions or richer FIT data are needed."
                ]
            },
        )
