import html
import textwrap

import streamlit as st

from core.next_run import build_next_run_recommendation
from ui.athlete_selection import render_athlete_selector


def _safe(value):
    return html.escape(str(value or ""))


def _html(markup):
    st.html(textwrap.dedent(markup).strip())


def _go_to_session():
    st.session_state["pp_navigation_request"] = "Today's Session"
    st.rerun()


def show_next_run_page():
    st.title("➡️ Recommended Next Run")
    st.write(
        "First PP tells you what to do next. Then it keeps sight of the next "
        "key workout that moves your Training Block forward."
    )

    athlete_id = render_athlete_selector(
        key="next_run_athlete_selector",
        label="Athlete",
    )

    if athlete_id is None:
        st.info("Add an athlete before asking for a next-run recommendation.")
        return

    with st.spinner("Asking the coaching team..."):
        recommendation = build_next_run_recommendation(athlete_id)

    if recommendation is None:
        st.info(
            "Performance Passport needs a recognised recent run before it can "
            "recommend what comes next."
        )
        return

    readiness_note = (
        " · Readiness check required"
        if recommendation.readiness_required
        else ""
    )

    _html(
        f"""
        <div class="pp-card pp-card-accent">
            <div class="pp-card-label">Immediate next run</div>
            <div class="pp-card-title">
                {_safe(recommendation.icon)} {_safe(recommendation.session_family)}
            </div>
            <div class="pp-card-copy" style="font-size:0.98rem;">
                {_safe(recommendation.headline)}
            </div>
            <div style="margin-top:0.8rem;">
                <span class="pp-status">
                    Recommendation confidence {_safe(recommendation.confidence_label)}
                    · {recommendation.confidence:.0%}
                </span>
                <span class="pp-status">
                    {_safe(recommendation.earliest_timing)}
                    {_safe(readiness_note)}
                </span>
            </div>
        </div>
        """
    )

    left, right = st.columns([1.15, 0.85], gap="medium")

    with left:
        st.markdown("### Why this run?")
        why_items = "".join(
            f"<li>{_safe(item)}</li>"
            for item in recommendation.why
        )
        _html(
            f"""
            <div class="pp-card">
                <ul style="margin:0; padding-left:1.2rem; line-height:1.75;">
                    {why_items}
                </ul>
            </div>
            """
        )

        st.markdown("### Expected benefit")
        _html(
            f"""
            <div class="pp-card">
                <div class="pp-card-title">Move the current block forward</div>
                <div class="pp-card-copy">
                    {_safe(recommendation.expected_benefit)}
                </div>
            </div>
            """
        )

    with right:
        st.markdown("### When?")
        _html(
            f"""
            <div class="pp-card">
                <div class="pp-card-title">
                    {_safe(recommendation.earliest_timing)}
                </div>
                <div class="pp-card-copy">
                    {_safe(recommendation.timing_detail)}
                </div>
            </div>
            """
        )

        st.markdown("### If recovery says no")
        _html(
            f"""
            <div class="pp-card">
                <div class="pp-card-title">
                    {_safe(recommendation.alternative)}
                </div>
                <div class="pp-card-copy">
                    {_safe(recommendation.alternative_reason)}
                </div>
            </div>
            """
        )

    st.markdown("## 🎯 Next key workout")

    if recommendation.next_key_session_family:
        key_readiness = (
            " · readiness check required"
            if recommendation.next_key_session_readiness_required
            else ""
        )
        _html(
            f"""
            <div class="pp-card pp-card-hero">
                <div class="pp-card-label">Where the block is heading</div>
                <div class="pp-card-title">
                    {_safe(recommendation.next_key_session_icon)}
                    {_safe(recommendation.next_key_session_family)}
                </div>
                <div class="pp-card-copy">
                    {_safe(recommendation.next_key_session_timing or "Timing building")}
                    {_safe(key_readiness)}
                </div>
                <div class="pp-card-copy" style="margin-top:0.45rem;">
                    {_safe(recommendation.next_key_session_timing_detail or "")}
                </div>
            </div>
            """
        )

        st.button(
            "View the full workout →",
            type="primary",
            on_click=_go_to_session,
            use_container_width=False,
        )
    else:
        _html(
            f"""
            <div class="pp-card">
                <div class="pp-card-title">No quality workout needs forcing yet.</div>
                <div class="pp-card-copy">
                    PP will keep watching the current block, your recent running
                    and the Decision Engine before naming the next key workout.
                </div>
            </div>
            """
        )

    if recommendation.readiness_required:
        st.info(
            "PP has identified the highest-value immediate session, but a "
            "dedicated Readiness/Fatigue engine is not connected yet. "
            "Only do the quality session if recovery, soreness and general "
            "energy feel normal."
        )

    st.caption(
        "Immediate next run = what to do next · Next key workout = where the "
        "Training Block is heading."
    )
