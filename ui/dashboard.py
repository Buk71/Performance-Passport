import datetime
import streamlit as st

from config import APP_NAME, APP_SUBTITLE
from core.database import get_connection
from core.coaching import RunProfile, classify_run, pace_per_km, pace_per_mile


SPORT_MAP = {
    "965611": ("🏃", "Running"),
    "965617": ("🚶", "Walking"),
    "965613": ("🚴", "Cycling"),
    "965619": ("🚴", "Indoor Cycling"),
    "965612": ("🏊", "Swimming"),
    "965614": ("🏋️", "Strength / Mobility"),
    "965615": ("🏋️", "Strength"),
    "965616": ("🏋️", "Other / Gym"),
    "965630": ("🧘", "Yoga / Stretching"),
    "965632": ("🥾", "Hiking"),
    "965621": ("🚵", "Mountain / Gravel Bike"),
    "1742104": ("⛳", "Golf"),
    "1637482": ("🧘", "Pilates"),
}


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
            COUNT(*),
            COALESCE(SUM(distance_m), 0),
            COALESCE(SUM(moving_time_s), 0),
            COALESCE(SUM(elevation_up_m), 0)
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
            COUNT(*),
            COALESCE(SUM(distance_m), 0),
            COALESCE(SUM(moving_time_s), 0),
            COALESCE(SUM(elevation_up_m), 0)
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
    return f"{distance_km or 0:,.1f} km"


def format_hours(seconds):
    return f"{(seconds or 0) / 3600:,.1f} hrs"


def format_duration(seconds):
    if not seconds:
        return "--"

    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    remaining_seconds = seconds % 60

    if hours:
        return f"{hours}:{minutes:02d}:{remaining_seconds:02d}"

    return f"{minutes}:{remaining_seconds:02d}"


def format_elevation(elevation_m):
    return f"{elevation_m or 0:,.0f} m"


def format_pace(distance_km, moving_time_s):
    if not distance_km or not moving_time_s:
        return "--"

    distance_metres = distance_km * 1000

    mile_pace = pace_per_mile(distance_metres, moving_time_s)
    km_pace = pace_per_km(distance_metres, moving_time_s)

    return f"{mile_pace}/mi • {km_pace}/km"


def format_date(date_text):
    try:
        parsed_date = datetime.date.fromisoformat(date_text)
        return parsed_date.strftime("%d %b %Y")
    except (TypeError, ValueError):
        return date_text or "Unknown date"


def get_sport_display(sport_id):
    sport_key = str(sport_id or "")
    return SPORT_MAP.get(sport_key, ("❓", f"Unknown sport {sport_key}"))


def render_activity_card(activity):
    activity_date, title, distance_km, moving_time_s, avg_hr, sport_id = activity

    icon, sport_name = get_sport_display(sport_id)

    run_profile = RunProfile(
        title=title,
        sport_id=sport_id,
        distance_km=distance_km,
        moving_time_seconds=moving_time_s,
        avg_hr=avg_hr,
    )
    run_classification = classify_run(run_profile)

    with st.container(border=True):
        st.write(f"{icon} **{title or sport_name}**")

        if run_classification:
            st.write(f"**{run_classification}**")

        st.caption(f"{format_date(activity_date)} • {sport_name}")

        col1, col2, col3, col4 = st.columns(4)

        col1.metric("Distance", format_distance(distance_km))
        col2.metric("Pace", format_pace(distance_km, moving_time_s))
        col3.metric("Duration", format_duration(moving_time_s))
        col4.metric("Avg HR", f"{avg_hr:.0f}" if avg_hr else "--")


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

    activities, distance_km, moving_time_s, elevation_up_m = get_lifetime_summary(
        selected_athlete_id
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Activities", f"{activities:,}")
    col2.metric("Distance", format_distance(distance_km))
    col3.metric("Moving Time", format_hours(moving_time_s))
    col4.metric("Elevation", format_elevation(elevation_up_m))

    st.divider()

    current_year = datetime.date.today().year
    st.subheader(f"{current_year} Summary")

    (
        year_activities,
        year_distance_km,
        year_moving_time_s,
        year_elevation_up_m,
    ) = get_year_summary(selected_athlete_id, current_year)

    weeks_elapsed = datetime.date.today().isocalendar().week
    average_weekly_distance_km = (
        year_distance_km / weeks_elapsed if weeks_elapsed else 0
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Activities", f"{year_activities:,}")
    col2.metric("Distance", format_distance(year_distance_km))
    col3.metric("Moving Time", format_hours(year_moving_time_s))
    col4.metric("Average Week", format_distance(average_weekly_distance_km))

    st.divider()

    st.subheader("Recent Activities")

    recent_activities = get_recent_activities(selected_athlete_id)

    if not recent_activities:
        st.info("No recent activities found.")
    else:
        for activity in recent_activities:
            render_activity_card(activity)

    st.divider()

    st.subheader("Coming Next")

    st.info(
        "Next sprint adds the first Passport Insight. Future sprints will add "
        "heat-adjusted performance, Best Ever Easy Run, durability, fatigue, "
        "race readiness and Passport Score."
    )