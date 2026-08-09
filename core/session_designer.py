"""
Performance Passport Session Designer.

Single responsibility:
    Translate the Recommended Next Run into a complete, athlete-specific
    session prescription.

The Session Designer does NOT decide what training system should be prioritised.
That remains the job of the Decision Engine / Recommended Next Run.

Its job is to answer:
- Why are we doing this session?
- What exactly should I do?
- What pace / HR / RPE should I use?
- What does successful execution look like?
- Which of my own historical sessions informed this design?

Historical Response Matching
----------------------------
The first version deliberately avoids claiming causality that the data cannot
yet prove. A historical workout is treated as "worked well" when:
- it belongs to the same athlete;
- the phase structure matches the requested session family;
- execution quality was strong;
- workout recognition / phase confidence was strong;
- where available, it has credible links to subsequent races.

Race links add supporting evidence, but v1 does not claim that a workout CAUSED
a later race result. The future Learning Engine will model response over time.

When enough personal history exists, the representative structure comes from
the athlete's own successful sessions. Otherwise the engine uses a conservative
coaching template.

Recognition before recommendation.
Context before advice.
Evidence before conclusions.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime
import math
import statistics
from typing import Any

from core.database import (
    get_active_goal,
    get_connection,
    get_effective_athlete_thresholds,
)
from core.next_run import (
    NextRunRecommendation,
    build_next_run_recommendation,
)
from core.training_blocks import get_active_training_block
from core.workout_library import (
    WorkoutLibraryRecord,
    get_athlete_workouts,
)


MILES_PER_KM = 0.621371192237334

QUALITY_PHASES = {
    "threshold",
    "long_intervals",
    "short_intervals",
    "strides",
    "tempo",
    "vo2",
    "long_run",
    "steady",
}

PHASE_ALIASES = {
    "continuous_threshold": "threshold",
    "long_threshold": "threshold",
    "sustained_quality": "threshold",
    "intervals": "long_intervals",
    "mile_repetitions": "long_intervals",
    "short_interval": "short_intervals",
    "short_reps": "short_intervals",
}

FAMILY_PHASES = {
    "threshold": {"threshold", "long_intervals", "tempo"},
    "vo2": {"short_intervals", "long_intervals", "vo2"},
    "speed": {"short_intervals", "strides"},
    "endurance": {"long_run", "steady"},
}

FAMILY_LABELS = {
    "recovery": "Recovery Run",
    "easy": "Easy Aerobic",
    "threshold": "Threshold Development",
    "vo2": "VO₂ Development",
    "speed": "Speed Development",
    "endurance": "Long Easy / Endurance",
    "race_pace": "Race-Pace Development",
}

FAMILY_ICONS = {
    "recovery": "🔋",
    "easy": "😊",
    "threshold": "❤️",
    "vo2": "⚡",
    "speed": "⚡",
    "endurance": "🧱",
    "race_pace": "🏁",
}


@dataclass(frozen=True)
class HistoricalWorkoutEvidence:
    activity_id: int
    activity_date: str | None
    activity_title: str
    workout_signature: str
    execution_score: float | None
    evidence_score: float
    race_link_count: int
    best_race_link_confidence: float | None
    phase_type: str
    rep_count: int
    average_rep_distance_km: float | None
    average_rep_duration_s: float | None
    pace_s_per_km: float | None
    recovery_duration_s: float | None


@dataclass(frozen=True)
class DesignedSession:
    athlete_id: int
    family: str
    family_label: str
    icon: str

    purpose: str

    warmup: tuple[str, ...]
    main_set: tuple[str, ...]
    cooldown: tuple[str, ...]

    pace_low_s_per_km: float | None
    pace_high_s_per_km: float | None
    hr_low: int | None
    hr_high: int | None
    rpe_low: float
    rpe_high: float

    success_looks_like: str
    common_mistake: str
    coach_tip: str

    why_this_session: tuple[str, ...]
    historical_evidence: tuple[HistoricalWorkoutEvidence, ...]
    historical_summary: str

    source: str
    confidence: float
    confidence_label: str

    earliest_timing: str
    readiness_required: bool

    block_name: str | None
    block_phase: str | None
    goal_name: str | None

    model_version: int = 1


def _safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(number):
        return None

    return number


def _canonical_phase_type(value: Any) -> str:
    phase_type = str(value or "unknown").strip().lower()
    return PHASE_ALIASES.get(phase_type, phase_type)


def _session_family_from_label(
    session_family: str,
) -> str:
    label = session_family.lower()

    if "recovery" in label:
        return "recovery"
    if "threshold" in label:
        return "threshold"
    if "vo₂" in label or "vo2" in label:
        return "vo2"
    if "speed" in label:
        return "speed"
    if "long" in label or "endurance" in label:
        return "endurance"
    if "race" in label:
        return "race_pace"

    return "easy"


def _race_link_support(
    workout_id: int,
) -> tuple[int, float | None]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            COUNT(*),
            MAX(link_confidence)
        FROM workout_race_links
        WHERE workout_id = ?
        """,
        (workout_id,),
    )
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return 0, None

    return int(row[0] or 0), _safe_float(row[1])


def _activity_title(activity_id: int) -> str:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT title FROM activities WHERE id = ?",
        (activity_id,),
    )
    row = cursor.fetchone()
    conn.close()

    if row and row[0]:
        return str(row[0])

    return "Historical workout"


def _representative_phase(
    record: WorkoutLibraryRecord,
    family: str,
) -> dict[str, Any] | None:
    wanted = FAMILY_PHASES.get(family)

    if not wanted:
        return None

    candidates = []

    for phase in record.phases:
        phase_type = _canonical_phase_type(
            phase.get("phase_type")
        )

        if phase_type not in wanted:
            continue

        distance = _safe_float(phase.get("distance_km")) or 0.0
        duration = _safe_float(phase.get("duration_s")) or 0.0
        rep_count = int(_safe_float(phase.get("rep_count")) or 1)

        # Prefer substantial phases; tiny fragments should not design sessions.
        load = duration + distance * 120.0 + max(rep_count - 1, 0) * 30.0

        candidates.append(
            (
                load,
                phase_type,
                phase,
            )
        )

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    _, phase_type, phase = candidates[0]
    result = dict(phase)
    result["_canonical_type"] = phase_type
    return result


def _structural_fit(
    record: WorkoutLibraryRecord,
    family: str,
) -> float:
    wanted = FAMILY_PHASES.get(family, set())

    if not wanted:
        return 0.0

    quality_types = {
        _canonical_phase_type(phase.get("phase_type"))
        for phase in record.phases
        if _canonical_phase_type(phase.get("phase_type"))
        in QUALITY_PHASES
    }

    if not quality_types:
        return 0.0

    overlap = quality_types & wanted

    if not overlap:
        return 0.0

    precision = len(overlap) / len(quality_types)
    coverage = min(len(overlap) / max(len(wanted), 1), 1.0)

    # Exact/simple sessions are preferable to mixed sessions when choosing
    # a representative structure.
    return min(
        0.72 * precision + 0.28 * coverage,
        1.0,
    )


def _historical_candidates(
    athlete_id: int,
    family: str,
    *,
    limit: int = 5,
) -> tuple[HistoricalWorkoutEvidence, ...]:
    if family not in FAMILY_PHASES:
        return ()

    records = get_athlete_workouts(athlete_id)
    scored = []

    today = datetime.date.today()

    for record in records:
        phase = _representative_phase(record, family)

        if phase is None:
            continue

        structural_fit = _structural_fit(
            record,
            family,
        )

        if structural_fit < 0.45:
            continue

        execution = (
            max(0.0, min(record.execution_score / 100.0, 1.0))
            if record.execution_score is not None
            else 0.55
        )

        recognition_conf = max(
            0.0,
            min(record.recognition_confidence, 1.0),
        )
        phase_conf = max(
            0.0,
            min(record.phase_confidence, 1.0),
        )

        race_link_count, race_link_conf = _race_link_support(
            record.id
        )
        race_support = race_link_conf or 0.0

        recency = 0.45

        if record.activity_date:
            try:
                workout_date = datetime.date.fromisoformat(
                    str(record.activity_date)[:10]
                )
                age_days = max((today - workout_date).days, 0)
                recency = max(
                    0.25,
                    1.0 - min(age_days / 730.0, 0.75),
                )
            except (TypeError, ValueError):
                pass

        evidence_score = (
            structural_fit * 0.32
            + execution * 0.32
            + phase_conf * 0.14
            + recognition_conf * 0.10
            + race_support * 0.07
            + recency * 0.05
        )

        rep_count = max(
            int(_safe_float(phase.get("rep_count")) or 1),
            1,
        )

        duration_s = _safe_float(phase.get("duration_s"))
        average_rep_duration = (
            duration_s / rep_count
            if duration_s is not None and rep_count > 0
            else None
        )

        avg_rep_distance = _safe_float(
            phase.get("average_rep_distance_km")
        )
        if avg_rep_distance is None:
            distance = _safe_float(phase.get("distance_km"))
            if distance is not None:
                avg_rep_distance = distance / rep_count

        pace = _safe_float(phase.get("pace_s_per_km"))
        recovery = _safe_float(
            phase.get("recovery_duration_s")
        )

        scored.append(
            HistoricalWorkoutEvidence(
                activity_id=record.activity_id,
                activity_date=record.activity_date,
                activity_title=_activity_title(
                    record.activity_id
                ),
                workout_signature=record.workout_signature,
                execution_score=record.execution_score,
                evidence_score=round(evidence_score, 4),
                race_link_count=race_link_count,
                best_race_link_confidence=(
                    round(race_link_conf, 4)
                    if race_link_conf is not None
                    else None
                ),
                phase_type=str(
                    phase.get("_canonical_type")
                ),
                rep_count=rep_count,
                average_rep_distance_km=(
                    round(avg_rep_distance, 3)
                    if avg_rep_distance is not None
                    else None
                ),
                average_rep_duration_s=(
                    round(average_rep_duration, 1)
                    if average_rep_duration is not None
                    else None
                ),
                pace_s_per_km=(
                    round(pace, 1)
                    if pace is not None
                    else None
                ),
                recovery_duration_s=(
                    round(recovery, 1)
                    if recovery is not None
                    else None
                ),
            )
        )

    scored.sort(
        key=lambda item: item.evidence_score,
        reverse=True,
    )

    return tuple(scored[:limit])


def _median(values: list[float]) -> float | None:
    usable = [
        value
        for value in values
        if value is not None and value > 0
    ]

    if not usable:
        return None

    return statistics.median(usable)


def _history_pace_band(
    evidence: tuple[HistoricalWorkoutEvidence, ...],
) -> tuple[float | None, float | None]:
    paces = [
        item.pace_s_per_km
        for item in evidence
        if item.pace_s_per_km is not None
        and 150 <= item.pace_s_per_km <= 600
    ]

    if len(paces) < 2:
        return None, None

    median = statistics.median(paces)

    # A narrow personal band rather than false precision from one exact pace.
    return (
        round(median * 0.975, 1),
        round(median * 1.025, 1),
    )


def _format_recovery(duration_s: float | None) -> str:
    """Format prescribed recoveries in coach-friendly increments."""
    if duration_s is None or duration_s <= 0:
        return "2 min"

    if duration_s < 120:
        rounded_seconds = max(
            15,
            int(round(duration_s / 15.0) * 15),
        )
        return f"{rounded_seconds} sec"

    rounded_seconds = int(round(duration_s / 30.0) * 30)
    minutes, seconds = divmod(rounded_seconds, 60)

    if seconds == 0:
        return f"{minutes} min"

    return f"{minutes}:{seconds:02d}"


def _history_structure(
    family: str,
    evidence: tuple[HistoricalWorkoutEvidence, ...],
) -> tuple[str, ...] | None:
    if not evidence:
        return None

    representative = evidence[0]

    if family == "threshold":
        if (
            representative.rep_count >= 2
            and representative.average_rep_duration_s is not None
            and representative.average_rep_duration_s >= 240
        ):
            minutes = max(
                round(representative.average_rep_duration_s / 60),
                4,
            )
            recovery = _format_recovery(
                representative.recovery_duration_s
            )
            return (
                f"{representative.rep_count} × {minutes} min threshold",
                f"{recovery} easy jog between reps",
            )

        if (
            representative.rep_count >= 2
            and representative.average_rep_distance_km is not None
            and representative.average_rep_distance_km >= 0.8
        ):
            distance = representative.average_rep_distance_km
            recovery = _format_recovery(
                representative.recovery_duration_s
            )
            return (
                f"{representative.rep_count} × {distance:.1f} km threshold",
                f"{recovery} easy jog between reps",
            )

    if family in {"vo2", "speed"}:
        if (
            representative.rep_count >= 3
            and representative.average_rep_distance_km is not None
        ):
            metres = int(
                round(
                    representative.average_rep_distance_km * 1000
                    / 100
                )
                * 100
            )
            recovery = _format_recovery(
                representative.recovery_duration_s
            )

            if metres >= 200:
                return (
                    f"{representative.rep_count} × {metres} m",
                    f"{recovery} easy jog / float between reps",
                )

        if (
            representative.rep_count >= 3
            and representative.average_rep_duration_s is not None
        ):
            minutes = round(
                representative.average_rep_duration_s / 60,
                1,
            )
            return (
                f"{representative.rep_count} × {minutes:g} min hard but controlled",
                "Equal-time easy jog recoveries",
            )

    if family == "endurance":
        duration = representative.average_rep_duration_s

        if duration and duration >= 3600:
            minutes = round(duration / 60 / 5) * 5
            return (
                f"{minutes} min continuous easy-long running",
            )

    return None


def _goal_context(
    athlete_id: int,
) -> tuple[str | None, float | None]:
    goal = get_active_goal(athlete_id)

    if not goal:
        return None, None

    target_time = _safe_float(
        goal.get("target_time_s")
    )
    distance_m = _safe_float(
        goal.get("distance_m")
    )

    goal_pace = None

    if (
        target_time is not None
        and distance_m is not None
        and distance_m > 0
    ):
        goal_pace = target_time / (distance_m / 1000.0)

    return goal.get("goal_name"), goal_pace


def _recent_easy_pace_band(
    athlete_id: int,
    *,
    lt1_hr: int | None,
) -> tuple[float | None, float | None]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            distance_m,
            moving_time_s,
            avg_hr
        FROM activities
        WHERE athlete_id = ?
          AND moving_time_s IS NOT NULL
          AND distance_m IS NOT NULL
        ORDER BY activity_datetime DESC
        LIMIT 120
        """,
        (athlete_id,),
    )
    rows = cursor.fetchall()
    conn.close()

    paces = []

    for distance_value, moving_time, avg_hr in rows:
        distance = _safe_float(distance_value)
        moving = _safe_float(moving_time)
        hr = _safe_float(avg_hr)

        if (
            distance is None
            or moving is None
            or distance <= 0
            or moving <= 0
        ):
            continue

        distance_km = (
            distance / 1000.0
            if distance > 250
            else distance
        )

        pace = moving / distance_km

        if not 210 <= pace <= 600:
            continue

        if (
            lt1_hr is not None
            and hr is not None
            and hr > lt1_hr * 1.02
        ):
            continue

        paces.append(pace)

    if len(paces) < 5:
        return None, None

    ordered = sorted(paces)

    lower = ordered[
        max(int(len(ordered) * 0.25), 0)
    ]
    upper = ordered[
        min(int(len(ordered) * 0.75), len(ordered) - 1)
    ]

    return round(lower, 1), round(upper, 1)


def _targets(
    athlete_id: int,
    family: str,
    evidence: tuple[HistoricalWorkoutEvidence, ...],
    *,
    goal_pace_s_per_km: float | None,
) -> tuple[
    float | None,
    float | None,
    int | None,
    int | None,
    float,
    float,
]:
    thresholds = get_effective_athlete_thresholds(
        athlete_id
    )
    lt1 = thresholds.get("lt1_hr")
    lt2 = thresholds.get("lt2_hr")
    max_hr = thresholds.get("athlete_max_hr")

    history_low, history_high = _history_pace_band(
        evidence
    )

    if family == "recovery":
        pace_low, pace_high = _recent_easy_pace_band(
            athlete_id,
            lt1_hr=lt1,
        )
        hr_low = (
            max(int(lt1 * 0.78), 90)
            if lt1
            else None
        )
        hr_high = (
            int(lt1 * 0.90)
            if lt1
            else None
        )
        return pace_low, pace_high, hr_low, hr_high, 2.0, 3.0

    if family == "easy":
        pace_low, pace_high = _recent_easy_pace_band(
            athlete_id,
            lt1_hr=lt1,
        )
        hr_low = (
            int(lt1 * 0.84)
            if lt1
            else None
        )
        hr_high = (
            int(lt1 * 0.98)
            if lt1
            else None
        )
        return pace_low, pace_high, hr_low, hr_high, 3.0, 4.0

    if family == "threshold":
        hr_low = (
            int(round(lt1 + (lt2 - lt1) * 0.45))
            if lt1 and lt2
            else None
        )
        hr_high = lt2 if lt2 else None
        return history_low, history_high, hr_low, hr_high, 6.5, 7.5

    if family == "vo2":
        hr_low = lt2 if lt2 else None
        hr_high = (
            int(round(max_hr * 0.97))
            if max_hr
            else None
        )
        return history_low, history_high, hr_low, hr_high, 8.0, 9.0

    if family == "speed":
        # HR lags too much to be a useful primary target for short reps.
        return history_low, history_high, None, None, 8.0, 9.0

    if family == "endurance":
        pace_low, pace_high = _recent_easy_pace_band(
            athlete_id,
            lt1_hr=lt1,
        )
        hr_low = (
            int(lt1 * 0.84)
            if lt1
            else None
        )
        hr_high = (
            int(lt1 * 0.99)
            if lt1
            else None
        )
        return pace_low, pace_high, hr_low, hr_high, 3.0, 5.0

    if family == "race_pace":
        if goal_pace_s_per_km:
            return (
                round(goal_pace_s_per_km * 0.99, 1),
                round(goal_pace_s_per_km * 1.01, 1),
                lt1,
                lt2,
                6.5,
                8.0,
            )

    return None, None, None, None, 3.0, 5.0


def _fallback_structure(
    family: str,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    if family == "recovery":
        return (
            ("5–10 min very easy",),
            ("30–40 min relaxed continuous running",),
            ("5 min easy walk / jog if useful",),
        )

    if family == "easy":
        return (
            ("10 min very easy",),
            ("35–50 min conversational running",),
            ("5–10 min very easy",),
        )

    if family == "threshold":
        return (
            (
                "15 min easy",
                "4 × 20 sec relaxed strides",
            ),
            (
                "3 × 10 min threshold",
                "2 min easy jog between reps",
            ),
            ("10–15 min easy",),
        )

    if family == "vo2":
        return (
            (
                "15 min easy",
                "4 × 20 sec relaxed strides",
            ),
            (
                "6 × 3 min strong and controlled",
                "2 min easy jog between reps",
            ),
            ("10–15 min easy",),
        )

    if family == "speed":
        return (
            (
                "15 min easy",
                "4 × 20 sec progressive strides",
            ),
            (
                "8 × 400 m fast but relaxed",
                "200 m very easy jog between reps",
            ),
            ("10–15 min easy",),
        )

    if family == "endurance":
        return (
            ("10–15 min very easy",),
            ("90 min comfortable continuous running",),
            ("5–10 min very easy",),
        )

    if family == "race_pace":
        return (
            (
                "15 min easy",
                "4 × 20 sec strides",
            ),
            (
                "3 × 2 km at goal race pace",
                "2 min easy jog between reps",
            ),
            ("10–15 min easy",),
        )

    return (
        ("10 min easy",),
        ("40 min comfortable running",),
        ("5–10 min easy",),
    )


def _session_structure(
    family: str,
    evidence: tuple[HistoricalWorkoutEvidence, ...],
) -> tuple[
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
    str,
]:
    warmup, fallback_main, cooldown = _fallback_structure(
        family
    )

    history_main = _history_structure(
        family,
        evidence,
    )

    if history_main is None:
        if evidence:
            return (
                warmup,
                fallback_main,
                cooldown,
                "Personal history + coaching progression",
            )

        return warmup, fallback_main, cooldown, "Coaching template"

    return (
        warmup,
        history_main,
        cooldown,
        "Personal history",
    )


def _purpose(
    family: str,
    *,
    block_name: str | None,
    goal_name: str | None,
) -> str:
    purposes = {
        "recovery": (
            "Absorb recent training while keeping the aerobic system moving."
        ),
        "easy": (
            "Build aerobic fitness without adding unnecessary fatigue."
        ),
        "threshold": (
            "Improve the pace you can sustain aerobically for a long time "
            "without turning the session into a race."
        ),
        "vo2": (
            "Develop high-end aerobic power while keeping repetition quality "
            "controlled."
        ),
        "speed": (
            "Improve speed, economy and relaxed leg turnover without chasing "
            "fatigue."
        ),
        "endurance": (
            "Build the durability to hold good running form and aerobic control "
            "for longer."
        ),
        "race_pace": (
            "Make goal pace feel familiar and controlled before race day."
        ),
    }

    base = purposes.get(
        family,
        "Add the most useful training stimulus for your current development.",
    )

    context = []

    if block_name:
        context.append(block_name)
    if goal_name:
        context.append(goal_name)

    if context:
        return base + " Current context: " + " · ".join(context) + "."

    return base


def _success_and_tip(
    family: str,
) -> tuple[str, str, str]:
    if family == "recovery":
        return (
            "You finish feeling better than when you started.",
            "Turning the run into a normal easy run because the legs begin to feel good.",
            "Keep the ego out of it. The win is freshness, not pace.",
        )

    if family == "easy":
        return (
            "Breathing stays conversational and the final 10 minutes feel as controlled as the first 10.",
            "Letting pace creep up because the run feels comfortable.",
            "Judge the run by control. Pace is an outcome, not the target.",
        )

    if family == "threshold":
        return (
            "The final rep is your best-controlled rep and you feel you could complete one more.",
            "Starting the first rep at the pace you hope to average rather than the effort you can sustain.",
            "Make rep one almost boring. Threshold rewards patience.",
        )

    if family == "vo2":
        return (
            "Rep pace stays consistent and your running form remains strong through the final repetition.",
            "Winning the first two reps and surviving the rest.",
            "The session should get hard because of accumulation, not because rep one was heroic.",
        )

    if family == "speed":
        return (
            "You stay fast, relaxed and technically tidy; stop before mechanics deteriorate.",
            "Chasing maximal effort rather than relaxed speed.",
            "Think quick and smooth, not strained.",
        )

    if family == "endurance":
        return (
            "You finish with stable form and aerobic control, not simply with the distance completed.",
            "Pushing the middle of the run because you feel good and paying for it late.",
            "Let duration do the work. The long run does not need to become a race.",
        )

    if family == "race_pace":
        return (
            "Goal pace feels controlled enough that you could confidently add another repetition.",
            "Treating the workout as a race simulation and exceeding goal pace.",
            "Practise the pace you want to own on race day — don't try to prove fitness.",
        )

    return (
        "You complete the session in control.",
        "Adding intensity that was not part of the purpose.",
        "Keep the purpose of the session more important than the numbers.",
    )


def _confidence(
    recommendation: NextRunRecommendation,
    evidence: tuple[HistoricalWorkoutEvidence, ...],
    source: str,
) -> tuple[float, str]:
    confidence = recommendation.confidence * 0.62

    if source.startswith("Personal history"):
        evidence_conf = statistics.fmean(
            item.evidence_score
            for item in evidence[:3]
        )
        confidence += evidence_conf * 0.30
        confidence += min(len(evidence) / 5.0, 1.0) * 0.08
    else:
        confidence += 0.18

    confidence = max(0.25, min(confidence, 0.95))

    if confidence >= 0.84:
        label = "High"
    elif confidence >= 0.68:
        label = "Good"
    elif confidence >= 0.52:
        label = "Developing"
    else:
        label = "Early evidence"

    return round(confidence, 4), label


def build_designed_session(
    athlete_id: int,
    *,
    family_override: str | None = None,
    main_set_override: tuple[str, ...] | None = None,
    timing_override: str | None = None,
    confidence_override: float | None = None,
    confidence_label_override: str | None = None,
    why_override: tuple[str, ...] | None = None,
) -> DesignedSession | None:
    recommendation = build_next_run_recommendation(
        athlete_id
    )

    if recommendation is None:
        return None

    prescribed_family = (
        recommendation.next_key_session_family
        or recommendation.session_family
    )
    family = (
        family_override
        if family_override is not None
        else _session_family_from_label(prescribed_family)
    )
    block = get_active_training_block(athlete_id)
    goal_name, goal_pace = _goal_context(athlete_id)

    evidence = _historical_candidates(
        athlete_id,
        family,
        limit=5,
    )

    warmup, main_set, cooldown, source = (
        _session_structure(
            family,
            evidence,
        )
    )
    if main_set_override:
        main_set = tuple(main_set_override)
        source = "Adaptive Coach + personal targets"

    (
        pace_low,
        pace_high,
        hr_low,
        hr_high,
        rpe_low,
        rpe_high,
    ) = _targets(
        athlete_id,
        family,
        evidence,
        goal_pace_s_per_km=goal_pace,
    )

    success, mistake, tip = _success_and_tip(
        family
    )

    confidence, confidence_label = _confidence(
        recommendation,
        evidence,
        source,
    )
    if confidence_override is not None:
        confidence = confidence_override
    if confidence_label_override is not None:
        confidence_label = confidence_label_override

    if source == "Personal history":
        representative = evidence[0]
        historical_summary = (
            f"PP found {len(evidence)} strong comparable session"
            f"{'s' if len(evidence) != 1 else ''}. "
            f"The structure is anchored to {representative.activity_title} "
            f"({representative.activity_date or 'date unknown'}), which had "
            f"an execution score of "
            f"{representative.execution_score:.0f}/100."
            if representative.execution_score is not None
            else (
                f"PP found {len(evidence)} comparable historical sessions and "
                "used the strongest structural match."
            )
        )
    elif source == "Personal history + coaching progression":
        representative = evidence[0]
        historical_summary = (
            f"PP found {len(evidence)} strong comparable historical session"
            f"{'s' if len(evidence) != 1 else ''}. Their pace and execution "
            "inform today's targets, but none had a clean enough structure to "
            "copy directly, so PP uses a conservative progression for the main "
            "set. The strongest evidence came from "
            f"{representative.activity_title} "
            f"({representative.activity_date or 'date unknown'})."
        )
    else:
        historical_summary = (
            "Not enough trustworthy matching workout structure exists yet, "
            "so PP is using a conservative coaching template. Personal history "
            "will take over as the evidence improves."
        )

    why = list(
        why_override
        if why_override is not None
        else recommendation.why
    )

    if source == "Personal history":
        why.append(
            "The workout structure is informed by your own strongest comparable historical sessions."
        )
    elif source == "Personal history + coaching progression":
        why.append(
            "Your own strong historical sessions inform the targets; PP uses a conservative progression where the old session structure is not clean enough to copy."
        )
    else:
        why.append(
            "The structure uses a conservative template because personal matching history is still limited."
        )

    return DesignedSession(
        athlete_id=athlete_id,
        family=family,
        family_label=FAMILY_LABELS.get(
            family,
            recommendation.session_family,
        ),
        icon=FAMILY_ICONS.get(
            family,
            recommendation.icon,
        ),
        purpose=_purpose(
            family,
            block_name=block.name if block else None,
            goal_name=goal_name,
        ),
        warmup=warmup,
        main_set=main_set,
        cooldown=cooldown,
        pace_low_s_per_km=pace_low,
        pace_high_s_per_km=pace_high,
        hr_low=hr_low,
        hr_high=hr_high,
        rpe_low=rpe_low,
        rpe_high=rpe_high,
        success_looks_like=success,
        common_mistake=mistake,
        coach_tip=tip,
        why_this_session=tuple(why),
        historical_evidence=evidence,
        historical_summary=historical_summary,
        source=source,
        confidence=confidence,
        confidence_label=confidence_label,
        earliest_timing=(
            timing_override
            or recommendation.next_key_session_timing
            or recommendation.earliest_timing
        ),
        readiness_required=(
            recommendation.next_key_session_readiness_required
            if recommendation.next_key_session_family
            else recommendation.readiness_required
        ),
        block_name=block.name if block else None,
        block_phase=(
            block.current_phase if block else None
        ),
        goal_name=goal_name,
    )
