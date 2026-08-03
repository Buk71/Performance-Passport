import sqlite3
from functools import lru_cache
from pathlib import Path

DATABASE_PATH = Path("database") / "performance_passport.db"
CURRENT_SCHEMA_VERSION = 5


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
        WHERE athlete_id = ? AND status = 'Active'
        ORDER BY
            CASE WHEN priority = 'Primary' THEN 0 ELSE 1 END,
            updated_at DESC,
            id DESC
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
    conn = get_connection()
    cursor = conn.cursor()

    if status == "Active" and priority == "Primary":
        cursor.execute(
            """
            UPDATE goals
            SET status = 'Planned', updated_at = CURRENT_TIMESTAMP
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


@lru_cache(maxsize=32)
def get_athlete_sport_roles(athlete_id):
    """
    Return stored sport-role mappings for one athlete.

    Important: this function must remain read-only because Session
    Intelligence calls it once for every activity during diagnostics.
    """
    conn = get_connection()
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

    return roles


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

    create_athlete_identities_table(cursor)
    create_goals_table(cursor)
    create_decoded_workouts_table(cursor)
    create_athlete_sport_mappings_table(cursor)

    backfill_missing_athlete_ids(cursor)

    cursor.execute(
        "SELECT COUNT(*) FROM athlete_sport_mappings"
    )
    mapping_count = cursor.fetchone()[0]

    if mapping_count == 0:
        infer_athlete_sport_mappings(cursor)

    conn.commit()
    conn.close()
