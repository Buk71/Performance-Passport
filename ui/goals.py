"""Production Goal Centre with explicit multi-goal hierarchy."""

from __future__ import annotations

import datetime
import html

import streamlit as st

from core.database import save_goal
from core.goals import (
    GOAL_ROLES,
    GoalHierarchy,
    GoalHierarchyItem,
    build_goal_hierarchy,
    remove_goal,
    restore_goal_as_future,
    set_goal_role,
    set_goal_status,
    set_primary_goal,
)
from core.training_blocks import (
    assign_goal_to_block,
    get_active_training_block,
)
from ui.athlete_selection import render_athlete_id_selector


DISTANCE_METRES = {
    "5K": 5000.0,
    "5 miles": 8046.72,
    "10K": 10000.0,
    "10 miles": 16093.44,
    "Half Marathon": 21097.5,
    "Marathon": 42195.0,
}


def _safe(value) -> str:
    return html.escape(str(value or ""))


def _date(value: str | None) -> datetime.date | None:
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _date_text(value: str | datetime.date | None) -> str:
    parsed = value if isinstance(value, datetime.date) else _date(value)
    return parsed.strftime("%-d %b %Y") if parsed else "Date not set"


def _time_text(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    total = int(round(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, remaining = divmod(remainder, 60)
    return (
        f"{hours}:{minutes:02d}:{remaining:02d}"
        if hours
        else f"{minutes}:{remaining:02d}"
    )


def _parse_target_time(value: str) -> tuple[float | None, bool]:
    text = value.strip()
    if not text:
        return None, True
    try:
        parts = [int(part) for part in text.split(":")]
    except ValueError:
        return None, False
    if len(parts) == 2:
        minutes, seconds = parts
        if minutes < 0 or not 0 <= seconds < 60:
            return None, False
        return float(minutes * 60 + seconds), True
    if len(parts) == 3:
        hours, minutes, seconds = parts
        if hours < 0 or not 0 <= minutes < 60 or not 0 <= seconds < 60:
            return None, False
        return float(hours * 3600 + minutes * 60 + seconds), True
    return None, False


def _distance_label(distance_m: float | None, goal_type: str = "") -> str:
    if distance_m:
        for label, known_distance in DISTANCE_METRES.items():
            tolerance = max(150.0, known_distance * 0.02)
            if abs(float(distance_m) - known_distance) <= tolerance:
                return label
        return f"{float(distance_m) / 1000.0:g} km"
    return goal_type or "Outcome"


def build_goal_hierarchy_html(hierarchy: GoalHierarchy) -> str:
    primary_count = 1 if hierarchy.primary else 0
    block = hierarchy.active_block_name or "No active block"
    return f"""
    <main class="goal-centre-shell">
        <section class="goal-centre-hero">
            <div>
                <div class="goal-eyebrow">GOAL HIERARCHY</div>
                <h1>{_safe(hierarchy.headline)}</h1>
                <p>{_safe(hierarchy.summary)}</p>
            </div>
            <div class="goal-block-context">
                <span>CURRENT TRAINING BLOCK</span>
                <strong>{_safe(block)}</strong>
                <small>Block design is handled separately from goal priority.</small>
            </div>
        </section>
        <section class="goal-role-grid">
            <article class="goal-role is-primary">
                <span>PRIMARY</span><strong>{primary_count}</strong>
                <p>Drives Home, Next Run and block direction.</p>
            </article>
            <article class="goal-role is-secondary">
                <span>SECONDARY</span><strong>{len(hierarchy.secondary)}</strong>
                <p>Tune-ups and benchmarks that support the journey.</p>
            </article>
            <article class="goal-role is-future">
                <span>FUTURE</span><strong>{len(hierarchy.future)}</strong>
                <p>Saved for later with no current coaching effect.</p>
            </article>
        </section>
    </main>
    <style>
        .goal-centre-shell {{ display:grid; gap:10px; color:#10263d; container-type:inline-size; margin-top:4px; }} .goal-centre-shell * {{ box-sizing:border-box; }}
        .goal-centre-hero,.goal-role-grid {{ background:#fff; border:1px solid #e5ddd2; border-radius:18px; box-shadow:0 8px 24px rgba(16,38,61,.045); }}
        .goal-centre-hero {{ display:grid; grid-template-columns:minmax(0,1fr) 250px; gap:24px; align-items:center; padding:22px 24px; }}
        .goal-eyebrow {{ color:#778594; font-size:10px; line-height:1.25; font-weight:800; letter-spacing:.13em; }}
        .goal-centre-hero h1 {{ color:#10263d!important; font-size:clamp(27px,3vw,40px); line-height:1.02; letter-spacing:-.04em; margin:6px 0 8px; }}
        .goal-centre-hero p {{ color:#647180; font-size:12px; line-height:1.45; margin:0; }}
        .goal-block-context {{ border:1px solid #d8e9df; background:#eef8f2; border-radius:13px; padding:15px; display:flex; flex-direction:column; gap:4px; }}
        .goal-block-context span {{ color:#71808d; font-size:9px; font-weight:800; letter-spacing:.1em; }} .goal-block-context strong {{ color:#238a52; font-size:18px; }} .goal-block-context small {{ color:#71808d; font-size:9px; line-height:1.35; }}
        .goal-role-grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:0; overflow:hidden; }} .goal-role {{ padding:16px 18px; border-right:1px solid #e5ddd2; }} .goal-role:last-child {{ border-right:0; }}
        .goal-role span {{ color:#778594; font-size:9px; font-weight:800; letter-spacing:.12em; }} .goal-role strong {{ display:block; font-size:26px; line-height:1; margin:7px 0; }} .goal-role p {{ color:#697683; font-size:9px; margin:0; }}
        .goal-role.is-primary {{ border-top:3px solid #238a52; }} .goal-role.is-secondary {{ border-top:3px solid #f05a28; }} .goal-role.is-future {{ border-top:3px solid #aab3bb; }}
        @container (max-width:720px) {{ .goal-centre-hero {{ grid-template-columns:1fr; }} .goal-role-grid {{ grid-template-columns:1fr; }} .goal-role {{ border-right:0; border-bottom:1px solid #e5ddd2; }} }}
    </style>
    """


def _goal_card_html(goal: GoalHierarchyItem) -> str:
    role_class = goal.role.lower()
    target = _time_text(goal.target_time_s) if goal.target_time_s is not None else "Outcome goal"
    event = goal.race_name or goal.goal_type
    return f"""
    <article class="goal-detail-card is-{role_class}">
        <div class="goal-detail-top"><div>
            <div class="goal-detail-label">{_safe(goal.role.upper())} · {_safe(goal.status.upper())}</div>
            <h2>{_safe(goal.name)}</h2><p>{_safe(event)}</p>
        </div><span class="goal-timing">{_safe(goal.timing_label)}</span></div>
        <div class="goal-detail-metrics">
            <div><small>TARGET</small><strong>{_safe(target)}</strong></div>
            <div><small>DISTANCE</small><strong>{_safe(_distance_label(goal.distance_m, goal.goal_type))}</strong></div>
            <div><small>DATE</small><strong>{_safe(_date_text(goal.target_date))}</strong></div>
        </div>
        <div class="goal-influence"><div><small>COACHING INFLUENCE</small><strong>{_safe(goal.influence_title)}</strong><p>{_safe(goal.influence_summary)}</p></div><span>{_safe(goal.block_relationship)}</span></div>
    </article>
    <style>
        .goal-detail-card {{ background:#fff; border:1px solid #e5ddd2; border-left:4px solid #aab3bb; border-radius:16px; box-shadow:0 7px 22px rgba(16,38,61,.04); padding:18px 20px; margin:7px 0 9px; color:#10263d; container-type:inline-size; }}
        .goal-detail-card.is-primary {{ border-left-color:#238a52; }} .goal-detail-card.is-secondary {{ border-left-color:#f05a28; }}
        .goal-detail-top {{ display:flex; align-items:flex-start; justify-content:space-between; gap:14px; }} .goal-detail-label {{ color:#778594; font-size:9px; font-weight:850; letter-spacing:.12em; }}
        .goal-detail-top h2 {{ color:#10263d!important; font-size:23px; line-height:1.05; letter-spacing:-.03em; margin:6px 0 4px; }} .goal-detail-top p {{ color:#687582; font-size:10px; margin:0; }}
        .goal-timing {{ background:#f8f5ef; border-radius:999px; padding:6px 9px; color:#687582; font-size:9px; font-weight:750; white-space:nowrap; }}
        .goal-detail-metrics {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:7px; margin-top:14px; }} .goal-detail-metrics > div {{ background:#f8f5ef; border-radius:10px; padding:10px 12px; }}
        .goal-detail-metrics small,.goal-influence small {{ display:block; color:#84909a; font-size:8px; font-weight:800; letter-spacing:.1em; }} .goal-detail-metrics strong {{ display:block; font-size:14px; margin-top:4px; }}
        .goal-influence {{ display:grid; grid-template-columns:minmax(0,1fr) auto; gap:18px; align-items:center; margin-top:9px; padding:12px; background:#fff8ee; border:1px solid #f0dfc4; border-radius:11px; }} .goal-influence strong {{ display:block; font-size:12px; margin:4px 0; }} .goal-influence p {{ color:#687582; font-size:9px; margin:0; }} .goal-influence > span {{ color:#238a52; font-size:9px; font-weight:800; }}
        @container (max-width:580px) {{ .goal-detail-top {{ flex-direction:column; }} .goal-detail-metrics {{ grid-template-columns:1fr; }} .goal-influence {{ grid-template-columns:1fr; }} }}
    </style>
    """


def _set_notice(message: str) -> None:
    # Goal and block choices feed Home, Next Run and Race Predictor caches.
    # A deliberate lifecycle change must be visible on the next page visit.
    st.cache_data.clear()
    st.session_state["goals_notice"] = message


def _action_buttons(goal: GoalHierarchyItem, athlete_id: int, active_block_id: int | None) -> None:
    columns = st.columns(4)
    action_index = 0
    if goal.role in {"Secondary", "Future"}:
        if columns[action_index].button("Make Primary", key=f"goal_primary_{goal.id}", type="primary", use_container_width=True):
            set_primary_goal(athlete_id, goal.id)
            message = f"{goal.name} is now the Primary goal."
            if active_block_id != goal.training_block_id:
                message += " Review how the current Training Block should respond."
            _set_notice(message)
            st.rerun()
        action_index += 1
    if goal.role == "Secondary":
        if columns[action_index].button("Move to Future", key=f"goal_future_{goal.id}", use_container_width=True):
            set_goal_role(athlete_id, goal.id, "Future")
            _set_notice(f"{goal.name} is parked as a Future goal.")
            st.rerun()
        action_index += 1
    elif goal.role == "Future":
        if columns[action_index].button("Use as Secondary", key=f"goal_secondary_{goal.id}", use_container_width=True):
            set_goal_role(athlete_id, goal.id, "Secondary")
            _set_notice(f"{goal.name} is now a Secondary goal.")
            st.rerun()
        action_index += 1
    if goal.role != "Past":
        if columns[action_index].button("Mark Complete", key=f"goal_complete_{goal.id}", use_container_width=True):
            set_goal_status(athlete_id, goal.id, "Complete")
            _set_notice(f"{goal.name} moved to Past goals.")
            st.rerun()
        action_index += 1
        if columns[action_index].button(
            "Remove goal",
            key=f"goal_remove_{goal.id}",
            use_container_width=True,
        ):
            st.session_state["goal_remove_confirmation"] = goal.id
            st.rerun()

    if st.session_state.get("goal_remove_confirmation") == goal.id:
        if goal.role == "Primary":
            st.warning(
                f"Remove {goal.name}? An existing Secondary goal will be "
                "restored as Primary when available. Your current Training "
                "Block will not be deleted or redesigned."
            )
        else:
            st.warning(
                f"Remove {goal.name}? It will disappear from active goals "
                "but can be restored later from Past goals."
            )
        confirm, cancel = st.columns(2)
        if confirm.button(
            "Confirm removal",
            key=f"goal_remove_confirm_{goal.id}",
            type="primary",
            use_container_width=True,
        ):
            result = remove_goal(athlete_id, goal.id)
            st.session_state.pop("goal_remove_confirmation", None)
            message = f"{result.goal_name} removed and safely archived."
            if result.replacement_goal_name:
                message += (
                    f" {result.replacement_goal_name} is now the Primary goal."
                )
            elif result.was_primary:
                message += " Choose another goal to lead your coaching."
            if result.was_linked_to_block:
                message += " Your current Training Block has not been changed."
            _set_notice(message)
            st.rerun()
        if cancel.button(
            "Keep goal",
            key=f"goal_remove_cancel_{goal.id}",
            use_container_width=True,
        ):
            st.session_state.pop("goal_remove_confirmation", None)
            st.rerun()


def _edit_goal_form(goal: GoalHierarchyItem, athlete_id: int) -> None:
    with st.expander(f"Edit {goal.name}"):
        options = list(DISTANCE_METRES) + ["Performance", "Other"]
        current_type = _distance_label(goal.distance_m, goal.goal_type)
        if current_type not in options:
            current_type = "Other"
        current_date = _date(goal.target_date) or (datetime.date.today() + datetime.timedelta(weeks=12))
        with st.form(f"edit_goal_{goal.id}"):
            name = st.text_input("Goal name", value=goal.name)
            columns = st.columns(2)
            with columns[0]:
                goal_type = st.selectbox("Goal type", options, index=options.index(current_type))
                target_date = st.date_input("Target date", value=current_date)
            with columns[1]:
                event = st.text_input("Race/event", value=goal.race_name or "")
                target_text = st.text_input("Target time (HH:MM:SS or MM:SS)", value=(_time_text(goal.target_time_s) if goal.target_time_s is not None else ""))
            motivation = st.text_area("Why this matters", value=goal.motivation or "")
            submitted = st.form_submit_button("Save changes", type="primary")
        if submitted:
            target_seconds, valid = _parse_target_time(target_text)
            if not name.strip():
                st.error("Please give the goal a name.")
            elif not valid:
                st.error("Use MM:SS or HH:MM:SS for target time.")
            else:
                save_goal(athlete_id=athlete_id, goal_name=name.strip(), goal_type=goal_type, distance_m=DISTANCE_METRES.get(goal_type), target_time_s=target_seconds, target_date=str(target_date), race_name=event.strip() or None, priority=goal.role, status=goal.status, motivation=motivation.strip() or None, goal_id=goal.id)
                _set_notice(f"{name.strip()} updated.")
                st.rerun()


def _render_goal(goal: GoalHierarchyItem, athlete_id: int, active_block_id: int | None) -> None:
    st.html(_goal_card_html(goal))
    _action_buttons(goal, athlete_id, active_block_id)
    _edit_goal_form(goal, athlete_id)


def _render_primary_block(primary: GoalHierarchyItem, athlete_id: int) -> None:
    active_block = get_active_training_block(athlete_id)
    if active_block is not None:
        if primary.training_block_id == active_block.id:
            st.success(f"Primary goal is connected to {active_block.name}.")
        else:
            st.warning(f"{active_block.name} is still active, but it is not linked to the current Primary goal. Its design has not been changed.")
    else:
        st.info(
            "This Primary goal is ready for a history-led and customisable "
            "Training Block. Your sustainable history and chosen week will "
            "set the starting point."
        )
    if st.button(
        "Open Training Block Designer",
        key=f"open_training_block_designer_{primary.id}",
        type="primary",
        use_container_width=True,
    ):
        st.session_state["pp_navigation_request"] = "Training Blocks"
        st.rerun()


def _new_goal_form(athlete_id: int) -> None:
    with st.expander("Add a goal"):
        st.caption("Primary drives coaching, Secondary supports the current journey, and Future remains parked.")
        with st.form(f"new_goal_form_{athlete_id}"):
            name = st.text_input("Goal name", placeholder="Spring half marathon")
            columns = st.columns(2)
            with columns[0]:
                goal_type = st.selectbox("Goal type", list(DISTANCE_METRES) + ["Performance", "Other"])
                role = st.selectbox("Role", GOAL_ROLES)
                target_date = st.date_input("Target date", value=datetime.date.today() + datetime.timedelta(weeks=12))
            with columns[1]:
                event = st.text_input("Race/event", placeholder="Optional")
                target_text = st.text_input("Target time (HH:MM:SS or MM:SS)", placeholder="39:00")
            motivation = st.text_area("Why this matters", placeholder="Optional motivation or context.")
            submitted = st.form_submit_button("Save goal", type="primary")
        if submitted:
            target_seconds, valid = _parse_target_time(target_text)
            if not name.strip():
                st.error("Please give the goal a name.")
            elif not valid:
                st.error("Use MM:SS or HH:MM:SS for target time.")
            else:
                status = "Planned" if role == "Future" else "Active"
                save_goal(athlete_id=athlete_id, goal_name=name.strip(), goal_type=goal_type, distance_m=DISTANCE_METRES.get(goal_type), target_time_s=target_seconds, target_date=str(target_date), race_name=event.strip() or None, priority=role, status=status, motivation=motivation.strip() or None)
                _set_notice(f"{name.strip()} saved as {role}.")
                st.rerun()


def show_goals_page() -> None:
    st.markdown("""
        <style>
            [data-testid="stMainBlockContainer"] { max-width:1450px; padding-top:4.25rem; padding-bottom:3rem; }
            [data-testid="stHeader"] { background:transparent; }
            [data-testid="stElementContainer"]:has(.goals-selector-marker) { display:none; }
            [data-testid="stHorizontalBlock"]:has(.goals-selector-marker) { align-items:flex-start; gap:8px; }
            .goals-context-strip { min-height:40px; border:1px solid #e5ddd2; border-radius:12px; background:#fff; padding:0 15px; display:flex; align-items:center; justify-content:space-between; gap:14px; color:#10263d; box-shadow:0 5px 18px rgba(16,38,61,.035); }
            .goals-context-strip strong { font-size:12px; letter-spacing:.12em; } .goals-context-strip span { color:#6c7885; font-size:11px; } .goals-context-strip em { color:#238a52; font-size:10px; font-style:normal; font-weight:800; letter-spacing:.08em; }
            @media (max-width:900px) { [data-testid="stHorizontalBlock"]:has(.goals-selector-marker) [data-testid="stColumn"]:last-child { display:none; } [data-testid="stHorizontalBlock"]:has(.goals-selector-marker) [data-testid="stColumn"]:first-child { flex:1 1 100%; width:100%; } }
        </style>""", unsafe_allow_html=True)
    selector_col, context_col = st.columns([390, 1051], gap="small")
    with selector_col:
        st.markdown('<span class="goals-selector-marker"></span>', unsafe_allow_html=True)
        athlete_id = render_athlete_id_selector(label_visibility="collapsed")
    with context_col:
        st.html('<div class="goals-context-strip"><strong>GOALS</strong><span>What am I targeting?</span><em>ONE DIRECTION · MORE THAN ONE OUTCOME</em></div>')
    if athlete_id is None:
        st.info("Add an athlete before creating goals.")
        return

    notice = st.session_state.pop("goals_notice", None)
    if notice:
        st.success(notice)
    hierarchy = build_goal_hierarchy(athlete_id)
    st.html(build_goal_hierarchy_html(hierarchy))
    for warning in hierarchy.warnings:
        st.warning(warning)

    if hierarchy.primary is not None:
        st.markdown("### Primary goal")
        _render_goal(hierarchy.primary, athlete_id, hierarchy.active_block_id)
        _render_primary_block(hierarchy.primary, athlete_id)
    else:
        st.warning("No Active Primary goal is set. Choose Make Primary on a saved goal, or add a new Primary goal.")

    st.markdown("### Secondary goals")
    if hierarchy.secondary:
        for goal in hierarchy.secondary:
            _render_goal(goal, athlete_id, hierarchy.active_block_id)
            if hierarchy.active_block_id is not None and goal.training_block_id != hierarchy.active_block_id:
                if st.button("Include in current Training Block", key=f"include_secondary_{goal.id}_{hierarchy.active_block_id}"):
                    assign_goal_to_block(athlete_id=athlete_id, goal_id=goal.id, block_id=hierarchy.active_block_id)
                    _set_notice(f"{goal.name} included in the current block.")
                    st.rerun()
    else:
        st.caption("No Secondary tune-ups or benchmarks are set.")

    st.markdown("### Future goals")
    if hierarchy.future:
        for goal in hierarchy.future:
            _render_goal(goal, athlete_id, hierarchy.active_block_id)
    else:
        st.caption("No goals are parked for a future cycle.")

    if hierarchy.past:
        with st.expander(f"Past goals ({len(hierarchy.past)})"):
            for goal in hierarchy.past:
                st.html(_goal_card_html(goal))
                if st.button("Restore as Future", key=f"restore_goal_{goal.id}"):
                    restore_goal_as_future(athlete_id, goal.id)
                    _set_notice(f"{goal.name} restored as a Future goal.")
                    st.rerun()
    _new_goal_form(athlete_id)
