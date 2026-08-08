import datetime
import html
import textwrap

import streamlit as st

from core.database import get_connection, save_goal
from core.training_blocks import (
    BLOCK_FOCUSES,
    BLOCK_PHASES,
    BLOCK_TYPES,
    get_active_training_block,
    save_training_block,
)
from ui.athlete_selection import render_athlete_selector


def _safe(value):
    return html.escape(str(value or ""))


def _html(markup):
    st.html(textwrap.dedent(markup).strip())


def _date_text(value):
    if not value:
        return "Not set"

    try:
        parsed = datetime.date.fromisoformat(str(value)[:10])
        return parsed.strftime("%-d %b %Y")
    except (TypeError, ValueError):
        return str(value)


def _time_text(seconds):
    if seconds is None:
        return "—"

    total = int(round(seconds))
    hours = total // 3600
    minutes = (total % 3600) // 60
    remaining = total % 60

    if hours:
        return f"{hours}:{minutes:02d}:{remaining:02d}"

    return f"{minutes}:{remaining:02d}"


def _load_goals(athlete_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            id,
            athlete_id,
            training_block_id,
            goal_name,
            goal_type,
            distance_m,
            target_time_s,
            target_date,
            race_name,
            priority,
            status,
            motivation
        FROM goals
        WHERE athlete_id = ?
        ORDER BY
            CASE priority
                WHEN 'Primary' THEN 0
                WHEN 'Secondary' THEN 1
                ELSE 2
            END,
            CASE status
                WHEN 'Active' THEN 0
                WHEN 'Planned' THEN 1
                ELSE 2
            END,
            target_date,
            id
        """,
        (athlete_id,),
    )
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": row[0],
            "athlete_id": row[1],
            "training_block_id": row[2],
            "goal_name": row[3],
            "goal_type": row[4],
            "distance_m": row[5],
            "target_time_s": row[6],
            "target_date": row[7],
            "race_name": row[8],
            "priority": row[9],
            "status": row[10],
            "motivation": row[11],
        }
        for row in rows
    ]


def _goal_distance_label(goal):
    distance_m = goal.get("distance_m")

    if distance_m:
        if abs(distance_m - 5000) < 200:
            return "5K"
        if abs(distance_m - 10000) < 300:
            return "10K"
        if abs(distance_m - 21097.5) < 500:
            return "Half Marathon"
        if abs(distance_m - 42195) < 800:
            return "Marathon"

    goal_type = str(goal.get("goal_type") or "").lower()

    if "half" in goal_type:
        return "Half Marathon"
    if "marathon" in goal_type:
        return "Marathon"
    if "10k" in goal_type:
        return "10K"
    if "5k" in goal_type:
        return "5K"

    return "General"


def recommend_training_block(goal, today=None):
    """
    Recommend a sensible block structure from the goal.

    This is deliberately transparent and deterministic. It is the first step
    toward a future Decision-Engine recommendation that also uses readiness,
    strengths, limiters and current training history.
    """
    today = today or datetime.date.today()
    distance_label = _goal_distance_label(goal)

    target_date = None
    if goal.get("target_date"):
        try:
            target_date = datetime.date.fromisoformat(
                str(goal["target_date"])[:10]
            )
        except (TypeError, ValueError):
            target_date = None

    if target_date is not None:
        days = max((target_date - today).days, 14)
        weeks = max(2, min(round(days / 7), 20))
        end_date = target_date
    else:
        weeks = {
            "5K": 10,
            "10K": 12,
            "Half Marathon": 14,
            "Marathon": 16,
        }.get(distance_label, 12)
        end_date = today + datetime.timedelta(weeks=weeks)

    if distance_label == "5K":
        block_type = "5K"
        focus = "Speed / VO₂"
        phase = "Build"
        purpose = (
            "Improve speed and VO₂ while preserving aerobic strength and "
            "threshold support."
        )
    elif distance_label == "10K":
        block_type = "10K"
        focus = "Threshold"
        phase = "Build"
        purpose = (
            "Develop threshold and 10K-specific strength while maintaining "
            "aerobic durability and enough speed reserve."
        )
    elif distance_label == "Half Marathon":
        block_type = "Half Marathon"
        focus = "Endurance"
        phase = "Build"
        purpose = (
            "Build endurance and threshold durability so goal pace becomes "
            "sustainable for the full half-marathon distance."
        )
    elif distance_label == "Marathon":
        block_type = "Marathon"
        focus = "Endurance"
        phase = "Base"
        purpose = (
            "Build endurance, durability and marathon-specific volume while "
            "protecting recovery."
        )
    else:
        block_type = "General"
        focus = "Balanced"
        phase = "Build"
        purpose = (
            "Build the fitness qualities most relevant to the selected goal "
            "while maintaining overall running consistency."
        )

    return {
        "name": f"{distance_label} Training Block",
        "block_type": block_type,
        "focus": focus,
        "phase": phase,
        "purpose": purpose,
        "start_date": today,
        "end_date": end_date,
        "weeks": weeks,
    }


def _render_goal(goal, athlete_id):
    primary = goal["priority"] == "Primary"
    title = f"{'⭐ ' if primary else ''}{goal['goal_name']}"

    _html(
        f"""
        <div class="pp-card" style="margin-top:0.7rem;">
            <div class="pp-card-label">
                {_safe(goal['priority'])} goal · {_safe(goal['status'])}
            </div>
            <div class="pp-card-title">{_safe(title)}</div>
            <div class="pp-card-copy">
                {_safe(goal.get('race_name') or goal.get('goal_type') or 'Goal')}
                {' · ' + _safe(_date_text(goal.get('target_date'))) if goal.get('target_date') else ''}
            </div>
        </div>
        """
    )

    metrics = st.columns(3)
    metrics[0].metric(
        "Target",
        _time_text(goal["target_time_s"])
        if goal["target_time_s"]
        else "Outcome goal",
    )
    metrics[1].metric(
        "Distance",
        _goal_distance_label(goal),
    )
    metrics[2].metric(
        "Training Block",
        "Attached" if goal["training_block_id"] else "Not yet",
    )

    recommendation = recommend_training_block(goal)

    if not goal["training_block_id"]:
        st.markdown("#### 📅 PP Recommended Training Block")

        _html(
            f"""
            <div class="pp-card pp-card-accent">
                <div class="pp-card-label">Recommended from this goal</div>
                <div class="pp-card-title">{_safe(recommendation['name'])}</div>
                <div class="pp-card-copy">
                    {_safe(recommendation['purpose'])}
                </div>
                <div style="margin-top:0.7rem;">
                    <span class="pp-status">{_safe(recommendation['weeks'])} weeks</span>
                    <span class="pp-status">{_safe(recommendation['phase'])}</span>
                    <span class="pp-status">{_safe(recommendation['focus'])}</span>
                </div>
            </div>
            """
        )

        st.caption(
            f"Suggested dates: {_date_text(recommendation['start_date'])} → "
            f"{_date_text(recommendation['end_date'])}. "
            "This first recommendation uses the goal distance and target date; "
            "future versions will also use Decision Engine evidence."
        )

        if st.button(
            "Create this Training Block",
            key=f"create_recommended_block_{goal['id']}",
        ):
            block_id = save_training_block(
                athlete_id=athlete_id,
                name=recommendation["name"],
                block_type=recommendation["block_type"],
                purpose=recommendation["purpose"],
                start_date=str(recommendation["start_date"]),
                end_date=str(recommendation["end_date"]),
                status="Active",
                primary_focus=recommendation["focus"],
                current_phase=recommendation["phase"],
                notes=(
                    f"Created from goal: {goal['goal_name']}"
                ),
            )

            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE goals
                SET training_block_id = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND athlete_id = ?
                """,
                (block_id, goal["id"], athlete_id),
            )
            conn.commit()
            conn.close()

            st.success("Recommended Training Block created and linked.")
            st.rerun()


def _new_goal_form(athlete_id):
    with st.expander("➕ Add a goal"):
        with st.form("new_goal_form"):
            goal_name = st.text_input(
                "Goal name",
                placeholder="Sub 39 10K",
            )

            cols = st.columns(2)

            with cols[0]:
                goal_type = st.selectbox(
                    "Goal type",
                    [
                        "5K",
                        "10K",
                        "Half Marathon",
                        "Marathon",
                        "Race",
                        "Performance",
                        "Other",
                    ],
                )
                priority = st.selectbox(
                    "Priority",
                    ["Primary", "Secondary", "Future"],
                )
                target_date = st.date_input(
                    "Target date",
                    value=datetime.date.today()
                    + datetime.timedelta(weeks=12),
                )

            with cols[1]:
                race_name = st.text_input(
                    "Race/event",
                    placeholder="Optional",
                )
                target_time_text = st.text_input(
                    "Target time (HH:MM:SS or MM:SS)",
                    placeholder="39:00",
                )
                status = st.selectbox(
                    "Status",
                    ["Active", "Planned"],
                )

            motivation = st.text_area(
                "Why this matters",
                placeholder="Optional motivation or context.",
            )

            submitted = st.form_submit_button("Save goal")

        if submitted:
            if not goal_name.strip():
                st.error("Please give the goal a name.")
                return

            target_seconds = None
            text = target_time_text.strip()

            if text:
                try:
                    parts = [int(part) for part in text.split(":")]
                    if len(parts) == 2:
                        target_seconds = parts[0] * 60 + parts[1]
                    elif len(parts) == 3:
                        target_seconds = (
                            parts[0] * 3600
                            + parts[1] * 60
                            + parts[2]
                        )
                    else:
                        raise ValueError
                except ValueError:
                    st.error(
                        "Use MM:SS or HH:MM:SS for target time."
                    )
                    return

            distance_m = {
                "5K": 5000.0,
                "10K": 10000.0,
                "Half Marathon": 21097.5,
                "Marathon": 42195.0,
            }.get(goal_type)

            save_goal(
                athlete_id=athlete_id,
                goal_name=goal_name.strip(),
                goal_type=goal_type,
                distance_m=distance_m,
                target_time_s=target_seconds,
                target_date=str(target_date),
                race_name=race_name.strip() or None,
                priority=priority,
                status=status,
                motivation=motivation.strip() or None,
            )

            st.success("Goal saved.")
            st.rerun()


def show_goals_page():
    st.title("🎯 Goals")
    st.write(
        "Goals define the outcome. Performance Passport can then recommend "
        "the Training Block most likely to move you toward it."
    )

    athlete_id = render_athlete_selector(
        key="goals_athlete_selector",
        label="Athlete",
    )

    if athlete_id is None:
        st.info("Add an athlete before creating goals.")
        return

    goals = _load_goals(athlete_id)
    active_block = get_active_training_block(athlete_id)

    if active_block:
        st.caption(
            f"Current Training Block: {active_block.name}"
        )

    if not goals:
        _html(
            """
            <div class="pp-card pp-card-accent">
                <div class="pp-card-label">Goals</div>
                <div class="pp-card-title">
                    Start with the outcome
                </div>
                <div class="pp-card-copy">
                    Set the thing you want to achieve. Performance Passport
                    can then recommend the shape of the Training Block behind it.
                </div>
            </div>
            """
        )
        _new_goal_form(athlete_id)
        return

    for goal in goals:
        _render_goal(goal, athlete_id)

    _new_goal_form(athlete_id)
