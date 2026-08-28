"""Athlete-facing Activity Review screen."""

from __future__ import annotations

import datetime
import html
import textwrap

import streamlit as st

from core.activity_review import (
    ActivityListItem,
    ActivityReview,
    build_activity_review,
    list_review_activities,
)
from core.workout_coach import (
    WorkoutCoachReview,
    build_workout_coach_review,
)
from core.database import (
    clear_activity_override,
    get_activity_overrides,
    get_connection,
    save_activity_override,
)
from ui.activity_navigation import (
    clear_activity_review_params,
    read_activity_review_request,
)
from ui import athlete_selection
from ui.athlete_selection import render_athlete_selector
from ui.training_coach_navigation import training_coach_url


WINDOWS = {
    "Last 90 days": 90,
    "Last 12 months": 365,
    "All time": None,
}


def _apply_home_activity_request() -> None:
    """Preselect a linked Home activity once, then return control to the UI."""
    request = read_activity_review_request(st.query_params)
    if request is None:
        return

    athletes = athlete_selection.get_athletes()
    row = next(
        (item for item in athletes if int(item[0]) == request.athlete_id),
        None,
    )
    if row is not None:
        selected_name = athlete_selection.athlete_name(row)
        st.session_state[athlete_selection.SESSION_ID_KEY] = request.athlete_id
        st.session_state[athlete_selection.SESSION_NAME_KEY] = selected_name
        st.session_state["activity_review_athlete"] = selected_name
        # v0.24.0 briefly used a second Home widget state. Remove any stale
        # value so production Home has one canonical athlete source again.
        st.session_state.pop("production_home_athlete_selector", None)

        if request.activity_id is not None:
            # Best Runs may be older than the current activity-history window.
            st.session_state["activity_review_window"] = "All time"
            st.session_state["activity_review_activity_id"] = request.activity_id

    clear_activity_review_params(st.query_params)


def _safe(value) -> str:
    return html.escape(str(value if value is not None else ""))


def _html(markup: str) -> None:
    st.html(textwrap.dedent(markup).strip())


def _data_version() -> tuple[int, int]:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        "SELECT COUNT(*), COALESCE(MAX(id), 0) FROM activities"
    )
    version = cursor.fetchone()
    connection.close()
    return int(version[0]), int(version[1])


@st.cache_data(show_spinner=False)
def _cached_activity_items(
    athlete_id: int,
    since_iso: str | None,
    data_version: tuple[int, int],
) -> tuple[ActivityListItem, ...]:
    del data_version
    since = (
        datetime.date.fromisoformat(since_iso)
        if since_iso
        else None
    )
    return list_review_activities(athlete_id, since=since)


@st.cache_data(show_spinner=False)
def _cached_review(
    athlete_id: int,
    activity_id: int,
    data_version: tuple[int, int],
) -> ActivityReview | None:
    del data_version
    return build_activity_review(athlete_id, activity_id)


@st.cache_data(ttl=900, show_spinner=False)
def _cached_workout_coach(
    athlete_id: int,
    activity_id: int,
    data_version: tuple[int, int],
    today_iso: str,
) -> WorkoutCoachReview | None:
    del data_version
    return build_workout_coach_review(
        athlete_id,
        activity_id,
        today=datetime.date.fromisoformat(today_iso),
    )


def _date_text(value: str | None) -> str:
    if not value:
        return "Date unavailable"
    try:
        parsed = datetime.date.fromisoformat(str(value)[:10])
        return parsed.strftime("%a %-d %b %Y")
    except (TypeError, ValueError):
        return str(value)


def _duration(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    total = max(int(round(seconds)), 0)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _pace_value(seconds_per_km: float | None) -> str:
    if seconds_per_km is None:
        return "—"

    def pace(seconds):
        minutes = int(seconds // 60)
        remaining = int(round(seconds % 60))
        if remaining == 60:
            minutes += 1
            remaining = 0
        return f"{minutes}:{remaining:02d}"

    return f"{pace(seconds_per_km * 1.609344)}/mi"


def _pace_context(seconds_per_km: float | None) -> str:
    if seconds_per_km is None:
        return "Pace not used"
    minutes = int(seconds_per_km // 60)
    remaining = int(round(seconds_per_km % 60))
    if remaining == 60:
        minutes += 1
        remaining = 0
    return f"{minutes}:{remaining:02d}/km"


def _distance_value(distance_km: float | None) -> tuple[str, str]:
    if distance_km is None:
        return "—", "Distance unavailable"
    return f"{distance_km / 1.609344:.1f} mi", f"{distance_km:.2f} km"


def _activity_option(item: ActivityListItem) -> str:
    distance = (
        f"{item.distance_km / 1.609344:.1f} mi"
        if item.distance_km
        else "distance unavailable"
    )
    return f"{_date_text(item.activity_date)} · {item.title} · {distance}"


def _status_class(review: ActivityReview) -> str:
    if review.classification_confidence >= 0.80:
        return "is-good"
    if review.classification_confidence >= 0.65:
        return "is-moderate"
    return "is-review"


def _session_display_label(review: ActivityReview) -> str:
    if (
        review.classification_confidence < 0.70
        and review.session_type in {"race", "structured_workout"}
    ):
        return f"Possible {review.session_label.lower()}"
    return review.session_label


def _header_html(review: ActivityReview) -> str:
    route = f" · {_safe(review.route_name)}" if review.route_name else ""
    status = _status_class(review)
    session_label = _session_display_label(review)
    return f"""
        <section class="ar-header">
            <div>
                <div class="ar-kicker">ACTIVITY REVIEW · {_safe(_date_text(review.activity_date))}{route}</div>
                <h1>{_safe(review.title)}</h1>
                <div class="ar-header-meta">
                    {_safe(review.purpose_label)} · {_safe(review.source or 'Imported activity')}
                </div>
            </div>
            <div class="ar-session-badge {status}">
                <span>{_safe(session_label)}</span>
                <strong>{review.classification_confidence:.0%}</strong>
                <small>{_safe(review.confidence_label)}</small>
            </div>
        </section>
    """


def build_workout_coach_hero_html(detail: WorkoutCoachReview) -> str:
    review = detail.activity
    status = _status_class(review)
    prediction = detail.prediction
    execution = (
        f" · execution {prediction.execution_score:.0f}/100"
        if prediction.execution_score is not None else ""
    )
    return f"""
        <section class="wc-hero">
            <div class="wc-hero-main">
                <div class="wc-kicker"><i>WC</i> YOUR WORKOUT COACH · {_safe(_date_text(review.activity_date))}</div>
                <h1>{_safe(review.title)}</h1>
                <p class="wc-hero-purpose">{_safe(review.coaching_headline)}</p>
                <p class="wc-hero-copy">{_safe(review.coaching_detail)}</p>
                <div class="wc-hero-meta">
                    <span>{_safe(review.purpose_label)}</span>
                    <span>{_safe(review.route_name or 'Route unavailable')}</span>
                    <span>{_safe(review.source or 'Imported activity')}</span>
                </div>
            </div>
            <aside class="wc-hero-verdict">
                <div class="wc-verdict-label">RECOGNISED PURPOSE</div>
                <strong>{_safe(_session_display_label(review))}</strong>
                <div class="wc-confidence {status}">{review.classification_confidence:.0%} · {_safe(review.confidence_label)}</div>
                <div class="wc-verdict-rule"></div>
                <div class="wc-verdict-label">PREDICTION STATUS</div>
                <b>{_safe(prediction.headline)}</b>
                <small>{prediction.confidence:.0%} evidence confidence{_safe(execution)}</small>
            </aside>
        </section>
    """


def build_plan_execution_html(detail: WorkoutCoachReview) -> str:
    plan = detail.plan
    alignment_class = f"is-{plan.alignment}"
    source = " · ".join(
        value for value in (plan.block_name, plan.week_label) if value
    ) or "No saved plan for this date"
    return f"""
        <section class="wc-section wc-plan">
            <div class="wc-section-head">
                <div><div class="wc-section-kicker">PLAN → PERFORMANCE</div><h2>Did the run deliver its intended purpose?</h2></div>
                <span class="wc-alignment {alignment_class}">{_safe(plan.alignment_label)}</span>
            </div>
            <div class="wc-plan-grid">
                <article>
                    <div class="wc-card-label">PLANNED</div>
                    <strong>{_safe(plan.planned_title)}</strong>
                    <p>{_safe(plan.planned_detail)}</p>
                </article>
                <div class="wc-plan-arrow">→</div>
                <article class="is-performed">
                    <div class="wc-card-label">PERFORMED</div>
                    <strong>{_safe(plan.performed_title)}</strong>
                    <p>{_safe(review_summary(detail.activity))}</p>
                </article>
            </div>
            <div class="wc-plan-note"><strong>{_safe(source)}</strong><span>{_safe(plan.detail)}</span></div>
        </section>
    """


def review_summary(review: ActivityReview) -> str:
    if review.workout_description and review.session_type == "structured_workout":
        return review.workout_description
    distance, _context = _distance_value(review.distance_km)
    pace = _pace_value(review.pace_s_per_km)
    return f"{distance} · {pace} · {review.purpose_label}"


def _zone_cards(detail: WorkoutCoachReview) -> str:
    if not detail.heart_rate.zones:
        return '<div class="wc-empty">LT1 and LT2 are not available for this athlete yet.</div>'
    return "".join(
        f"""
        <article class="wc-zone {'is-current' if zone.is_current else ''}">
            <div class="wc-card-label">{_safe(zone.label)}</div>
            <strong>{_safe(zone.range_text)}</strong>
            <p>{_safe(zone.purpose)}</p>
            {'<span>WHOLE-RUN AVERAGE</span>' if zone.is_current else ''}
        </article>
        """
        for zone in detail.heart_rate.zones
    )


def build_workout_intelligence_html(detail: WorkoutCoachReview) -> str:
    heart_rate = detail.heart_rate
    prediction = detail.prediction
    coaches = " · ".join(prediction.coaches) or "Context only"
    return f"""
        <div class="wc-intelligence-grid">
            <section class="wc-section wc-zones">
                <div class="wc-section-kicker">PERSONAL EFFORT CONTEXT</div>
                <h2>{_safe(heart_rate.current_label)}</h2>
                <p class="wc-intro">{_safe(heart_rate.current_detail)}</p>
                <div class="wc-zone-grid">{_zone_cards(detail)}</div>
                <div class="wc-audit">LT1/LT2 source: {_safe(heart_rate.source)}. These are coaching boundaries, not a medical assessment.</div>
            </section>
            <section class="wc-prediction is-{_safe(prediction.status)}">
                <div class="wc-section-kicker">WHAT CHANGES IN THE COACHING TEAM?</div>
                <h2>{_safe(prediction.headline)}</h2>
                <p>{_safe(prediction.detail)}</p>
                <div class="wc-prediction-footer"><span>USED BY</span><strong>{_safe(coaches)}</strong><em>{prediction.confidence:.0%} confidence</em></div>
            </section>
        </div>
    """


def build_workout_direction_html(detail: WorkoutCoachReview) -> str:
    direction = detail.next_direction
    link = html.escape(training_coach_url(detail.athlete_id), quote=True)
    return f"""
        <section class="wc-direction">
            <div class="wc-direction-mark">LC</div>
            <div>
                <div class="wc-section-kicker">LEAD COACH · WHAT HAPPENS NEXT</div>
                <h2>{_safe(direction.timing)} · {_safe(direction.title)}</h2>
                <p>{_safe(direction.detail)}</p>
                <small>{_safe(direction.caveat)}</small>
            </div>
            <a href="{link}" target="_self">Open Training Coach →</a>
        </section>
    """


def _metric_html(label: str, value: str, context: str) -> str:
    return f"""
        <div class="ar-metric">
            <div class="ar-label">{_safe(label)}</div>
            <div class="ar-metric-value">{_safe(value)}</div>
            <div class="ar-metric-context">{_safe(context)}</div>
        </div>
    """


def build_activity_overview_html(review: ActivityReview) -> str:
    distance_value, distance_context = _distance_value(review.distance_km)
    hr_context = (
        f"Max {review.max_hr:.0f} bpm"
        if review.max_hr is not None
        else "Maximum unavailable"
    )
    continuity_context = (
        f"{review.moving_percent:.1f}% moving"
        if review.moving_percent is not None
        else "Continuity unavailable"
    )
    metrics = "".join(
        (
            _metric_html("Distance", distance_value, distance_context),
            _metric_html("Moving time", _duration(review.moving_time_s), f"Elapsed {_duration(review.elapsed_time_s)}"),
            _metric_html("Moving pace", _pace_value(review.pace_s_per_km), _pace_context(review.pace_s_per_km)),
            _metric_html("Heart rate", f"{review.avg_hr:.0f} bpm" if review.avg_hr is not None else "—", hr_context),
            _metric_html("Stopped time", _duration(review.stopped_time_s), continuity_context),
        )
    )
    return f'<div class="ar-metric-grid">{metrics}</div>'


def _score_html(review: ActivityReview) -> str:
    cards = []
    for score in review.scores:
        winner = " is-winner" if score.winner else ""
        cards.append(
            f"""
            <div class="ar-score{winner}">
                <div class="ar-score-top">
                    <span>{_safe(score.label)}</span><strong>{score.score:.0f}</strong>
                </div>
                <div class="ar-score-track"><i style="width:{max(0, min(score.score, 100)):.1f}%"></i></div>
            </div>
            """
        )
    return "".join(cards)


def _comparison_html(review: ActivityReview) -> str:
    comparison = review.comparison
    if comparison is None:
        return f"""
            <div class="ar-comparison-empty">
                <div class="ar-label">ATHLETE-RELATIVE COMPARISON</div>
                <strong>No pace ranking applied</strong>
                <p>{_safe(review.reliability_detail)}</p>
            </div>
        """

    provisional = (
        '<span class="ar-mini-badge is-warn">PROVISIONAL</span>'
        if comparison.provisional
        else '<span class="ar-mini-badge">COMPARABLE</span>'
    )
    adjusted = ""
    if abs(comparison.adjustment_s_per_km) >= 0.5:
        adjusted = (
            f"Conditions-adjusted pace {_pace_context(comparison.adjusted_pace_s_per_km)}"
        )
    else:
        adjusted = "No material conditions adjustment"

    return f"""
        <div class="ar-comparison">
            <div class="ar-comparison-top">
                <div>
                    <div class="ar-label">ATHLETE-RELATIVE COMPARISON</div>
                    <div class="ar-comparison-category">{_safe(comparison.category)}</div>
                </div>
                {provisional}
            </div>
            <div class="ar-rank-line">
                <strong>#{comparison.rank}</strong>
                <span>of {comparison.total} comparable sessions</span>
            </div>
            <div class="ar-top-percent">Top {comparison.top_percent:.0f}% of your history</div>
            <p>{_safe(comparison.detail)}</p>
            <div class="ar-footnote">{_safe(adjusted)} · Evidence {comparison.confidence:.0%}</div>
            <div class="ar-footnote">{_safe(comparison.basis_detail)}</div>
        </div>
    """


def build_activity_verdict_html(review: ActivityReview) -> str:
    return f"""
        <div class="ar-two-col ar-verdict-row">
            <section class="ar-panel">
                <div class="ar-panel-head">
                    <div>
                        <div class="ar-label">HOW IT WAS CLASSIFIED</div>
                <h2>{_safe(_session_display_label(review))}</h2>
                    </div>
                    <span class="ar-mini-badge">{review.classification_confidence:.0%} CONFIDENCE</span>
                </div>
                <p>{_safe(review.classification_summary)}</p>
                <div class="ar-score-grid">{_score_html(review)}</div>
                <div class="ar-trust-line">
                    <strong>{_safe(review.reliability_label)}</strong>
                    <span>{_safe(review.reliability_detail)}</span>
                </div>
            </section>
            <section class="ar-panel ar-comparison-panel">
                {_comparison_html(review)}
            </section>
        </div>
    """


def _condition_items(review: ActivityReview) -> str:
    conditions = [
        ("Temperature", f"{review.temperature_c:.0f}°C" if review.temperature_c is not None else "—"),
        ("Humidity", f"{review.humidity:.0f}%" if review.humidity is not None else "—"),
        ("Wind", f"{review.wind_speed:.0f} km/h" if review.wind_speed is not None else "—"),
        ("Climbing", f"{review.elevation_up_m:.0f} m" if review.elevation_up_m is not None else "—"),
    ]
    return "".join(
        f'<div><span>{_safe(label)}</span><strong>{_safe(value)}</strong></div>'
        for label, value in conditions
    )


def build_activity_detail_html(review: ActivityReview) -> str:
    if review.split_count:
        if review.session_type == "structured_workout":
            structure_value = (
                f"{sum(1 for split in review.splits if split.role == 'Work')} work · "
                f"{review.recovery_count} recovery"
            )
        else:
            structure_value = f"{review.split_count} recorded laps"
        structure_detail = " ".join(review.structure_notes)
    else:
        structure_value = "No split structure"
        structure_detail = review.structure_notes[0]

    confidence = (
        f" · decoder confidence {review.workout_confidence:.0%}"
        if review.workout_confidence is not None
        and review.session_type == "structured_workout"
        else ""
    )

    return f"""
        <div class="ar-two-col ar-detail-row">
            <section class="ar-panel">
                <div class="ar-label">STRUCTURE & CONTINUITY</div>
                <h2>{_safe(structure_value)}</h2>
                <p>{_safe(structure_detail)}</p>
                <div class="ar-structure-strip">
                    <div><span>Boundaries</span><strong>{review.boundary_count}</strong></div>
                    <div><span>Likely stopped recoveries</span><strong>{review.unknown_recovery_count}</strong></div>
                    <div><span>Moving share</span><strong>{f'{review.moving_percent:.1f}%' if review.moving_percent is not None else '—'}</strong></div>
                </div>
                <div class="ar-footnote">Source laps: {review.split_count}{_safe(confidence)}</div>
            </section>
            <section class="ar-panel">
                <div class="ar-label">CONDITIONS & TERRAIN</div>
                <h2>{_safe(review.route_name or 'Route unavailable')}</h2>
                <div class="ar-condition-grid">{_condition_items(review)}</div>
                <p>Conditions are shown beside the judgement. Only supported adjustments enter the comparable-session result.</p>
            </section>
        </div>
    """


def build_coaching_html(review: ActivityReview) -> str:
    return f"""
        <section class="ar-coaching">
            <div class="ar-label">WHAT THIS RUN GAVE YOU</div>
            <div class="ar-coaching-grid">
                <div>
                    <h2>{_safe(review.coaching_headline)}</h2>
                    <p>{_safe(review.coaching_detail)}</p>
                </div>
                <div class="ar-benefit">
                    <span>TRAINING VALUE</span>
                    <strong>{_safe(review.coaching_benefit)}</strong>
                </div>
            </div>
        </section>
    """


def _split_table_html(review: ActivityReview) -> str:
    rows = []
    for split in review.splits:
        role_class = split.role.lower().replace("-", "")
        rows.append(
            f"""
            <div class="ar-split-row">
                <span>{split.index}</span>
                <strong class="role-{_safe(role_class)}">{_safe(split.role)}</strong>
                <span>{split.distance_km:.3f} km</span>
                <span>{_duration(split.duration_s)}</span>
                <span>{_pace_context(split.pace_s_per_km)}</span>
            </div>
            """
        )
    return f"""
        <div class="ar-split-table">
            <div class="ar-split-head">
                <span>#</span><span>Role</span><span>Distance</span><span>Time</span><span>Pace</span>
            </div>
            {''.join(rows)}
        </div>
    """


def _reasoning(review: ActivityReview) -> None:
    with st.expander("Classification evidence"):
        for score in review.scores:
            st.markdown(f"**{score.label} — {score.score:.0f}/100**")
            if score.reasons:
                for reason in score.reasons:
                    st.write(f"• {reason}")
            else:
                st.write("• No supporting reason was recorded.")


def _inject_activity_styles() -> None:
    st.markdown(
        """
        <style>
            [data-testid="stMainBlockContainer"] { max-width:1450px; }
            .wc-hero { display:grid; grid-template-columns:minmax(0,1.55fr) minmax(300px,.45fr); overflow:hidden; margin-top:8px; color:#fff!important; background:linear-gradient(135deg,#0b2942,#0d3f53); border:1px solid #214e62; border-radius:24px; box-shadow:0 18px 45px rgba(16,38,61,.14); }
            .wc-hero * { box-sizing:border-box; }
            .wc-hero-main { min-height:320px; padding:34px 38px; background:radial-gradient(circle at 92% 4%,rgba(99,182,142,.18),transparent 33%); }
            .wc-kicker,.wc-section-kicker { display:flex; align-items:center; gap:10px; color:#63d0a1; font-size:12px; font-weight:800; letter-spacing:.13em; text-transform:uppercase; }
            .wc-kicker i { display:inline-grid; place-items:center; width:39px; height:39px; color:#fff; background:#f05a28; border-radius:11px; font-style:normal; font-size:13px; letter-spacing:0; }
            .wc-hero h1 { margin:22px 0 0; color:#fff!important; font-size:clamp(38px,4.4vw,64px); line-height:.98; letter-spacing:-.052em; }
            .wc-hero-purpose { margin:20px 0 0; color:#fff!important; font-size:clamp(19px,2vw,28px); font-weight:650; line-height:1.15; }
            .wc-hero-copy { max-width:820px; margin:12px 0 0; color:#cfdae2!important; font-size:16px; line-height:1.55; }
            .wc-hero-meta { display:flex; flex-wrap:wrap; gap:9px; margin-top:24px; }
            .wc-hero-meta span { padding:7px 11px; color:#e5edf2!important; background:rgba(255,255,255,.08); border:1px solid rgba(255,255,255,.13); border-radius:999px; font-size:12px; font-weight:650; }
            .wc-hero-verdict { display:flex; flex-direction:column; justify-content:center; padding:30px; color:#10263d!important; background:#fffaf3; }
            .wc-verdict-label,.wc-card-label { color:#7b8791; font-size:11px; font-weight:820; letter-spacing:.1em; text-transform:uppercase; }
            .wc-hero-verdict > strong { margin-top:8px; color:#10263d!important; font-size:25px; line-height:1.1; }
            .wc-confidence { margin-top:9px; color:#3e8e72!important; font-size:13px; font-weight:750; }
            .wc-confidence.is-moderate { color:#ad6a14!important; }
            .wc-confidence.is-review { color:#d94d22!important; }
            .wc-verdict-rule { height:1px; margin:25px 0; background:#e7e1d8; }
            .wc-hero-verdict b { margin-top:8px; color:#10263d!important; font-size:18px; line-height:1.25; }
            .wc-hero-verdict small { margin-top:9px; color:#687581!important; font-size:12px; font-weight:650; }
            .wc-section { margin-top:10px; padding:24px 27px; background:#fff; border:1px solid #e7e1d8; border-radius:19px; box-shadow:0 7px 24px rgba(16,38,61,.04); }
            .wc-section-head { display:flex; justify-content:space-between; align-items:flex-start; gap:18px; }
            .wc-section-kicker { color:#3e8e72; }
            .wc-section h2,.wc-prediction h2,.wc-direction h2 { margin:7px 0 0; color:#10263d!important; font-size:clamp(22px,2.4vw,32px); line-height:1.08; letter-spacing:-.035em; }
            .wc-alignment { display:inline-flex; padding:7px 10px; color:#3e8e72; background:#eaf6ef; border-radius:999px; font-size:12px; font-weight:800; white-space:nowrap; }
            .wc-alignment.is-different,.wc-alignment.is-extra { color:#b55d19; background:#fff0e8; }
            .wc-alignment.is-unplanned { color:#687581; background:#f1eee8; }
            .wc-plan-grid { display:grid; grid-template-columns:minmax(0,1fr) 42px minmax(0,1fr); gap:12px; align-items:stretch; margin-top:19px; }
            .wc-plan-grid article { padding:18px; background:#f8f5ef; border:1px solid #ece5da; border-radius:14px; }
            .wc-plan-grid article.is-performed { background:#f1f8f5; border-color:#cde5da; }
            .wc-plan-grid strong { display:block; margin-top:7px; color:#10263d; font-size:20px; line-height:1.15; }
            .wc-plan-grid p,.wc-intro,.wc-prediction p,.wc-direction p { margin:8px 0 0; color:#687581; font-size:14px; line-height:1.5; }
            .wc-plan-arrow { display:grid; place-items:center; color:#f05a28; font-size:26px; font-weight:500; }
            .wc-plan-note { display:grid; grid-template-columns:minmax(180px,.35fr) 1fr; gap:18px; margin-top:16px; padding-top:14px; border-top:1px solid #eee8df; }
            .wc-plan-note strong { color:#10263d; font-size:13px; }
            .wc-plan-note span { color:#687581; font-size:13px; line-height:1.45; }
            .wc-intelligence-grid { display:grid; grid-template-columns:minmax(0,1.35fr) minmax(320px,.65fr); gap:10px; }
            .wc-zone-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:9px; margin-top:18px; }
            .wc-zone { position:relative; min-height:130px; padding:15px; background:#f8f5ef; border:1px solid #ece5da; border-radius:13px; }
            .wc-zone.is-current { background:#eaf6ef; border-color:#a9d8c3; box-shadow:inset 0 3px 0 #3e8e72; }
            .wc-zone strong { display:block; margin-top:7px; color:#10263d; font-size:18px; }
            .wc-zone p { margin:6px 0 0; color:#687581; font-size:12px; line-height:1.4; }
            .wc-zone span { display:inline-block; margin-top:9px; color:#3e8e72; font-size:9px; font-weight:850; letter-spacing:.06em; }
            .wc-audit { margin-top:13px; color:#7b8791; font-size:11px; line-height:1.45; }
            .wc-empty { margin-top:15px; padding:18px; color:#687581; background:#f8f5ef; border-radius:12px; font-size:13px; }
            .wc-prediction { margin-top:10px; padding:27px; color:#fff!important; background:linear-gradient(145deg,#0b2942,#0d3f53); border:1px solid #214e62; border-radius:19px; box-shadow:0 9px 26px rgba(16,38,61,.10); }
            .wc-prediction .wc-section-kicker { color:#63d0a1!important; }
            .wc-prediction h2 { color:#fff!important; }
            .wc-prediction p { color:#d1dce3!important; font-size:15px; }
            .wc-prediction-footer { display:grid; grid-template-columns:1fr; gap:4px; margin-top:25px; padding-top:18px; border-top:1px solid rgba(255,255,255,.16); }
            .wc-prediction-footer span { color:#8fa7b6!important; font-size:10px; font-weight:800; letter-spacing:.1em; }
            .wc-prediction-footer strong { color:#fff!important; font-size:15px; }
            .wc-prediction-footer em { margin-top:4px; color:#63d0a1!important; font-size:12px; font-style:normal; font-weight:750; }
            .wc-direction { display:grid; grid-template-columns:auto 1fr auto; gap:20px; align-items:center; margin-top:10px; padding:23px 27px; background:linear-gradient(90deg,#fff0e8,#fff 68%); border:1px solid #f0d4c6; border-left:4px solid #f05a28; border-radius:18px; }
            .wc-direction-mark { display:grid; place-items:center; width:56px; height:56px; color:#fff; background:#10263d; border-radius:15px; font-size:14px; font-weight:800; }
            .wc-direction small { display:block; margin-top:8px; color:#7b8791; font-size:11px; line-height:1.4; }
            .wc-direction a { display:inline-flex; padding:12px 16px; color:#fff!important; background:#10263d; border-radius:11px; text-decoration:none!important; font-size:13px; font-weight:800; white-space:nowrap; }
            .wc-review-divider { display:flex; align-items:center; gap:13px; margin:25px 3px 7px; color:#687581; font-size:11px; font-weight:850; letter-spacing:.12em; }
            .wc-review-divider::before { content:""; width:31px; height:3px; background:#f05a28; border-radius:999px; }
            .ar-header { display:flex; justify-content:space-between; align-items:flex-start; gap:24px; padding:18px 20px; background:#fff; border:1px solid #e7e1d8; border-radius:18px; box-shadow:0 7px 22px rgba(16,38,61,.045); }
            .ar-kicker,.ar-label { color:#7b8791; font-size:11px; font-weight:800; letter-spacing:.11em; text-transform:uppercase; }
            .ar-header h1 { margin:5px 0 0; color:#10263d!important; font-size:clamp(24px,3vw,36px); line-height:1.05; letter-spacing:-.035em; }
            .ar-header-meta { margin-top:7px; color:#687581; font-size:12px; font-weight:650; }
            .ar-session-badge { min-width:170px; padding:10px 12px; text-align:right; color:#10263d; background:#eef6f2; border:1px solid #cce4d8; border-radius:13px; }
            .ar-session-badge span,.ar-session-badge strong,.ar-session-badge small { display:block; }
            .ar-session-badge span { font-size:11px; font-weight:800; text-transform:uppercase; letter-spacing:.06em; }
            .ar-session-badge strong { margin-top:2px; color:#3e8e72; font-size:21px; line-height:1; }
            .ar-session-badge small { margin-top:3px; color:#687581; font-size:10px; font-weight:700; }
            .ar-session-badge.is-moderate { background:#fff5e4; border-color:#efdab5; }
            .ar-session-badge.is-moderate strong { color:#b86d08; }
            .ar-session-badge.is-review { background:#fff0e8; border-color:#f4cdbd; }
            .ar-session-badge.is-review strong { color:#f05a28; }
            .ar-metric-grid { display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:8px; margin-top:8px; }
            .ar-metric { padding:12px 13px; background:#fff; border:1px solid #e7e1d8; border-radius:14px; }
            .ar-metric-value { margin-top:5px; color:#10263d; font-size:20px; font-weight:820; letter-spacing:-.035em; }
            .ar-metric-context { margin-top:2px; color:#687581; font-size:11px; font-weight:600; }
            .ar-two-col { display:grid; grid-template-columns:minmax(0,1.25fr) minmax(340px,.75fr); gap:8px; margin-top:8px; }
            .ar-panel { padding:15px 16px; background:#fff; border:1px solid #e7e1d8; border-radius:16px; box-shadow:0 5px 18px rgba(16,38,61,.035); }
            .ar-panel-head,.ar-comparison-top { display:flex; justify-content:space-between; align-items:flex-start; gap:15px; }
            .ar-panel h2,.ar-coaching h2 { margin:5px 0 0; color:#10263d!important; font-size:18px; line-height:1.15; letter-spacing:-.025em; }
            .ar-panel p,.ar-coaching p,.ar-comparison-empty p { margin:7px 0 0; color:#687581; font-size:13px; line-height:1.5; }
            .ar-mini-badge { display:inline-flex; padding:4px 7px; color:#3e8e72; background:#eaf6ef; border-radius:999px; font-size:10px; font-weight:800; letter-spacing:.04em; white-space:nowrap; }
            .ar-mini-badge.is-warn { color:#b86d08; background:#fff5e4; }
            .ar-score-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:7px; margin-top:12px; }
            .ar-score { padding:8px 9px; background:#f7f3ec; border:1px solid transparent; border-radius:10px; }
            .ar-score.is-winner { background:#fff0e8; border-color:#f4cdbd; }
            .ar-score-top { display:flex; justify-content:space-between; color:#687581; font-size:10px; font-weight:750; }
            .ar-score-top strong { color:#10263d; font-size:12px; }
            .ar-score-track { height:4px; margin-top:6px; overflow:hidden; background:#e6e0d7; border-radius:999px; }
            .ar-score-track i { display:block; height:100%; background:#9aa6ae; border-radius:999px; }
            .ar-score.is-winner .ar-score-track i { background:#f05a28; }
            .ar-trust-line { display:grid; grid-template-columns:145px 1fr; gap:10px; margin-top:12px; padding-top:10px; border-top:1px solid #ece6dd; }
            .ar-trust-line strong { color:#10263d; font-size:11px; }
            .ar-trust-line span { color:#687581; font-size:11px; line-height:1.4; }
            .ar-comparison-panel { background:linear-gradient(135deg,#10263d,#14354f); border-color:#10263d; }
            .ar-comparison-panel .ar-label,.ar-comparison-panel p,.ar-comparison-panel .ar-footnote { color:#c7d2dc!important; }
            .ar-comparison-category { margin-top:4px; color:#fff!important; font-size:15px; font-weight:760; }
            .ar-rank-line { display:flex; align-items:baseline; gap:8px; margin-top:10px; color:#fff!important; }
            .ar-rank-line strong { color:#63b68e; font-size:31px; line-height:1; letter-spacing:-.04em; }
            .ar-rank-line span { color:#e5ecf0!important; font-size:11px; font-weight:700; }
            .ar-top-percent { margin-top:4px; color:#fff!important; font-size:14px; font-weight:780; }
            .ar-comparison-empty strong { display:block; margin-top:7px; color:#fff!important; font-size:18px; }
            .ar-footnote { margin-top:9px; color:#7b8791; font-size:10px; font-weight:650; }
            .ar-structure-strip,.ar-condition-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:7px; margin-top:12px; }
            .ar-condition-grid { grid-template-columns:repeat(4,1fr); }
            .ar-structure-strip div,.ar-condition-grid div { padding:8px; background:#f7f3ec; border-radius:9px; }
            .ar-structure-strip span,.ar-condition-grid span { display:block; color:#7b8791; font-size:10px; font-weight:700; }
            .ar-structure-strip strong,.ar-condition-grid strong { display:block; margin-top:3px; color:#10263d; font-size:13px; }
            .ar-coaching { margin-top:8px; padding:15px 17px; background:linear-gradient(90deg,#fff0e8,#fff 65%); border:1px solid #f1d8cc; border-left:4px solid #f05a28; border-radius:16px; }
            .ar-coaching-grid { display:grid; grid-template-columns:1.4fr .6fr; gap:22px; align-items:center; }
            .ar-benefit { padding-left:16px; border-left:1px solid #ecdcd3; }
            .ar-benefit span { display:block; color:#f05a28; font-size:10px; font-weight:850; letter-spacing:.08em; }
            .ar-benefit strong { display:block; margin-top:4px; color:#10263d; font-size:12px; line-height:1.4; }
            .ar-split-table { overflow:hidden; border:1px solid #e7e1d8; border-radius:12px; }
            .ar-split-head,.ar-split-row { display:grid; grid-template-columns:45px 110px 1fr 1fr 1fr; gap:8px; padding:8px 10px; align-items:center; }
            .ar-split-head { color:#7b8791; background:#f7f3ec; font-size:10px; font-weight:800; text-transform:uppercase; letter-spacing:.05em; }
            .ar-split-row { color:#687581; font-size:11px; border-top:1px solid #eee8df; }
            .ar-split-row strong { color:#10263d; }
            .ar-split-row .role-work { color:#f05a28; }
            .ar-split-row .role-recovery { color:#3e8e72; }
            .ar-split-row .role-boundary { color:#9a7b69; }
            @media (max-width:900px) {
                .wc-hero,.wc-intelligence-grid { grid-template-columns:1fr; }
                .wc-hero-main { min-height:auto; }
                .wc-plan-grid { grid-template-columns:1fr; }
                .wc-plan-arrow { transform:rotate(90deg); }
                .wc-direction { grid-template-columns:auto 1fr; }
                .wc-direction a { grid-column:1/-1; justify-content:center; }
                .ar-header { flex-direction:column; }
                .ar-session-badge { width:100%; text-align:left; }
                .ar-metric-grid { grid-template-columns:repeat(2,1fr); }
                .ar-two-col { grid-template-columns:1fr; }
                .ar-coaching-grid { grid-template-columns:1fr; }
                .ar-benefit { padding:10px 0 0; border-left:0; border-top:1px solid #ecdcd3; }
            }
            @media (max-width:560px) {
                .wc-hero-main,.wc-hero-verdict,.wc-section,.wc-prediction,.wc-direction { padding:20px; }
                .wc-zone-grid { grid-template-columns:1fr; }
                .wc-plan-note { grid-template-columns:1fr; gap:6px; }
                .wc-section-head { flex-direction:column; }
                .ar-metric-grid,.ar-score-grid { grid-template-columns:1fr 1fr; }
                .ar-trust-line { grid-template-columns:1fr; }
                .ar-condition-grid { grid-template-columns:1fr 1fr; }
                .ar-split-head,.ar-split-row { grid-template-columns:32px 85px 1fr 1fr; }
                .ar-split-head span:last-child,.ar-split-row span:last-child { display:none; }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def show_activities_page() -> None:
    _apply_home_activity_request()
    _inject_activity_styles()

    _html(
        """
        <div class="pp-page-header">
            <div class="pp-page-eyebrow">Your completed-run coaching</div>
            <div class="pp-page-title">Workout Coach</div>
            <div class="pp-page-intro">
                What did this run deliver, how trustworthy is the evidence,
                and what should happen next? Plan, performance, zones and
                prediction impact stay separate so the review remains honest.
            </div>
        </div>
        """
    )

    athlete_col, window_col = st.columns([2, 1], gap="small")
    with athlete_col:
        athlete_id = render_athlete_selector(
            key="activity_review_athlete",
            label="Runner",
        )
    with window_col:
        selected_window = st.selectbox(
            "Activity history",
            list(WINDOWS),
            key="activity_review_window",
        )

    if athlete_id is None:
        st.info("Add an athlete before reviewing activities.")
        return

    days = WINDOWS[selected_window]
    since = (
        datetime.date.today() - datetime.timedelta(days=days)
        if days is not None
        else None
    )
    data_version = _data_version()
    items = _cached_activity_items(
        athlete_id,
        since.isoformat() if since else None,
        data_version,
    )

    if not items:
        st.info("No running activities are available in this window.")
        return

    options = [item.activity_id for item in items]
    labels = {item.activity_id: _activity_option(item) for item in items}
    selector_key = "activity_review_activity_id"
    if st.session_state.get(selector_key) not in options:
        st.session_state[selector_key] = options[0]

    activity_id = st.selectbox(
        "Choose an activity",
        options,
        key=selector_key,
        format_func=lambda value: labels[value],
    )

    with st.spinner("Workout Coach is reviewing this run against your plan and history…"):
        workout_coach = _cached_workout_coach(
            athlete_id,
            int(activity_id),
            data_version,
            datetime.date.today().isoformat(),
        )

    if workout_coach is None:
        st.warning("This activity is no longer available for this athlete.")
        return
    review = workout_coach.activity

    _html(build_workout_coach_hero_html(workout_coach))
    _html(build_activity_overview_html(review))
    _html(build_plan_execution_html(workout_coach))
    _html(build_workout_intelligence_html(workout_coach))
    _html(build_workout_direction_html(workout_coach))

    _html('<div class="wc-review-divider"><span>DETAILED EVIDENCE REVIEW</span></div>')
    _html(build_activity_verdict_html(review))
    _html(build_activity_detail_html(review))
    _html(build_coaching_html(review))

    override = get_activity_overrides(int(athlete_id)).get(int(activity_id), {})
    with st.expander("Coach corrections · classification and heart-rate quality"):
        st.caption(
            "Corrections belong only to this athlete and never change the imported "
            "Garmin or Runalyze activity. Clear them at any time."
        )
        intent_labels = {
            "Automatic recognition": None,
            "Easy run": "easy",
            "Easy run with strides": "easy_with_strides",
            "Easy run with pickups": "easy_with_pickups",
            "Long run": "long_run",
            "Structured workout": "workout",
            "Threshold workout": "threshold",
            "Race": "race",
        }
        existing_label = next(
            (label for label, value in intent_labels.items()
             if value == override.get("session_intent")),
            "Automatic recognition",
        )
        with st.form(f"coach_corrections_{athlete_id}_{activity_id}"):
            classification = st.selectbox(
                "How should the coaches treat this activity?",
                list(intent_labels),
                index=list(intent_labels).index(existing_label),
            )
            hr_reliable = st.checkbox(
                "Recorded heart rate is trustworthy",
                value=override.get("heart_rate_reliable") is not False,
            )
            corrected_hr = st.number_input(
                "Corrected average heart rate, if known (0 leaves it unused)",
                min_value=0,
                max_value=250,
                value=int(override.get("corrected_avg_hr") or 0),
            )
            notes = st.text_input("Optional coach note", value=override.get("notes") or "")
            save_col, clear_col = st.columns(2)
            save = save_col.form_submit_button("Save coach correction", type="primary")
            clear = clear_col.form_submit_button("Restore automatic evidence")
        if save:
            save_activity_override(
                int(athlete_id), int(activity_id),
                session_intent=intent_labels[classification],
                heart_rate_reliable=hr_reliable,
                corrected_avg_hr=corrected_hr or None,
                notes=notes.strip() or None,
            )
            st.cache_data.clear()
            st.rerun()
        if clear:
            clear_activity_override(int(athlete_id), int(activity_id))
            st.cache_data.clear()
            st.rerun()

    detail_left, detail_right = st.columns(2, gap="small")
    with detail_left:
        _reasoning(review)
    with detail_right:
        with st.expander(
            f"Recorded laps and splits ({review.split_count})"
        ):
            if review.splits:
                _html(_split_table_html(review))
            else:
                st.write("No decodable lap or split data was available.")

    if review.limitations:
        with st.expander("Evidence limits"):
            for limitation in review.limitations:
                st.write(f"• {limitation}")

    st.caption(
        "Recognition before recommendation. Corrections remain reversible. Every run has something to give."
    )
