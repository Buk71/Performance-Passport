import html
import textwrap

import streamlit as st

from core.session_designer import build_designed_session
from core.live_integration import build_adaptive_coach_proposal
from core.next_run import build_next_run_recommendation
from core.coaching_arbitration import build_coaching_arbitration
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

    if (
        session.pace_low_s_per_km is not None
        and session.pace_high_s_per_km is not None
    ):
        # Lower seconds = faster pace. Display fast-to-slow naturally.
        faster = min(
            session.pace_low_s_per_km,
            session.pace_high_s_per_km,
        )
        slower = max(
            session.pace_low_s_per_km,
            session.pace_high_s_per_km,
        )
        items.append(
            (
                "Pace",
                f"{_pace_per_mile(faster)} – "
                f"{_pace_per_mile(slower)}",
            )
        )

    if session.hr_low is not None and session.hr_high is not None:
        items.append(
            (
                "Heart rate",
                f"{session.hr_low}–{session.hr_high} bpm",
            )
        )
    elif session.hr_high is not None:
        items.append(
            (
                "Heart rate",
                f"≤ {session.hr_high} bpm",
            )
        )

    items.append(
        (
            "RPE",
            f"{session.rpe_low:g}–{session.rpe_high:g}/10",
        )
    )

    return items


def _list_card(label, icon, items):
    list_items = "".join(
        f"<li>{_safe(item)}</li>"
        for item in items
    )

    _html(
        f"""
        <div class="pp-card">
            <div class="pp-card-label">{_safe(icon)} {_safe(label)}</div>
            <ul style="margin:0.55rem 0 0; padding-left:1.2rem; line-height:1.75;">
                {list_items}
            </ul>
        </div>
        """
    )


def show_todays_session_page():
    # The title becomes dynamic after the session has been designed: a quality
    # workout due later should never be presented as if it must be done today.
    st.write(
        "The complete key workout behind PP's coaching recommendation — with "
        "purpose, targets, execution cues and your own successful historical "
        "sessions used where the evidence is strong enough."
    )

    athlete_id = render_athlete_selector(
        key="todays_session_athlete_selector",
        label="Athlete",
    )

    if athlete_id is None:
        st.info("Add an athlete before designing a session.")
        return

    with st.spinner("Designing today's session..."):
        session = build_designed_session(
            athlete_id
        )

    if session is None:
        st.info(
            "Performance Passport needs enough recent coaching evidence to "
            "design today's session."
        )
        return

    due_today = str(session.earliest_timing or "").lower().startswith("today")
    page_title = "🏃 Today's Session" if due_today else "🎯 Upcoming Key Session"
    st.title(page_title)

    readiness = (
        " · Readiness check required"
        if session.readiness_required
        else ""
    )

    _html(
        f"""
        <div class="pp-card pp-card-accent">
            <div class="pp-card-label">Key workout prescription</div>
            <div class="pp-card-title">
                {_safe(session.icon)} {_safe(session.family_label)}
            </div>
            <div class="pp-card-copy" style="font-size:0.98rem;">
                {_safe(session.purpose)}
            </div>
            <div style="margin-top:0.8rem;">
                <span class="pp-status">
                    {_safe(session.earliest_timing)}{_safe(readiness)}
                </span>
                <span class="pp-status">
                    Confidence {_safe(session.confidence_label)}
                    · {session.confidence:.0%}
                </span>
                <span class="pp-status">
                    {_safe(session.source)}
                </span>
            </div>
        </div>
        """
    )

    st.markdown("## The workout")

    col1, col2, col3 = st.columns(
        [0.9, 1.2, 0.9],
        gap="medium",
    )

    with col1:
        _list_card(
            "Warm-up",
            "🔥",
            session.warmup,
        )

    with col2:
        _list_card(
            "Main set",
            "🏃",
            session.main_set,
        )

    with col3:
        _list_card(
            "Cool-down",
            "🧊",
            session.cooldown,
        )

    st.markdown("## Targets")

    targets = _target_text(session)
    target_columns = st.columns(
        len(targets),
        gap="small",
    )

    for column, (label, value) in zip(
        target_columns,
        targets,
    ):
        with column:
            st.metric(label, value)

    left, right = st.columns(2, gap="medium")

    with left:
        st.markdown("### ✅ Success looks like...")
        _html(
            f"""
            <div class="pp-card">
                <div class="pp-card-copy" style="font-size:0.95rem;">
                    {_safe(session.success_looks_like)}
                </div>
            </div>
            """
        )

        st.markdown("### ⚠️ Common mistake")
        _html(
            f"""
            <div class="pp-card">
                <div class="pp-card-copy">
                    {_safe(session.common_mistake)}
                </div>
            </div>
            """
        )

    with right:
        st.markdown("### 💬 Coach's Tip")
        _html(
            f"""
            <div class="pp-card pp-card-hero">
                <div class="pp-card-copy" style="font-size:0.95rem;">
                    {_safe(session.coach_tip)}
                </div>
            </div>
            """
        )

        st.markdown("### 🔗 Why this session?")
        why_items = "".join(
            f"<li>{_safe(item)}</li>"
            for item in session.why_this_session
        )
        _html(
            f"""
            <div class="pp-card">
                <ul style="margin:0; padding-left:1.2rem; line-height:1.7;">
                    {why_items}
                </ul>
            </div>
            """
        )

    st.markdown("## 🧠 Personal history")

    _html(
        f"""
        <div class="pp-card">
            <div class="pp-card-label">Historical Response Matching</div>
            <div class="pp-card-title">
                {_safe(session.source)}
            </div>
            <div class="pp-card-copy">
                {_safe(session.historical_summary)}
            </div>
        </div>
        """
    )

    if session.historical_evidence:
        with st.expander(
            "See the historical sessions that informed this workout"
        ):
            for item in session.historical_evidence[:5]:
                execution = (
                    f"{item.execution_score:.0f}/100"
                    if item.execution_score is not None
                    else "not scored"
                )
                race_support = (
                    f" · {item.race_link_count} subsequent race link"
                    f"{'s' if item.race_link_count != 1 else ''}"
                    if item.race_link_count
                    else ""
                )

                st.markdown(
                    f"**{item.activity_date or 'Unknown date'} — "
                    f"{item.activity_title}**  \n"
                    f"Execution {execution} · "
                    f"Evidence {item.evidence_score:.0%}"
                    f"{race_support}"
                )

    if session.readiness_required:
        st.info(
            "PP has designed the highest-value session, but the dedicated "
            "Readiness/Fatigue engine is not connected yet. Only complete the "
            "quality session if soreness, recovery and general energy feel normal."
        )

    st.markdown("## 🧪 Adaptive Coach session rehearsal")

    proposal = build_adaptive_coach_proposal(
        athlete_id,
        existing_label=session.family_label,
    )

    if proposal is not None and proposal.key_prescription:
        _html(
            f"""
            <div class="pp-card pp-card-hero">
                <div class="pp-card-label">Adaptive Coach proposed key workout</div>
                <div class="pp-card-title">
                    {_safe(proposal.key_day)} · {_safe(proposal.key_prescription)}
                </div>
                <div class="pp-card-copy">
                    {_safe(proposal.progression_headline or "Progression evidence building")}
                </div>
                <div style="margin-top:0.8rem;">
                    <span class="pp-status">{_safe(proposal.safety_status)}</span>
                    <span class="pp-status">
                        Confidence {_safe(proposal.adaptive_confidence_label)}
                        · {proposal.adaptive_confidence:.0%}
                    </span>
                </div>
            </div>
            """
        )

        st.caption(f"Existing session comparison: {proposal.comparison}")

        with st.expander("See integration reasoning"):
            for item in proposal.why:
                st.markdown(f"- {item}")

        st.info(
            "Safety switch is still ON: the existing Today's Session remains "
            "authoritative in v0.19.6."
        )

    st.markdown("## ⚖️ Arbitration result")

    existing_for_arbitration = build_next_run_recommendation(athlete_id)

    arbitration = (
        build_coaching_arbitration(
            athlete_id,
            existing_recommendation=existing_for_arbitration,
        )
        if existing_for_arbitration is not None
        else None
    )

    if arbitration is not None:
        if arbitration.ready_for_live:
            st.success(
                f"{arbitration.headline} · "
                f"{arbitration.confidence_label} confidence "
                f"({arbitration.confidence:.0%})"
            )
        else:
            st.warning(
                f"{arbitration.headline} · review before live takeover."
            )

        with st.expander("Why arbitration chose this"):
            for item in arbitration.evidence:
                st.markdown(f"- {item}")
            for item in arbitration.safety_notes:
                st.caption(item)

    st.caption(
        "Historical sessions inform the prescription; they do not yet prove "
        "causal training response. The Learning Engine will add that next."
    )
