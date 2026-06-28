import sqlite3
from pathlib import Path


DATABASE_PATH = Path("database") / "performance_passport.db"


def get_connection():
    """Return a connection to the SQLite database."""
    return sqlite3.connect(DATABASE_PATH)


def initialise_database():
    """Create all database tables."""

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
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
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            athlete_id INTEGER NOT NULL,
            source TEXT NOT NULL,
            source_activity_id TEXT,
            file_hash TEXT,
            sport TEXT,
            start_time TEXT,
            distance_m REAL,
            moving_time_s INTEGER,
            elapsed_time_s INTEGER,
            avg_pace_s_per_km REAL,
            avg_speed_mps REAL,
            avg_hr INTEGER,
            max_hr INTEGER,
            avg_cadence REAL,
            elevation_gain_m REAL,
            elevation_loss_m REAL,
            temperature_c REAL,
            humidity REAL,
            dew_point_c REAL,
            calories INTEGER,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (athlete_id) REFERENCES athletes(id)
        )
    """)

    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_activity_source
        ON activities (athlete_id, source, source_activity_id)
        WHERE source_activity_id IS NOT NULL
    """)

    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_activity_file_hash
        ON activities (athlete_id, file_hash)
        WHERE file_hash IS NOT NULL
    """)

    conn.commit()
    conn.close()