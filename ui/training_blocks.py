import datetime
import html
import textwrap

import streamlit as st

from core.training_blocks import (
    BLOCK_FOCUSES,
    BLOCK_PHASES,
    BLOCK_STATUSES,
    BLOCK_TYPES,
    assign_goal_to_block,
    block_progress,
    get_active_training_block,
    list_goals_for_block,
    list_training_blocks,
    list_unassigned_goals,
    save_training_block,
    set_active_training_block,
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


def _render_active_block(block):
    progress = block_progress(block)

    if progress.week_number is not None and progress.total_weeks is not None:
        week_label = (
            f"Week {progress.week_number} of {progress.total_weeks}"
            if progress.week_number > 0
            else f"Starts soon · {progress.total_weeks} week block"
        )
    else:
        week_label = "Block dates not fully configured"

    _html(
        f"""
        <div class="pp-card pp-card-accent">
            <div class="pp-card-label">Current Training Block</div>
            <div class="pp-card-title">{_safe(block.name)}</div>
            <div class="pp-card-copy">
                {_safe(block.purpose or "Purpose not yet added.")}
            </div>
            <div style="margin-top:0.7rem;">
                <span class="pp-status">{_safe(week_label)}</span>
                <span class="pp-status">{_safe(block.current_phase or "Phase not set")}</span>
                <span class="pp-status">{_safe(block.primary_focus or "Balanced")}</span>
            </div>
        </div>
        """
    )

    metrics = st.columns(4)
    metrics[0].metric("Block type", block.block_type)
    metrics[1].metric("Phase", block.current_phase or "Not set")
    metrics[2].metric("Primary focus", block.primary_focus or "Balanced")
    metrics[3].metric(
        "Days remaining",
        (
            str(progress.days_remaining)
            if progress.days_remaining is not None
            else "—"
        ),
    )

    if progress.progress_fraction is not None:
        st.progress(progress.progress_fraction)

    st.caption(
        f"{_date_text(block.start_date)} → {_date_text(block.end_date)}"
    )


def _render_block_goals(athlete_id, block):
    st.markdown("### 🎯 Goals in this block")

    goals = list_goals_for_block(
        athlete_id,
        block.id,
    )

    if goals:
        columns = st.columns(min(len(goals), 3))

        for column, goal in zip(columns, goals):
            with column:
                st.markdown(
                    f"**{'⭐ ' if goal.priority == 'Primary' else ''}"
                    f"{goal.goal_name}**"
                )

                if goal.target_time_s:
                    st.metric(
                        "Target",
                        _time_text(goal.target_time_s),
                    )

                detail = []

                if goal.race_name:
                    detail.append(goal.race_name)

                if goal.target_date:
                    detail.append(_date_text(goal.target_date))

                if detail:
                    st.caption(" · ".join(detail))

                st.caption(
                    f"{goal.priority} · {goal.status}"
                )
    else:
        st.info(
            "No goals are attached to this Training Block yet."
        )

    unassigned = list_unassigned_goals(athlete_id)

    if unassigned:
        with st.expander("Attach an existing goal"):
            options = {
                f"{goal.goal_name} · {goal.priority}": goal
                for goal in unassigned
            }
            selected = st.selectbox(
                "Existing goal",
                list(options.keys()),
                key=f"attach_goal_{block.id}",
            )

            if st.button(
                "Attach goal to this block",
                key=f"attach_goal_button_{block.id}",
            ):
                goal = options[selected]
                assign_goal_to_block(
                    athlete_id=athlete_id,
                    goal_id=goal.id,
                    block_id=block.id,
                )
                st.success("Goal attached to Training Block.")
                st.rerun()


def _render_block_history(athlete_id, active_block_id):
    blocks = list_training_blocks(athlete_id)

    historical = [
        block
        for block in blocks
        if block.id != active_block_id
    ]

    if not historical:
        return

    st.markdown("### 🗓️ Block Timeline")

    for block in historical:
        progress = block_progress(block)

        _html(
            f"""
            <div class="pp-card" style="margin-top:0.6rem;">
                <div class="pp-card-label">{_safe(block.status)}</div>
                <div class="pp-card-title">{_safe(block.name)}</div>
                <div class="pp-card-copy">
                    {_safe(block.block_type)} ·
                    {_safe(block.current_phase or "Phase not set")} ·
                    {_safe(block.primary_focus or "Balanced")}
                </div>
                <div class="pp-card-copy">
                    {_safe(_date_text(block.start_date))} →
                    {_safe(_date_text(block.end_date))}
                </div>
            </div>
            """
        )

        if block.status == "Planned":
            if st.button(
                f"Make {block.name} active",
                key=f"activate_block_{block.id}",
            ):
                set_active_training_block(
                    athlete_id,
                    block.id,
                )
                st.success("Training Block activated.")
                st.rerun()


def _new_block_form(athlete_id):
    st.markdown("### ➕ Create a Training Block")

    today = datetime.date.today()
    default_end = today + datetime.timedelta(weeks=12)

    with st.form("new_training_block"):
        name = st.text_input(
            "Block name",
            placeholder="Autumn 10K Block",
        )

        columns = st.columns(2)

        with columns[0]:
            block_type = st.selectbox(
                "Block type",
                BLOCK_TYPES,
                index=2,
            )
            start_date = st.date_input(
                "Start date",
                value=today,
            )
            primary_focus = st.selectbox(
                "Primary focus",
                BLOCK_FOCUSES,
                index=1,
            )

        with columns[1]:
            status = st.selectbox(
                "Status",
                BLOCK_STATUSES,
                index=1,
            )
            end_date = st.date_input(
                "End date",
                value=default_end,
            )
            phase = st.selectbox(
                "Current phase",
                BLOCK_PHASES,
                index=1,
            )

        purpose = st.text_area(
            "Purpose",
            placeholder=(
                "Build threshold pace while maintaining aerobic strength."
            ),
        )

        notes = st.text_area(
            "Notes",
            placeholder="Anything you or your coach want to remember.",
        )

        submitted = st.form_submit_button(
            "Create Training Block"
        )

    if submitted:
        if not name.strip():
            st.error("Please give the Training Block a name.")
            return

        if end_date < start_date:
            st.error("End date must be after the start date.")
            return

        block_id = save_training_block(
            athlete_id=athlete_id,
            name=name.strip(),
            block_type=block_type,
            purpose=purpose.strip() or None,
            start_date=str(start_date),
            end_date=str(end_date),
            status=status,
            primary_focus=primary_focus,
            current_phase=phase,
            notes=notes.strip() or None,
        )

        st.success(
            f"Training Block created (#{block_id})."
        )
        st.rerun()


def show_training_blocks_page():
    st.title("📅 Training Blocks")
    st.write(
        "Organise your running around purposeful periods of training rather "
        "than isolated activities."
    )

    athlete_id = render_athlete_selector(
        key="training_blocks_athlete_selector",
        label="Athlete",
    )

    if athlete_id is None:
        st.info("Add an athlete before creating a Training Block.")
        return

    active = get_active_training_block(athlete_id)

    if active is None:
        _html(
            """
            <div class="pp-card pp-card-accent">
                <div class="pp-card-label">Training Blocks</div>
                <div class="pp-card-title">
                    Your next chapter starts here
                </div>
                <div class="pp-card-copy">
                    Create a block around the period of training you are in
                    now—Base, 5K, 10K, Half Marathon, Recovery or something
                    more personal.
                </div>
            </div>
            """
        )

        _new_block_form(athlete_id)
        _render_block_history(athlete_id, active_block_id=-1)
        return

    _render_active_block(active)
    _render_block_goals(athlete_id, active)

    st.markdown("### 🧠 Coaching context")
    _html(
        f"""
        <div class="pp-card">
            <div class="pp-card-label">Block focus</div>
            <div class="pp-card-title">
                {_safe(active.primary_focus or "Balanced")} development
            </div>
            <div class="pp-card-copy">
                The Decision Engine, Recommended Next Run and Dynamic Plan will
                use this Training Block as context in the next releases.
            </div>
        </div>
        """
    )

    _render_block_history(
        athlete_id,
        active_block_id=active.id,
    )

    with st.expander("Create another Training Block"):
        _new_block_form(athlete_id)
