"""Production History-Led Training Block Designer."""

from __future__ import annotations

import datetime
import html

import streamlit as st

from core.training_block_designer import (
    WEEKDAYS,
    TrainingBlockDesign,
    TrainingBlockPreferences,
    TrainingHistoryProfile,
    build_training_history_profile,
    design_training_block,
    history_to_dict,
    preferences_from_dict,
    preferences_to_dict,
    recommend_preferences,
)
from core.goals import GoalHierarchy, build_goal_hierarchy
from core.training_blocks import (
    assign_goal_to_block,
    get_active_training_block,
    get_training_block_design,
    list_training_blocks,
    save_training_block,
    save_training_block_design,
)
from ui.athlete_selection import render_athlete_id_selector


TRAINING_BLOCK_CACHE_SCHEMA = 1


@st.cache_data(show_spinner=False, ttl=300)
def _cached_foundation(
    athlete_id: int,
    schema: int,
) -> tuple[TrainingHistoryProfile | None, GoalHierarchy]:
    del schema
    return build_training_history_profile(athlete_id), build_goal_hierarchy(athlete_id)


def _escape(value) -> str:
    return html.escape(str(value or ""))


def _date_text(value: str) -> str:
    try:
        return datetime.date.fromisoformat(value[:10]).strftime("%-d %b %Y")
    except (TypeError, ValueError):
        return str(value)


def _clock(seconds: float | None) -> str:
    if seconds is None:
        return "No target time"
    rounded = int(round(seconds))
    hours, remainder = divmod(rounded, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def _goal_distance(distance_m: float | None) -> str:
    if distance_m is None:
        return "Distance not set"
    return f"{distance_m / 1000.0:g}K · {distance_m / 1609.344:.1f} mi"


def build_training_block_overview_html(
    history: TrainingHistoryProfile,
    hierarchy: GoalHierarchy,
    design: TrainingBlockDesign,
) -> str:
    primary = hierarchy.primary
    secondary_text = (
        f"{len(design.secondary_goal_ids)} relevant Secondary race"
        f"{'s' if len(design.secondary_goal_ids) != 1 else ''} included"
        if design.secondary_goal_ids
        else "No Secondary races currently fall inside this block"
    )
    rationale = "".join(f"<li>{_escape(item)}</li>" for item in design.rationale)
    warnings = "".join(
        f'<div class="tb-warning">{_escape(item)}</div>' for item in design.warnings
    )
    long_run = (
        f"{history.typical_long_run_miles:.1f} mi"
        if history.typical_long_run_miles is not None else "Building"
    )
    return f"""
    <main class="tb-shell">
      <section class="tb-hero">
        <div>
          <div class="tb-eyebrow">HISTORY-LED TRAINING BLOCK</div>
          <div class="tb-hero-row"><h1>{_escape(design.block_name)}</h1><span>PROPOSED</span></div>
          <p>Real sustainable training sets the starting point. Your choices set the weekly shape.</p>
        </div>
        <div class="tb-goal-card">
          <small>PRIMARY GOAL</small>
          <strong>{_escape(primary.name if primary else "No Primary goal")}</strong>
          <span>{_escape(_goal_distance(primary.distance_m if primary else None))} · {_escape(_clock(primary.target_time_s if primary else None))}</span>
          <span>{_escape(_date_text(primary.target_date) if primary and primary.target_date else "Date required")}</span>
        </div>
      </section>

      <section class="tb-section">
        <div class="tb-heading"><div><small>WHAT YOUR HISTORY SUPPORTS</small><h2>A demonstrated starting point</h2></div><span>{_escape(history.confidence.upper())} EVIDENCE</span></div>
        <div class="tb-evidence-grid">
          <article><small>RECENT RHYTHM</small><strong>{history.recent_days_per_week:.1f}<i> days/wk</i></strong><p>{history.recent_hours_per_week:.1f} hours across the latest six weeks.</p></article>
          <article><small>RELIABLE VOLUME</small><strong>{history.recent_miles_per_week:.1f}<i> mi/wk</i></strong><p>{history.prior_miles_per_week:.1f} miles in the preceding six weeks.</p></article>
          <article><small>LONG-RUN PATTERN</small><strong>{_escape(long_run)}</strong><p>{_escape(history.inferred_long_run_day)} is the clearest historical long-run day.</p></article>
          <article><small>QUALITY RHYTHM</small><strong>{history.supported_sessions_per_week}<i> sessions/wk</i></strong><p>{history.recent_quality_miles_per_week:.1f} recent quality miles per week.</p></article>
        </div>
      </section>

      <section class="tb-plan-summary">
        <div><small>GENERATED DIRECTION</small><h2>{len(design.weeks)} weeks · {_escape(design.block_type)} development</h2><p>{_escape(design.start_date)} → {_escape(design.end_date)} · {_escape(secondary_text)}</p></div>
        <div class="tb-plan-metrics"><span><strong>{design.baseline_miles:.1f}</strong>starting mi/wk</span><span><strong>{design.peak_miles:.1f}</strong>peak mi/wk</span></div>
      </section>
      <section class="tb-rationale"><div><small>WHY THIS SHAPE</small><ul>{rationale}</ul></div>{warnings}</section>
    </main>
    <style>
      .tb-shell{{container-type:inline-size;color:#10263D;font-family:Inter,system-ui,sans-serif;display:grid;gap:14px;margin-top:10px}}
      .tb-shell *{{box-sizing:border-box}} .tb-hero,.tb-section,.tb-plan-summary,.tb-rationale{{background:#fff;border:1px solid #DED8CE;border-radius:18px;box-shadow:0 8px 24px rgba(16,38,61,.05)}}
      .tb-hero{{padding:28px 30px;display:grid;grid-template-columns:minmax(0,1fr) 260px;gap:28px;align-items:center}}
      .tb-eyebrow,.tb-heading small,.tb-goal-card small,.tb-plan-summary small,.tb-evidence-grid small,.tb-rationale small{{font-size:11px;letter-spacing:.16em;font-weight:800;color:#718091}}
      .tb-hero-row{{display:flex;align-items:center;gap:12px;flex-wrap:wrap}} .tb-hero h1{{font-size:36px;line-height:1.03;margin:8px 0;color:#10263D;letter-spacing:-.04em}}
      .tb-hero-row>span,.tb-heading>span{{font-size:10px;font-weight:900;letter-spacing:.12em;color:#3E8E72;background:#E8F5EE;padding:7px 10px;border-radius:999px}}
      .tb-hero p,.tb-section p,.tb-plan-summary p,.tb-evidence-grid p{{margin:4px 0 0;color:#69798A;font-size:13px;line-height:1.45}}
      .tb-goal-card{{background:#F7F3EC;border:1px solid #E3DCCF;border-radius:15px;padding:18px;display:grid;gap:6px}}
      .tb-goal-card strong{{font-size:23px}} .tb-goal-card span{{font-size:12px;color:#56697B;font-weight:650}}
      .tb-section{{padding:22px 24px}} .tb-heading{{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;margin-bottom:16px}}
      .tb-heading h2,.tb-plan-summary h2{{font-size:22px;margin:4px 0 0;letter-spacing:-.025em}} .tb-evidence-grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}}
      .tb-evidence-grid article{{background:#F7F3EC;border:1px solid #E8E1D7;border-radius:14px;padding:16px;min-width:0}}
      .tb-evidence-grid strong{{display:block;font-size:26px;margin-top:8px;letter-spacing:-.03em}} .tb-evidence-grid strong i{{font-size:12px;font-style:normal;color:#6D7B88}}
      .tb-plan-summary{{padding:20px 24px;display:flex;justify-content:space-between;gap:20px;align-items:center;border-top:3px solid #3E8E72}}
      .tb-plan-metrics{{display:flex;gap:9px}} .tb-plan-metrics span{{min-width:112px;background:#F7F3EC;border-radius:12px;padding:12px;color:#667789;font-size:10px;font-weight:700;text-align:right}}
      .tb-plan-metrics strong{{display:block;color:#10263D;font-size:22px}} .tb-rationale{{padding:18px 24px;display:grid;gap:8px}} .tb-rationale ul{{margin:8px 0 0;padding-left:18px;color:#5D6E7E;font-size:12px;line-height:1.55}}
      .tb-warning{{background:#FFF0E8;border-left:3px solid #F05A28;border-radius:9px;padding:9px 12px;color:#9A451F;font-size:12px;font-weight:650}}
      @container (max-width:800px){{.tb-hero{{grid-template-columns:1fr}}.tb-evidence-grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}
      @container (max-width:560px){{.tb-hero{{padding:21px}}.tb-hero h1{{font-size:28px}}.tb-section{{padding:18px}}.tb-evidence-grid{{grid-template-columns:1fr}}.tb-plan-summary{{align-items:flex-start;flex-direction:column}}.tb-plan-metrics{{width:100%}}.tb-plan-metrics span{{flex:1;text-align:left}}}}
    </style>
    """


def build_week_timeline_html(design: TrainingBlockDesign) -> str:
    ceiling = max((week.target_miles for week in design.weeks), default=1.0)
    cards = []
    for week in design.weeks:
        width = max(week.target_miles / ceiling * 100.0, 8.0)
        flags = []
        if week.is_cutback:
            flags.append("CUTBACK")
        if week.event_name:
            flags.append(_escape(week.event_name).upper())
        flag = " · ".join(flags) or _escape(week.phase.upper())
        cards.append(
            f"""
            <article class="tb-week {'is-event' if week.event_name else ''}">
              <div class="tb-week-top"><span>WEEK {week.week_number}</span><i>{flag}</i></div>
              <strong>{week.target_miles:.1f} mi</strong>
              <div class="tb-week-track"><span style="width:{width:.1f}%"></span></div>
              <p>{_escape(week.emphasis)}</p>
              <small>{_escape(_date_text(week.start_date))} · {week.long_run_miles:.1f} mi long · {week.session_count} session{'s' if week.session_count != 1 else ''}</small>
            </article>
            """
        )
    return f"""
    <section class="tb-timeline-shell">
      <div class="tb-timeline-heading"><div><small>WEEK-BY-WEEK SHAPE</small><h2>Progression, recovery and taper</h2></div><span>SESSION DETAIL STAYS IN NEXT RUN</span></div>
      <div class="tb-timeline">{''.join(cards)}</div>
    </section>
    <style>
      .tb-timeline-shell{{container-type:inline-size;background:#fff;border:1px solid #DED8CE;border-radius:18px;padding:22px 24px;color:#10263D;font-family:Inter,system-ui,sans-serif;margin-top:14px}}
      .tb-timeline-heading{{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;margin-bottom:14px}} .tb-timeline-heading small{{font-size:11px;letter-spacing:.16em;font-weight:800;color:#718091}}
      .tb-timeline-heading h2{{font-size:22px;margin:4px 0;letter-spacing:-.025em}} .tb-timeline-heading>span{{font-size:10px;font-weight:850;letter-spacing:.1em;color:#3E8E72}}
      .tb-timeline{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px}} .tb-week{{background:#F7F3EC;border:1px solid #E7E0D5;border-radius:13px;padding:13px;min-width:0}}
      .tb-week.is-event{{border-color:#F2A98D;background:#FFF7F2}} .tb-week-top{{display:flex;justify-content:space-between;gap:5px;align-items:center}} .tb-week-top span,.tb-week-top i{{font-size:9px;font-style:normal;font-weight:850;letter-spacing:.08em;color:#718091}}
      .tb-week-top i{{color:#F05A28;text-align:right}} .tb-week>strong{{display:block;font-size:22px;margin:8px 0 5px}} .tb-week-track{{height:5px;background:#E3DED5;border-radius:999px;overflow:hidden}} .tb-week-track span{{display:block;height:100%;background:#3E8E72;border-radius:999px}}
      .tb-week p{{font-size:11px;font-weight:750;line-height:1.35;min-height:30px;margin:9px 0 5px}} .tb-week>small{{font-size:9px;line-height:1.35;color:#718091}}
      @container (max-width:850px){{.tb-timeline{{grid-template-columns:repeat(2,minmax(0,1fr))}}}} @container (max-width:520px){{.tb-timeline-shell{{padding:18px}}.tb-timeline{{grid-template-columns:1fr}}.tb-timeline-heading{{flex-direction:column}}.tb-week p{{min-height:auto}}}}
    </style>
    """


def build_daily_week_html(week) -> str:
    cards = "".join(
        f"""
        <article class="tb-day {'is-hard' if day.is_hard else ''}">
          <small>{_escape(day.day[:3].upper())}</small>
          <strong>{_escape(day.session_type)}</strong>
          <p>{_escape(day.detail)}</p>
        </article>
        """
        for day in week.days
    )
    return f"""
    <section class="tb-daily-shell">
      <div><small>DAILY SHAPE · WEEK {week.week_number}</small><h3>{_escape(week.emphasis)}</h3></div>
      <div class="tb-days">{cards}</div>
    </section>
    <style>
      .tb-daily-shell{{container-type:inline-size;background:#fff;border:1px solid #DED8CE;border-radius:16px;padding:18px;color:#10263D;font-family:Inter,system-ui,sans-serif}}
      .tb-daily-shell>div>small,.tb-day small{{font-size:9px;letter-spacing:.12em;font-weight:850;color:#718091}} .tb-daily-shell h3{{font-size:17px;margin:4px 0 13px}}
      .tb-days{{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:7px}} .tb-day{{background:#F7F3EC;border:1px solid #E6DFD4;border-radius:11px;padding:11px;min-width:0}}
      .tb-day.is-hard{{border-top:3px solid #F05A28}} .tb-day strong{{display:block;font-size:12px;line-height:1.25;margin:6px 0}} .tb-day p{{font-size:9px;line-height:1.35;color:#68798A;margin:0;overflow-wrap:anywhere}}
      @container (max-width:800px){{.tb-days{{grid-template-columns:repeat(4,minmax(0,1fr))}}}} @container (max-width:480px){{.tb-days{{grid-template-columns:1fr 1fr}}}}
    </style>
    """


def _initial_preferences(athlete_id, history, hierarchy):
    defaults = recommend_preferences(history)
    active = get_active_training_block(athlete_id)
    saved = get_training_block_design(active.id, athlete_id=athlete_id) if active else None
    if saved is not None and saved.primary_goal_id == hierarchy.primary.id:
        return preferences_from_dict(saved.preferences), active, saved
    return defaults, active, saved


def _set_widget_defaults(athlete_id, preferences):
    prefix = f"tb_{athlete_id}_"
    keys = {name: prefix + suffix for name, suffix in {
        "running": "running_days", "long": "long_day", "sessions": "session_days",
        "strength": "strength_days", "ceiling": "ceiling", "replace": "race_replaces",
        "note": "recovery_note",
    }.items()}
    initial = {
        keys["running"]: list(preferences.running_days), keys["long"]: preferences.long_run_day,
        keys["sessions"]: list(preferences.session_days), keys["strength"]: list(preferences.strength_days),
        keys["ceiling"]: float(preferences.max_weekly_miles), keys["replace"]: preferences.race_replaces_session,
        keys["note"]: preferences.recovery_note,
    }
    for key, value in initial.items():
        if key not in st.session_state:
            st.session_state[key] = value
    return keys


def _customisation_controls(athlete_id, history, initial):
    keys = _set_widget_defaults(athlete_id, initial)
    st.markdown("### Customise the week")
    st.caption("History proposes a starting point. These constraints decide how the block fits real life.")
    running_days = tuple(st.multiselect("Days you want to run", WEEKDAYS, key=keys["running"]))
    long_options = running_days or WEEKDAYS
    if st.session_state.get(keys["long"]) not in long_options:
        st.session_state[keys["long"]] = long_options[-1]
    columns = st.columns(2)
    with columns[0]:
        long_day = st.selectbox("Long-run day", long_options, key=keys["long"])
        session_options = tuple(day for day in running_days if day != long_day)
        valid_sessions = [day for day in st.session_state.get(keys["sessions"], []) if day in session_options]
        if valid_sessions != st.session_state.get(keys["sessions"]):
            st.session_state[keys["sessions"]] = valid_sessions
        session_days = tuple(st.multiselect(
            "Session days", session_options, key=keys["sessions"],
            help="Threshold, intervals, speed or race-specific work. The long run is separate.",
        ))
        strength_days = tuple(st.multiselect("Strength days", WEEKDAYS, key=keys["strength"]))
    with columns[1]:
        lower = max(10.0, float(round(history.recent_miles_per_week * 0.65)))
        upper = max(lower + 5.0, float(round(history.recent_miles_per_week * 1.35)))
        current = float(st.session_state.get(keys["ceiling"], initial.max_weekly_miles))
        st.session_state[keys["ceiling"]] = min(max(current, lower), upper)
        max_miles = st.slider("Maximum weekly volume (miles)", lower, upper, step=1.0, key=keys["ceiling"])
        race_replaces = st.toggle(
            "A race replaces a session", key=keys["replace"],
            help="Prevents a Secondary race being added on top of normal quality load.",
        )
        recovery_note = st.text_area(
            "Recovery, injury or life constraint", key=keys["note"],
            placeholder="Optional: protect Achilles; avoid two hard evenings; travel in week 6.",
        )
    return TrainingBlockPreferences(
        running_days=running_days, long_run_day=long_day, session_days=session_days,
        strength_days=strength_days, max_weekly_miles=max_miles,
        race_replaces_session=race_replaces, recovery_note=recovery_note.strip(),
    )


def _daily_preview(design):
    labels = {
        f"Week {week.week_number} · {_date_text(week.start_date)} · {week.phase}": week
        for week in design.weeks
    }
    selected = st.selectbox("Inspect a week's daily shape", list(labels), key=f"tb_week_preview_{design.athlete_id}")
    st.html(build_daily_week_html(labels[selected]))


def _save_design(athlete_id, hierarchy, history, preferences, design, active):
    primary = hierarchy.primary
    saved_active = (
        get_training_block_design(active.id, athlete_id=athlete_id)
        if active is not None else None
    )
    can_update = active is not None and (
        primary.training_block_id == active.id
        or (
            saved_active is not None
            and saved_active.primary_goal_id == primary.id
        )
    )
    block_id = save_training_block(
        athlete_id=athlete_id, name=design.block_name, block_type=design.block_type,
        purpose=f"History-led preparation for {primary.name}. Starts from {history.recent_miles_per_week:.1f} reliable miles per week.",
        start_date=design.start_date, end_date=design.end_date, status="Active",
        primary_focus="Threshold" if design.block_type == "10K" else "Balanced",
        current_phase=design.weeks[0].phase, notes=preferences.recovery_note or None,
        block_id=active.id if can_update else None,
    )
    assign_goal_to_block(athlete_id=athlete_id, goal_id=primary.id, block_id=block_id)
    for goal_id in design.secondary_goal_ids:
        assign_goal_to_block(athlete_id=athlete_id, goal_id=goal_id, block_id=block_id)
    save_training_block_design(
        athlete_id=athlete_id, training_block_id=block_id, primary_goal_id=primary.id,
        preferences=preferences_to_dict(preferences), evidence=history_to_dict(history),
        plan=design.to_dict(), model_version=design.model_version,
    )
    return block_id


def _existing_blocks(athlete_id, current_id):
    historical = [block for block in list_training_blocks(athlete_id) if block.id != current_id]
    if not historical:
        return
    with st.expander("Previous and parked Training Blocks"):
        for block in historical:
            st.markdown(f"**{block.name}** · {block.status}")
            st.caption(f"{block.block_type} · {block.start_date or 'No start'} → {block.end_date or 'No end'}")


def show_training_blocks_page():
    selector, heading = st.columns([1, 2.7])
    with selector:
        athlete_id = render_athlete_id_selector(label_visibility="collapsed")
    with heading:
        st.markdown("## Training Block Designer")
        st.caption("How should this athlete’s real history become a safe, realistic block?")
    if athlete_id is None:
        st.info("Add an athlete before designing a Training Block.")
        return
    history, hierarchy = _cached_foundation(athlete_id, TRAINING_BLOCK_CACHE_SCHEMA)
    if hierarchy.primary is None:
        st.warning("Choose one Active Primary goal in Goals before designing a Training Block.")
        return
    if hierarchy.primary.target_date is None:
        st.warning("Add a target date to the Primary goal before designing its block.")
        return
    if history is None:
        st.warning("There is not enough running history to create a history-led block yet.")
        return
    initial, active, saved = _initial_preferences(athlete_id, history, hierarchy)
    preferences = _customisation_controls(athlete_id, history, initial)
    try:
        design = design_training_block(
            history=history, hierarchy=hierarchy, preferences=preferences,
        )
    except ValueError as exc:
        st.error(str(exc))
        return
    st.html(build_training_block_overview_html(history, hierarchy, design))
    st.html(build_week_timeline_html(design))
    _daily_preview(design)
    if saved is not None and saved.primary_goal_id == hierarchy.primary.id:
        st.caption("This active block already has a saved custom design. Saving again updates it in place.")
    elif active is not None and hierarchy.primary.training_block_id != active.id:
        st.warning(
            f"{active.name} is not linked to the current Primary goal. Saving will complete it and create a new active block; it will not be silently rewritten."
        )
    button_label = (
        "Update active Training Block"
        if active is not None and hierarchy.primary.training_block_id == active.id
        else "Save as active Training Block"
    )
    if st.button(button_label, type="primary", use_container_width=True):
        block_id = _save_design(athlete_id, hierarchy, history, preferences, design, active)
        st.cache_data.clear()
        st.success(f"Training Block #{block_id} saved with its history evidence, custom week and generated progression.")
        st.rerun()
    st.caption(
        "Saving sets the block's direction and weekly shape. It does not pre-write every workout; Next Run remains responsible for the exact next prescription."
    )
    _existing_blocks(athlete_id, active.id if active else None)
