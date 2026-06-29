import sqlite3
from pathlib import Path


DATABASE_PATH = Path("database") / "performance_passport.db"
CURRENT_SCHEMA_VERSION = 2


def get_connection():
    """Return a connection to the SQLite database."""
    DATABASE_PATH.parent.mkdir(exist_ok=True)
    return sqlite3.connect(DATABASE_PATH)


def get_table_columns(cursor, table_name):
    """Return a list of column names for a table."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [row[1] for row in cursor.fetchall()]


def ensure_column(cursor, table_name, column_name, column_definition):
    """Add a column if it does not already exist."""
    columns = get_table_columns(cursor, table_name)

    if column_name not in columns:
        cursor.execute(
            f"""
            ALTER TABLE {table_name}
            ADD COLUMN {column_name} {column_definition}
            """
        )


def create_schema_version_table(cursor):
    """Create schema version tracking table."""
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
    """Return current schema version."""
    create_schema_version_table(cursor)

    cursor.execute("SELECT version FROM schema_version WHERE id = 1")
    row = cursor.fetchone()

    if row is None:
        cursor.execute(
            """
            INSERT INTO schema_version (id, version)
            VALUES (1, 1)
            """
        )
        return 1

    return row[0]


def set_schema_version(cursor, version):
    """Set database schema version."""
    cursor.execute(
        """
        UPDATE schema_version
        SET version = ?,
            applied_at = CURRENT_TIMESTAMP
        WHERE id = 1
        """,
        (version,),
    )


def get_activity_count():
    """Return the number of activities currently stored."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM activities")
    count = cursor.fetchone()[0]

    conn.close()
    return count


def create_base_tables(cursor):
    """Create all base schema v1 tables."""

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
    """Create athlete identities table for external source names."""
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


def migrate_to_schema_v2(cursor):
    """
    Migrate database to schema v2.

    Adds:
    - activities.athlete_id
    - athlete_identities table
    - safe backfill for existing activities
    """

    ensure_column(
        cursor,
        "activities",
        "athlete_id",
        "INTEGER REFERENCES athletes(id)",
    )

    create_athlete_identities_table(cursor)

    cursor.execute(
        """
        SELECT id, first_name, last_name
        FROM athletes
        ORDER BY id
        """
    )
    athletes = cursor.fetchall()

    for athlete_id, first_name, last_name in athletes:
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
                    athlete_id,
                    source,
                    external_name,
                    is_primary
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


def initialise_database():
    """Create and migrate all database tables."""

    conn = get_connection()
    cursor = conn.cursor()

    create_base_tables(cursor)
    create_schema_version_table(cursor)

    schema_version = get_schema_version(cursor)

    if schema_version < 2:
        migrate_to_schema_v2(cursor)

    conn.commit()
    conn.close()