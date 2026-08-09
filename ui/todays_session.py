import html
import textwrap

import streamlit as st

from core.adaptive_coach_live import build_live_coach_decision
from core.session_designer import build_designed_session
from ui.athlete_selection import render_athlete_selector


MILES_PER_KM = 0.621371192237334


def _safe(value):
    return html.escape(str(value or ""))


def _html(markup):
    st.html(textwrap.dedent(markup).strip())


def _pace_per_mile(seconds_per_km):
    if seconds_per_km is None:
        return None
    seconds_per_mile = seconds_per_km / MILES_PER_KM
    minutes = int(seconds_per_mile // 60)
    seconds = int(round(seconds_per_mile % 60))
    if seconds == 60:
        minutes += 1
        seconds = 0
    return f"{minutes}:{seconds:02d}/mi"


def _target_text(session):
    items = []
    if session.pace_low_s_per_km is not None and session.pace_high_s_per_km is not None:
        faster = min(session.pace_low_s_per_km, session.pace_high_s_per_km)
        slower = max(session.pace_low_s_per_km, session.pace_high_s_per_km)
        items.append(("Pace", f"{_pace_per_mile(faster)} – {_pace_per_mile(slower)}"))
    if session.hr_low is not None and session.hr_high is not None:
        items.append(("Heart rate", f"{session.hr_low}–{session.hr_high} bpm"))
    elif session.hr_high is not None:
        items.append(("Heart rate", f"≤ {session.hr_high} bpm"))
    items.append(("RPE", f"{session.rpe_low:g}–{session.rpe_high:g}/10"))
    return items


def _list_card(label, icon, items):
    list_items = "".join(f"<li>{_safe(item)}</li>" for item in items)
    _html(
        f"""
        <div class="pp-card">
            <div class="pp-card-label">{_safe(icon)} {_safe(label)}</div>
            <ul style="margin:0.55rem 0 0; padding-left:1.2rem; line-height:1.75;">{list_items}</ul>
        </div>
        """
    )


def show_todays_session_page():
    st.write(
        "The full workout behind Adaptive Coach's live recommendation — with "
        "purpose, targets, execution cues and personal historical evidence."
    )

    athlete_id = render_athlete_selector(
        key="todays_session_athlete_selector",
        label="Athlete",
    )
    if athlete_id is None:
        st.info("Add an athlete before designing a session.")
        return

    with st.spinner("Adaptive Coach is designing the session..."):
        decision = build_live_coach_decision(athlete_id)
        if decision is None:
            session = None
        else:
            main_override = (
                (decision.key_prescription,)
                if decision.key_prescription
                else None
            )
            session = build_designed_session(
                athlete_id,
                family_override=decision.key_family,
                main_set_override=main_override,
                timing_override=decision.key_day,
                confidence_override=decision.confidence,
                confidence_label_override=decision.confidence_label,
                why_override=decision.why,
            )

    if session is None:
        st.info("Performance Passport needs enough recent coaching evidence to design this session.")
        return

    due_today = str(session.earliest_timing or "").lower().startswith("today")
    st.title("🏃 Next Run" if due_today else "🎯 Upcoming Key Session")

    _html(
        f"""
        <div class="pp-card pp-card-accent">
            <div class="pp-card-label">Adaptive Coach prescription</div>
            <div class="pp-card-title">{_safe(session.icon)} {_safe(session.family_label)}</div>
            <div class="pp-card-copy">{_safe(session.purpose)}</div>
            <div style="margin-top:0.8rem;">
                <span class="pp-status">{_safe(session.earliest_timing)}</span>
                <span class="pp-status">Confidence {_safe(session.confidence_label)} · {session.confidence:.0%}</span>
                <span class="pp-status">{_safe(session.source)}</span>
            </div>
        </div>
        """
    )

    st.markdown("## The workout")
    col1, col2, col3 = st.columns([0.9, 1.2, 0.9], gap="medium")
    with col1:
        _list_card("Warm-up", "🔥", session.warmup)
    with col2:
        _list_card("Main set", "🏃", session.main_set)
    with col3:
        _list_card("Cool-down", "🧊", session.cooldown)

    st.markdown("## Targets")
    targets = _target_text(session)
    columns = st.columns(len(targets), gap="small")
    for column, (label, value) in zip(columns, targets):
        with column:
            st.metric(label, value)

    left, right = st.columns(2, gap="medium")
    with left:
        st.markdown("### ✅ Success looks like...")
        _html(f'<div class="pp-card"><div class="pp-card-copy">{_safe(session.success_looks_like)}</div></div>')
        st.markdown("### ⚠️ Common mistake")
        _html(f'<div class="pp-card"><div class="pp-card-copy">{_safe(session.common_mistake)}</div></div>')

    with right:
        st.markdown("### 💬 Coach's Tip")
        _html(f'<div class="pp-card pp-card-hero"><div class="pp-card-copy">{_safe(session.coach_tip)}</div></div>')
        st.markdown("### 🔗 Why this session?")
        why_items = "".join(f"<li>{_safe(item)}</li>" for item in session.why_this_session)
        _html(f'<div class="pp-card"><ul style="margin:0;padding-left:1.2rem;line-height:1.7;">{why_items}</ul></div>')

    st.markdown("## 🧠 Personal history")
    _html(
        f'<div class="pp-card"><div class="pp-card-label">Historical Response Matching</div><div class="pp-card-title">{_safe(session.source)}</div><div class="pp-card-copy">{_safe(session.historical_summary)}</div></div>'
    )

    if session.historical_evidence:
        with st.expander("See the historical sessions that informed this workout"):
            for item in session.historical_evidence[:5]:
                execution = f"{item.execution_score:.0f}/100" if item.execution_score is not None else "not scored"
                st.markdown(
                    f"**{item.activity_date or 'Unknown date'} — {item.activity_title}**  \n"
                    f"Execution {execution} · Evidence {item.evidence_score:.0%}"
                )

    for note in decision.safety_notes:
        st.info(note)

    st.caption(
        "Adaptive Coach is live. The workout will continue to evolve as new training evidence arrives."
    )
