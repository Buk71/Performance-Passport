import datetime
import html
import textwrap

import streamlit as st

from core.coach_brain import CoachBrain
from core.coaching import (
    METRES_PER_MILE,
    RunProfile,
    best_easy_run,
    build_baseline,
    equivalent_performance,
    seconds_to_pace,
)
from core.database import get_active_goal, get_connection
from core.evidence import EvidenceStatus
from core.performance_dna import build_performance_dna


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


def format_pace_value(seconds_per_km):
    if seconds_per_km is None:
        return "—"

    minutes = int(seconds_per_km // 60)
    seconds = int(round(seconds_per_km % 60))

    if seconds == 60:
        minutes += 1
        seconds = 0

    return f"{minutes}:{seconds:02d}/km"


def athlete_full_name(first_name, last_name):
    return f"{first_name or ''} {last_name or ''}".strip()


def update_selected_athlete():
    """Persist the athlete selected in the visible page widget."""
    st.session_state.selected_athlete_name = (
        st.session_state.athlete_selector_widget
    )


def initialise_selected_athlete(athlete_names):
    """Set a valid shared athlete selection for all pages."""
    if (
        "selected_athlete_name" not in st.session_state
        or st.session_state.selected_athlete_name not in athlete_names
    ):
        st.session_state.selected_athlete_name = athlete_names[0]

    st.session_state.athlete_selector_widget = (
        st.session_state.selected_athlete_name
    )


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


def get_recent_weekly_average(athlete_id, weeks=26):
    """
    Return trailing average weekly distance ending on the latest imported run.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT MAX(date(activity_date))
        FROM activities
        WHERE athlete_id = ?
          AND activity_date IS NOT NULL
        """,
        (athlete_id,),
    )
    row = cursor.fetchone()
    latest_date_text = row[0] if row else None

    if not latest_date_text:
        conn.close()
        return 0.0, None

    latest_date = datetime.date.fromisoformat(latest_date_text)
    start_date = latest_date - datetime.timedelta(weeks=weeks)

    cursor.execute(
        """
        SELECT COALESCE(SUM(distance_m), 0)
        FROM activities
        WHERE athlete_id = ?
          AND date(activity_date) > ?
          AND date(activity_date) <= ?
        """,
        (
            athlete_id,
            start_date.isoformat(),
            latest_date.isoformat(),
        ),
    )
    total_distance_km = cursor.fetchone()[0] or 0
    conn.close()

    return total_distance_km / weeks, latest_date


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
            athlete_id=athlete_id,
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
    cleaned_markup = textwrap.dedent(markup).strip()
    st.html(cleaned_markup)


def format_date(date_text):
    try:
        parsed_date = datetime.date.fromisoformat(date_text)
        return parsed_date.strftime("%d %b")
    except (TypeError, ValueError):
        return date_text or "Unknown"


def format_goal_date(date_text):
    if not date_text:
        return "No target date"

    try:
        parsed_date = datetime.date.fromisoformat(date_text)
        return parsed_date.strftime("%d %b %Y")
    except (TypeError, ValueError):
        return date_text


def format_clock(seconds):
    if seconds is None:
        return "--"

    seconds = int(round(seconds))
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    remaining_seconds = seconds % 60

    if hours:
        return f"{hours}:{minutes:02d}:{remaining_seconds:02d}"

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


def evidence_strength(confidence):
    if confidence >= 0.85:
        return "Very strong"
    if confidence >= 0.70:
        return "Strong"
    if confidence >= 0.50:
        return "Developing"
    if confidence > 0:
        return "Limited"
    return "Unavailable"


def status_label(status):
    if status == EvidenceStatus.AVAILABLE:
        return "Available"
    if status == EvidenceStatus.BUILDING:
        return "Building"
    return "Unavailable"



def greeting_for_current_time(now=None):
    """Return a local, time-aware greeting."""
    current = now or datetime.datetime.now()
    hour = current.hour

    if 5 <= hour < 12:
        return "Good morning"
    if 12 <= hour < 17:
        return "Good afternoon"
    if 17 <= hour < 22:
        return "Good evening"

    return "Hello"

def render_header(first_name, goal):
    if goal is None:
        intro = (
            "Choose an objective to connect your training history to "
            "personalised progress and future race prediction."
        )
    else:
        intro = (
            f"Your active goal is "
            f"<strong>{safe_text(goal['goal_name'])}</strong>. "
            "The Coach Brain is now inspecting the evidence behind it."
        )

    render_html(
        f"""
        <div class="pp-page-header">
            <div class="pp-page-eyebrow">Coach</div>
            <div class="pp-page-title">
                {safe_text(greeting_for_current_time())}, {safe_text(first_name)}.
            </div>
            <div class="pp-page-intro">{intro}</div>
        </div>
        """
    )



def coach_status_icon(status):
    return {
        "strong": "🟢",
        "steady": "🟡",
        "limited": "🟠",
        "building": "⚪",
    }.get(status, "⚪")


def render_coaching_meeting(performance_dna, prediction):
    """Render the shared Personal Performance DNA view."""
    render_html(
        f"""
        <div class="pp-card pp-card-hero">
            <div class="pp-card-label">Personal Performance DNA</div>
            <div class="pp-card-title">
                {safe_text(performance_dna.headline)}
            </div>
            <div class="pp-card-copy">
                {safe_text(performance_dna.summary)}
            </div>

            <div style="
                display:grid;
                grid-template-columns:repeat(3, minmax(0, 1fr));
                gap:0.8rem;
                margin-top:1rem;
                padding-top:0.9rem;
                border-top:1px solid var(--pp-border);
            ">
                <div>
                    <div class="pp-stat-label">Coaches connected</div>
                    <div class="pp-stat-value" style="font-size:1rem;">
                        {performance_dna.available_coach_count}/
                        {performance_dna.total_coach_count}
                    </div>
                </div>
                <div>
                    <div class="pp-stat-label">Team confidence</div>
                    <div class="pp-stat-value" style="font-size:1rem;">
                        {performance_dna.overall_confidence:.0%}
                    </div>
                </div>
                <div>
                    <div class="pp-stat-label">Consensus</div>
                    <div class="pp-stat-value" style="font-size:1rem;">
                        {safe_text(
                            performance_dna.consensus_status
                            .replace("_", " ")
                            .title()
                        )}
                    </div>
                </div>
            </div>
        </div>
        """
    )

    st.markdown("### Today's coaching meeting")

    for verdict in performance_dna.verdicts:
        left, middle, right = st.columns([0.48, 0.27, 0.25])

        with left:
            st.markdown(
                f"{coach_status_icon(verdict.status)} "
                f"**{verdict.icon} {verdict.title}**"
            )
            st.caption(verdict.evidence_summary)

        with middle:
            st.write(verdict.verdict)
            if verdict.available:
                st.caption(f"Confidence {verdict.confidence:.0%}")
            else:
                st.caption("No invented opinion")

        with right:
            if verdict.predicted_seconds is not None:
                st.metric(
                    "Goal view",
                    format_clock(verdict.predicted_seconds),
                )
            elif verdict.available:
                st.write(verdict.signal)
            else:
                st.write("Building")

    st.markdown("### 🎯 Goal Coach consensus")

    if prediction.available:
        st.success(
            f"Current consensus capability: "
            f"**{format_clock(prediction.predicted_seconds)}**. "
            f"The team confidence is "
            f"**{performance_dna.overall_confidence:.0%}**."
        )
    else:
        st.info(
            "The Goal Coach is waiting for enough specialist evidence "
            "before giving a consensus capability."
        )

    if performance_dna.strongest_signal:
        st.caption(
            "Strongest current signal: "
            f"{performance_dna.strongest_signal}. "
            "This is a first shared DNA view; deeper threshold, easy-run, "
            "endurance and readiness comparisons come next."
        )

def render_daily_coach(
    first_name,
    goal,
    prediction,
    brain_brief,
    evidence_bundle,
    latest_activity_date,
):
    goal_name = goal["goal_name"] if goal else "No active goal"
    capability = (
        format_clock(prediction.predicted_seconds)
        if prediction.available
        else "Not available"
    )
    strength = evidence_strength(evidence_bundle.confidence)
    data_date = (
        latest_activity_date.strftime("%d %b %Y")
        if latest_activity_date is not None
        else "No activity date"
    )

    render_html(
        f"""
        <div class="pp-card pp-card-hero pp-card-accent">
            <div class="pp-card-label">Daily coach</div>
            <div class="pp-card-title" style="font-size:1.55rem;">
                {safe_text(brain_brief.headline)}
            </div>
            <div class="pp-card-copy" style="font-size:1rem;">
                {safe_text(brain_brief.summary)}
            </div>

            <div style="
                display:grid;
                grid-template-columns:repeat(3, minmax(0, 1fr));
                gap:1rem;
                margin-top:1.2rem;
                padding-top:1rem;
                border-top:1px solid var(--pp-border);
            ">
                <div>
                    <div class="pp-stat-label">Goal</div>
                    <div class="pp-stat-value" style="font-size:1rem;">
                        {safe_text(goal_name)}
                    </div>
                </div>
                <div>
                    <div class="pp-stat-label">Current capability</div>
                    <div class="pp-stat-value" style="font-size:1rem;">
                        {safe_text(capability)}
                    </div>
                </div>
                <div>
                    <div class="pp-stat-label">Evidence strength</div>
                    <div class="pp-stat-value" style="font-size:1rem;">
                        {safe_text(strength)}
                    </div>
                </div>
            </div>

            <div style="
                margin-top:1rem;
                padding-top:0.9rem;
                border-top:1px solid var(--pp-border);
            ">
                <div class="pp-card-label">Today's recommendation</div>
                <div class="pp-card-title" style="font-size:1rem;">
                    Not available yet
                </div>
                <div class="pp-small-meta">
                    Recovery and training-load evidence are not connected yet,
                    so Performance Passport will not invent a session.
                </div>
            </div>

            <div class="pp-small-meta" style="margin-top:0.9rem;">
                Evidence updated through {safe_text(data_date)}.
            </div>
        </div>
        """
    )

    with st.expander("Why is the Coach saying this?"):
        st.write(f"**Goal:** {goal_name}")
        st.write(
            f"**Prediction:** "
            f"{capability if prediction.available else prediction.explanation}"
        )
        st.write(
            f"**Evidence strength:** {strength} "
            f"({evidence_bundle.confidence:.0%})"
        )

        for item in evidence_bundle.items:
            st.markdown(f"**{item.title}**")
            st.write(item.summary)

            limitations = item.metadata.get("limitations", [])
            if limitations:
                st.caption("Limitations")
                for limitation in limitations:
                    st.write(f"• {limitation}")


def render_goal_card(goal, prediction):
    if goal is None:
        render_html(
            """
            <div class="pp-card pp-card-hero pp-card-accent">
                <div class="pp-card-label">Goal progress</div>
                <div class="pp-card-title">No active goal</div>
                <div class="pp-card-copy">
                    Open the Goal page to choose the objective that matters
                    most to this athlete.
                </div>
                <div style="margin-top:0.8rem;">
                    <span class="pp-status pp-status-warning">
                        Goal not configured
                    </span>
                </div>
            </div>
            """
        )
        return

    target_text = (
        format_clock(goal["target_time_s"])
        if goal["target_time_s"] is not None
        else "Completion goal"
    )

    if prediction.available:
        prediction_text = format_clock(prediction.predicted_seconds)
        prediction_context = evidence_strength(prediction.confidence)
    else:
        prediction_text = "Not available"
        prediction_context = prediction.explanation

    race_text = goal["race_name"] or "No race selected"

    render_html(
        f"""
        <div class="pp-card pp-card-hero pp-card-accent">
            <div class="pp-card-label">Goal progress</div>
            <div class="pp-card-title">{safe_text(goal["goal_name"])}</div>

            <div style="
                display:grid;
                grid-template-columns:1fr 1fr;
                gap:1rem;
                margin-top:0.9rem;
            ">
                <div>
                    <div class="pp-small-meta">Target</div>
                    <div class="pp-large-value" style="margin-top:0.2rem;">
                        {safe_text(target_text)}
                    </div>
                </div>

                <div>
                    <div class="pp-small-meta">Prediction</div>
                    <div class="pp-card-title">{safe_text(prediction_text)}</div>
                    <div class="pp-small-meta">
                        {safe_text(prediction_context)}
                    </div>
                </div>
            </div>

            <div style="
                margin-top:0.9rem;
                padding-top:0.8rem;
                border-top:1px solid var(--pp-border);
                display:flex;
                justify-content:space-between;
                align-items:center;
                gap:1rem;
            ">
                <div class="pp-small-meta">
                    {safe_text(race_text)} ·
                    {safe_text(format_goal_date(goal["target_date"]))}
                </div>
                <div class="pp-status">Active goal</div>
            </div>
        </div>
        """
    )


def render_coach_brief(current_baseline, all_time_baseline, brain_brief):
    if current_baseline and all_time_baseline:
        pace_change_per_mile = (
            all_time_baseline.avg_pace_seconds_per_km
            - current_baseline.avg_pace_seconds_per_km
        ) * (METRES_PER_MILE / 1000)

        if pace_change_per_mile >= 2:
            baseline_message = (
                f"Your current easy-running baseline is approximately "
                f"{pace_change_per_mile:.0f} sec/mi faster than your "
                f"all-time baseline."
            )
        else:
            baseline_message = (
                "Your recent easy running is broadly consistent with your "
                "long-term baseline."
            )
    else:
        baseline_message = (
            "More comparable easy runs will strengthen your aerobic baseline."
        )

    render_html(
        f"""
        <div class="pp-card pp-card-hero">
            <div class="pp-card-label">Coach's brief</div>
            <div class="pp-card-title">
                {safe_text(brain_brief.headline)}
            </div>
            <div class="pp-card-copy">
                {safe_text(brain_brief.summary)}
            </div>

            <div style="
                margin-top:0.95rem;
                padding-top:0.85rem;
                border-top:1px solid var(--pp-border);
            ">
                <div class="pp-card-label">Aerobic context</div>
                <div class="pp-small-meta">
                    {safe_text(baseline_message)}
                </div>
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


def render_evidence_card(item):
    status = status_label(item.status)
    strength = evidence_strength(item.confidence)
    prediction_text = (
        format_clock(item.predicted_seconds)
        if item.predicted_seconds is not None
        else "No direct prediction"
    )

    render_html(
        f"""
        <div class="pp-card">
            <div style="
                display:flex;
                justify-content:space-between;
                align-items:flex-start;
                gap:1rem;
            ">
                <div>
                    <div class="pp-card-label">Specialist coach</div>
                    <div class="pp-card-title">{safe_text(item.title)}</div>
                </div>
                <div class="pp-status">{safe_text(status)}</div>
            </div>

            <div class="pp-card-copy">{safe_text(item.summary)}</div>

            <div style="
                display:grid;
                grid-template-columns:repeat(3, minmax(0, 1fr));
                gap:0.8rem;
                margin-top:1rem;
                padding-top:0.9rem;
                border-top:1px solid var(--pp-border);
            ">
                <div>
                    <div class="pp-stat-label">Evidence strength</div>
                    <div class="pp-stat-value" style="font-size:1rem;">
                        {safe_text(strength)}
                    </div>
                </div>
                <div>
                    <div class="pp-stat-label">Confidence</div>
                    <div class="pp-stat-value" style="font-size:1rem;">
                        {item.confidence:.0%}
                    </div>
                </div>
                <div>
                    <div class="pp-stat-label">Goal estimate</div>
                    <div class="pp-stat-value" style="font-size:1rem;">
                        {safe_text(prediction_text)}
                    </div>
                </div>
            </div>
        </div>
        """
    )

    strengths = item.metadata.get("strengths", [])
    limitations = item.metadata.get("limitations", [])

    if strengths or limitations:
        with st.expander(f"Why does {item.title} believe this?"):
            if strengths:
                st.markdown("**Strengths**")
                for strength in strengths:
                    st.write(f"✓ {strength}")

            if limitations:
                st.markdown("**Limitations**")
                for limitation in limitations:
                    st.write(f"• {limitation}")

            latest_workout = item.metadata.get("latest_workout")
            best_evidence = item.metadata.get("best_evidence")
            top_workouts = item.metadata.get("top_workouts", [])

            if latest_workout and best_evidence:
                st.markdown("**Workout Coach evidence selection**")
                st.write(
                    f"Latest: {latest_workout.get('description', '—')} · "
                    f"{latest_workout.get('date', '—')} · "
                    f"trust {latest_workout.get('trust_score', 0):.0f}/100"
                )
                st.write(
                    f"Best current evidence: "
                    f"{best_evidence.get('description', '—')} · "
                    f"{best_evidence.get('date', '—')} · "
                    f"trust {best_evidence.get('trust_score', 0):.0f}/100"
                )

                warning = item.metadata.get("representative_warning")
                if warning:
                    st.warning(warning)

            historical_similarity = item.metadata.get(
                "historical_similarity"
            )
            if isinstance(historical_similarity, dict):
                st.markdown("**Historical workout matches**")

                match_count = historical_similarity.get(
                    "match_count",
                    0,
                )
                distinct_workouts = historical_similarity.get(
                    "distinct_workout_count",
                    0,
                )
                distinct_races = historical_similarity.get(
                    "distinct_race_count",
                    0,
                )
                similarity_confidence = historical_similarity.get(
                    "confidence",
                    0,
                )

                similarity_columns = st.columns(4)
                similarity_columns[0].metric(
                    "Strong matches",
                    match_count,
                )
                similarity_columns[1].metric(
                    "Workouts searched",
                    distinct_workouts,
                )
                similarity_columns[2].metric(
                    "Linked races",
                    distinct_races,
                )
                similarity_columns[3].metric(
                    "Match confidence",
                    f"{similarity_confidence:.0%}",
                )

                matches = historical_similarity.get("matches", [])

                if matches:
                    st.caption(
                        "These matches explain the athlete's historical "
                        "workout evidence."
                    )

                    for index, match in enumerate(
                        matches[:5],
                        start=1,
                    ):
                        race_distance = match.get(
                            "race_distance_km",
                            0,
                        )
                        st.write(
                            f"**{index}. "
                            f"{match.get('workout_date', '—')} · "
                            f"{match.get('similarity', 0):.0%} similar**"
                        )
                        st.write(
                            f"Race {match.get('days_after', 0)} days later: "
                            f"{race_distance:.2f} km in "
                            f"{format_clock(match.get('race_time_s'))} "
                            f"({match.get('race_date', '—')})"
                        )

                        reasons = match.get("reasons", [])
                        if reasons:
                            st.caption(
                                "Why it matched: "
                                + "; ".join(reasons)
                            )

                        differences = match.get("differences", [])
                        if differences:
                            st.caption(
                                "Main differences: "
                                + "; ".join(differences)
                            )
                else:
                    st.info(
                        "No sufficiently similar linked historical "
                        "workout was found yet."
                    )

                for limitation in historical_similarity.get(
                    "limitations",
                    [],
                ):
                    st.caption("Similarity note: " + limitation)

            best_workout_dna = item.metadata.get(
                "best_workout_dna"
            )
            latest_workout_dna = item.metadata.get(
                "latest_workout_dna"
            )

            if isinstance(best_workout_dna, dict):
                st.markdown("**Workout DNA**")

                dna_columns = st.columns(4)
                dna_columns[0].metric(
                    "Primary intent",
                    best_workout_dna.get(
                        "primary_label",
                        "Unknown",
                    ),
                )
                dna_columns[1].metric(
                    "Archetype",
                    best_workout_dna.get(
                        "archetype",
                        "Structured workout",
                    ),
                )
                dna_columns[2].metric(
                    "DNA confidence",
                    f"{best_workout_dna.get('confidence', 0):.0%}",
                )
                dna_columns[3].metric(
                    "Execution",
                    (
                        f"{best_workout_dna.get('execution_quality'):.0f}/100"
                        if best_workout_dna.get("execution_quality")
                        is not None
                        else "—"
                    ),
                )

                st.caption(
                    "Workout DNA describes the physiological purpose of the "
                    "best current evidence, rather than only its lap pattern."
                )

                stimulus_scores = best_workout_dna.get(
                    "stimulus_scores",
                    {},
                )

                labels = {
                    "threshold": "❤️ Threshold",
                    "speed": "⚡ Speed / VO₂",
                    "endurance": "🧱 Endurance",
                    "aerobic": "😊 Aerobic",
                }

                for system_key in (
                    "threshold",
                    "speed",
                    "endurance",
                    "aerobic",
                ):
                    score = float(
                        stimulus_scores.get(system_key, 0) or 0
                    )
                    st.write(
                        f"{labels[system_key]} — **{score:.0f}/100**"
                    )
                    st.progress(
                        min(max(score / 100.0, 0.0), 1.0)
                    )

                secondary = best_workout_dna.get(
                    "secondary_systems",
                    [],
                )
                if secondary:
                    st.caption(
                        "Secondary systems: "
                        + ", ".join(
                            system.replace("_", " ").title()
                            for system in secondary
                        )
                    )

                with st.expander("Why this Workout DNA?"):
                    reasons = best_workout_dna.get(
                        "reasons",
                        [],
                    )
                    limitations = best_workout_dna.get(
                        "limitations",
                        [],
                    )

                    if reasons:
                        st.markdown("**Evidence**")
                        for reason in reasons:
                            st.write(f"✓ {reason}")

                    if limitations:
                        st.markdown("**Limitations**")
                        for limitation in limitations:
                            st.write(f"• {limitation}")

                    if (
                        isinstance(latest_workout_dna, dict)
                        and latest_workout_dna.get("activity_id")
                        != best_workout_dna.get("activity_id")
                    ):
                        st.markdown("**Latest versus best evidence**")
                        st.write(
                            "Latest workout intent: "
                            f"{latest_workout_dna.get('primary_label', 'Unknown')}"
                        )
                        st.write(
                            "Best current evidence intent: "
                            f"{best_workout_dna.get('primary_label', 'Unknown')}"
                        )

            workout_prediction = item.metadata.get(
                "workout_prediction"
            )
            if workout_prediction:
                prediction_source = item.metadata.get(
                    "prediction_source",
                    "formula_fallback",
                )
                source_label = (
                    "PB Shape prediction"
                    if prediction_source == "pb_shape"
                    else "Historical similarity prediction"
                    if prediction_source == "historical_similarity"
                    else "Formula fallback prediction"
                )

                st.markdown(f"**{source_label}**")
                prediction_columns = st.columns(3)
                prediction_columns[0].metric(
                    "Central estimate",
                    format_clock(
                        workout_prediction.get("central_seconds")
                    ),
                )
                prediction_columns[1].metric(
                    "Likely range",
                    (
                        f"{format_clock(workout_prediction.get('low_seconds'))}"
                        f"–{format_clock(workout_prediction.get('high_seconds'))}"
                    ),
                )
                prediction_columns[2].metric(
                    "Prediction confidence",
                    f"{workout_prediction.get('confidence', 0):.0%}",
                )
                if prediction_source == "pb_shape":
                    st.caption(
                        "Compared with the athlete's recognised workouts "
                        "7-28 days before their PB at this goal distance."
                    )
                elif prediction_source == "historical_similarity":
                    st.caption(
                        "Ideal, flat conditions · based on "
                        f"{workout_prediction.get('distinct_race_count', 0)} "
                        "distinct historical race outcome(s) following similar "
                        "workouts. Recognition and prediction confidence remain "
                        "separate."
                    )
                else:
                    st.caption(
                        f"{workout_prediction.get('conditions', 'Ideal conditions')} · "
                        f"based on {workout_prediction.get('estimate_count', 0)} "
                        "representative workout estimate(s). Recognition confidence "
                        "and prediction confidence are deliberately separate."
                    )

                if prediction_source == "pb_shape":
                    st.markdown("**PB benchmark**")
                    pb_columns = st.columns(3)
                    pb_columns[0].metric(
                        "PB",
                        format_clock(
                            workout_prediction.get("pb_time_s")
                        ),
                    )
                    pb_columns[1].metric(
                        "PB date",
                        workout_prediction.get("pb_date", "—"),
                    )
                    shape_percent = workout_prediction.get(
                        "current_shape_percent"
                    )
                    pb_columns[2].metric(
                        "Current PB shape",
                        (
                            f"{shape_percent:.1f}%"
                            if shape_percent is not None
                            else "—"
                        ),
                    )

                    with st.expander(
                        "Workouts behind the PB Shape comparison"
                    ):
                        for match in workout_prediction.get(
                            "matches",
                            [],
                        ):
                            st.write(
                                f"**{match.get('date', '—')} · "
                                f"{match.get('similarity', 0):.0%} similar**"
                            )
                            st.write(
                                "PB-shape equivalent: "
                                f"{format_clock(match.get('estimated_seconds'))}"
                            )
                            reasons = match.get("reasons", [])
                            if reasons:
                                st.caption(
                                    "Why matched: " + "; ".join(reasons)
                                )
                            differences = match.get("differences", [])
                            if differences:
                                st.caption(
                                    "Differences: "
                                    + "; ".join(differences)
                                )

                        for limitation in workout_prediction.get(
                            "limitations",
                            [],
                        ):
                            st.caption("PB Shape note: " + limitation)

                elif prediction_source == "historical_similarity":
                    with st.expander(
                        "Historical outcomes behind this prediction"
                    ):
                        for outcome in workout_prediction.get(
                            "outcomes",
                            [],
                        ):
                            st.write(
                                f"**Workout {outcome.get('workout_date', '—')} · "
                                f"{outcome.get('similarity', 0):.0%} similar**"
                            )
                            st.write(
                                f"Race {outcome.get('days_after', 0)} days later: "
                                f"{outcome.get('race_distance_km', 0):.2f} km in "
                                f"{format_clock(outcome.get('race_time_s'))} · "
                                "goal-distance equivalent "
                                f"{format_clock(outcome.get('equivalent_goal_time_s'))}"
                            )
                            reasons = outcome.get("reasons", [])
                            if reasons:
                                st.caption(
                                    "Why matched: " + "; ".join(reasons)
                                )

                        for limitation in workout_prediction.get(
                            "limitations",
                            [],
                        ):
                            st.caption("Prediction note: " + limitation)
                else:
                    with st.expander(
                        "How each workout predicted the goal"
                    ):
                        for estimate in workout_prediction.get(
                            "estimates",
                            [],
                        ):
                            st.write(
                                f"**{estimate.get('date', '—')} · "
                                f"{estimate.get('description', '—')}**"
                            )
                            st.write(
                                f"Estimate: "
                                f"{format_clock(estimate.get('predicted_seconds'))} · "
                                f"prediction quality "
                                f"{estimate.get('quality', 0):.0%} · "
                                f"trust {estimate.get('trust_score', 0):.0f}/100"
                            )

                            component_summary = estimate.get(
                                "component_summary"
                            )
                            if component_summary:
                                st.caption(
                                    "Components: " + component_summary
                                )

                            for component in estimate.get(
                                "components",
                                [],
                            ):
                                pace_seconds = component.get(
                                    "average_pace_s_per_km"
                                )
                                pace_text = (
                                    format_pace_value(pace_seconds)
                                    if pace_seconds is not None
                                    else "—"
                                )
                                st.write(
                                    f"• {component.get('label', 'Component')}: "
                                    f"{component.get('rep_count', 0)} reps · "
                                    f"{component.get('average_rep_distance_km', 0):.2f} km "
                                    f"average · {pace_text} · component estimate "
                                    f"{format_clock(component.get('predicted_seconds'))}"
                                )

            phase_engine = item.metadata.get("workout_phases")
            if isinstance(phase_engine, dict):
                st.markdown("**Reconstructed workout phases**")
                st.caption(
                    f"Source: {phase_engine.get('source', 'unknown')} · "
                    f"confidence {phase_engine.get('confidence', 0):.0%}"
                )

                for phase in phase_engine.get("phases", []):
                    pace_text = format_pace_value(
                        phase.get("pace_s_per_km")
                    )
                    recovery = phase.get("recovery_duration_s")
                    recovery_text = (
                        f" · recovery {recovery:.0f}s"
                        if recovery is not None
                        else ""
                    )
                    st.write(
                        f"• **{phase.get('label', 'Phase')}** · "
                        f"{phase.get('rep_count', 1)} block(s) · "
                        f"{phase.get('distance_km', 0):.2f} km · "
                        f"{format_clock(phase.get('duration_s'))} · "
                        f"{pace_text}{recovery_text}"
                    )

                limitations = phase_engine.get("limitations", [])
                if limitations:
                    for limitation in limitations:
                        st.caption("Limitation: " + limitation)

            if top_workouts:
                st.markdown("**Strongest five recent workouts**")
                for workout_item in top_workouts:
                    execution = workout_item.get("execution_score")
                    execution_text = (
                        f" · execution {execution:.0f}/100"
                        if execution is not None
                        else ""
                    )
                    st.write(
                        f"{workout_item.get('rank', '—')}. "
                        f"{workout_item.get('date', '—')} · "
                        f"{workout_item.get('description', '—')} · "
                        f"trust {workout_item.get('trust_score', 0):.0f}/100"
                        f"{execution_text}"
                    )
                    reasons = workout_item.get("trust_reasons", [])
                    if reasons:
                        st.caption("Why trusted: " + "; ".join(reasons))

            workout_trend = item.metadata.get("trend")
            if isinstance(workout_trend, dict):
                st.markdown("**Comparable workout trend**")
                st.write(
                    f"{workout_trend.get('label', '—')} "
                    f"({str(workout_trend.get('confidence', 'Limited')).lower()} "
                    f"confidence; {workout_trend.get('sample_size', 0)} "
                    "comparable session(s))"
                )
                change = workout_trend.get("change_seconds_per_km")
                if change is not None:
                    direction = "faster" if change > 0 else "slower"
                    st.write(
                        f"Recent comparable rep pace is "
                        f"{abs(change):.1f} sec/km {direction}."
                    )

            workout_json = item.metadata.get("workout_json")
            if workout_json:
                st.markdown("**Workout structure**")
                st.write(
                    f"Type: {item.metadata.get('workout_type', '—')}"
                )

                execution = item.metadata.get("execution_score")
                if execution is not None:
                    st.write(f"Execution score: {execution:.0f}/100")

                variation = item.metadata.get(
                    "rep_pace_variation_percent"
                )
                if variation is not None:
                    st.write(
                        f"Rep pace variation: {variation:.1f}%"
                    )

                work_splits = workout_json.get("work_splits", [])
                if work_splits:
                    st.markdown("**Work reps**")
                    for rep in work_splits:
                        st.write(
                            f"Rep {rep.get('index', '—')}: "
                            f"{rep.get('distance_km', 0):.3f} km · "
                            f"{rep.get('duration', '—')} · "
                            f"{rep.get('pace', '—')}"
                        )

                recoveries = workout_json.get("recovery_splits", [])
                if recoveries:
                    st.markdown("**Recoveries**")
                    for recovery in recoveries:
                        st.write(
                            f"{recovery.get('distance_km', 0):.3f} km · "
                            f"{recovery.get('duration', '—')}"
                        )

            trend = item.metadata.get("trend")
            if trend:
                recent_pace = item.metadata.get(
                    "recent_adjusted_pace_seconds_per_km"
                )
                previous_pace = item.metadata.get(
                    "previous_adjusted_pace_seconds_per_km"
                )
                change = item.metadata.get("change_seconds_per_km")
                trend_confidence = item.metadata.get(
                    "trend_confidence",
                    "Limited",
                )

                st.markdown("**Trend comparison**")
                st.write(
                    f"Conclusion: {trend} "
                    f"({trend_confidence.lower()} confidence)"
                )

                if recent_pace is not None:
                    st.write(
                        "Recent adjusted threshold pace: "
                        f"{seconds_to_pace(recent_pace)}/km "
                        f"from {item.metadata.get('recent_session_count', 0)} "
                        "session(s)"
                    )

                if previous_pace is not None:
                    st.write(
                        "Earlier adjusted threshold pace: "
                        f"{seconds_to_pace(previous_pace)}/km "
                        f"from {item.metadata.get('previous_session_count', 0)} "
                        "session(s)"
                    )

                if change is not None:
                    direction = "faster" if change > 0 else "slower"
                    st.write(
                        f"Difference: {abs(change):.1f} sec/km {direction}"
                    )

                recommendation = item.metadata.get("recommendation")
                if recommendation:
                    st.write(f"Recommendation: {recommendation}")

            candidates = item.metadata.get("candidate_debug", [])
            if candidates:
                st.markdown("**Top sessions considered**")
                for index, candidate in enumerate(candidates, start=1):
                    moving_ratio = candidate.get("moving_ratio")
                    moving_text = (
                        f"{moving_ratio:.1%}"
                        if moving_ratio is not None
                        else "—"
                    )
                    pace_text = (
                        candidate.get("equivalent_pace")
                        or candidate.get("elapsed")
                        or "—"
                    )
                    workout = candidate.get("workout") or {}
                    workout_text = workout.get("description")
                    st.write(
                        f"{index}. {candidate.get('date', '—')} · "
                        f"{candidate.get('title', 'Untitled')} · "
                        f"{candidate.get('distance_km', 0):.2f} km · "
                        f"{pace_text} · moving {moving_text} · "
                        f"score {candidate.get('score', 0):.1f}"
                    )
                    if workout_text:
                        st.caption(
                            f"Workout decoder: {workout_text} "
                            f"({workout.get('confidence', 0):.0%} confidence)"
                        )


def render_placeholder_coach(title, description):
    render_html(
        f"""
        <div class="pp-card">
            <div class="pp-card-label">Specialist coach</div>
            <div class="pp-card-title">{safe_text(title)}</div>
            <div class="pp-card-copy">{safe_text(description)}</div>
            <div style="margin-top:0.8rem;">
                <span class="pp-status pp-status-warning">Coming soon</span>
            </div>
        </div>
        """
    )


def render_coach_evidence_panel(evidence_bundle):
    specialist_items = [
        item
        for item in evidence_bundle.items
        if item.key != "activity_history"
    ]
    history_items = [
        item
        for item in evidence_bundle.items
        if item.key == "activity_history"
    ]

    render_html(
        f"""
        <div class="pp-card pp-card-hero">
            <div class="pp-card-label">Your Coaching Team</div>
            <div class="pp-card-title">
                {len(specialist_items)} specialist coach(es) have reported
            </div>
            <div class="pp-card-copy">
                Overall evidence strength is
                <strong>
                    {safe_text(evidence_strength(evidence_bundle.confidence))}
                </strong>
                from
                <strong>{evidence_bundle.total_sample_size:,}</strong>
                observations.
            </div>
            <div style="margin-top:0.8rem;">
                <span class="pp-status">
                    {evidence_bundle.confidence:.0%} evidence confidence
                </span>
            </div>
        </div>
        """
    )

    cards = [*specialist_items, *history_items]

    for index in range(0, len(cards), 2):
        left, right = st.columns(2, gap="medium")

        with left:
            render_evidence_card(cards[index])

        if index + 1 < len(cards):
            with right:
                render_evidence_card(cards[index + 1])

    placeholder_left, placeholder_right = st.columns(2, gap="medium")

    with placeholder_left:
        render_placeholder_coach(
            "Easy Run Coach",
            "Will interpret aerobic efficiency and best easy-run evidence.",
        )

    with placeholder_right:
        render_placeholder_coach(
            "Environment Coach",
            "Will specialise in heat, humidity, terrain, wind and surface.",
        )



def render_recent_activities(run_profiles):
    rows = []

    for run in run_profiles[:5]:
        sport_name, fallback_title = get_sport_name(run.sport_id)
        performance = equivalent_performance(run)

        pace = (
            format_pace_per_mile(performance.actual_pace_seconds_per_km)
            if performance is not None
            else "--"
        )

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
                    <span class="pp-status">Analysed</span>
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
            <div class="pp-card-label">Training history</div>
            <div class="pp-card-title">Recent activities</div>
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

    athlete_names = list(athlete_options.keys())
    initialise_selected_athlete(athlete_names)

    selector_col, _ = st.columns([0.35, 0.65])

    with selector_col:
        st.selectbox(
            "Athlete",
            athlete_names,
            key="athlete_selector_widget",
            on_change=update_selected_athlete,
            label_visibility="collapsed",
        )

    selected_name = st.session_state.selected_athlete_name
    selected = athlete_options[selected_name]
    athlete_id = selected["id"]

    brain = CoachBrain(athlete_id)
    goal = get_active_goal(athlete_id)
    evidence_bundle = brain.build_evidence()
    prediction = brain.goal_prediction()
    brain_brief = brain.morning_brief()
    performance_dna = build_performance_dna(
        evidence_bundle,
        consensus_prediction_s=(
            prediction.predicted_seconds
            if prediction.available
            else None
        ),
    )

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

    render_header(selected["first_name"], goal)

    recent_weekly_distance_km, latest_activity_date = (
        get_recent_weekly_average(athlete_id, weeks=26)
    )

    render_daily_coach(
        first_name=selected["first_name"],
        goal=goal,
        prediction=prediction,
        brain_brief=brain_brief,
        evidence_bundle=evidence_bundle,
        latest_activity_date=latest_activity_date,
    )

    st.markdown("## Coaching team")
    render_coaching_meeting(
        performance_dna,
        prediction,
    )

    st.markdown("## Goal and context")

    top_left, top_right = st.columns([1.05, 0.95], gap="medium")

    with top_left:
        render_goal_card(goal, prediction)

    with top_right:
        render_coach_brief(
            current_baseline,
            all_time_baseline,
            brain_brief,
        )

    st.markdown("## This year")
    current_year = datetime.date.today().year

    (
        year_activities,
        _year_distance_km,
        year_moving_time_s,
        _,
    ) = get_year_summary(athlete_id, current_year)

    recent_weekly_distance_miles = recent_weekly_distance_km / (
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
        latest_context = (
            f"26 weeks ending {latest_activity_date.strftime('%d %b %Y')}"
            if latest_activity_date is not None
            else "No activity date available"
        )
        render_stat_card(
            "Average week",
            f"{recent_weekly_distance_miles:.1f} mi",
            latest_context,
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

    st.markdown("## Coach evidence")
    render_coach_evidence_panel(evidence_bundle)

    st.markdown("## Latest training")
    render_recent_activities(run_profiles)
