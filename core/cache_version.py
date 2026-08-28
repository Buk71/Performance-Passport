"""Lightweight athlete-data versions for safe, durable UI caching.

Streamlit reruns the application for every navigation action. Expensive coach
services should survive those reruns, but their cached values must change as
soon as the athlete's evidence changes. This module returns a small hashable
snapshot from summary queries; it never caches athlete data itself.
"""

from __future__ import annotations

from typing import Any

from core.database import get_connection


NAVIGATION_CACHE_TTL_SECONDS = 3600


def get_athlete_cache_version(athlete_id: int) -> tuple[Any, ...]:
    """Return a hashable version covering athlete-facing source tables."""
    connection = get_connection()
    try:
        row = connection.execute(
            """
            SELECT
                (SELECT
                    COALESCE(first_name, '') || '|' ||
                    COALESCE(last_name, '') || '|' ||
                    COALESCE(date_of_birth, '') || '|' ||
                    COALESCE(sex, '') || '|' ||
                    COALESCE(CAST(height_cm AS TEXT), '') || '|' ||
                    COALESCE(CAST(weight_kg AS TEXT), '') || '|' ||
                    COALESCE(CAST(resting_hr AS TEXT), '') || '|' ||
                    COALESCE(CAST(max_hr AS TEXT), '') || '|' ||
                    COALESCE(CAST(lt1_hr AS TEXT), '') || '|' ||
                    COALESCE(CAST(lt2_hr AS TEXT), '') || '|' ||
                    COALESCE(notes, '')
                    FROM athletes WHERE id = ?),
                (SELECT COUNT(*) FROM activities WHERE athlete_id = ?),
                (SELECT COALESCE(MAX(id), 0) FROM activities WHERE athlete_id = ?),
                (SELECT COALESCE(MAX(activity_date), '') FROM activities WHERE athlete_id = ?),
                (SELECT COALESCE(SUM(CASE WHEN source = 'garmin_fit'
                    OR original_file LIKE 'uploads/garmin/%' THEN 1 ELSE 0 END), 0)
                    FROM activities WHERE athlete_id = ?),
                (SELECT COUNT(*) FROM athlete_health_daily WHERE athlete_id = ?),
                (SELECT COALESCE(MAX(updated_at), '') FROM athlete_health_daily WHERE athlete_id = ?),
                (SELECT COUNT(*) FROM goals WHERE athlete_id = ?),
                (SELECT COALESCE(MAX(updated_at), '') FROM goals WHERE athlete_id = ?),
                (SELECT COUNT(*) FROM training_blocks WHERE athlete_id = ?),
                (SELECT COALESCE(MAX(updated_at), '') FROM training_blocks WHERE athlete_id = ?),
                (SELECT COUNT(*) FROM training_block_designs WHERE athlete_id = ?),
                (SELECT COALESCE(MAX(updated_at), '') FROM training_block_designs WHERE athlete_id = ?),
                (SELECT COUNT(*) FROM block_review_actions WHERE athlete_id = ?),
                (SELECT COALESCE(MAX(id), 0) FROM block_review_actions WHERE athlete_id = ?),
                (SELECT COALESCE(MAX(updated_at), '') FROM athlete_nutrition_profiles WHERE athlete_id = ?),
                (SELECT COUNT(*) FROM nutrition_week_selections WHERE athlete_id = ?),
                (SELECT COALESCE(MAX(updated_at), '') FROM nutrition_week_selections WHERE athlete_id = ?),
                (SELECT COUNT(*) FROM athlete_recovery_checkins WHERE athlete_id = ?),
                (SELECT COALESCE(MAX(updated_at), '') FROM athlete_recovery_checkins WHERE athlete_id = ?),
                (SELECT COUNT(*) FROM athlete_activity_overrides WHERE athlete_id = ?),
                (SELECT COALESCE(MAX(updated_at), '') FROM athlete_activity_overrides WHERE athlete_id = ?),
                (SELECT COUNT(*) FROM athlete_personal_best_overrides WHERE athlete_id = ?),
                (SELECT COALESCE(MAX(updated_at), '') FROM athlete_personal_best_overrides WHERE athlete_id = ?),
                (SELECT COALESCE(MAX(updated_at), '') FROM athlete_threshold_overrides WHERE athlete_id = ?),
                (SELECT COUNT(*) FROM athlete_sport_mappings WHERE athlete_id = ?),
                (SELECT COALESCE(MAX(updated_at), '') FROM athlete_sport_mappings WHERE athlete_id = ?),
                (SELECT COUNT(*) FROM workout_library WHERE athlete_id = ?),
                (SELECT COALESCE(MAX(updated_at), '') FROM workout_library WHERE athlete_id = ?)
            """,
            (int(athlete_id),) * 29,
        ).fetchone()
    finally:
        connection.close()
    return tuple(row or ())
