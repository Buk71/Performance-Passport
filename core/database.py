import sqlite3
import json
from functools import lru_cache
from pathlib import Path

DATABASE_PATH = Path("database") / "performance_passport.db"
CURRENT_SCHEMA_VERSION = 15


def get_connection():
    DATABASE_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_table_columns(cursor, table_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [row[1] for row in cursor.fetchall()]


def ensure_column(cursor, table_name, column_name, column_definition):
    if column_name not in get_table_columns(cursor, table_name):
        cursor.execute(
            f"ALTER TABLE {table_name} ADD COLUMN "
            f"{column_name} {column_definition}"
        )


def create_schema_version_table(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            version INTEGER NOT NULL,
            applied_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def get_schema_version(cursor):
    create_schema_version_table(cursor)
    cursor.execute("SELECT version FROM schema_version WHERE id = 1")
    row = cursor.fetchone()

    if row is None:
        cursor.execute(
            "INSERT INTO schema_version (id, version) VALUES (1, 1)"
        )
        return 1

    return row[0]


def set_schema_version(cursor, version):
    cursor.execute(
        """
        UPDATE schema_version
        SET version = ?, applied_at = CURRENT_TIMESTAMP
        WHERE id = 1
        """,
        (version,),
    )


def get_activity_count():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM activities")
    count = cursor.fetchone()[0]
    conn.close()
    return count


def create_base_tables(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS athletes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT,
            date_of_birth TEXT,
            sex TEXT,
            height_cm REAL,
            weight_kg REAL,
            resting_hr INTEGER,
            max_hr INTEGER,
            lt1_hr INTEGER,
            lt2_hr INTEGER,
            notes TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            athlete_name TEXT NOT NULL,
            athlete_id INTEGER,
            source TEXT NOT NULL,
            source_activity_id TEXT NOT NULL,
            activity_hash TEXT,
            activity_datetime TEXT,
            activity_date TEXT,
            title TEXT,
            sport_id TEXT,
            type_id TEXT,
            distance_m REAL,
            moving_time_s REAL,
            elapsed_time_s REAL,
            elevation_up_m REAL,
            elevation_down_m REAL,
            avg_hr REAL,
            max_hr REAL,
            avg_power REAL,
            cadence REAL,
            calories REAL,
            temperature_c REAL,
            humidity REAL,
            wind_speed REAL,
            route_name TEXT,
            equipment_ids TEXT,
            original_file TEXT,
            raw_json TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(athlete_name, source, source_activity_id),
            FOREIGN KEY(athlete_id) REFERENCES athletes(id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS derived_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id INTEGER NOT NULL,
            metric_name TEXT NOT NULL,
            metric_value REAL,
            metric_text TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(activity_id) REFERENCES activities(id),
            UNIQUE(activity_id, metric_name)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS benchmarks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            athlete_name TEXT NOT NULL,
            activity_id INTEGER,
            benchmark_type TEXT NOT NULL,
            benchmark_date TEXT,
            distance_m REAL,
            duration_s REAL,
            avg_hr REAL,
            avg_power REAL,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(activity_id) REFERENCES activities(id)
        )
        """
    )


def create_athlete_identities_table(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS athlete_identities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            athlete_id INTEGER NOT NULL,
            source TEXT NOT NULL,
            external_name TEXT NOT NULL,
            external_id TEXT,
            is_primary INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(athlete_id) REFERENCES athletes(id),
            UNIQUE(source, external_name)
        )
        """
    )


def create_goals_table(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            athlete_id INTEGER NOT NULL,
            goal_name TEXT NOT NULL,
            goal_type TEXT NOT NULL,
            distance_m REAL,
            target_time_s INTEGER,
            target_date TEXT,
            race_name TEXT,
            priority TEXT NOT NULL DEFAULT 'Primary',
            status TEXT NOT NULL DEFAULT 'Active',
            motivation TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(athlete_id) REFERENCES athletes(id)
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_goals_athlete_status
        ON goals (athlete_id, status)
        """
    )


def migrate_to_schema_v2(cursor):
    ensure_column(
        cursor,
        "activities",
        "athlete_id",
        "INTEGER REFERENCES athletes(id)",
    )
    create_athlete_identities_table(cursor)

    cursor.execute(
        "SELECT id, first_name, last_name FROM athletes ORDER BY id"
    )

    for athlete_id, first_name, last_name in cursor.fetchall():
        full_name = f"{first_name or ''} {last_name or ''}".strip()
        possible_names = set()

        if first_name:
            possible_names.add(first_name.strip())
        if full_name:
            possible_names.add(full_name)

        for external_name in possible_names:
            cursor.execute(
                """
                INSERT OR IGNORE INTO athlete_identities (
                    athlete_id, source, external_name, is_primary
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    athlete_id,
                    "runalyze_csv",
                    external_name,
                    1 if external_name == full_name else 0,
                ),
            )

    cursor.execute(
        """
        UPDATE activities
        SET athlete_id = (
            SELECT ai.athlete_id
            FROM athlete_identities ai
            WHERE ai.source = activities.source
              AND lower(ai.external_name) = lower(activities.athlete_name)
            LIMIT 1
        )
        WHERE athlete_id IS NULL
        """
    )
    set_schema_version(cursor, 2)


def migrate_to_schema_v3(cursor):
    create_goals_table(cursor)
    set_schema_version(cursor, 3)


def get_active_goal(athlete_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            id, athlete_id, goal_name, goal_type, distance_m,
            target_time_s, target_date, race_name, priority,
            status, motivation, created_at, updated_at
        FROM goals
        WHERE athlete_id = ?
          AND status = 'Active'
          AND priority = 'Primary'
        ORDER BY updated_at DESC, id DESC
        LIMIT 1
        """,
        (athlete_id,),
    )
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return None

    columns = [
        "id", "athlete_id", "goal_name", "goal_type", "distance_m",
        "target_time_s", "target_date", "race_name", "priority",
        "status", "motivation", "created_at", "updated_at",
    ]
    return dict(zip(columns, row))


def get_goals_for_athlete(athlete_id):
    """Return every saved goal in coaching priority order."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            id, athlete_id, training_block_id, goal_name, goal_type,
            distance_m, target_time_s, target_date, race_name, priority,
            status, motivation, created_at, updated_at
        FROM goals
        WHERE athlete_id = ?
        ORDER BY
            CASE priority
                WHEN 'Primary' THEN 0
                WHEN 'Secondary' THEN 1
                ELSE 2
            END,
            CASE status
                WHEN 'Active' THEN 0
                WHEN 'Planned' THEN 1
                ELSE 2
            END,
            target_date,
            id
        """,
        (athlete_id,),
    )
    rows = cursor.fetchall()
    conn.close()

    columns = (
        "id", "athlete_id", "training_block_id", "goal_name", "goal_type",
        "distance_m", "target_time_s", "target_date", "race_name",
        "priority", "status", "motivation", "created_at", "updated_at",
    )
    return [dict(zip(columns, row)) for row in rows]


def save_goal(
    athlete_id,
    goal_name,
    goal_type,
    distance_m=None,
    target_time_s=None,
    target_date=None,
    race_name=None,
    priority="Primary",
    status="Active",
    motivation=None,
    goal_id=None,
):
    if priority not in {"Primary", "Secondary", "Future"}:
        raise ValueError(f"Unsupported goal priority: {priority}")
    if status not in {"Active", "Planned", "Complete", "Archived"}:
        raise ValueError(f"Unsupported goal status: {status}")

    if priority == "Primary" and status not in {"Complete", "Archived"}:
        status = "Active"
    elif priority == "Future" and status not in {"Complete", "Archived"}:
        status = "Planned"

    conn = get_connection()
    cursor = conn.cursor()

    if status == "Active" and priority == "Primary":
        cursor.execute(
            """
            UPDATE goals
            SET priority = 'Secondary', updated_at = CURRENT_TIMESTAMP
            WHERE athlete_id = ?
              AND status = 'Active'
              AND priority = 'Primary'
              AND (? IS NULL OR id != ?)
            """,
            (athlete_id, goal_id, goal_id),
        )

    values = (
        athlete_id, goal_name, goal_type, distance_m, target_time_s,
        target_date, race_name, priority, status, motivation,
    )

    if goal_id is None:
        cursor.execute(
            """
            INSERT INTO goals (
                athlete_id, goal_name, goal_type, distance_m,
                target_time_s, target_date, race_name, priority,
                status, motivation
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            values,
        )
        goal_id = cursor.lastrowid
    else:
        cursor.execute(
            """
            UPDATE goals
            SET goal_name = ?, goal_type = ?, distance_m = ?,
                target_time_s = ?, target_date = ?, race_name = ?,
                priority = ?, status = ?, motivation = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND athlete_id = ?
            """,
            (
                goal_name, goal_type, distance_m, target_time_s,
                target_date, race_name, priority, status, motivation,
                goal_id, athlete_id,
            ),
        )

    conn.commit()
    conn.close()
    return goal_id



def create_decoded_workouts_table(cursor):
    """Create cached Workout Coach output."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS decoded_workouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id INTEGER NOT NULL UNIQUE,
            workout_type TEXT NOT NULL,
            description TEXT,
            confidence REAL NOT NULL DEFAULT 0,
            execution_score REAL,
            rep_count INTEGER NOT NULL DEFAULT 0,
            average_rep_distance_km REAL,
            average_rep_pace_s_per_km REAL,
            rep_pace_variation_percent REAL,
            workout_json TEXT NOT NULL,
            decoder_version INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(activity_id) REFERENCES activities(id)
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_decoded_workouts_type
        ON decoded_workouts (workout_type)
        """
    )


def migrate_to_schema_v4(cursor):
    """Add the Workout Coach cache table."""
    create_decoded_workouts_table(cursor)
    set_schema_version(cursor, 4)


def create_athlete_sport_mappings_table(cursor):
    """Store account-specific sport IDs for each athlete."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS athlete_sport_mappings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            athlete_id INTEGER NOT NULL,
            sport_id TEXT NOT NULL,
            sport_role TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 0,
            source TEXT NOT NULL DEFAULT 'inferred',
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(athlete_id) REFERENCES athletes(id),
            UNIQUE(athlete_id, sport_id)
        )
        """
    )


def backfill_missing_athlete_ids(cursor):
    """
    Repair imported activities that have athlete_name but no athlete_id.

    Matching is case-insensitive and accepts first name or full name.
    """
    cursor.execute(
        """
        SELECT id, first_name, last_name
        FROM athletes
        ORDER BY id
        """
    )

    for athlete_id, first_name, last_name in cursor.fetchall():
        first = (first_name or "").strip()
        full = f"{first_name or ''} {last_name or ''}".strip()

        names = [name for name in {first, full} if name]

        for name in names:
            cursor.execute(
                """
                UPDATE activities
                SET athlete_id = ?
                WHERE athlete_id IS NULL
                  AND lower(trim(athlete_name)) = lower(trim(?))
                """,
                (athlete_id, name),
            )


def infer_athlete_sport_mappings(cursor):
    """
    Infer running and walking sport IDs separately for every athlete.

    Runalyze sport IDs are account-specific. We infer roles from title
    evidence and activity frequency, then store the result.
    """
    create_athlete_sport_mappings_table(cursor)

    cursor.execute("SELECT id FROM athletes ORDER BY id")
    athlete_ids = [row[0] for row in cursor.fetchall()]

    for athlete_id in athlete_ids:
        cursor.execute(
            """
            SELECT
                CAST(sport_id AS TEXT) AS sport_id,
                COUNT(*) AS total,
                SUM(
                    CASE
                        WHEN lower(COALESCE(title, '')) LIKE '%running%'
                          OR lower(COALESCE(title, '')) LIKE '% run%'
                          OR lower(COALESCE(title, '')) LIKE 'run%'
                          OR lower(COALESCE(title, '')) LIKE '%parkrun%'
                          OR lower(COALESCE(title, '')) LIKE '%5k%'
                          OR lower(COALESCE(title, '')) LIKE '%10k%'
                          OR lower(COALESCE(title, '')) LIKE '%race%'
                        THEN 1 ELSE 0
                    END
                ) AS run_signals,
                SUM(
                    CASE
                        WHEN lower(COALESCE(title, '')) LIKE '%walking%'
                          OR lower(COALESCE(title, '')) LIKE '% walk%'
                          OR lower(COALESCE(title, '')) LIKE 'walk%'
                        THEN 1 ELSE 0
                    END
                ) AS walk_signals
            FROM activities
            WHERE athlete_id = ?
              AND sport_id IS NOT NULL
            GROUP BY CAST(sport_id AS TEXT)
            """,
            (athlete_id,),
        )

        rows = cursor.fetchall()

        if not rows:
            continue

        running = max(
            rows,
            key=lambda row: (
                row[2] or 0,
                row[1] if (row[2] or 0) > 0 else 0,
            ),
        )
        walking = max(
            rows,
            key=lambda row: (
                row[3] or 0,
                row[1] if (row[3] or 0) > 0 else 0,
            ),
        )

        mappings = []

        if (running[2] or 0) > 0:
            confidence = min((running[2] or 0) / max(running[1], 1), 1.0)
            mappings.append((running[0], "running", confidence))

        if (walking[3] or 0) > 0 and walking[0] != running[0]:
            confidence = min((walking[3] or 0) / max(walking[1], 1), 1.0)
            mappings.append((walking[0], "walking", confidence))

        for sport_id, sport_role, confidence in mappings:
            cursor.execute(
                """
                INSERT INTO athlete_sport_mappings (
                    athlete_id,
                    sport_id,
                    sport_role,
                    confidence,
                    source,
                    updated_at
                )
                VALUES (?, ?, ?, ?, 'inferred', CURRENT_TIMESTAMP)
                ON CONFLICT(athlete_id, sport_id) DO UPDATE SET
                    sport_role = excluded.sport_role,
                    confidence = excluded.confidence,
                    source = excluded.source,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    athlete_id,
                    str(sport_id),
                    sport_role,
                    confidence,
                ),
            )


@lru_cache(maxsize=64)
def _get_athlete_sport_roles_cached(athlete_id, database_path):
    """Read sport roles from one exact database-backed cache namespace."""
    conn = sqlite3.connect(database_path)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT sport_id, sport_role
        FROM athlete_sport_mappings
        WHERE athlete_id = ?
        """,
        (athlete_id,),
    )

    roles = {str(row[0]): row[1] for row in cursor.fetchall()}
    conn.close()

    # Direct Garmin FIT imports use canonical sport names rather than the
    # account-specific numeric IDs supplied by Runalyze.  Keep those canonical
    # values visible alongside the inferred mappings so an athlete can have
    # more than one source representing the same sport.
    roles.setdefault("running", "running")
    roles.setdefault("walking", "walking")

    return roles


def get_athlete_sport_roles(athlete_id):
    """
    Return stored sport-role mappings for one athlete.

    The database path is part of the internal cache key. This matters for the
    isolated test databases and also keeps a future database switch from
    reusing another database's athlete IDs. The public cache_clear contract is
    retained for import and repair workflows.
    """
    return _get_athlete_sport_roles_cached(
        int(athlete_id),
        str(DATABASE_PATH.resolve()),
    )


get_athlete_sport_roles.cache_clear = _get_athlete_sport_roles_cached.cache_clear


def refresh_athlete_sport_mappings():
    """Rebuild sport mappings after an import or explicit repair."""
    conn = get_connection()
    cursor = conn.cursor()

    create_athlete_sport_mappings_table(cursor)
    infer_athlete_sport_mappings(cursor)

    conn.commit()
    conn.close()

    get_athlete_sport_roles.cache_clear()


def migrate_to_schema_v5(cursor):
    """Add automatic athlete repair and athlete-specific sport mappings."""
    create_athlete_sport_mappings_table(cursor)
    backfill_missing_athlete_ids(cursor)
    infer_athlete_sport_mappings(cursor)
    set_schema_version(cursor, 5)


def create_workout_library_tables(cursor):
    """
    Create the permanent workout knowledge-base tables.

    These tables store normalised workout intelligence separately from raw
    activities so future decoders can rebuild the library without changing
    or losing the original activity data.
    """
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS workout_library (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id INTEGER NOT NULL UNIQUE,
            athlete_id INTEGER NOT NULL,
            activity_date TEXT,
            session_type TEXT NOT NULL,
            workout_signature TEXT NOT NULL,
            phase_json TEXT NOT NULL,
            execution_score REAL,
            recognition_confidence REAL NOT NULL DEFAULT 0,
            phase_confidence REAL NOT NULL DEFAULT 0,
            source TEXT NOT NULL,
            decoder_version INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(activity_id) REFERENCES activities(id)
                ON DELETE CASCADE,
            FOREIGN KEY(athlete_id) REFERENCES athletes(id)
                ON DELETE CASCADE
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_workout_library_athlete_date
        ON workout_library(athlete_id, activity_date DESC)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_workout_library_signature
        ON workout_library(athlete_id, workout_signature)
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS workout_race_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workout_id INTEGER NOT NULL,
            race_activity_id INTEGER NOT NULL,
            days_after INTEGER NOT NULL,
            race_distance_km REAL,
            race_time_s REAL,
            link_confidence REAL NOT NULL DEFAULT 0,
            similarity_score REAL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(workout_id) REFERENCES workout_library(id)
                ON DELETE CASCADE,
            FOREIGN KEY(race_activity_id) REFERENCES activities(id)
                ON DELETE CASCADE,
            UNIQUE(workout_id, race_activity_id)
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_workout_race_links_workout
        ON workout_race_links(workout_id)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_workout_race_links_race
        ON workout_race_links(race_activity_id)
        """
    )


def migrate_to_schema_v6(cursor):
    """Add the workout intelligence library and race-link foundation."""
    create_workout_library_tables(cursor)
    create_threshold_overrides_table(cursor)
    set_schema_version(cursor, 6)


def create_threshold_overrides_table(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS athlete_threshold_overrides (
            athlete_id INTEGER PRIMARY KEY,
            lt1_hr INTEGER,
            lt2_hr INTEGER,
            max_hr INTEGER,
            source TEXT,
            tested_at TEXT,
            notes TEXT,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(athlete_id) REFERENCES athletes(id)
                ON DELETE CASCADE
        )
        """
    )


def migrate_to_schema_v7(cursor):
    """Add verified manual physiological-threshold overrides."""
    create_threshold_overrides_table(cursor)
    set_schema_version(cursor, 7)



def create_training_blocks_table(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS training_blocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            athlete_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            block_type TEXT NOT NULL DEFAULT 'General',
            purpose TEXT,
            start_date TEXT,
            end_date TEXT,
            status TEXT NOT NULL DEFAULT 'Planned',
            primary_focus TEXT,
            current_phase TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(athlete_id) REFERENCES athletes(id)
                ON DELETE CASCADE
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_training_blocks_athlete_status
        ON training_blocks (athlete_id, status, start_date)
        """
    )


def migrate_to_schema_v8(cursor):
    """Add Training Blocks and allow goals to belong to a block."""
    create_training_blocks_table(cursor)

    ensure_column(
        cursor,
        "goals",
        "training_block_id",
        "INTEGER REFERENCES training_blocks(id)",
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_goals_training_block
        ON goals (training_block_id)
        """
    )

    set_schema_version(cursor, 8)


def get_effective_athlete_thresholds(athlete_id):
    conn = get_connection()
    cursor = conn.cursor()
    create_threshold_overrides_table(cursor)

    cursor.execute(
        """
        SELECT
            a.lt1_hr,
            a.lt2_hr,
            a.max_hr,
            o.lt1_hr,
            o.lt2_hr,
            o.max_hr,
            o.source,
            o.tested_at,
            o.notes,
            COALESCE(o.enabled, 0)
        FROM athletes a
        LEFT JOIN athlete_threshold_overrides o
          ON o.athlete_id = a.id
        WHERE a.id = ?
        """,
        (athlete_id,),
    )
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return {
            "lt1_hr": None,
            "lt2_hr": None,
            "athlete_max_hr": None,
            "source": "Not set",
        }

    (
        calculated_lt1,
        calculated_lt2,
        calculated_max,
        manual_lt1,
        manual_lt2,
        manual_max,
        manual_source,
        tested_at,
        notes,
        enabled,
    ) = row

    use_manual = bool(enabled)
    from core.threshold_estimation import estimate_athlete_thresholds
    estimate = estimate_athlete_thresholds(int(athlete_id))
    estimated_lt1 = estimate.lt1.value_bpm
    estimated_lt2 = estimate.lt2.value_bpm
    estimated_max = estimate.max_hr_basis
    effective_lt1 = (
        manual_lt1 if use_manual and manual_lt1
        else calculated_lt1 if calculated_lt1
        else estimated_lt1
    )
    effective_lt2 = (
        manual_lt2 if use_manual and manual_lt2
        else calculated_lt2 if calculated_lt2
        else estimated_lt2
    )
    effective_max = (
        manual_max if use_manual and manual_max
        else calculated_max if calculated_max
        else estimated_max
    )
    if use_manual:
        effective_source = manual_source or "Verified manual values"
    elif calculated_lt1 or calculated_lt2:
        effective_source = "Athlete profile values"
    elif estimate.available:
        effective_source = "Estimated from training history"
    else:
        effective_source = "Not set"

    return {
        "lt1_hr": effective_lt1,
        "lt2_hr": effective_lt2,
        "athlete_max_hr": effective_max,
        "source": effective_source,
        "tested_at": tested_at if use_manual else None,
        "notes": notes if use_manual else None,
        "estimated_lt1_hr": estimated_lt1,
        "estimated_lt2_hr": estimated_lt2,
        "estimated_max_hr": estimated_max,
        "estimate_confidence": estimate.lt1.confidence,
        "estimate_sample_size": estimate.reliable_run_count,
    }


def get_athletes_with_effective_thresholds():
    conn = get_connection()
    cursor = conn.cursor()
    create_threshold_overrides_table(cursor)

    cursor.execute(
        """
        SELECT
            a.id,
            a.first_name,
            a.last_name,
            a.lt1_hr,
            a.lt2_hr,
            a.max_hr,
            o.lt1_hr,
            o.lt2_hr,
            o.max_hr,
            o.source,
            o.tested_at,
            o.notes,
            COALESCE(o.enabled, 0)
        FROM athletes a
        LEFT JOIN athlete_threshold_overrides o
          ON o.athlete_id = a.id
        ORDER BY a.first_name, a.last_name, a.id
        """
    )
    rows = cursor.fetchall()
    conn.close()

    athletes = []

    for row in rows:
        (
            athlete_id,
            first_name,
            last_name,
            calculated_lt1,
            calculated_lt2,
            calculated_max,
            manual_lt1,
            manual_lt2,
            manual_max,
            override_source,
            tested_at,
            override_notes,
            override_enabled,
        ) = row

        use_manual = bool(override_enabled)
        from core.threshold_estimation import estimate_athlete_thresholds
        estimate = estimate_athlete_thresholds(int(athlete_id))
        estimated_lt1 = estimate.lt1.value_bpm
        estimated_lt2 = estimate.lt2.value_bpm
        estimated_max = estimate.max_hr_basis
        effective_lt1 = (
            manual_lt1 if use_manual and manual_lt1
            else calculated_lt1 if calculated_lt1 else estimated_lt1
        )
        effective_lt2 = (
            manual_lt2 if use_manual and manual_lt2
            else calculated_lt2 if calculated_lt2 else estimated_lt2
        )
        effective_max = (
            manual_max if use_manual and manual_max
            else calculated_max if calculated_max else estimated_max
        )
        if use_manual:
            effective_source = override_source or "Verified manual values"
        elif calculated_lt1 or calculated_lt2:
            effective_source = "Athlete profile values"
        elif estimate.available:
            effective_source = "Estimated from training history"
        else:
            effective_source = "Not set"

        athletes.append(
            {
                "id": athlete_id,
                "first_name": first_name,
                "last_name": last_name,
                "calculated_lt1_hr": calculated_lt1,
                "calculated_lt2_hr": calculated_lt2,
                "calculated_max_hr": calculated_max,
                "estimated_lt1_hr": estimated_lt1,
                "estimated_lt2_hr": estimated_lt2,
                "estimated_max_hr": estimated_max,
                "estimate_confidence": estimate.lt1.confidence,
                "estimate_sample_size": estimate.reliable_run_count,
                "estimate_latest_date": estimate.latest_evidence_date,
                "manual_lt1_hr": manual_lt1,
                "manual_lt2_hr": manual_lt2,
                "manual_max_hr": manual_max,
                "override_source": override_source,
                "tested_at": tested_at,
                "override_notes": override_notes,
                "override_enabled": use_manual,
                "effective_lt1_hr": effective_lt1,
                "effective_lt2_hr": effective_lt2,
                "effective_max_hr": effective_max,
                "effective_source": effective_source,
            }
        )

    return athletes


def save_threshold_override(
    athlete_id,
    lt1_hr,
    lt2_hr,
    max_hr,
    source,
    tested_at,
    notes,
):
    conn = get_connection()
    cursor = conn.cursor()
    create_threshold_overrides_table(cursor)

    cursor.execute(
        """
        INSERT INTO athlete_threshold_overrides (
            athlete_id,
            lt1_hr,
            lt2_hr,
            max_hr,
            source,
            tested_at,
            notes,
            enabled,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(athlete_id) DO UPDATE SET
            lt1_hr = excluded.lt1_hr,
            lt2_hr = excluded.lt2_hr,
            max_hr = excluded.max_hr,
            source = excluded.source,
            tested_at = excluded.tested_at,
            notes = excluded.notes,
            enabled = 1,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            athlete_id,
            lt1_hr,
            lt2_hr,
            max_hr,
            source,
            tested_at,
            notes,
        ),
    )
    conn.commit()
    conn.close()


def clear_threshold_override(athlete_id):
    conn = get_connection()
    cursor = conn.cursor()
    create_threshold_overrides_table(cursor)
    cursor.execute(
        """
        UPDATE athlete_threshold_overrides
        SET enabled = 0,
            updated_at = CURRENT_TIMESTAMP
        WHERE athlete_id = ?
        """,
        (athlete_id,),
    )
    conn.commit()
    conn.close()


def _merge_duplicate_activity_children(cursor, keeper_id, duplicate_id):
    """
    Move child records from duplicate_id onto keeper_id without losing useful
    analysis. Tables with uniqueness on activity_id are merged conservatively.
    """

    # derived_metrics: unique(activity_id, metric_name)
    cursor.execute(
        """
        INSERT OR IGNORE INTO derived_metrics (
            activity_id, metric_name, metric_value, metric_text, created_at
        )
        SELECT ?, metric_name, metric_value, metric_text, created_at
        FROM derived_metrics
        WHERE activity_id = ?
        """,
        (keeper_id, duplicate_id),
    )
    cursor.execute(
        "DELETE FROM derived_metrics WHERE activity_id = ?",
        (duplicate_id,),
    )

    # benchmarks can safely be re-pointed.
    cursor.execute(
        "UPDATE benchmarks SET activity_id = ? WHERE activity_id = ?",
        (keeper_id, duplicate_id),
    )

    # decoded_workouts: one row per activity.
    cursor.execute(
        "SELECT 1 FROM decoded_workouts WHERE activity_id = ?",
        (keeper_id,),
    )
    keeper_has_decoded = cursor.fetchone() is not None

    if keeper_has_decoded:
        cursor.execute(
            "DELETE FROM decoded_workouts WHERE activity_id = ?",
            (duplicate_id,),
        )
    else:
        cursor.execute(
            "UPDATE decoded_workouts SET activity_id = ? WHERE activity_id = ?",
            (keeper_id, duplicate_id),
        )

    # workout_library: one record per activity in current schema. If both
    # exist, keep the keeper's record and remove only the duplicate record.
    cursor.execute(
        "SELECT id FROM workout_library WHERE activity_id = ?",
        (keeper_id,),
    )
    keeper_workout = cursor.fetchone()

    cursor.execute(
        "SELECT id FROM workout_library WHERE activity_id = ?",
        (duplicate_id,),
    )
    duplicate_workout = cursor.fetchone()

    if duplicate_workout:
        duplicate_workout_id = duplicate_workout[0]

        if keeper_workout:
            # Any race links attached to the duplicate workout are copied onto
            # the keeper workout where possible.
            cursor.execute(
                """
                INSERT OR IGNORE INTO workout_race_links (
                    workout_id,
                    race_activity_id,
                    days_after,
                    race_distance_km,
                    race_time_s,
                    link_confidence,
                    similarity_score,
                    created_at,
                    updated_at
                )
                SELECT ?, race_activity_id, days_after, race_distance_km,
                       race_time_s, link_confidence, similarity_score,
                       created_at, updated_at
                FROM workout_race_links
                WHERE workout_id = ?
                """,
                (keeper_workout[0], duplicate_workout_id),
            )
            cursor.execute(
                "DELETE FROM workout_race_links WHERE workout_id = ?",
                (duplicate_workout_id,),
            )
            cursor.execute(
                "DELETE FROM workout_library WHERE id = ?",
                (duplicate_workout_id,),
            )
        else:
            cursor.execute(
                "UPDATE workout_library SET activity_id = ? WHERE id = ?",
                (keeper_id, duplicate_workout_id),
            )


def _prefer_activity_payload(cursor, keeper_id, duplicate_id):
    """
    Keep the older canonical row id (safer for historical links), but refresh
    user-facing/raw fields from the newer duplicate when the newer record is
    at least as rich.
    """
    cursor.execute(
        """
        SELECT raw_json, title, route_name, activity_hash, athlete_name
        FROM activities
        WHERE id = ?
        """,
        (keeper_id,),
    )
    keeper = cursor.fetchone()

    cursor.execute(
        """
        SELECT raw_json, title, route_name, activity_hash, athlete_name
        FROM activities
        WHERE id = ?
        """,
        (duplicate_id,),
    )
    duplicate = cursor.fetchone()

    if not keeper or not duplicate:
        return

    keeper_raw = keeper[0] or "{}"
    duplicate_raw = duplicate[0] or "{}"

    try:
        keeper_fields = len(json.loads(keeper_raw))
    except Exception:
        keeper_fields = 0

    try:
        duplicate_fields = len(json.loads(duplicate_raw))
    except Exception:
        duplicate_fields = 0

    raw_json = duplicate_raw if duplicate_fields >= keeper_fields else keeper_raw
    title = duplicate[1] or keeper[1]
    route_name = duplicate[2] or keeper[2]
    activity_hash = duplicate[3] or keeper[3]

    cursor.execute(
        """
        UPDATE activities
        SET raw_json = ?,
            title = ?,
            route_name = ?,
            activity_hash = ?
        WHERE id = ?
        """,
        (raw_json, title, route_name, activity_hash, keeper_id),
    )


def migrate_to_schema_v9(cursor):
    """
    Make Runalyze identity athlete-based rather than display-name-based.

    The old unique key included athlete_name, so changing 'Richard' to
    'Richard Burke' allowed the same Runalyze activity to be imported twice.
    """
    cursor.execute(
        """
        SELECT athlete_id, source, source_activity_id
        FROM activities
        WHERE athlete_id IS NOT NULL
          AND source_activity_id IS NOT NULL
        GROUP BY athlete_id, source, source_activity_id
        HAVING COUNT(*) > 1
        """
    )
    groups = cursor.fetchall()

    for athlete_id, source, source_activity_id in groups:
        cursor.execute(
            """
            SELECT id
            FROM activities
            WHERE athlete_id = ?
              AND source = ?
              AND source_activity_id = ?
            ORDER BY id
            """,
            (athlete_id, source, source_activity_id),
        )
        ids = [row[0] for row in cursor.fetchall()]

        if len(ids) < 2:
            continue

        keeper_id = ids[0]

        for duplicate_id in ids[1:]:
            _prefer_activity_payload(
                cursor,
                keeper_id,
                duplicate_id,
            )
            _merge_duplicate_activity_children(
                cursor,
                keeper_id,
                duplicate_id,
            )
            cursor.execute(
                "DELETE FROM activities WHERE id = ?",
                (duplicate_id,),
            )

    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS
        idx_activities_athlete_source_external_unique
        ON activities (athlete_id, source, source_activity_id)
        WHERE athlete_id IS NOT NULL
        """
    )

    set_schema_version(cursor, 9)


def create_training_block_designs_table(cursor):
    """Persist the athlete-approved shape behind a Training Block."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS training_block_designs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            athlete_id INTEGER NOT NULL,
            training_block_id INTEGER NOT NULL UNIQUE,
            primary_goal_id INTEGER NOT NULL,
            preferences_json TEXT NOT NULL,
            evidence_json TEXT NOT NULL,
            plan_json TEXT NOT NULL,
            model_version INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(athlete_id) REFERENCES athletes(id)
                ON DELETE CASCADE,
            FOREIGN KEY(training_block_id) REFERENCES training_blocks(id)
                ON DELETE CASCADE,
            FOREIGN KEY(primary_goal_id) REFERENCES goals(id)
                ON DELETE CASCADE
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_training_block_designs_athlete
        ON training_block_designs (athlete_id, updated_at)
        """
    )


def migrate_to_schema_v10(cursor):
    """Add persisted history-led Training Block designs."""
    create_training_blocks_table(cursor)
    create_training_block_designs_table(cursor)
    set_schema_version(cursor, 10)


def create_block_review_actions_table(cursor):
    """Persist append-only athlete decisions without rewriting the saved plan."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS block_review_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            athlete_id INTEGER NOT NULL,
            training_block_id INTEGER NOT NULL,
            review_key TEXT NOT NULL,
            review_type TEXT NOT NULL,
            week_number INTEGER NOT NULL,
            target_date TEXT NOT NULL,
            decision TEXT NOT NULL CHECK (
                decision IN ('Accept', 'Defer', 'Reject')
            ),
            original_json TEXT NOT NULL,
            proposed_json TEXT NOT NULL,
            evidence TEXT NOT NULL,
            reason TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(athlete_id) REFERENCES athletes(id)
                ON DELETE CASCADE,
            FOREIGN KEY(training_block_id) REFERENCES training_blocks(id)
                ON DELETE CASCADE
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_block_review_actions_lookup
        ON block_review_actions (
            athlete_id, training_block_id, review_key, id
        )
        """
    )


def migrate_to_schema_v11(cursor):
    """Add the auditable Deliberate Block Review action history."""
    create_training_blocks_table(cursor)
    create_block_review_actions_table(cursor)
    set_schema_version(cursor, 11)


def create_nutrition_tables(cursor):
    """Store athlete food preferences and explicit weekly meal choices."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS athlete_nutrition_profiles (
            athlete_id INTEGER PRIMARY KEY,
            dietary_style TEXT NOT NULL DEFAULT 'Omnivore' CHECK (
                dietary_style IN (
                    'Omnivore', 'Pescatarian', 'Vegetarian', 'Vegan'
                )
            ),
            servings INTEGER NOT NULL DEFAULT 1 CHECK (
                servings BETWEEN 1 AND 12
            ),
            allergies_json TEXT NOT NULL DEFAULT '[]',
            dislikes_json TEXT NOT NULL DEFAULT '[]',
            max_cook_minutes INTEGER NOT NULL DEFAULT 45,
            budget_style TEXT NOT NULL DEFAULT 'Standard' CHECK (
                budget_style IN (
                    'Value conscious', 'Standard', 'Flexible'
                )
            ),
            use_leftovers INTEGER NOT NULL DEFAULT 1,
            show_nutrition_detail INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(athlete_id) REFERENCES athletes(id)
                ON DELETE CASCADE
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS nutrition_week_selections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            athlete_id INTEGER NOT NULL,
            training_block_id INTEGER NOT NULL,
            week_start TEXT NOT NULL,
            meal_date TEXT NOT NULL,
            meal_slot TEXT NOT NULL CHECK (
                meal_slot IN (
                    'Breakfast', 'Lunch', 'Dinner', 'Recovery snack'
                )
            ),
            recipe_id TEXT NOT NULL,
            servings INTEGER NOT NULL CHECK (servings BETWEEN 1 AND 12),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(athlete_id) REFERENCES athletes(id)
                ON DELETE CASCADE,
            FOREIGN KEY(training_block_id) REFERENCES training_blocks(id)
                ON DELETE CASCADE,
            UNIQUE(athlete_id, meal_date, meal_slot)
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_nutrition_week_lookup
        ON nutrition_week_selections (athlete_id, week_start, meal_date)
        """
    )


def migrate_to_schema_v12(cursor):
    """Add Weekly Fuel Planner profiles and saved meal selections."""
    create_training_blocks_table(cursor)
    create_nutrition_tables(cursor)
    set_schema_version(cursor, 12)


def create_athlete_evidence_overrides_tables(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS athlete_activity_overrides (
            activity_id INTEGER PRIMARY KEY,
            athlete_id INTEGER NOT NULL,
            session_intent TEXT,
            heart_rate_reliable INTEGER,
            corrected_avg_hr REAL,
            notes TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(activity_id) REFERENCES activities(id) ON DELETE CASCADE,
            FOREIGN KEY(athlete_id) REFERENCES athletes(id) ON DELETE CASCADE
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS athlete_personal_best_overrides (
            athlete_id INTEGER NOT NULL,
            event_key TEXT NOT NULL,
            official_time_s REAL NOT NULL,
            event_date TEXT,
            notes TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (athlete_id, event_key),
            FOREIGN KEY(athlete_id) REFERENCES athletes(id) ON DELETE CASCADE
        )
        """
    )


def migrate_to_schema_v13(cursor):
    create_athlete_evidence_overrides_tables(cursor)
    set_schema_version(cursor, 13)


def create_recovery_checkins_table(cursor):
    """Store one explicit, athlete-reported recovery check-in per day."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS athlete_recovery_checkins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            athlete_id INTEGER NOT NULL,
            checkin_date TEXT NOT NULL,
            sleep_quality INTEGER NOT NULL CHECK (sleep_quality BETWEEN 1 AND 5),
            fatigue INTEGER NOT NULL CHECK (fatigue BETWEEN 1 AND 5),
            soreness INTEGER NOT NULL CHECK (soreness BETWEEN 1 AND 5),
            motivation INTEGER NOT NULL CHECK (motivation BETWEEN 1 AND 5),
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(athlete_id) REFERENCES athletes(id) ON DELETE CASCADE,
            UNIQUE(athlete_id, checkin_date)
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_recovery_checkins_athlete_date
        ON athlete_recovery_checkins (athlete_id, checkin_date DESC)
        """
    )


def migrate_to_schema_v14(cursor):
    """Add athlete-reported recovery check-ins without inferred physiology."""
    create_recovery_checkins_table(cursor)
    set_schema_version(cursor, 14)


def create_athlete_health_daily_table(cursor):
    """Store source-labelled daily health evidence for one athlete."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS athlete_health_daily (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            athlete_id INTEGER NOT NULL,
            health_date TEXT NOT NULL,
            source TEXT NOT NULL,
            hrv_value REAL,
            hrv_metric_code TEXT,
            hrv_measurement_type TEXT,
            hrv_source_code TEXT,
            hrv_source_id TEXT,
            resting_hr REAL,
            resting_hr_source_id TEXT,
            sleep_source_id TEXT,
            sleep_start_time TEXT,
            sleep_end_time TEXT,
            sleep_duration_min REAL,
            sleep_rem_min REAL,
            sleep_awake_min REAL,
            sleep_deep_min REAL,
            sleep_light_min REAL,
            sleep_unknown_min REAL,
            sleep_quality REAL,
            sleep_quality_100 REAL,
            weight_kg REAL,
            raw_json TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(athlete_id) REFERENCES athletes(id) ON DELETE CASCADE,
            UNIQUE(athlete_id, health_date, source)
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_health_daily_athlete_date
        ON athlete_health_daily (athlete_id, health_date DESC)
        """
    )


def migrate_to_schema_v15(cursor):
    """Add auditable Runalyze health evidence without a readiness score."""
    create_athlete_health_daily_table(cursor)
    set_schema_version(cursor, 15)


@lru_cache(maxsize=128)
def get_activity_overrides(athlete_id):
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT activity_id, session_intent, heart_rate_reliable,
                      corrected_avg_hr, notes
               FROM athlete_activity_overrides WHERE athlete_id = ?""",
            (athlete_id,),
        ).fetchall()
    except sqlite3.OperationalError:
        rows = ()
    finally:
        conn.close()
    return {
        int(row[0]): {
            "session_intent": row[1],
            "heart_rate_reliable": None if row[2] is None else bool(row[2]),
            "corrected_avg_hr": row[3],
            "notes": row[4],
        }
        for row in rows
    }


def get_effective_activity_heart_rate(athlete_id, activity_id, recorded_avg_hr):
    override = get_activity_overrides(int(athlete_id)).get(int(activity_id), {})
    if override.get("heart_rate_reliable") is False:
        corrected = override.get("corrected_avg_hr")
        return float(corrected) if corrected is not None else None
    corrected = override.get("corrected_avg_hr")
    return float(corrected) if corrected is not None else recorded_avg_hr


def save_activity_override(
    athlete_id, activity_id, *, session_intent=None,
    heart_rate_reliable=None, corrected_avg_hr=None, notes=None,
):
    conn = get_connection()
    create_athlete_evidence_overrides_tables(conn.cursor())
    owner = conn.execute(
        "SELECT athlete_id FROM activities WHERE id = ?", (activity_id,)
    ).fetchone()
    if owner is None or int(owner[0]) != int(athlete_id):
        conn.close()
        raise ValueError("Activity does not belong to this athlete.")
    conn.execute(
        """INSERT INTO athlete_activity_overrides
               (activity_id, athlete_id, session_intent, heart_rate_reliable,
                corrected_avg_hr, notes)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(activity_id) DO UPDATE SET
               session_intent=excluded.session_intent,
               heart_rate_reliable=excluded.heart_rate_reliable,
               corrected_avg_hr=excluded.corrected_avg_hr,
               notes=excluded.notes, updated_at=CURRENT_TIMESTAMP""",
        (activity_id, athlete_id, session_intent,
         None if heart_rate_reliable is None else int(heart_rate_reliable),
         corrected_avg_hr, notes),
    )
    conn.commit()
    conn.close()
    get_activity_overrides.cache_clear()


def clear_activity_override(athlete_id, activity_id):
    conn = get_connection()
    create_athlete_evidence_overrides_tables(conn.cursor())
    conn.execute(
        "DELETE FROM athlete_activity_overrides WHERE athlete_id=? AND activity_id=?",
        (athlete_id, activity_id),
    )
    conn.commit()
    conn.close()
    get_activity_overrides.cache_clear()


def get_personal_best_overrides(athlete_id):
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT event_key, official_time_s, event_date, notes
               FROM athlete_personal_best_overrides WHERE athlete_id=?""",
            (athlete_id,),
        ).fetchall()
    except sqlite3.OperationalError:
        rows = ()
    finally:
        conn.close()
    return {
        row[0]: {"official_time_s": float(row[1]), "event_date": row[2], "notes": row[3]}
        for row in rows
    }


def save_personal_best_override(athlete_id, event_key, official_time_s, *, event_date=None, notes=None):
    if event_key not in {"5k", "10k", "half_marathon"} or float(official_time_s) <= 0:
        raise ValueError("Provide a supported distance and a positive official time.")
    conn = get_connection()
    create_athlete_evidence_overrides_tables(conn.cursor())
    conn.execute(
        """INSERT INTO athlete_personal_best_overrides
               (athlete_id, event_key, official_time_s, event_date, notes)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(athlete_id,event_key) DO UPDATE SET
               official_time_s=excluded.official_time_s,
               event_date=excluded.event_date, notes=excluded.notes,
               updated_at=CURRENT_TIMESTAMP""",
        (athlete_id, event_key, official_time_s, event_date, notes),
    )
    conn.commit()
    conn.close()


def clear_personal_best_override(athlete_id, event_key):
    conn = get_connection()
    create_athlete_evidence_overrides_tables(conn.cursor())
    conn.execute(
        "DELETE FROM athlete_personal_best_overrides WHERE athlete_id=? AND event_key=?",
        (athlete_id, event_key),
    )
    conn.commit()
    conn.close()


def initialise_database():
    conn = get_connection()
    cursor = conn.cursor()

    create_base_tables(cursor)
    create_schema_version_table(cursor)

    schema_version = get_schema_version(cursor)

    if schema_version < 2:
        migrate_to_schema_v2(cursor)
        schema_version = 2

    if schema_version < 3:
        migrate_to_schema_v3(cursor)
        schema_version = 3

    if schema_version < 4:
        migrate_to_schema_v4(cursor)
        schema_version = 4

    if schema_version < 5:
        migrate_to_schema_v5(cursor)
        schema_version = 5

    if schema_version < 6:
        migrate_to_schema_v6(cursor)
        schema_version = 6

    if schema_version < 7:
        migrate_to_schema_v7(cursor)
        schema_version = 7

    if schema_version < 8:
        migrate_to_schema_v8(cursor)
        schema_version = 8

    if schema_version < 9:
        migrate_to_schema_v9(cursor)
        schema_version = 9

    if schema_version < 10:
        migrate_to_schema_v10(cursor)
        schema_version = 10

    if schema_version < 11:
        migrate_to_schema_v11(cursor)
        schema_version = 11

    if schema_version < 12:
        migrate_to_schema_v12(cursor)
        schema_version = 12

    if schema_version < 13:
        migrate_to_schema_v13(cursor)
        schema_version = 13

    if schema_version < 14:
        migrate_to_schema_v14(cursor)
        schema_version = 14

    if schema_version < 15:
        migrate_to_schema_v15(cursor)
        schema_version = 15

    create_athlete_identities_table(cursor)
    create_goals_table(cursor)
    create_training_blocks_table(cursor)
    create_training_block_designs_table(cursor)
    create_block_review_actions_table(cursor)
    create_nutrition_tables(cursor)
    create_decoded_workouts_table(cursor)
    create_athlete_sport_mappings_table(cursor)
    create_workout_library_tables(cursor)
    create_athlete_evidence_overrides_tables(cursor)
    create_recovery_checkins_table(cursor)
    create_athlete_health_daily_table(cursor)

    backfill_missing_athlete_ids(cursor)

    cursor.execute(
        "SELECT COUNT(*) FROM athlete_sport_mappings"
    )
    mapping_count = cursor.fetchone()[0]

    if mapping_count == 0:
        infer_athlete_sport_mappings(cursor)

    conn.commit()
    conn.close()
