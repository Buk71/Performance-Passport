import html
import textwrap

import streamlit as st

from core.adaptive_coach_live import build_live_coach_decision
from ui.athlete_selection import render_athlete_id_selector


def _safe(value):
    return html.escape(str(value or ""))


def _html(markup):
    st.html(textwrap.dedent(markup).strip())


def _go_to_session():
    st.session_state["pp_navigation_request"] = "Next Run"


def show_next_run_page():
    st.title("➡️ Recommended Next Run")
    st.write(
        "Adaptive Coach combines your goal, training block, current development "
        "needs, personal history and recent execution into one coaching decision."
    )

    athlete_id = render_athlete_id_selector(
        label="Athlete",
    )
    if athlete_id is None:
        st.info("Add an athlete before asking for a next-run recommendation.")
        return

    with st.spinner("Adaptive Coach is reviewing the plan..."):
        decision = build_live_coach_decision(athlete_id)

    if decision is None:
        st.info("Performance Passport needs enough recent evidence to coach the next run.")
        return

    if decision.operational_week_number is not None:
        completed = decision.operational_completed_miles or 0.0
        planned = decision.operational_planned_miles or 0.0
        st.caption(
            f"Saved Week {decision.operational_week_number} · "
            f"{decision.operational_status} · "
            f"{completed:.1f} of {planned:.1f} reliable miles complete"
        )

    _html(
        f"""
        <div class="pp-card pp-card-accent">
            <div class="pp-card-label">Immediate next run</div>
            <div class="pp-card-title">{_safe(decision.immediate_label)}</div>
            <div class="pp-card-copy">{_safe(decision.headline)}</div>
            <div style="margin-top:0.8rem;">
                <span class="pp-status">{_safe(decision.immediate_timing)}</span>
                <span class="pp-status">Confidence {_safe(decision.confidence_label)} · {decision.confidence:.0%}</span>
                <span class="pp-status">{_safe(decision.source)}</span>
            </div>
        </div>
        """
    )

    left, right = st.columns([1.15, 0.85], gap="medium")
    with left:
        st.markdown("### Why?")
        items = "".join(
            f"<li>{_safe(item)}</li>"
            for item in decision.why
        )
        _html(
            f'<div class="pp-card"><ul style="margin:0;padding-left:1.2rem;line-height:1.75;">{items}</ul></div>'
        )

    with right:
        st.markdown("### When?")
        _html(
            f'<div class="pp-card"><div class="pp-card-title">{_safe(decision.immediate_timing)}</div><div class="pp-card-copy">{_safe(decision.immediate_detail)}</div></div>'
        )

    st.markdown("## 🎯 Next key workout")

    if decision.key_label:
        key_text = (
            decision.key_prescription
            or decision.key_label
        )
        _html(
            f"""
            <div class="pp-card pp-card-hero">
                <div class="pp-card-label">Adaptive Coach prescription</div>
                <div class="pp-card-title">{_safe(decision.key_day or 'Timing building')} · {_safe(key_text)}</div>
                <div class="pp-card-copy">{_safe(decision.key_label)}</div>
            </div>
            """
        )
        st.button(
            "View the full workout →",
            type="primary",
            on_click=_go_to_session,
        )

    for note in decision.safety_notes:
        st.info(note)

    st.caption(
        "The saved Training Block sets the weekly commitments. Adaptive Coach uses real execution evidence to recommend the safest useful next step without silently changing that block."
    )
