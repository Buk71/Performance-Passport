"""
Workout Coach v2.

The coach uses:
- the latest recognised workout;
- the strongest five recent workouts;
- evidence quality and representativeness;
- trends across genuinely comparable sessions.

It supports both manual lap/stop workouts and programmed sessions. A workout
does not need boundary fragments when alternating work/recovery structure is
clear in the decoded splits.
"""

from __future__ import annotations

from collections import Counter
import datetime
from statistics import mean

from core.database import get_athlete_sport_roles, get_connection
from core.evidence import EvidenceItem, EvidenceStatus
from core.evidence_providers.base import EvidenceContext, EvidenceProvider
from core.session import SessionType
from core.session_intelligence import ActivityFacts, classify_session
from core.workouts import get_or_decode_workout


RECENT_WINDOW_DAYS = 365
TOP_EVIDENCE_COUNT = 5


def _as_date(value: str | None) -> datetime.date | None:
    if not value:
        return None

    try:
        return datetime.date.fromisoformat(value[:10])
    except (TypeError, ValueError):
        return None


def _explicit_workout_title(title: str) -> bool:
    value = (title or "").lower()
    words = (
        "threshold",
        "tempo",
        "interval",
        "intervals",
        "reps",
        "fartlek",
        "hill",
        "track",
        "vo2",
        "cruise",
        "session",
    )
    return any(word in value for word in words)


def _programmed_structure_evidence(workout) -> bool:
    """
    Accept programmed-watch sessions without manual boundary fragments.

    Clear recorded recoveries, mixed work families or several alternating
    work segments can establish a workout independently of lap/stop artefacts.
    """
    data = workout.recognition_json
    recoveries = data.get("recovery_splits", [])
    boundaries = data.get("boundary_splits", [])
    unknown_recoveries = data.get("unknown_recovery_count", 0) or 0

    if recoveries:
        return True

    if boundaries or unknown_recoveries:
        return True

    if workout.workout_type == "Mixed interval session":
        return workout.rep_count >= 3

    return (
        workout.rep_count >= 3
        and workout.workout_type
        in {
            "Short intervals",
            "Long intervals",
            "Mile repetitions",
            "Long threshold repetitions",
        }
    )


def _trust_score(session, workout, activity_date, reference_date) -> float:
    age_days = (
        max((reference_date - activity_date).days, 0)
        if activity_date
        else RECENT_WINDOW_DAYS
    )
    recency = max(0.0, 1.0 - age_days / RECENT_WINDOW_DAYS)

    execution = (
        workout.execution_score / 100.0
        if workout.execution_score is not None
        else 0.50
    )

    structure_bonus = 0.0
    data = workout.recognition_json

    if data.get("recovery_splits"):
        structure_bonus += 0.05
    if data.get("boundary_splits"):
        structure_bonus += 0.03
    if workout.workout_type == "Mixed interval session":
        structure_bonus += 0.03

    score = (
        session.confidence * 25.0
        + workout.confidence * 30.0
        + execution * 25.0
        + recency * 20.0
        + structure_bonus * 100.0
    )

    return min(round(score, 1), 100.0)


def _reason_for_trust(item) -> list[str]:
    session = item["session"]
    workout = item["workout"]
    reasons = [
        f"Session classification {session.confidence:.0%}",
        f"Workout recognition {workout.confidence:.0%}",
    ]

    if workout.execution_score is not None:
        reasons.append(f"Execution {workout.execution_score:.0f}/100")

    data = workout.recognition_json

    if data.get("recovery_splits"):
        reasons.append("Recorded work/recovery structure")
    elif data.get("boundary_splits"):
        reasons.append("Manual lap/stop boundary pattern")
    elif workout.rep_count >= 3:
        reasons.append("Repeated programmed work pattern")

    return reasons


def _comparable(reference, candidate) -> bool:
    ref_workout = reference["workout"]
    candidate_workout = candidate["workout"]

    if ref_workout.workout_type != candidate_workout.workout_type:
        return False

    ref_distance = ref_workout.average_rep_distance_km
    candidate_distance = candidate_workout.average_rep_distance_km

    if not ref_distance or not candidate_distance:
        return False

    tolerance = max(ref_distance * 0.20, 0.08)
    return abs(candidate_distance - ref_distance) <= tolerance


def _trend(comparable_items) -> dict:
    usable = [
        item
        for item in comparable_items
        if item["workout"].average_rep_pace_s_per_km is not None
    ]

    if len(usable) < 3:
        return {
            "label": "Not enough comparable sessions",
            "confidence": "Limited",
            "change_seconds_per_km": None,
            "sample_size": len(usable),
        }

    ordered = sorted(
        usable,
        key=lambda item: item["activity_date"] or datetime.date.min,
        reverse=True,
    )

    split_at = max(1, min(2, len(ordered) // 2))
    recent = ordered[:split_at]
    earlier = ordered[split_at:]

    if not earlier:
        return {
            "label": "Not enough comparable sessions",
            "confidence": "Limited",
            "change_seconds_per_km": None,
            "sample_size": len(usable),
        }

    recent_pace = mean(
        item["workout"].average_rep_pace_s_per_km
        for item in recent
    )
    earlier_pace = mean(
        item["workout"].average_rep_pace_s_per_km
        for item in earlier
    )
    change = earlier_pace - recent_pace

    if change >= 4.0:
        label = "Improving"
    elif change <= -4.0:
        label = "Declining"
    else:
        label = "Stable"

    confidence = "Strong" if len(usable) >= 5 else "Moderate"

    return {
        "label": label,
        "confidence": confidence,
        "change_seconds_per_km": round(change, 1),
        "recent_pace_seconds_per_km": round(recent_pace, 1),
        "earlier_pace_seconds_per_km": round(earlier_pace, 1),
        "sample_size": len(usable),
    }


class WorkoutEvidenceProvider(EvidenceProvider):
    key = "workout"
    title = "Workout Coach"

    def build(self, context: EvidenceContext) -> EvidenceItem:
        conn = get_connection()
        cursor = conn.cursor()

        sport_roles = get_athlete_sport_roles(context.athlete_id)
        running_ids = [
            sport_id
            for sport_id, role in sport_roles.items()
            if role == "running"
        ]

        if not running_ids:
            conn.close()
            return EvidenceItem(
                key=self.key,
                title=self.title,
                summary="No running sport mapping is available.",
                status=EvidenceStatus.BUILDING,
                confidence=0.15,
                sample_size=0,
                predicted_seconds=None,
                weight=0.0,
                metadata={
                    "limitations": [
                        "Workout Coach cannot inspect activities until the "
                        "athlete's running sport is identified."
                    ]
                },
            )

        placeholders = ",".join("?" for _ in running_ids)

        cursor.execute(
            f"""
            SELECT
                a.id,
                a.athlete_id,
                a.activity_date,
                a.title,
                a.sport_id,
                a.distance_m,
                a.moving_time_s,
                a.elapsed_time_s,
                a.avg_hr,
                a.max_hr,
                a.elevation_up_m,
                a.temperature_c,
                a.humidity,
                a.wind_speed,
                a.route_name,
                a.raw_json,
                at.lt1_hr,
                at.lt2_hr,
                at.max_hr
            FROM activities a
            JOIN athletes at ON at.id = a.athlete_id
            WHERE a.athlete_id = ?
              AND CAST(a.sport_id AS TEXT) IN ({placeholders})
              AND a.raw_json IS NOT NULL
            ORDER BY a.activity_datetime DESC
            """,
            (context.athlete_id, *running_ids),
        )

        rows = cursor.fetchall()
        conn.close()

        reference_date = max(
            (
                _as_date(row[2])
                for row in rows
                if _as_date(row[2]) is not None
            ),
            default=datetime.date.today(),
        )

        session_counts = Counter()
        candidates = []

        for row in rows:
            facts = ActivityFacts(
                activity_id=row[0],
                athlete_id=row[1],
                activity_date=row[2],
                title=row[3] or "Activity",
                sport_id=str(row[4]) if row[4] is not None else None,
                distance_km=float(row[5]) if row[5] is not None else None,
                moving_time_s=float(row[6]) if row[6] is not None else None,
                elapsed_time_s=float(row[7]) if row[7] is not None else None,
                avg_hr=float(row[8]) if row[8] is not None else None,
                max_hr=float(row[9]) if row[9] is not None else None,
                elevation_up_m=(
                    float(row[10]) if row[10] is not None else None
                ),
                temperature_c=(
                    float(row[11]) if row[11] is not None else None
                ),
                humidity=float(row[12]) if row[12] is not None else None,
                wind_speed=float(row[13]) if row[13] is not None else None,
                route_name=row[14],
                raw_json_text=row[15],
                athlete_lt2_hr=(
                    float(row[17]) if row[17] is not None else None
                ),
                athlete_max_hr=(
                    float(row[18]) if row[18] is not None else None
                ),
            )

            session = classify_session(facts)
            session_counts[session.session_type.value] += 1

            workout = get_or_decode_workout(row[0], row[15])

            if workout.workout_type in ("No split data", "Unclassified"):
                continue

            accepted = (
                session.session_type == SessionType.STRUCTURED_WORKOUT
                or _explicit_workout_title(session.title)
                or _programmed_structure_evidence(workout)
            )

            if not accepted:
                continue

            activity_date = _as_date(session.activity_date)
            item = {
                "session": session,
                "workout": workout,
                "activity_date": activity_date,
            }
            item["trust_score"] = _trust_score(
                session,
                workout,
                activity_date,
                reference_date,
            )
            item["trust_reasons"] = _reason_for_trust(item)
            candidates.append(item)

        if not candidates:
            return EvidenceItem(
                key=self.key,
                title=self.title,
                summary=(
                    "No confidently recognised workout was found. "
                    "Continuous auto-lap runs were excluded."
                ),
                status=EvidenceStatus.BUILDING,
                confidence=0.25,
                sample_size=0,
                predicted_seconds=None,
                weight=0.0,
                metadata={
                    "session_counts": dict(session_counts),
                    "limitations": [
                        "Programmed sessions require alternating work/recovery "
                        "or another clear repeated work pattern.",
                        "Some workouts may need richer FIT workout-step data.",
                    ],
                },
            )

        chronological = sorted(
            candidates,
            key=lambda item: item["activity_date"] or datetime.date.min,
            reverse=True,
        )
        latest = chronological[0]

        recent_candidates = [
            item
            for item in candidates
            if item["activity_date"] is not None
            and (reference_date - item["activity_date"]).days
            <= RECENT_WINDOW_DAYS
        ] or candidates

        strongest = sorted(
            recent_candidates,
            key=lambda item: item["trust_score"],
            reverse=True,
        )[:TOP_EVIDENCE_COUNT]

        best = strongest[0]
        comparable = [
            item for item in recent_candidates if _comparable(best, item)
        ]
        trend = _trend(comparable)

        latest_is_representative = (
            latest["trust_score"] >= best["trust_score"] - 10.0
            and _comparable(best, latest)
        )

        warning = None
        if not latest_is_representative:
            warning = (
                "The latest workout is not the strongest representation of "
                "current fitness, so Workout Coach is placing more weight on "
                "earlier high-quality sessions."
            )

        latest_session = latest["session"]
        latest_workout = latest["workout"]
        best_session = best["session"]
        best_workout = best["workout"]

        summary_parts = [
            f"Latest session: {latest_workout.description} on "
            f"{(latest_session.activity_date or 'unknown')[:10]}.",
            f"Best current evidence: {best_workout.description} on "
            f"{(best_session.activity_date or 'unknown')[:10]}.",
        ]

        if trend["label"] != "Not enough comparable sessions":
            summary_parts.append(
                f"Recent comparable trend: {trend['label'].lower()} across "
                f"{trend['sample_size']} session(s)."
            )
        else:
            summary_parts.append(
                "There are not yet enough directly comparable workouts for "
                "a reliable trend."
            )

        if warning:
            summary_parts.append(warning)

        top_workouts = []
        for rank, item in enumerate(strongest, start=1):
            session = item["session"]
            workout = item["workout"]
            top_workouts.append(
                {
                    "rank": rank,
                    "activity_id": session.activity_id,
                    "date": (
                        session.activity_date[:10]
                        if session.activity_date
                        else "Unknown"
                    ),
                    "title": session.title,
                    "workout_type": workout.workout_type,
                    "description": workout.description,
                    "trust_score": item["trust_score"],
                    "execution_score": workout.execution_score,
                    "recognition_confidence": workout.confidence,
                    "session_confidence": session.confidence,
                    "average_rep_pace_s_per_km":
                        workout.average_rep_pace_s_per_km,
                    "trust_reasons": item["trust_reasons"],
                }
            )

        confidence = min(
            0.96,
            (
                best["session"].confidence * 0.35
                + best["workout"].confidence * 0.40
                + min(len(strongest) / TOP_EVIDENCE_COUNT, 1.0) * 0.25
            ),
        )

        strengths = [
            f"{len(candidates)} recognised workout(s) in the athlete history",
            f"Strongest {len(strongest)} recent workout(s) were ranked by "
            "recency, structure, recognition and execution",
            f"Best evidence trust score {best['trust_score']:.0f}/100",
        ]

        if latest_is_representative:
            strengths.append("Latest workout is representative of current evidence")

        limitations = [
            "Trends compare only sessions with similar workout type and rep distance.",
            "Runalyze CSV splits do not contain full lap-level heart rate or power.",
        ]

        if warning:
            limitations.append(warning)

        return EvidenceItem(
            key=self.key,
            title=self.title,
            summary=" ".join(summary_parts),
            status=EvidenceStatus.AVAILABLE,
            confidence=confidence,
            sample_size=len(candidates),
            predicted_seconds=None,
            weight=0.0,
            metadata={
                "activity_id": latest_session.activity_id,
                "activity_date": latest_session.activity_date,
                "selected_title": latest_session.title,
                "workout_type": latest_workout.workout_type,
                "description": latest_workout.description,
                "execution_score": latest_workout.execution_score,
                "rep_count": latest_workout.rep_count,
                "average_rep_distance_km":
                    latest_workout.average_rep_distance_km,
                "average_rep_pace_s_per_km":
                    latest_workout.average_rep_pace_s_per_km,
                "rep_pace_variation_percent":
                    latest_workout.rep_pace_variation_percent,
                "workout_json": latest_workout.recognition_json,
                "latest_workout": {
                    "date": (
                        latest_session.activity_date[:10]
                        if latest_session.activity_date
                        else "Unknown"
                    ),
                    "title": latest_session.title,
                    "description": latest_workout.description,
                    "trust_score": latest["trust_score"],
                    "representative": latest_is_representative,
                },
                "best_evidence": {
                    "date": (
                        best_session.activity_date[:10]
                        if best_session.activity_date
                        else "Unknown"
                    ),
                    "title": best_session.title,
                    "description": best_workout.description,
                    "trust_score": best["trust_score"],
                },
                "top_workouts": top_workouts,
                "trend": trend,
                "latest_not_representative": not latest_is_representative,
                "representative_warning": warning,
                "recognised_workout_count": len(candidates),
                "session_counts": dict(session_counts),
                "strengths": strengths,
                "limitations": limitations,
            },
        )
