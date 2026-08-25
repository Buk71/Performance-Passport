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
            .ar-header { display:flex; justify-content:space-between; align-items:flex-start; gap:24px; padding:18px 20px; background:#fff; border:1px solid #e7e1d8; border-radius:18px; box-shadow:0 7px 22px rgba(16,38,61,.045); }
            .ar-kicker,.ar-label { color:#7b8791; font-size:10px; font-weight:800; letter-spacing:.11em; text-transform:uppercase; }
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
            .ar-panel p,.ar-coaching p,.ar-comparison-empty p { margin:7px 0 0; color:#687581; font-size:12px; line-height:1.4; }
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
            .ar-comparison-panel .ar-label,.ar-comparison-panel p,.ar-comparison-panel .ar-footnote { color:#c7d2dc; }
            .ar-comparison-category { margin-top:4px; color:#fff; font-size:15px; font-weight:760; }
            .ar-rank-line { display:flex; align-items:baseline; gap:8px; margin-top:10px; color:#fff; }
            .ar-rank-line strong { color:#63b68e; font-size:31px; line-height:1; letter-spacing:-.04em; }
            .ar-rank-line span { color:#e5ecf0; font-size:11px; font-weight:700; }
            .ar-top-percent { margin-top:4px; color:#fff; font-size:14px; font-weight:780; }
            .ar-comparison-empty strong { display:block; margin-top:7px; color:#fff; font-size:18px; }
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
                .ar-header { flex-direction:column; }
                .ar-session-badge { width:100%; text-align:left; }
                .ar-metric-grid { grid-template-columns:repeat(2,1fr); }
                .ar-two-col { grid-template-columns:1fr; }
                .ar-coaching-grid { grid-template-columns:1fr; }
                .ar-benefit { padding:10px 0 0; border-left:0; border-top:1px solid #ecdcd3; }
            }
            @media (max-width:560px) {
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
            <div class="pp-page-eyebrow">Your running evidence</div>
            <div class="pp-page-title">Activity Review</div>
            <div class="pp-page-intro">
                How good was this run, really—and why? Classification,
                continuity, conditions and comparison are kept separate so
                the conclusion remains honest.
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

    with st.spinner("Reviewing this activity against your real history…"):
        review = _cached_review(
            athlete_id,
            int(activity_id),
            data_version,
        )

    if review is None:
        st.warning("This activity is no longer available for this athlete.")
        return

    _html(_header_html(review))
    _html(build_activity_overview_html(review))
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
        "Recognition before recommendation. Every run has something to give."
    )
