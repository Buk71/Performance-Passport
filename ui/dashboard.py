import datetime
import html
import textwrap

import streamlit as st

from core.coaching import (
    METRES_PER_MILE,
    RunProfile,
    best_easy_run,
    build_baseline,
    equivalent_performance,
    seconds_to_pace,
)
from core.database import get_connection


SPORT_MAP = {
    "965611": ("Running", "Run"),
    "965617": ("Walking", "Walk"),
    "965613": ("Cycling", "Ride"),
    "965619": ("Indoor Cycling", "Indoor Ride"),
    "965612": ("Swimming", "Swim"),
    "965614": ("Strength / Mobility", "Strength"),
    "965615": ("Strength", "Strength"),
    "965616": ("Other / Gym", "Training"),
    "965630": ("Yoga / Stretching", "Yoga"),
    "965632": ("Hiking", "Hike"),
    "965621": ("Mountain / Gravel Bike", "Ride"),
    "1742104": ("Golf", "Golf"),
    "1637482": ("Pilates", "Pilates"),
}


# Temporary goal values until the Goal screen and goal table are built.
GOAL_NAME = "Sub 39:00 10K"
GOAL_TARGET_SECONDS = 39 * 60
CURRENT_PREDICTION_SECONDS = (39 * 60) + 18
GOAL_PROGRESS_PERCENT = 74


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
            elevation_up_m,
            temperature_c,
            humidity
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
            temperature_c=temperature_c,
            humidity=humidity,
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
            temperature_c,
            humidity,
        ) in rows
    ]


def safe_text(value):
    return html.escape(str(value or ""))

def render_html(markup):
    """Render a custom Performance Passport HTML component."""

    cleaned_markup = textwrap.dedent(markup).strip()
    st.html(cleaned_markup)

def format_date(date_text):
    try:
        parsed_date = datetime.date.fromisoformat(date_text)
        return parsed_date.strftime("%d %b")
    except (TypeError, ValueError):
        return date_text or "Unknown"


def format_clock(seconds):
    if seconds is None:
        return "--"

    seconds = int(round(seconds))
    minutes = seconds // 60
    remaining_seconds = seconds % 60
    return f"{minutes}:{remaining_seconds:02d}"


def format_distance_miles(distance_km):
    miles = (distance_km or 0) / (METRES_PER_MILE / 1000)
    return f"{miles:.1f} mi"


def format_pace_per_mile(seconds_per_km):
    if not seconds_per_km:
        return "--"

    seconds_per_mile = seconds_per_km * (METRES_PER_MILE / 1000)
    return f"{seconds_to_pace(seconds_per_mile)}/mi"


def format_hours(seconds):
    return f"{(seconds or 0) / 3600:,.0f} hrs"


def get_sport_name(sport_id):
    return SPORT_MAP.get(str(sport_id or ""), ("Activity", "Activity"))


def render_header(first_name):
    render_html(
        f"""
        <div class="pp-page-header">
            <div class="pp-page-eyebrow">Coach</div>
            <div class="pp-page-title">
                Good morning, {safe_text(first_name)}.
            </div>
            <div class="pp-page-intro">
                You are <strong>18 seconds away</strong> from your
                sub-39:00 goal. Today's easy running is an opportunity
                to build fitness without adding unnecessary fatigue.
            </div>
        </div>
        """
    )


def render_goal_card():
    difference = CURRENT_PREDICTION_SECONDS - GOAL_TARGET_SECONDS

    render_html(
        f"""
        <div class="pp-card pp-card-hero pp-card-accent">
            <div class="pp-card-label">Goal progress</div>

            <div style="
                display:flex;
                justify-content:space-between;
                align-items:flex-start;
                gap:1rem;
                margin-top:0.45rem;
            ">
                <div>
                    <div class="pp-card-title">{GOAL_NAME}</div>
                    <div class="pp-small-meta">
                        Current prediction
                    </div>
                    <div
                        class="pp-large-value"
                        style="margin-top:0.2rem;"
                    >
                        {format_clock(CURRENT_PREDICTION_SECONDS)}
                    </div>
                </div>

                <div style="text-align:right;">
                    <div
                        class="
                            pp-large-value
                            pp-large-value-accent
                        "
                    >
                        {GOAL_PROGRESS_PERCENT}%
                    </div>
                    <div class="pp-small-meta">
                        {difference} seconds to goal
                    </div>
                </div>
            </div>

            <div class="pp-progress-track">
                <div
                    class="pp-progress-fill"
                    style="width:{GOAL_PROGRESS_PERCENT}%;"
                ></div>
            </div>

            <div style="
                display:flex;
                justify-content:space-between;
                align-items:center;
                margin-top:0.75rem;
            ">
                <div class="pp-small-meta">
                    Target {format_clock(GOAL_TARGET_SECONDS)}
                </div>
                <div class="pp-status">
                    High confidence
                </div>
            </div>
        </div>
        """
    )


def render_coach_brief(current_baseline, all_time_baseline):
    if current_baseline and all_time_baseline:
        pace_change_per_mile = (
            all_time_baseline.avg_pace_seconds_per_km
            - current_baseline.avg_pace_seconds_per_km
        ) * (METRES_PER_MILE / 1000)

        if pace_change_per_mile >= 2:
            main_message = (
                "Your aerobic fitness is moving in the right direction."
            )
            evidence = (
                f"Your current easy-running baseline is approximately "
                f"{pace_change_per_mile:.0f} sec/mi faster than your "
                f"all-time baseline."
            )
        else:
            main_message = "Your aerobic fitness is currently stable."
            evidence = (
                "Your recent easy running is broadly consistent with your "
                "long-term baseline."
            )
    else:
        main_message = "Your training history is ready to be interpreted."
        evidence = (
            "More comparable easy runs will strengthen the confidence "
            "of your aerobic baseline."
        )

    render_html(
        f"""
        <div class="pp-card pp-card-hero">
            <div class="pp-card-label">Coach's brief</div>
            <div class="pp-card-title">{safe_text(main_message)}</div>
            <div class="pp-card-copy">{safe_text(evidence)}</div>

            <div style="
                margin-top:0.95rem;
                padding-top:0.85rem;
                border-top:1px solid var(--pp-border);
                display:flex;
                justify-content:space-between;
                align-items:center;
                gap:1rem;
            ">
                <div>
                    <div class="pp-card-label">Today's recommendation</div>
                    <div class="pp-card-title" style="font-size:1rem;">
                        Easy run · 8 miles
                    </div>
                </div>
                <div class="pp-status">High confidence</div>
            </div>
        </div>
        """
    )


def render_stat_card(label, value, context):
    render_html(
        f"""
        <div class="pp-stat-card">
            <div class="pp-stat-label">{safe_text(label)}</div>
            <div class="pp-stat-value">{safe_text(value)}</div>
            <div class="pp-stat-context">{safe_text(context)}</div>
        </div>
        """
    )


def render_latest_discovery(best_run):
    if best_run is None:
        title = "Your first discovery is taking shape."
        copy = (
            "Performance Passport needs more comparable easy runs before "
            "selecting your strongest aerobic performance."
        )
        confidence = "Building evidence"
    else:
        run = best_run.run
        performance = best_run.equivalent_performance

        title = "One of your strongest aerobic performances."
        copy = (
            f"{run.title or 'Easy Run'} on {format_date(run.activity_date)} "
            f"produced an equivalent pace of "
            f"{format_pace_per_mile(performance.equivalent_pace_seconds_per_km)}."
        )
        confidence = "High confidence"

    render_html(
        f"""
        <div class="pp-card">
            <div class="pp-card-label">Latest discovery</div>
            <div class="pp-card-title">{safe_text(title)}</div>
            <div class="pp-card-copy">{safe_text(copy)}</div>
            <div style="margin-top:0.8rem;">
                <span class="pp-status">{safe_text(confidence)}</span>
            </div>
        </div>
        """
    )


def render_recent_activities(run_profiles):
    rows = []

    for run in run_profiles[:5]:
        sport_name, fallback_title = get_sport_name(run.sport_id)
        performance = equivalent_performance(run)

        if performance is not None:
            pace = format_pace_per_mile(
                performance.actual_pace_seconds_per_km
            )
        else:
            pace = "--"

        rows.append(
            f"""
            <div class="pp-activity-row">
                <div class="pp-activity-date">
                    {safe_text(format_date(run.activity_date))}
                </div>

                <div>
                    <div class="pp-activity-name">
                        {safe_text(run.title or fallback_title)}
                    </div>
                    <div class="pp-activity-detail">
                        {safe_text(sport_name)}
                    </div>
                </div>

                <div class="pp-activity-detail">
                    {safe_text(format_distance_miles(run.distance_km))}
                </div>

                <div class="pp-activity-detail">
                    {safe_text(pace)}
                </div>

                <div>
                    <span class="pp-status">
                        Analysed
                    </span>
                </div>
            </div>
            """
        )

    if not rows:
        rows.append(
            """
            <div class="pp-card-copy">
                No recent activities are available.
            </div>
            """
        )

    render_html(
        f"""
        <div class="pp-card">
            <div style="
                display:flex;
                align-items:center;
                justify-content:space-between;
                margin-bottom:0.2rem;
            ">
                <div>
                    <div class="pp-card-label">Training history</div>
                    <div class="pp-card-title">Recent activities</div>
                </div>
            </div>
            {''.join(rows)}
        </div>
        """
    )


def show_dashboard():
    athletes = get_athletes()

    if not athletes:
        st.warning("No athletes found. Add an athlete first.")
        return

    athlete_options = {
        athlete_full_name(first_name, last_name): {
            "id": athlete_id,
            "first_name": first_name or "Athlete",
        }
        for athlete_id, first_name, last_name in athletes
    }

    selector_col, spacer_col = st.columns([0.35, 0.65])

    with selector_col:
        selected_name = st.selectbox(
            "Athlete",
            list(athlete_options.keys()),
            label_visibility="collapsed",
        )

    selected = athlete_options[selected_name]
    athlete_id = selected["id"]

    thresholds = get_athlete_thresholds(athlete_id)
    run_profiles = get_run_profiles(athlete_id, thresholds)

    current_baseline = build_baseline(
        runs=run_profiles,
        run_type="🟢 Run",
        baseline_name="Current",
        period_days=90,
    )

    all_time_baseline = build_baseline(
        runs=run_profiles,
        run_type="🟢 Run",
        baseline_name="All Time",
        period_days=None,
    )

    best_run = best_easy_run(run_profiles)

    render_header(selected["first_name"])

    top_left, top_right = st.columns([1.05, 0.95], gap="medium")

    with top_left:
        render_goal_card()

    with top_right:
        render_coach_brief(current_baseline, all_time_baseline)

    st.markdown("## This year")

    current_year = datetime.date.today().year

    (
        year_activities,
        year_distance_km,
        year_moving_time_s,
        _,
    ) = get_year_summary(athlete_id, current_year)

    weeks_elapsed = max(datetime.date.today().isocalendar().week, 1)
    weekly_distance_km = year_distance_km / weeks_elapsed
    weekly_distance_miles = weekly_distance_km / (
        METRES_PER_MILE / 1000
    )

    stat1, stat2, stat3, stat4 = st.columns(4, gap="small")

    with stat1:
        render_stat_card(
            "Activities",
            f"{year_activities:,}",
            f"Recorded in {current_year}",
        )

    with stat2:
        render_stat_card(
            "Average week",
            f"{weekly_distance_miles:.1f} mi",
            "Across the current year",
        )

    with stat3:
        render_stat_card(
            "Moving time",
            format_hours(year_moving_time_s),
            "Training time this year",
        )

    with stat4:
        if current_baseline:
            render_stat_card(
                "Easy-run pace",
                format_pace_per_mile(
                    current_baseline.avg_pace_seconds_per_km
                ),
                f"Based on {current_baseline.run_count} recent runs",
            )
        else:
            render_stat_card(
                "Easy-run pace",
                "--",
                "Building your current baseline",
            )

    st.markdown("## What matters now")

    discovery_col, context_col = st.columns([1.15, 0.85], gap="medium")

    with discovery_col:
        render_latest_discovery(best_run)

    with context_col:
        lifetime_activities, _, _, _ = get_lifetime_summary(athlete_id)

        render_html(
            f"""
            <div class="pp-card">
                <div class="pp-card-label">Passport confidence</div>
                <div class="pp-card-title">Very high</div>
                <div class="pp-card-copy">
                    Performance Passport has
                    <strong>{lifetime_activities:,} activities</strong>
                    available for learning about your training history.
            </div>
            <div style="margin-top:0.8rem;">
                <span class="pp-status">Strong evidence base</span>
            </div>
        </div>
        """
)

    st.markdown("## Latest training")
    render_recent_activities(run_profiles)