"""
Threshold Coach v1.

This provider identifies whole-activity threshold-like sessions using:
- heart rate progressively from LT1 towards LT2;
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
import json
from dataclasses import dataclass
from statistics import median

from core.activity_reliability import has_reliable_distance_and_pace
from core.coaching import (
    RunProfile,
    equivalent_performance,
    humidity_adjustment_seconds_per_km,
    temperature_adjustment_seconds_per_km,
)
from core.database import get_athlete_sport_roles, get_connection
from core.distance_calibration import personal_pb_ratio_projection
from core.pb_shape import find_race_pb
from core.splits import parse_splits, recognise_workout, splits_to_dicts
from core.workouts import get_or_decode_workout
from core.evidence import EvidenceItem, EvidenceStatus
from core.evidence_providers.base import EvidenceContext, EvidenceProvider
from core.race_detection import score_race_evidence


MAX_AGE_DAYS = 548
MIN_SCORE = 58.0

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
    athlete_id: int
    sport_id: str | None
    activity_date: datetime.date
    title: str
    distance_km: float
    moving_time_s: float
    elapsed_time_s: float | None
    avg_hr: float | None
    max_hr: float | None
    lt1_hr: float | None
    lt2_hr: float | None
    athlete_max_hr: float | None
    elevation_m: float | None
    temperature_c: float | None
    humidity: float | None
    raw_splits: str | None
    raw_json_text: str | None


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


def _as_date(value: str | None) -> datetime.date | None:
    if not value:
        return None

    try:
        return datetime.date.fromisoformat(value[:10])
    except (TypeError, ValueError):
        return None


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
    """
    Score threshold HR progressively from LT1 towards LT2.

    LT1 is the entry point for threshold evidence. The signal strengthens
    through the LT1-LT2 range rather than requiring the whole-activity
    average to sit close to LT2. This is more robust for interval recoveries
    and wrist-based heart-rate data.
    """
    signals = []

    if (
        candidate.avg_hr
        and candidate.lt1_hr
        and candidate.lt2_hr
        and candidate.lt2_hr > candidate.lt1_hr > 0
    ):
        span = candidate.lt2_hr - candidate.lt1_hr
        position = (
            candidate.avg_hr - candidate.lt1_hr
        ) / span

        if position < -0.15:
            avg_signal = 0.10
        elif position < 0.0:
            avg_signal = 0.30 + (position + 0.15) / 0.15 * 0.20
        elif position <= 1.0:
            avg_signal = 0.50 + position * 0.50
        elif position <= 1.20:
            avg_signal = 1.0 - (position - 1.0) / 0.20 * 0.20
        else:
            avg_signal = 0.55

        signals.append(_clamp(avg_signal))

    elif candidate.avg_hr and candidate.lt1_hr and candidate.lt1_hr > 0:
        ratio = candidate.avg_hr / candidate.lt1_hr

        if 1.00 <= ratio <= 1.12:
            signals.append(0.70)
        elif 0.95 <= ratio < 1.00:
            signals.append(0.50)
        elif 1.12 < ratio <= 1.20:
            signals.append(0.65)
        else:
            signals.append(0.20)

    elif candidate.avg_hr and candidate.lt2_hr and candidate.lt2_hr > 0:
        ratio = candidate.avg_hr / candidate.lt2_hr
        signals.append(_clamp((ratio - 0.82) / 0.18))

    if candidate.max_hr and candidate.athlete_max_hr:
        ratio = candidate.max_hr / candidate.athlete_max_hr
        max_signal = _clamp((ratio - 0.78) / 0.18)
        signals.append(max_signal * 0.75)

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


def _weather_adjusted_rep_pace(
    candidate: ThresholdCandidate,
    raw_rep_pace_s_per_km: float,
) -> tuple[float, dict]:
    """
    Convert recognised rep pace to a conservative cool-weather equivalent.

    This uses the same temperature and humidity/dew-point penalties already
    used elsewhere in Performance Passport. Elevation, surface and wind are
    still reported as limitations rather than guessed.
    """
    temperature_cost = temperature_adjustment_seconds_per_km(
        candidate.temperature_c
    )
    humidity_cost = humidity_adjustment_seconds_per_km(
        candidate.temperature_c,
        candidate.humidity,
    )
    total_cost = max(temperature_cost + humidity_cost, 0.0)

    adjusted = max(raw_rep_pace_s_per_km - total_cost, 1.0)

    return adjusted, {
        "raw_rep_pace_seconds_per_km": raw_rep_pace_s_per_km,
        "temperature_cost_seconds_per_km": temperature_cost,
        "humidity_cost_seconds_per_km": humidity_cost,
        "total_weather_cost_seconds_per_km": total_cost,
        "adjusted_rep_pace_seconds_per_km": adjusted,
    }


def _split_threshold_evidence(candidate: ThresholdCandidate):
    decoded = get_or_decode_workout(
        candidate.activity_id,
        candidate.raw_json_text,
    )
    splits = parse_splits(candidate.raw_splits)
    recognition = recognise_workout(splits)

    if not decoded.recognition_json.get("work_splits"):
        return None, recognition, splits

    average_distance = decoded.average_rep_distance_km or 0.0
    workout_type = decoded.workout_type

    if workout_type == "Long threshold repetitions":
        relevance = 1.0
    elif workout_type == "Mile repetitions":
        relevance = 0.88
    elif workout_type == "Long intervals" and average_distance >= 0.8:
        relevance = 0.62
    elif workout_type == "Continuous sustained effort":
        relevance = 0.70
    else:
        relevance = 0.0

    if decoded.rep_count >= 2 and relevance > 0:
        relevance += 0.05

    return min(relevance, 1.0), recognition, splits


class ThresholdEvidenceProvider(EvidenceProvider):
    key = "threshold"
    title = "Threshold Coach"

    def build(self, context: EvidenceContext) -> EvidenceItem:
        candidates, reference_date = self._load_candidates(context.athlete_id)
        easy_pace = self._easy_pace_anchor(candidates, reference_date)
        phase_evidence = self._trusted_threshold_phases(
            context.athlete_id,
            easy_pace,
        )

        if not candidates:
            return self._unavailable(
                "No running activities had enough data for threshold analysis."
            )

        scored = []

        for candidate in candidates:
            item = self._score(
                candidate,
                reference_date,
                easy_pace=easy_pace,
                trusted_phase=phase_evidence.get(candidate.activity_id),
            )
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
        recent_five_k_floor = self._five_k_threshold_floor(
            candidates,
            reference_date,
        )
        if threshold_pace is not None and recent_five_k_floor is not None:
            threshold_pace = max(threshold_pace, recent_five_k_floor)

        goal = context.goal or {}
        goal_distance_km = (
            float(goal["distance_m"]) / 1000.0
            if goal.get("distance_m")
            else None
        )

        predicted_seconds = None
        generic_predicted_seconds = None
        personal_distance_calibration = None

        if threshold_pace is not None and goal_distance_km:
            race_pace = threshold_pace * _nearest_goal_factor(
                goal_distance_km
            )
            generic_predicted_seconds = race_pace * goal_distance_km
            predicted_seconds = generic_predicted_seconds

            if goal_distance_km >= 15.0:
                source_pb = find_race_pb(
                    athlete_id=context.athlete_id,
                    goal_distance_km=10.0,
                )
                target_pb = find_race_pb(
                    athlete_id=context.athlete_id,
                    goal_distance_km=goal_distance_km,
                )
                if source_pb and target_pb:
                    target_pb_date = _as_date(target_pb.get("date"))
                    source_pb_date = _as_date(source_pb.get("date"))
                    dates_are_relevant = bool(
                        target_pb_date
                        and source_pb_date
                        and 0 <= (reference_date - target_pb_date).days <= 365
                        and 0 <= (reference_date - source_pb_date).days <= 1825
                    )
                    if (
                        dates_are_relevant
                        and source_pb.get("classification") == "confirmed_race"
                        and target_pb.get("classification") == "confirmed_race"
                    ):
                        current_ten_k_seconds = (
                            threshold_pace
                            * TARGET_PACE_FACTORS[10.0]
                            * 10.0
                        )
                        personal_distance_calibration = (
                            personal_pb_ratio_projection(
                                source_distance_km=10.0,
                                target_distance_km=goal_distance_km,
                                source_pb_seconds=float(source_pb["time_s"]),
                                source_current_seconds=current_ten_k_seconds,
                                target_pb_seconds=float(target_pb["time_s"]),
                            )
                        )
                        if personal_distance_calibration is not None:
                            personal_distance_calibration.update(
                                {
                                    "source_pb_date": source_pb["date"],
                                    "source_pb_title": source_pb["title"],
                                    "target_pb_date": target_pb["date"],
                                    "target_pb_title": target_pb["title"],
                                }
                            )
                            predicted_seconds = personal_distance_calibration[
                                "predicted_seconds"
                            ]

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
        trend_confidence = "Limited"
        change_s_per_km = None

        if recent_pace is not None and previous_pace is not None:
            change_s_per_km = previous_pace - recent_pace

            recent_count = len(recent[:5])
            previous_count = len(previous[:5])

            if recent_count >= 2 and previous_count >= 2:
                trend_confidence = "Moderate"

            if recent_count >= 3 and previous_count >= 3:
                trend_confidence = "Strong"

            if change_s_per_km >= 3:
                trend = "Improving"
            elif change_s_per_km <= -3:
                trend = (
                    "Declining"
                    if trend_confidence == "Strong"
                    else "Possible decline"
                )

        best = scored[0]
        sample_factor = min(len(scored) / 12.0, 1.0)
        comparability_factor = min(len(representative) / 5.0, 1.0)
        confidence = _clamp(
            (best.score / 100.0) * 0.55
            + sample_factor * 0.25
            + comparability_factor * 0.20
        )

        recent_text = (
            _format_pace(recent_pace)
            if recent_pace is not None
            else "unavailable"
        )
        previous_text = (
            _format_pace(previous_pace)
            if previous_pace is not None
            else "unavailable"
        )

        summary = (
            f"Current threshold estimate: {_format_pace(threshold_pace)}, "
            f"calculated from the {len(representative)} strongest comparable "
            f"sessions out of {len(scored)} identified. "
            f"Trend: {trend.lower()} ({trend_confidence.lower()} confidence). "
            f"Recent adjusted pace {recent_text}; earlier adjusted pace "
            f"{previous_text}."
        )

        if trend == "Improving":
            recommendation = "Maintain the current threshold pattern."
        elif trend == "Stable":
            recommendation = "Keep the current threshold structure consistent."
        elif trend == "Possible decline":
            recommendation = (
                "Do not change training from this signal alone; gather more "
                "comparable sessions first."
            )
        else:
            recommendation = (
                "Review fatigue and recent session quality before increasing "
                "threshold intensity."
            )

        best_splits = parse_splits(best.candidate.raw_splits)
        best_recognition = recognise_workout(best_splits)

        strengths = [
            f"{len(scored)} threshold-like sessions identified",
            f"Best session score {best.score:.1f}/100",
            "Pace adjusted for available temperature and humidity data",
            "Heart rate assessed progressively from LT1 towards LT2",
        ]

        if best_recognition.work_splits:
            strengths.append(
                f"Split decoder recognised: {best_recognition.description}"
            )

        limitations = [
            "Recognised rep pace is adjusted for activity-level temperature and humidity, but per-lap heart rate is unavailable.",
            "Elevation is reported but not yet used as a precise pace correction.",
            "Surface and wind are not stored reliably enough for adjustment.",
            (
                "Longer-goal conversion uses the athlete's own verified 10K-to-goal PB relationship."
                if personal_distance_calibration is not None
                else "Goal conversion uses transparent generic race-pace factors."
            ),
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
                "generic_predicted_seconds": generic_predicted_seconds,
                "personal_distance_calibration": personal_distance_calibration,
                "threshold_pace_text": _format_pace(threshold_pace),
                "recent_five_k_threshold_floor_seconds_per_km": (
                    round(recent_five_k_floor, 1)
                    if recent_five_k_floor is not None
                    else None
                ),
                "trend": trend,
                "trend_confidence": trend_confidence,
                "change_seconds_per_km": change_s_per_km,
                "recent_adjusted_pace_seconds_per_km": recent_pace,
                "previous_adjusted_pace_seconds_per_km": previous_pace,
                "recent_session_count": len(recent[:5]),
                "previous_session_count": len(previous[:5]),
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
        *,
        easy_pace: float | None = None,
        trusted_phase: tuple[float, float, float] | None = None,
    ) -> ScoredThreshold | None:
        try:
            raw = json.loads(candidate.raw_json_text or "{}")
        except (TypeError, json.JSONDecodeError):
            raw = {}
        raw = raw if isinstance(raw, dict) else {}
        genuine_title = str(
            raw.get("title")
            or (
                ""
                if candidate.title == "Threshold-like session"
                else candidate.title
            )
        )
        race_signals = score_race_evidence(
            title=genuine_title,
            distance_km=candidate.distance_km,
            moving_time_s=candidate.moving_time_s,
            elapsed_time_s=candidate.elapsed_time_s,
            avg_hr=candidate.avg_hr,
            max_hr=candidate.max_hr,
            athlete_lt2_hr=candidate.lt2_hr,
            athlete_max_hr=candidate.athlete_max_hr,
            official_race_name=raw.get("race_name"),
            official_distance_m=raw.get("race_officialDistance"),
            official_time_s=raw.get("race_officialTime"),
            officially_measured=bool(raw.get("race_officiallyMeasured")),
        )
        if race_signals.classification in {
            "confirmed_race",
            "race_quality_effort",
        }:
            split_check = recognise_workout(parse_splits(candidate.raw_splits))
            genuinely_interrupted = bool(
                split_check.recovery_splits
                or split_check.unknown_recovery_count
            )
            explicitly_threshold = _contains(genuine_title, THRESHOLD_WORDS)
            if not genuinely_interrupted and not explicitly_threshold:
                return None

        run = RunProfile(
            athlete_id=candidate.athlete_id,
            title=candidate.title,
            sport_id=candidate.sport_id,
            distance_km=candidate.distance_km,
            moving_time_seconds=candidate.moving_time_s,
            avg_hr=candidate.avg_hr,
            run_max_hr=candidate.max_hr,
            activity_date=candidate.activity_date.isoformat(),
            elevation_m=candidate.elevation_m,
            temperature_c=candidate.temperature_c,
            humidity=candidate.humidity,
            lt1_hr=candidate.lt1_hr,
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

        split_relevance, recognition, parsed_splits = (
            _split_threshold_evidence(candidate)
        )
        phase_pace = None
        if trusted_phase is not None:
            phase_pace, _phase_distance, phase_confidence = trusted_phase
            split_relevance = max(split_relevance or 0.0, 0.95)

        observed_work_pace = (
            phase_pace
            if phase_pace is not None
            else recognition.average_rep_pace_s_per_km
        )
        if (
            easy_pace is not None
            and observed_work_pace is not None
            and observed_work_pace > easy_pace * 0.90
        ):
            return None

        # A decoded structure must be genuinely threshold-relevant.
        # Short intervals, mixed sessions and ordinary route splits are not
        # allowed to become threshold evidence just because HR was elevated.
        if split_relevance == 0.0 and title_signal == 0.0:
            return None

        structure_confidence = (
            max(recognition.confidence, phase_confidence)
            if trusted_phase is not None
            else recognition.confidence
        )
        split_bonus = (
            structure_confidence * split_relevance * 28.0
            if split_relevance is not None
            else 0.0
        )

        score = (
            recency * 18.0
            + heart_rate * 27.0
            + duration * 15.0
            + continuity * 12.0
            + title_signal * 7.0
            + split_bonus
            + 3.0
            - race_penalty * 25.0
            - easy_penalty * 35.0
        )

        split_adjustment = None

        if (
            split_relevance is not None
            and split_relevance >= 0.55
            and observed_work_pace is not None
        ):
            equivalent_pace, split_adjustment = _weather_adjusted_rep_pace(
                candidate,
                observed_work_pace,
            )
        else:
            equivalent_pace = performance.equivalent_pace_seconds_per_km

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
            equivalent_pace_s_per_km=equivalent_pace,
            actual_pace_s_per_km=(
                performance.actual_pace_seconds_per_km
            ),
            age_days=age_days,
            moving_ratio=moving_ratio,
        )

    def _easy_pace_anchor(
        self,
        candidates: list[ThresholdCandidate],
        reference_date: datetime.date,
    ) -> float | None:
        paces = []
        for candidate in candidates:
            age_days = (reference_date - candidate.activity_date).days
            if age_days < 0 or age_days > 365:
                continue
            if not candidate.lt1_hr or not candidate.avg_hr:
                continue
            if candidate.avg_hr > candidate.lt1_hr * 0.95:
                continue
            if candidate.distance_km < 4.0 or candidate.distance_km > 20.0:
                continue
            if (
                candidate.elapsed_time_s
                and candidate.moving_time_s / candidate.elapsed_time_s < 0.90
            ):
                continue
            pace = candidate.moving_time_s / candidate.distance_km
            if 200.0 <= pace <= 480.0:
                paces.append(pace)
        return float(median(paces)) if len(paces) >= 8 else None

    def _trusted_threshold_phases(
        self,
        athlete_id: int,
        easy_pace: float | None,
    ) -> dict[int, tuple[float, float, float]]:
        connection = get_connection()
        try:
            rows = connection.execute(
                """
                SELECT activity_id, phase_json, phase_confidence
                FROM workout_library
                WHERE athlete_id = ?
                  AND recognition_confidence >= 0.65
                  AND phase_confidence >= 0.70
                """,
                (athlete_id,),
            ).fetchall()
        except Exception:
            connection.close()
            return {}
        connection.close()

        accepted_types = {
            "threshold", "continuous_threshold", "long_threshold",
            "sustained_quality",
        }
        result = {}
        for activity_id, raw_phases, phase_confidence in rows:
            try:
                phases = json.loads(raw_phases or "[]")
            except (TypeError, json.JSONDecodeError):
                continue
            matching = []
            for phase in phases if isinstance(phases, list) else ():
                try:
                    pace = float(phase.get("pace_s_per_km") or 0.0)
                    distance = float(phase.get("distance_km") or 0.0)
                    confidence = float(phase.get("confidence") or 0.0)
                except (AttributeError, TypeError, ValueError):
                    continue
                if (
                    str(phase.get("phase_type") or "").lower()
                    not in accepted_types
                    or pace <= 0
                    or distance <= 0
                    or confidence < 0.80
                ):
                    continue
                matching.append((pace, distance, confidence))
            distance = sum(item[1] for item in matching)
            if distance < 2.5:
                continue
            pace = sum(item[0] * item[1] for item in matching) / distance
            if easy_pace is not None and pace > easy_pace * 0.90:
                continue
            result[int(activity_id)] = (
                pace,
                distance,
                max(float(phase_confidence or 0.0), min(p[2] for p in matching)),
            )
        return result

    def _five_k_threshold_floor(
        self,
        candidates: list[ThresholdCandidate],
        reference_date: datetime.date,
    ) -> float | None:
        observed_paces = []
        for candidate in candidates:
            age_days = (reference_date - candidate.activity_date).days
            if age_days < 0 or age_days > 180:
                continue
            if not 4.80 <= candidate.distance_km <= 5.20:
                continue
            if (
                candidate.elapsed_time_s
                and candidate.moving_time_s / candidate.elapsed_time_s < 0.97
            ):
                continue
            if _contains(candidate.title, EASY_WORDS):
                continue
            observed_paces.append(
                candidate.moving_time_s / candidate.distance_km
            )
        if not observed_paces:
            return None
        # Threshold is sustainable for materially longer than a maximal 5K.
        # This conservative separation prevents short fast reps being sold as
        # threshold pace while preserving genuine athlete-specific evidence.
        return min(observed_paces) * 1.04

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

        sport_roles = get_athlete_sport_roles(athlete_id)
        running_sport_ids = [
            sport_id
            for sport_id, role in sport_roles.items()
            if role == "running"
        ]

        if not running_sport_ids:
            conn.close()
            return [], reference_date

        placeholders = ",".join("?" for _ in running_sport_ids)

        cursor.execute(
            f"""
            SELECT
                a.id,
                a.athlete_id,
                CAST(a.sport_id AS TEXT),
                a.activity_date,
                a.title,
                a.distance_m,
                a.moving_time_s,
                a.elapsed_time_s,
                a.avg_hr,
                a.max_hr,
                at.lt1_hr,
                at.lt2_hr,
                at.max_hr,
                a.elevation_up_m,
                a.temperature_c,
                a.humidity,
                a.raw_json
            FROM activities a
            JOIN athletes at ON at.id = a.athlete_id
            WHERE a.athlete_id = ?
              AND CAST(a.sport_id AS TEXT) IN ({placeholders})
              AND a.activity_date IS NOT NULL
              AND a.distance_m BETWEEN 3.0 AND 20.0
              AND a.moving_time_s BETWEEN 900 AND 5400
              AND date(a.activity_date) >= date(?, '-730 days')
              AND (
                    (
                        a.avg_hr IS NOT NULL
                        AND at.lt1_hr IS NOT NULL
                        AND a.avg_hr >= at.lt1_hr * 0.85
                    )
                    OR lower(COALESCE(a.title, '')) LIKE '%threshold%'
                    OR lower(COALESCE(a.title, '')) LIKE '%tempo%'
                    OR lower(COALESCE(a.title, '')) LIKE '%cruise%'
                    OR lower(COALESCE(a.title, '')) LIKE '%interval%'
                    OR lower(COALESCE(a.title, '')) LIKE '%reps%'
                    OR a.raw_json LIKE '%"splits": "I%'
                  )
            ORDER BY a.activity_datetime DESC
            """,
            (
                athlete_id,
                *running_sport_ids,
                reference_date.isoformat(),
            ),
        )

        result = []

        for row in cursor.fetchall():
            if not has_reliable_distance_and_pace(
                title=row[4],
                sport_id=str(row[2] or ""),
                raw_json_text=row[16],
            ):
                continue

            try:
                activity_date = datetime.date.fromisoformat(row[3][:10])
            except (TypeError, ValueError):
                continue

            result.append(
                ThresholdCandidate(
                    activity_id=int(row[0]),
                    athlete_id=int(row[1]),
                    sport_id=row[2],
                    activity_date=activity_date,
                    title=row[4] or "Threshold-like session",
                    distance_km=float(row[5]),
                    moving_time_s=float(row[6]),
                    elapsed_time_s=(
                        float(row[7]) if row[7] is not None else None
                    ),
                    avg_hr=float(row[8]) if row[8] is not None else None,
                    max_hr=float(row[9]) if row[9] is not None else None,
                    lt1_hr=float(row[10]) if row[10] is not None else None,
                    lt2_hr=float(row[11]) if row[11] is not None else None,
                    athlete_max_hr=(
                        float(row[12]) if row[12] is not None else None
                    ),
                    elevation_m=(
                        float(row[13]) if row[13] is not None else None
                    ),
                    temperature_c=(
                        float(row[14]) if row[14] is not None else None
                    ),
                    humidity=(
                        float(row[15]) if row[15] is not None else None
                    ),
                    raw_splits=(
                        self._extract_splits(row[16])
                    ),
                    raw_json_text=row[16],
                )
            )

        conn.close()
        return result, reference_date

    def _extract_splits(self, raw_json_text):
        if not raw_json_text:
            return None

        try:
            raw = json.loads(raw_json_text)
        except (TypeError, json.JSONDecodeError):
            return None

        return raw.get("splits") or raw.get("splitsCustom")

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
                "workout": self._workout_debug(item.candidate),
            }
            for item in scored
        ]

    def _workout_debug(self, candidate):
        splits = parse_splits(candidate.raw_splits)
        recognition = recognise_workout(splits)

        weather_adjustment = None

        if recognition.average_rep_pace_s_per_km is not None:
            _, weather_adjustment = _weather_adjusted_rep_pace(
                candidate,
                recognition.average_rep_pace_s_per_km,
            )

        return {
            "type": recognition.workout_type,
            "confidence": round(recognition.confidence, 3),
            "description": recognition.description,
            "weather_adjustment": weather_adjustment,
            "rep_count": recognition.rep_count,
            "average_rep_distance_km": (
                round(recognition.average_rep_distance_km, 3)
                if recognition.average_rep_distance_km is not None
                else None
            ),
            "average_rep_pace": (
                _format_pace(recognition.average_rep_pace_s_per_km)
                if recognition.average_rep_pace_s_per_km is not None
                else None
            ),
            "pace_variation_percent": (
                round(recognition.rep_pace_variation_percent, 2)
                if recognition.rep_pace_variation_percent is not None
                else None
            ),
            "splits": splits_to_dicts(splits),
        }

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
