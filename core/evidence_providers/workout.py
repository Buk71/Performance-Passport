"""
Workout Coach migrated to Session Intelligence.

Workout Coach now analyses only activities classified as structured sessions.
Continuous runs, including long runs with ordinary mile auto-laps, bypass it.
"""

from __future__ import annotations

from collections import Counter

from core.database import get_connection
from core.evidence import EvidenceItem, EvidenceStatus
from core.evidence_providers.base import EvidenceContext, EvidenceProvider
from core.session import SessionType
from core.session_intelligence import ActivityFacts, classify_session
from core.workouts import get_or_decode_workout


class WorkoutEvidenceProvider(EvidenceProvider):
    key = "workout"
    title = "Workout Coach"

    def build(self, context: EvidenceContext) -> EvidenceItem:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                id,
                athlete_id,
                activity_date,
                title,
                sport_id,
                distance_m,
                moving_time_s,
                elapsed_time_s,
                avg_hr,
                max_hr,
                elevation_up_m,
                temperature_c,
                humidity,
                wind_speed,
                route_name,
                raw_json
            FROM activities
            WHERE athlete_id = ?
            ORDER BY activity_datetime DESC
            """,
            (context.athlete_id,),
        )

        rows = cursor.fetchall()
        conn.close()

        session_counts = Counter()
        structured_sessions = []
        recognised_workouts = []
        inspected_count = 0

        for row in rows:
            facts = ActivityFacts(
                activity_id=row[0],
                athlete_id=row[1],
                activity_date=row[2],
                title=row[3] or "Activity",
                sport_id=str(row[4]) if row[4] is not None else None,
                distance_km=(
                    float(row[5]) if row[5] is not None else None
                ),
                moving_time_s=(
                    float(row[6]) if row[6] is not None else None
                ),
                elapsed_time_s=(
                    float(row[7]) if row[7] is not None else None
                ),
                avg_hr=float(row[8]) if row[8] is not None else None,
                max_hr=float(row[9]) if row[9] is not None else None,
                elevation_up_m=(
                    float(row[10]) if row[10] is not None else None
                ),
                temperature_c=(
                    float(row[11]) if row[11] is not None else None
                ),
                humidity=(
                    float(row[12]) if row[12] is not None else None
                ),
                wind_speed=(
                    float(row[13]) if row[13] is not None else None
                ),
                route_name=row[14],
                raw_json_text=row[15],
            )

            session = classify_session(facts)
            session_counts[session.session_type.value] += 1
            inspected_count += 1

            if session.session_type != SessionType.STRUCTURED_WORKOUT:
                continue

            structured_sessions.append(
                {
                    "session": session,
                    "raw_json": row[15],
                }
            )

            workout = get_or_decode_workout(
                session.activity_id,
                row[15],
            )

            if workout.workout_type in (
                "No split data",
                "Unclassified",
            ):
                continue

            recognised_workouts.append(
                {
                    "session": session,
                    "workout": workout,
                }
            )

        if not recognised_workouts:
            return EvidenceItem(
                key=self.key,
                title=self.title,
                summary=(
                    "No confidently recognised structured workout was found. "
                    "Continuous runs were correctly excluded."
                ),
                status=EvidenceStatus.BUILDING,
                confidence=0.25,
                sample_size=0,
                predicted_seconds=None,
                weight=0.0,
                metadata={
                    "inspected_activity_count": inspected_count,
                    "structured_session_count":
                        len(structured_sessions),
                    "session_counts": dict(session_counts),
                    "limitations": [
                        "Workout Coach only analyses sessions routed as "
                        "structured by Session Intelligence.",
                        "Some genuine workouts may remain unclassified until "
                        "FIT lap detail is available.",
                    ],
                },
            )

        latest = recognised_workouts[0]
        session = latest["session"]
        workout = latest["workout"]

        summary = (
            f"Latest structured workout: {workout.description} from "
            f"{session.title} on {(session.activity_date or 'unknown')[:10]}. "
            f"{len(recognised_workouts)} recognised workout(s) were found "
            f"from {len(structured_sessions)} structured session(s)."
        )

        strengths = [
            "Session Intelligence routed this activity to Workout Coach.",
            f"Session classification confidence "
            f"{session.confidence:.0%}",
            f"Workout recognition confidence "
            f"{workout.confidence:.0%}",
            f"{workout.rep_count} work rep(s) identified",
        ]

        if workout.execution_score is not None:
            strengths.append(
                f"Execution score {workout.execution_score:.0f}/100"
            )

        limitations = list(
            workout.recognition_json.get("limitations", [])
        )
        limitations.append(
            "Continuous runs and auto-lap long runs are deliberately "
            "excluded from Workout Coach."
        )

        combined_confidence = min(
            session.confidence,
            workout.confidence,
        )

        return EvidenceItem(
            key=self.key,
            title=self.title,
            summary=summary,
            status=EvidenceStatus.AVAILABLE,
            confidence=combined_confidence,
            sample_size=len(recognised_workouts),
            predicted_seconds=None,
            weight=0.0,
            metadata={
                "activity_id": session.activity_id,
                "activity_date": session.activity_date,
                "selected_title": session.title,
                "session_type": session.session_type.value,
                "session_purpose": session.purpose.value,
                "session_confidence": session.confidence,
                "session_evidence": [
                    {
                        "key": item.key,
                        "description": item.description,
                        "strength": item.strength,
                        "supports": item.supports,
                        "metadata": item.metadata,
                    }
                    for item in session.evidence
                ],
                "suitable_coaches": [
                    route.value
                    for route in session.suitable_coaches
                ],
                "recognised_workout_count":
                    len(recognised_workouts),
                "structured_session_count":
                    len(structured_sessions),
                "inspected_activity_count": inspected_count,
                "session_counts": dict(session_counts),
                "workout_type": workout.workout_type,
                "description": workout.description,
                "execution_score": workout.execution_score,
                "rep_count": workout.rep_count,
                "average_rep_distance_km":
                    workout.average_rep_distance_km,
                "average_rep_pace_s_per_km":
                    workout.average_rep_pace_s_per_km,
                "rep_pace_variation_percent":
                    workout.rep_pace_variation_percent,
                "strengths": strengths,
                "limitations": limitations,
                "workout_json": workout.recognition_json,
            },
        )
