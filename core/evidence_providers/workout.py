"""
Workout Coach evidence provider.
"""

from __future__ import annotations

from core.database import get_connection
from core.evidence import EvidenceItem, EvidenceStatus
from core.evidence_providers.base import EvidenceContext, EvidenceProvider
from core.workouts import get_or_decode_workout


class WorkoutEvidenceProvider(EvidenceProvider):
    key = "workout"
    title = "Workout Coach"

    def build(self, context: EvidenceContext) -> EvidenceItem:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, activity_date, title, raw_json
            FROM activities
            WHERE athlete_id = ?
              AND raw_json IS NOT NULL
            ORDER BY activity_datetime DESC
            """,
            (context.athlete_id,),
        )
        rows = cursor.fetchall()
        conn.close()

        recognised = []
        decoded_count = 0

        for activity_id, activity_date, title, raw_json in rows:
            workout = get_or_decode_workout(activity_id, raw_json)
            decoded_count += 1

            if workout.workout_type in ("No split data", "Unclassified"):
                continue

            recognised.append(
                {
                    "activity_id": activity_id,
                    "activity_date": activity_date,
                    "title": title or "Workout",
                    "workout": workout,
                }
            )

        if not recognised:
            return EvidenceItem(
                key=self.key,
                title=self.title,
                summary=(
                    "No confidently recognised workout structure was found "
                    "in the athlete's imported history."
                ),
                status=EvidenceStatus.BUILDING,
                confidence=0.25,
                sample_size=0,
                predicted_seconds=None,
                weight=0.0,
                metadata={
                    "decoded_activity_count": decoded_count,
                    "limitations": [
                        "Only activities with decodable lap splits can be "
                        "recognised at present."
                    ]
                },
            )

        latest = recognised[0]
        workout = latest["workout"]
        summary = (
            f"Latest recognised workout: {workout.description} from "
            f"{latest['title']} on {latest['activity_date'][:10]}. "
            f"{len(recognised)} recognised workout(s) were found across the "
            "imported history."
        )

        strengths = [
            f"Workout recognition confidence {workout.confidence:.0%}",
            f"{workout.rep_count} work rep(s) identified",
        ]

        if workout.execution_score is not None:
            strengths.append(
                f"Execution score {workout.execution_score:.0f}/100"
            )

        limitations = workout.recognition_json.get("limitations", [])

        return EvidenceItem(
            key=self.key,
            title=self.title,
            summary=summary,
            status=EvidenceStatus.AVAILABLE,
            confidence=workout.confidence,
            sample_size=len(recognised),
            predicted_seconds=None,
            weight=0.0,
            metadata={
                "activity_id": latest["activity_id"],
                "recognised_workout_count": len(recognised),
                "decoded_activity_count": decoded_count,
                "activity_date": latest["activity_date"],
                "selected_title": latest["title"],
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
