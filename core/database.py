import sqlite3
from pathlib import Path


DATABASE_PATH = Path("database") / "performance_passport.db"


def get_connection():
    """Return a connection to the SQLite database."""
    DATABASE_PATH.parent.mkdir(exist_ok=True)
    return sqlite3.connect(DATABASE_PATH)


def get_activity_count():
    """Return the number of activities currently stored."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM activities")
    count = cursor.fetchone()[0]

    conn.close()
    return count


def initialise_database():
    """Create all database tables."""

    conn = get_connection()
    cursor = conn.cursor()

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
            UNIQUE(athlete_name, source, source_activity_id)
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

    conn.commit()
    conn.close()