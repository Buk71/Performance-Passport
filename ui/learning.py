import html
import textwrap

import streamlit as st

from core.learning_engine import (
    build_learning_observations,
    build_learning_profile,
)
from core.performance_backtracking import build_performance_backtracking_profile
from core.adaptive_training_block import build_adaptive_block_preview
from core.adaptive_weekly_plan import build_adaptive_weekly_plan
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

            history_detail = (
                f"{pattern.pure_session_count} pure · "
                f"{pattern.mixed_session_count} mixed"
            )

            cols = st.columns(5, gap="small")
            cols[0].metric(
                "History identified",
                str(pattern.trusted_session_count),
                help=history_detail,
            )
            cols[1].metric(
                "Usable response windows",
                str(pattern.response_observation_count),
            )
            cols[2].metric(
                "Response association",
                _delta_text(
                    pattern.average_response_delta
                ),
            )
            cols[3].metric(
                "Positive windows",
                _rate_text(
                    pattern.positive_response_rate
                ),
            )
            cols[4].metric(
                "Learning confidence",
                f"{pattern.confidence_label} · "
                f"{pattern.confidence:.0%}",
            )

            st.caption(
                f"History: {pattern.trusted_session_count} sessions identified · "
                f"{pattern.pure_session_count} pure {pattern.family_label.lower()} · "
                f"{pattern.mixed_session_count} mixed sessions containing "
                f"{pattern.family_label.lower()}. Only "
                f"{pattern.response_observation_count} currently have complete "
                "before/after response windows."
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
                PP first counts every trustworthy decoded workout that
                contains the training stimulus — including mixed sessions.
                Response learning is stricter: where enough surrounding data
                exists, it compares average quality-workout execution in the
                21 days before with the 21 days after. Race links add supporting
                confidence, but are not treated as proof that a workout caused
                a race result.
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

    st.markdown("## 🏁 Performance Backtracking")

    with st.spinner("Reconstructing training before strong performances..."):
        backtracking = build_performance_backtracking_profile(athlete_id)

    st.write(backtracking.summary)

    if backtracking.performances:
        st.caption(
            "This starts with PBs and other top race-quality performances, then "
            "looks backwards. It treats the whole preparation pattern as evidence "
            "rather than pretending one Wednesday or Saturday workout caused the result."
        )

        for item in backtracking.performances[:8]:
            anchor = item.anchor
            badge = "PB" if anchor.is_pb else "Strong performance"

            with st.expander(
                f"{anchor.activity_date} · {anchor.distance_label} · "
                f"{badge} · {anchor.title}"
            ):
                st.caption(
                    f"{anchor.anchor_reason} · anchor confidence "
                    f"{anchor.confidence:.0%}"
                )

                cols = st.columns(4, gap="small")
                for col, days in zip(cols, (14, 28, 42, 56)):
                    window = next(
                        value for value in item.windows
                        if value.days == days
                    )
                    with col:
                        st.metric(
                            f"{days // 7}-week volume",
                            f"{window.average_weekly_km:.1f} km/wk",
                        )
                        st.caption(
                            f"{window.quality_session_count} quality · "
                            f"{window.threshold_session_count} threshold · "
                            f"{window.short_interval_session_count} short/VO₂ · "
                            f"{window.long_run_count} long runs"
                        )

                six_week = next(
                    value for value in item.windows
                    if value.days == 42
                )
                if six_week.signatures:
                    st.markdown("**Most repeated decoded workouts in the 6-week build:**")
                    st.write(
                        " · ".join(
                            f"{signature} ×{count}"
                            for signature, count in six_week.signatures
                        )
                    )

        if backtracking.preparation_contrasts:
            st.markdown("### 🔍 What was different from normal training?")
            st.caption(
                "This is the important control-group comparison: successful "
                "6-week builds versus ordinary 6-week blocks from the same athlete."
            )

            for contrast in backtracking.preparation_contrasts:
                relative_text = (
                    f"{contrast.relative_difference:+.0%}"
                    if contrast.relative_difference is not None
                    else "n/a"
                )

                cols = st.columns([1.7, 1, 1, 1], gap="small")
                cols[0].markdown(f"**{contrast.metric_label}**")
                cols[1].metric(
                    "Before strong performances",
                    f"{contrast.successful_average:g}",
                )
                cols[2].metric(
                    "Normal training",
                    f"{contrast.normal_average:g}",
                )
                cols[3].metric(
                    "Difference",
                    relative_text,
                )

                st.caption(
                    f"{contrast.evidence_label} · "
                    f"{contrast.direction} before strong performances."
                )

        if backtracking.signature_lifts:
            st.markdown("### ⭐ Workout structures unusually associated with strong performances")
            st.caption(
                "A workout only matters here if it appears more often in "
                "successful 6-week builds than in ordinary 6-week training."
            )

            for signature in backtracking.signature_lifts[:8]:
                if signature.lift is None:
                    lift_text = "only seen in successful blocks"
                else:
                    lift_text = f"{signature.lift:.1f}× as common"

                st.markdown(
                    f"**{signature.workout_signature}** — "
                    f"{lift_text} · "
                    f"{signature.successful_block_rate:.0%} of successful builds "
                    f"vs {signature.normal_block_rate:.0%} of normal blocks"
                )

        if backtracking.recurring_42d_signatures:
            st.markdown("### Recurring patterns before strong performances")
            st.caption(
                "Workout structures appearing across multiple successful "
                "6-week preparation blocks."
            )
            st.write(
                " · ".join(
                    f"{signature} ({count} blocks)"
                    for signature, count
                    in backtracking.recurring_42d_signatures
                )
            )

    st.markdown("## 🧭 Adaptive Training Block Preview")

    adaptive = build_adaptive_block_preview(athlete_id)

    if not adaptive.available:
        st.info(adaptive.summary)
    else:
        st.write(adaptive.summary)

        top = st.columns(4, gap="small")
        top[0].metric("Goal", adaptive.distance_label or "—")
        top[1].metric("Weeks remaining", str(adaptive.weeks_remaining or "—"))
        top[2].metric("Current phase", adaptive.current_phase or "—")
        top[3].metric("Mode", "Preview only")

        if adaptive.learned_signals:
            st.markdown("### What PP has learned from this athlete")
            for signal in adaptive.learned_signals:
                st.markdown(f"- {signal}")

        st.markdown("### Proposed progression")

        for phase in adaptive.phases:
            week_text = (
                f"Week {phase.start_week}"
                if phase.start_week == phase.end_week
                else f"Weeks {phase.start_week}–{phase.end_week}"
            )

            with st.expander(
                f"{week_text} · {phase.name} · {phase.primary_focus}",
                expanded=(phase.name == adaptive.current_phase),
            ):
                st.markdown(f"**Purpose:** {phase.purpose}")
                st.markdown(
                    f"**Quality emphasis:** {phase.quality_emphasis}"
                )

                if phase.athlete_evidence:
                    st.markdown("**Why this suits this athlete:**")
                    for evidence in phase.athlete_evidence:
                        st.markdown(f"- {evidence}")
                else:
                    st.caption(
                        "Personal evidence is still building for this phase; "
                        "PP is using the goal's physiological demands conservatively."
                    )

        st.info(
            "Nothing on this preview changes the live prescription yet. "
            "The next step is to connect current weakness, readiness and completed-session "
            "response before PP is allowed to adapt the live rolling plan."
        )

    st.markdown("## 📅 Adaptive Weekly Plan Preview")

    weekly_plan = build_adaptive_weekly_plan(athlete_id)

    if not weekly_plan.available:
        st.info(weekly_plan.summary)
    else:
        st.write(weekly_plan.summary)
        st.caption(
            "This is the first full calendar-style preview. It remains advisory "
            "until we are happy with the progression and readiness logic."
        )

        rhythm = st.columns(4, gap="small")
        rhythm[0].metric("Quality day 1", weekly_plan.quality_days[0])
        rhythm[1].metric("Quality day 2", weekly_plan.quality_days[1])
        rhythm[2].metric("Long run", weekly_plan.long_run_day or "—")
        rhythm[3].metric("Rest", weekly_plan.rest_day or "—")

        for week in weekly_plan.weeks:
            with st.expander(
                f"Week {week.week_number} · {week.phase_name} · {week.theme}",
                expanded=(week.week_number == 1),
            ):
                for day in week.days:
                    st.markdown(
                        f"**{day.day_name} — {day.title}**  \n"
                        f"{day.prescription}"
                    )
                    if day.target:
                        st.caption(f"Target: {day.target}")
                    st.caption(
                        f"Why: {day.purpose} · Evidence: {day.evidence}"
                    )

    st.markdown("## Guardrails")

    for limitation in profile.limitations:
        st.caption(f"• {limitation}")

    st.info(
        "Learning Engine v1 is deliberately observation-only. We'll inspect "
        "what it has learned about the real athletes before allowing it to "
        "change Recommended Next Run or Today's Session."
    )
