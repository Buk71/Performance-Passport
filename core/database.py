import sqlite3
from pathlib import Path


DATABASE_PATH = Path("database") / "performance_passport.db"


def get_connection():
    """Return a connection to the Performance Passport database."""
    return sqlite3.connect(DATABASE_PATH)


def initialise_database():
    """Create the database and tables if they don't already exist."""

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_date TEXT,
            distance REAL,
            duration INTEGER,
            average_hr INTEGER,
            average_pace REAL
        )
    """)

    conn.commit()
    conn.close()