import datetime
import html
import textwrap

import streamlit as st

from core.database import get_active_goal, get_connection, save_goal


DISTANCE_OPTIONS = {
    "5K": 5000.0,
    "10K": 10000.0,
    "10 Mile": 16093.44,
    "Half Marathon": 21097.5,
    "Marathon": 42195.0,
    "Custom": None,
}

GOAL_TYPES = [
    "Race time",
    "Complete a distance",
    "Improve aerobic fitness",
    "General fitness",
    "Custom",
]


def safe_text(value):
    return html.escape(str(value or ""))


def render_html(markup):
    cleaned_markup = textwrap.dedent(markup).strip()
    st.html(cleaned_markup)


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
    rows = cursor.fetchall()
    conn.close()
    return rows


def athlete_full_name(first_name, last_name):
    return f"{first_name or ''} {last_name or ''}".strip()

def update_selected_athlete():
    """Persist the athlete selected in the visible page widget."""

    st.session_state.selected_athlete_name = (
        st.session_state.goal_athlete_selector_widget
    )


def initialise_selected_athlete(athlete_names):
    """Set a valid shared athlete selection for all pages."""

    if (
        "selected_athlete_name" not in st.session_state
        or st.session_state.selected_athlete_name not in athlete_names
    ):
        st.session_state.selected_athlete_name = athlete_names[0]

    st.session_state.goal_athlete_selector_widget = (
        st.session_state.selected_athlete_name
    )

def seconds_to_clock(total_seconds):
    if total_seconds is None:
        return None

    total_seconds = int(total_seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"

    return f"{minutes}:{seconds:02d}"


def clock_to_seconds(hours, minutes, seconds):
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds)


def render_goal_summary(goal):
    if goal is None:
        render_html(
            """
            <div class="pp-card pp-card-hero pp-card-accent">
                <div class="pp-card-label">Active goal</div>
                <div class="pp-card-title">No goal configured yet</div>
                <div class="pp-card-copy">
                    Add an objective for this athlete. The Coach page will then
                    show the real target rather than a placeholder.
                </div>
                <div style="margin-top:0.8rem;">
                    <span class="pp-status pp-status-warning">
                        Goal needed
                    </span>
                </div>
            </div>
            """
        )
        return

    target = seconds_to_clock(goal["target_time_s"]) or "Completion goal"
    date_text = goal["target_date"] or "No target date"
    race_text = goal["race_name"] or "No race selected"

    render_html(
        f"""
        <div class="pp-card pp-card-hero pp-card-accent">
            <div class="pp-card-label">Active goal</div>
            <div class="pp-card-title">{safe_text(goal["goal_name"])}</div>

            <div style="
                display:grid;
                grid-template-columns:repeat(3, minmax(0, 1fr));
                gap:1rem;
                margin-top:1rem;
            ">
                <div>
                    <div class="pp-stat-label">Target</div>
                    <div class="pp-stat-value">{safe_text(target)}</div>
                </div>
                <div>
                    <div class="pp-stat-label">Race</div>
                    <div class="pp-stat-value" style="font-size:1rem;">
                        {safe_text(race_text)}
                    </div>
                </div>
                <div>
                    <div class="pp-stat-label">Date</div>
                    <div class="pp-stat-value" style="font-size:1rem;">
                        {safe_text(date_text)}
                    </div>
                </div>
            </div>

            <div class="pp-card-copy" style="margin-top:1rem;">
                Race prediction and goal probability are not calculated yet.
                They will be added in Sprint D2.2.
            </div>

            <div style="margin-top:0.8rem;">
                <span class="pp-status">Active</span>
            </div>
        </div>
        """
    )


def show_goals_page():
    athletes = get_athletes()

    if not athletes:
        st.warning("No athletes found. Add an athlete first.")
        return

    athlete_options = {
        athlete_full_name(first_name, last_name): athlete_id
        for athlete_id, first_name, last_name in athletes
    }

    athlete_names = list(athlete_options.keys())
    initialise_selected_athlete(athlete_names)

    selector_col, _ = st.columns([0.35, 0.65])

    with selector_col:
        st.selectbox(
            "Athlete",
            athlete_names,
            key="goal_athlete_selector_widget",
            on_change=update_selected_athlete,
            label_visibility="collapsed",
        )

    selected_name = st.session_state.selected_athlete_name

    athlete_id = athlete_options[selected_name]
    active_goal = get_active_goal(athlete_id)

    render_html(
        f"""
        <div class="pp-page-header">
            <div class="pp-page-eyebrow">Goal</div>
            <div class="pp-page-title">{safe_text(selected_name)}'s objective</div>
            <div class="pp-page-intro">
                Set the outcome that matters most. Performance Passport will
                use it to organise future predictions, progress and coaching.
            </div>
        </div>
        """
    )

    render_goal_summary(active_goal)

    st.markdown("## Configure goal")

    default_type = active_goal["goal_type"] if active_goal else "Race time"
    default_name = active_goal["goal_name"] if active_goal else ""
    default_race = active_goal["race_name"] if active_goal else ""
    default_motivation = active_goal["motivation"] if active_goal else ""
    default_status = active_goal["status"] if active_goal else "Active"
    default_priority = active_goal["priority"] if active_goal else "Primary"

    current_distance = active_goal["distance_m"] if active_goal else 10000.0
    distance_label = "Custom"

    for label, metres in DISTANCE_OPTIONS.items():
        if metres is not None and current_distance is not None:
            if abs(metres - current_distance) < 1:
                distance_label = label
                break

    target_seconds = active_goal["target_time_s"] if active_goal else 0
    target_hours = target_seconds // 3600
    target_minutes = (target_seconds % 3600) // 60
    target_secs = target_seconds % 60

    target_date_value = None
    if active_goal and active_goal["target_date"]:
        try:
            target_date_value = datetime.date.fromisoformat(
                active_goal["target_date"]
            )
        except ValueError:
            target_date_value = None

    with st.form("goal_form"):
        goal_type = st.selectbox(
            "Goal type",
            GOAL_TYPES,
            index=GOAL_TYPES.index(default_type)
            if default_type in GOAL_TYPES
            else 0,
        )

        goal_name = st.text_input(
            "Goal name",
            value=default_name,
            placeholder="e.g. Sub 39:00 10K",
        )

        distance_choice = st.selectbox(
            "Distance",
            list(DISTANCE_OPTIONS.keys()),
            index=list(DISTANCE_OPTIONS.keys()).index(distance_label),
        )

        custom_distance_km = None
        if distance_choice == "Custom":
            custom_distance_km = st.number_input(
                "Custom distance (km)",
                min_value=0.1,
                value=(current_distance or 10000.0) / 1000,
                step=0.1,
            )

        st.caption(
            "Enter a target time for race-time goals. Leave it at zero for "
            "completion, fitness or non-time goals."
        )

        time_col1, time_col2, time_col3 = st.columns(3)
        with time_col1:
            hours = st.number_input(
                "Hours",
                min_value=0,
                max_value=24,
                value=int(target_hours),
            )
        with time_col2:
            minutes = st.number_input(
                "Minutes",
                min_value=0,
                max_value=59,
                value=int(target_minutes),
            )
        with time_col3:
            seconds = st.number_input(
                "Seconds",
                min_value=0,
                max_value=59,
                value=int(target_secs),
            )

        race_name = st.text_input(
            "Race or event (optional)",
            value=default_race or "",
        )

        target_date = st.date_input(
            "Target date (optional)",
            value=target_date_value,
        )

        motivation = st.text_area(
            "Why does this matter? (optional)",
            value=default_motivation or "",
            placeholder="A short personal reason for choosing this goal",
        )

        col1, col2 = st.columns(2)
        with col1:
            priority = st.selectbox(
                "Priority",
                ["Primary", "Secondary"],
                index=0 if default_priority == "Primary" else 1,
            )
        with col2:
            statuses = ["Active", "Planned", "Completed", "Paused"]
            status = st.selectbox(
                "Status",
                statuses,
                index=statuses.index(default_status)
                if default_status in statuses
                else 0,
            )

        submitted = st.form_submit_button(
            "Save goal",
            use_container_width=True,
        )

    if submitted:
        if not goal_name.strip():
            st.error("Please enter a goal name.")
            return

        distance_m = DISTANCE_OPTIONS[distance_choice]
        if distance_choice == "Custom":
            distance_m = float(custom_distance_km) * 1000

        target_time_s = clock_to_seconds(hours, minutes, seconds)
        if target_time_s <= 0:
            target_time_s = None

        target_date_text = (
            target_date.isoformat()
            if isinstance(target_date, datetime.date)
            else None
        )

        save_goal(
            athlete_id=athlete_id,
            goal_name=goal_name.strip(),
            goal_type=goal_type,
            distance_m=distance_m,
            target_time_s=target_time_s,
            target_date=target_date_text,
            race_name=race_name.strip() or None,
            priority=priority,
            status=status,
            motivation=motivation.strip() or None,
            goal_id=active_goal["id"] if active_goal else None,
        )

        st.success("Goal saved.")
        st.rerun()
