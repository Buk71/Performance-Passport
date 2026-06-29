import datetime
import streamlit as st

from config import APP_NAME, APP_SUBTITLE
from core.database import get_connection


def athlete_full_name(first_name, last_name):
    return f"{first_name or ''} {last_name or ''}".strip()


def get_athletes():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, first_name, last_name
        FROM athletes
        ORDER BY first_name, last_name
        """
    )

    athletes = cursor.fetchall()
    conn.close()

    return athletes


def get_lifetime_summary(athlete_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            COUNT(*) AS activities,
            COALESCE(SUM(distance_m), 0) AS distance_m,
            COALESCE(SUM(moving_time_s), 0) AS moving_time_s,
            COALESCE(SUM(elevation_up_m), 0) AS elevation_up_m
        FROM activities
        WHERE athlete_id = ?
        """,
        (athlete_id,),
    )

    row = cursor.fetchone()
    conn.close()

    return row


def get_year_summary(athlete_id, year):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            COUNT(*) AS activities,
            COALESCE(SUM(distance_m), 0) AS distance_m,
            COALESCE(SUM(moving_time_s), 0) AS moving_time_s,
            COALESCE(SUM(elevation_up_m), 0) AS elevation_up_m
        FROM activities
        WHERE athlete_id = ?
          AND substr(activity_date, 1, 4) = ?
        """,
        (athlete_id, str(year)),
    )

    row = cursor.fetchone()
    conn.close()

    return row


def get_recent_activities(athlete_id, limit=5):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            activity_date,
            title,
            distance_m,
            moving_time_s,
            avg_hr,
            sport_id
        FROM activities
        WHERE athlete_id = ?
        ORDER BY activity_datetime DESC
        LIMIT ?
        """,
        (athlete_id, limit),
    )

    rows = cursor.fetchall()
    conn.close()

    return rows


def format_distance(distance_km):
    if distance_km is None:
        return "0.0 km"

    return f"{distance_km:,.1f} km"


def format_hours(seconds):
    return f"{seconds / 3600:,.1f} hrs"


def format_elevation(elevation_m):
    return f"{elevation_m:,.0f} m"


def format_pace(distance_m, moving_time_s):
    if not distance_m or not moving_time_s:
        return "--"

    km = distance_m / 1000
    pace_seconds = moving_time_s / km
    minutes = int(pace_seconds // 60)
    seconds = int(round(pace_seconds % 60))

    return f"{minutes}:{seconds:02d}/km"


def show_dashboard():
    st.title(APP_NAME)
    st.subheader(APP_SUBTITLE)

    st.write(
        "A coaching dashboard built to interpret your running data, not just display it."
    )

    athletes = get_athletes()

    if not athletes:
        st.warning("No athletes found. Add an athlete first.")
        return

    athlete_options = {
        athlete_full_name(first_name, last_name): athlete_id
        for athlete_id, first_name, last_name in athletes
    }

    selected_athlete_name = st.selectbox(
        "Athlete",
        list(athlete_options.keys()),
    )

    selected_athlete_id = athlete_options[selected_athlete_name]

    st.divider()

    st.subheader(f"{selected_athlete_name} — Lifetime Summary")

    activities, distance_m, moving_time_s, elevation_up_m = get_lifetime_summary(
        selected_athlete_id
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Activities", f"{activities:,}")
    col2.metric("Distance", format_distance(distance_m))
    col3.metric("Moving Time", format_hours(moving_time_s))
    col4.metric("Elevation", format_elevation(elevation_up_m))

    st.divider()

    current_year = datetime.date.today().year
    st.subheader(f"{current_year} Summary")

    (
        year_activities,
        year_distance_m,
        year_moving_time_s,
        year_elevation_up_m,
    ) = get_year_summary(selected_athlete_id, current_year)

    weeks_elapsed = datetime.date.today().isocalendar().week
    average_weekly_distance_m = (
        year_distance_m / weeks_elapsed if weeks_elapsed else 0
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Activities", f"{year_activities:,}")
    col2.metric("Distance", format_distance(year_distance_m))
    col3.metric("Moving Time", format_hours(year_moving_time_s))
    col4.metric("Average Week", format_distance(average_weekly_distance_m))

    st.divider()

    st.subheader("Recent Activities")

    recent_activities = get_recent_activities(selected_athlete_id)

    if not recent_activities:
        st.info("No recent activities found.")
    else:
        for activity in recent_activities:
            (
                activity_date,
                title,
                activity_distance_m,
                activity_moving_time_s,
                avg_hr,
                sport_id,
            ) = activity

            pace = format_pace(activity_distance_m, activity_moving_time_s)

            st.write(
                f"**{activity_date}** — {title or 'Untitled activity'}  \n"
                f"{format_distance(activity_distance_m)} • {pace} • "
                f"Avg HR {avg_hr or '--'} • Sport {sport_id or '--'}"
            )

    st.divider()

    st.subheader("Passport Insights")

    st.info(
        "Sprint 3.0 creates the live dashboard foundation. "
        "Future sprints will add heat-adjusted performance, best ever easy run, "
        "durability, fatigue, race readiness and Passport Score."
    )