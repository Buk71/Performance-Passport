import datetime
import streamlit as st

from config import APP_NAME, APP_SUBTITLE
from core.database import get_connection
from core.coaching import (
    METRES_PER_MILE,
    RunProfile,
    build_baseline,
    classify_run,
    pace_per_km,
    pace_per_mile,
    seconds_to_pace,
)


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


def get_athlete_thresholds(athlete_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT lt1_hr, lt2_hr, max_hr
        FROM athletes
        WHERE id = ?
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
        }

    return {
        "lt1_hr": row[0],
        "lt2_hr": row[1],
        "athlete_max_hr": row[2],
    }


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


def get_run_profiles(athlete_id, athlete_thresholds):
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
            max_hr,
            sport_id,
            elevation_up_m
        FROM activities
        WHERE athlete_id = ?
        ORDER BY activity_datetime DESC
        """,
        (athlete_id,),
    )
    rows = cursor.fetchall()
    conn.close()

    return [
        RunProfile(
            activity_date=activity_date,
            title=title,
            distance_km=distance_km,
            moving_time_seconds=moving_time_s,
            avg_hr=avg_hr,
            run_max_hr=run_max_hr,
            sport_id=sport_id,
            elevation_m=elevation_m,
            lt1_hr=athlete_thresholds["lt1_hr"],
            lt2_hr=athlete_thresholds["lt2_hr"],
            athlete_max_hr=athlete_thresholds["athlete_max_hr"],
        )
        for (
            activity_date,
            title,
            distance_km,
            moving_time_s,
            avg_hr,
            run_max_hr,
            sport_id,
            elevation_m,
        ) in rows
    ]


def format_distance(distance_km):
    return f"{distance_km or 0:,.1f} km"


def format_distance_dual(distance_km):
    miles = (distance_km or 0) / (METRES_PER_MILE / 1000)
    return f"{miles:,.1f} mi • {distance_km or 0:,.1f} km"


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


def format_baseline_pace(avg_pace_seconds_per_km):
    if not avg_pace_seconds_per_km:
        return "--"

    seconds_per_mile = avg_pace_seconds_per_km * (METRES_PER_MILE / 1000)

    mile_pace = seconds_to_pace(seconds_per_mile)
    km_pace = seconds_to_pace(avg_pace_seconds_per_km)

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


def baseline_value(baseline, formatter):
    if baseline is None:
        return "--"
    return formatter(baseline)


def render_activity_card(activity):
    activity_date, title, distance_km, moving_time_s, avg_hr, sport_id = activity

    icon, sport_name = get_sport_display(sport_id)

    run_profile = RunProfile(
        title=title,
        sport_id=sport_id,
        distance_km=distance_km,
        moving_time_seconds=moving_time_s,
        avg_hr=avg_hr,
        activity_date=activity_date,
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


def render_baseline_insight(current, all_time):
    if current is None or all_time is None:
        return

    pace_diff_seconds_per_mile = (
        all_time.avg_pace_seconds_per_km - current.avg_pace_seconds_per_km
    ) * (METRES_PER_MILE / 1000)

    hr_diff = all_time.avg_hr - current.avg_hr

    if pace_diff_seconds_per_mile > 0 and hr_diff > 0:
        st.success(
            "Passport Insight: Your current easy-run baseline is faster and at a "
            "lower heart rate than your all-time baseline, suggesting improved "
            "aerobic fitness."
        )
    elif pace_diff_seconds_per_mile > 0:
        st.info(
            "Passport Insight: Your current easy-run baseline is faster than your "
            "all-time baseline."
        )
    elif hr_diff > 0:
        st.info(
            "Passport Insight: Your current easy-run baseline is at a lower heart "
            "rate than your all-time baseline."
        )
    else:
        st.info(
            "Passport Insight: Your current baseline is broadly similar to your "
            "all-time easy-running baseline."
        )


def render_typical_run_section(athlete_id):
    athlete_thresholds = get_athlete_thresholds(athlete_id)
    run_profiles = get_run_profiles(athlete_id, athlete_thresholds)

    current = build_baseline(
        runs=run_profiles,
        run_type="🟢 Run",
        baseline_name="Current",
        period_days=90,
    )

    season = build_baseline(
        runs=run_profiles,
        run_type="🟢 Run",
        baseline_name="Season",
        period_days=365,
    )

    all_time = build_baseline(
        runs=run_profiles,
        run_type="🟢 Run",
        baseline_name="All Time",
        period_days=None,
    )

    st.subheader("Typical Easy Run")
    st.caption("Baselines for activities included in the easy aerobic baseline")

    if current is None and season is None and all_time is None:
        st.info("Not enough running data yet to calculate a typical easy run.")
        return

    baseline_table = [
        {
            "Metric": "Runs analysed",
            "Current": baseline_value(current, lambda b: f"{b.run_count:,}"),
            "Season": baseline_value(season, lambda b: f"{b.run_count:,}"),
            "All Time": baseline_value(all_time, lambda b: f"{b.run_count:,}"),
        },
        {
            "Metric": "Typical pace",
            "Current": baseline_value(
                current, lambda b: format_baseline_pace(b.avg_pace_seconds_per_km)
            ),
            "Season": baseline_value(
                season, lambda b: format_baseline_pace(b.avg_pace_seconds_per_km)
            ),
            "All Time": baseline_value(
                all_time, lambda b: format_baseline_pace(b.avg_pace_seconds_per_km)
            ),
        },
        {
            "Metric": "Typical HR",
            "Current": baseline_value(current, lambda b: f"{b.avg_hr:.0f} bpm"),
            "Season": baseline_value(season, lambda b: f"{b.avg_hr:.0f} bpm"),
            "All Time": baseline_value(all_time, lambda b: f"{b.avg_hr:.0f} bpm"),
        },
        {
            "Metric": "Typical distance",
            "Current": baseline_value(
                current, lambda b: format_distance_dual(b.avg_distance_km)
            ),
            "Season": baseline_value(
                season, lambda b: format_distance_dual(b.avg_distance_km)
            ),
            "All Time": baseline_value(
                all_time, lambda b: format_distance_dual(b.avg_distance_km)
            ),
        },
        {
            "Metric": "Average elevation",
            "Current": baseline_value(
                current, lambda b: format_elevation(b.avg_elevation_m)
            ),
            "Season": baseline_value(
                season, lambda b: format_elevation(b.avg_elevation_m)
            ),
            "All Time": baseline_value(
                all_time, lambda b: format_elevation(b.avg_elevation_m)
            ),
        },
    ]

    st.table(baseline_table)
    render_baseline_insight(current, all_time)


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

    render_typical_run_section(selected_athlete_id)

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
        "Next sprint adds individual run comparison. Future sprints will add "
        "percentile rankings, heat-adjusted performance, Best Ever Easy Run, "
        "durability, fatigue, race readiness and Passport Score."
    )