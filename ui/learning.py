import html
import textwrap

import streamlit as st

from core.learning_engine import (
    build_learning_observations,
    build_learning_profile,
)
from ui.athlete_selection import render_athlete_selector


def _safe(value):
    return html.escape(str(value or ""))


def _html(markup):
    st.html(textwrap.dedent(markup).strip())


def _delta_text(value):
    if value is None:
        return "Building"

    return f"{value:+.1f} pts"


def _rate_text(value):
    if value is None:
        return "Building"

    return f"{value:.0%}"


def show_learning_page():
    st.title("🧠 Learning")
    st.write(
        "What Performance Passport is learning from this athlete's real "
        "training history. v1 observes patterns first; it does not yet change "
        "workout prescriptions."
    )

    athlete_id = render_athlete_selector(
        key="learning_athlete_selector",
        label="Athlete",
    )

    if athlete_id is None:
        st.info("Add an athlete before building a Learning Profile.")
        return

    with st.spinner("Learning from historical training..."):
        profile = build_learning_profile(athlete_id)

    _html(
        f"""
        <div class="pp-card pp-card-accent">
            <div class="pp-card-label">Personal Learning Profile</div>
            <div class="pp-card-title">
                {_safe(profile.strongest_association or "Still building")}
            </div>
            <div class="pp-card-copy">
                {_safe(profile.summary)}
            </div>
            <div style="margin-top:0.8rem;">
                <span class="pp-status">
                    {profile.trusted_workout_count} trusted historical workouts
                </span>
                <span class="pp-status">
                    {profile.learned_pattern_count} learned workout families
                </span>
                <span class="pp-status">
                    Observation only
                </span>
            </div>
        </div>
        """
    )

    if not profile.patterns:
        st.info(
            "There is not enough high-confidence decoded history yet to show "
            "workout-response patterns."
        )
        return

    st.markdown("## What appears to work")

    for pattern in profile.patterns:
        with st.container():
            _html(
                f"""
                <div class="pp-card" style="margin-top:0.75rem;">
                    <div class="pp-card-label">
                        {_safe(pattern.family_label)}
                    </div>
                    <div class="pp-card-title">
                        {_safe(pattern.headline)}
                    </div>
                    <div class="pp-card-copy">
                        {_safe(pattern.explanation)}
                    </div>
                </div>
                """
            )

            cols = st.columns(4, gap="small")
            cols[0].metric(
                "Response association",
                _delta_text(
                    pattern.average_response_delta
                ),
            )
            cols[1].metric(
                "Positive windows",
                _rate_text(
                    pattern.positive_response_rate
                ),
            )
            cols[2].metric(
                "Usable responses",
                str(
                    pattern.response_observation_count
                ),
            )
            cols[3].metric(
                "Learning confidence",
                f"{pattern.confidence_label} · "
                f"{pattern.confidence:.0%}",
            )

            if pattern.best_associated_signature:
                st.caption(
                    "Best repeated historical structure: "
                    f"{pattern.best_associated_signature} · "
                    f"{pattern.best_signature_observations} usable windows · "
                    f"{_delta_text(pattern.best_signature_average_delta)} "
                    "average association."
                )

    st.markdown("## How PP is learning")

    _html(
        """
        <div class="pp-card">
            <div class="pp-card-title">21 days before → workout → 21 days after</div>
            <div class="pp-card-copy">
                PP only uses workouts with a trustworthy decoded phase
                structure. For each one, it compares average quality-workout
                execution in the 21 days before with the 21 days after.
                Race links add supporting confidence, but are not treated as
                proof that a workout caused a race result.
            </div>
        </div>
        """
    )

    observations = build_learning_observations(
        athlete_id
    )
    usable = [
        item
        for item in observations
        if item.response_delta is not None
    ]

    if usable:
        with st.expander(
            "See real historical response observations"
        ):
            for item in sorted(
                usable,
                key=lambda value: (
                    value.response_delta
                    if value.response_delta is not None
                    else -999
                ),
                reverse=True,
            )[:20]:
                st.markdown(
                    f"**{item.activity_date} — "
                    f"{item.activity_title}**  \n"
                    f"{item.family.replace('_', ' ').title()} · "
                    f"Execution {item.execution_score:.1f}/100 · "
                    f"21-day response association "
                    f"{item.response_delta:+.1f} points"
                )

    st.markdown("## Guardrails")

    for limitation in profile.limitations:
        st.caption(f"• {limitation}")

    st.info(
        "Learning Engine v1 is deliberately observation-only. We'll inspect "
        "what it has learned about the real athletes before allowing it to "
        "change Recommended Next Run or Today's Session."
    )
