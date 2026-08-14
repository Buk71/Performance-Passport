"""Standalone interactive Race Predictor controls and presentation."""

from __future__ import annotations

import html

import streamlit as st

from core.database import get_goals_for_athlete
from core.home_predictions import HomePredictions, build_goal_predictions
from core.race_outlook import (
    InteractiveRaceOutlook,
    RaceConditions,
    build_interactive_race_outlook,
)
from ui.athlete_selection import render_athlete_id_selector


RACE_OUTLOOK_CACHE_SCHEMA = 2

DISTANCE_OPTIONS = {
    "5K": 5000.0,
    "5 miles": 8046.72,
    "10K": 10000.0,
    "10 miles": 16093.44,
    "Half marathon": 21097.5,
    "Marathon": 42195.0,
}


def _escape(value) -> str:
    return html.escape(str(value or ""))


def _clock(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    total = int(round(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def _pace(seconds_per_km: float | None) -> str:
    if seconds_per_km is None:
        return "—"
    total = int(round(seconds_per_km * 1.609344))
    minutes, secs = divmod(total, 60)
    return f"{minutes}:{secs:02d}/mi"


def _signed_clock(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    sign = "+" if seconds > 0 else "−" if seconds < 0 else ""
    return f"{sign}{_clock(abs(seconds))}"


def _confidence_class(value: str) -> str:
    return {
        "Strong": "is-strong",
        "Moderate": "is-moderate",
    }.get(value, "is-limited")


def _factor_cards(outlook: InteractiveRaceOutlook) -> str:
    return "".join(
        f"""
        <article class="race-factor">
            <div class="race-card-label">{_escape(factor.label.upper())}</div>
            <strong>{_signed_clock(factor.total_seconds)}</strong>
            <p>{_escape(factor.context)}</p>
            <span>{'PERSONALISED' if factor.personalised else 'GENERIC'} · {factor.confidence:.0%} support</span>
            <small>{_escape(factor.evidence)}</small>
        </article>
        """
        for factor in outlook.factors
    )


def build_race_outlook_html(outlook: InteractiveRaceOutlook) -> str:
    if not outlook.available:
        return f'<div class="race-empty"><strong>{_escape(outlook.headline)}</strong><p>{_escape(outlook.summary)}</p></div>'
    probability = (
        f"{outlook.target_probability:.0%}"
        if outlook.target_probability is not None
        else "—"
    )
    condition_cost = _signed_clock(outlook.condition_cost_seconds)
    gap = _signed_clock(outlook.target_gap_seconds)
    notes = "".join(f"<li>{_escape(note)}</li>" for note in outlook.limitations)
    return f"""
    <main class="race-outlook-shell">
        <section class="race-verdict">
            <div>
                <div class="race-eyebrow">SELECTED RACE OUTLOOK · {_escape(outlook.distance_label)}</div>
                <h1>{_escape(outlook.headline)}</h1>
                <p>{_escape(outlook.summary)}</p>
                <div class="race-condition-summary">{_escape(outlook.conditions_summary)}</div>
            </div>
            <div class="race-confidence {_confidence_class(outlook.confidence_label)}"><span>FORECAST CONFIDENCE</span><strong>{_escape(outlook.confidence_label)}</strong><small>{outlook.confidence:.0%} combined capability and condition support</small></div>
        </section>

        <section class="race-comparison" aria-label="Ideal capability and selected conditions comparison">
            <article class="race-result-card">
                <div class="race-card-label">CURRENT CAPABILITY</div>
                <strong>{_clock(outlook.ideal_seconds)}</strong>
                <span>{_clock(outlook.ideal_low_seconds)}–{_clock(outlook.ideal_high_seconds)}</span>
                <p>Ideal · cool · flat road · light wind</p>
            </article>
            <div class="race-transition"><span>CONDITION COST</span><strong>{condition_cost}</strong><small>{outlook.condition_cost_percent:.1f}% of ideal time</small></div>
            <article class="race-result-card is-selected">
                <div class="race-card-label">SELECTED RACE</div>
                <strong>{_clock(outlook.selected_seconds)}</strong>
                <span>{_clock(outlook.selected_low_seconds)}–{_clock(outlook.selected_high_seconds)}</span>
                <p>{_pace(outlook.selected_pace_s_per_km)} central pace</p>
            </article>
            <article class="race-goal-card">
                <div class="race-card-label">COMPARISON · {_escape(outlook.goal_name)}</div>
                <strong>{_clock(outlook.target_seconds)}</strong>
                <div><span>Central gap</span><b>{gap}</b></div>
                <div><span>Estimated likelihood</span><b>{probability}</b></div>
            </article>
        </section>

        <section class="race-factors">
            <div class="race-section-heading"><div><div class="race-eyebrow">CONDITION COST</div><h2>What moved the prediction</h2></div><span>FACTOR-BY-FACTOR AUDIT</span></div>
            <div class="race-factor-grid">{_factor_cards(outlook)}</div>
        </section>
        <details class="race-method"><summary>What this forecast can—and cannot—claim</summary><ul>{notes}</ul></details>
    </main>
    <style>
        .race-outlook-shell {{ display:grid; gap:10px; color:#10263d; container-type:inline-size; margin-top:4px; }} .race-outlook-shell * {{ box-sizing:border-box; }}
        .race-verdict,.race-comparison,.race-factors,.race-method,.race-empty {{ background:#fff; border:1px solid #e5ddd2; border-radius:18px; box-shadow:0 8px 24px rgba(16,38,61,.045); }}
        .race-verdict {{ padding:22px 24px; display:grid; grid-template-columns:minmax(0,1fr) 215px; gap:24px; align-items:center; }}
        .race-eyebrow,.race-card-label {{ color:#778594; font-size:10px; line-height:1.25; font-weight:800; letter-spacing:.13em; }}
        .race-verdict h1 {{ color:#10263d!important; font-size:clamp(27px,3vw,40px); line-height:1.02; margin:6px 0 8px; letter-spacing:-.04em; }} .race-verdict p {{ color:#647180; font-size:12px; line-height:1.45; margin:0; }}
        .race-condition-summary {{ display:inline-flex; margin-top:12px; padding:7px 10px; border-radius:999px; background:#f8f5ef; color:#5f6d79; font-size:9px; font-weight:750; }}
        .race-confidence {{ padding:15px; border-radius:13px; background:#eaf6ef; border:1px solid #d2e9dc; display:flex; flex-direction:column; gap:3px; }} .race-confidence span {{ color:#71808d; font-size:9px; font-weight:800; letter-spacing:.1em; }} .race-confidence strong {{ color:#238a52; font-size:24px; }} .race-confidence small {{ color:#71808d; font-size:9px; line-height:1.3; }}
        .race-confidence.is-moderate {{ background:#fff5e4; border-color:#f1dfbd; }} .race-confidence.is-moderate strong {{ color:#ad6500; }} .race-confidence.is-limited {{ background:#fff0e8; border-color:#f2d7ca; }} .race-confidence.is-limited strong {{ color:#cf5225; }}
        .race-comparison {{ padding:16px; display:grid; grid-template-columns:1fr 150px 1fr 1fr; gap:9px; align-items:stretch; }}
        .race-result-card,.race-goal-card,.race-transition {{ border-radius:13px; padding:14px; min-width:0; }} .race-result-card {{ background:#f8f5ef; border:1px solid #ebe4da; }} .race-result-card.is-selected {{ background:#10263d; border:1px solid #10263d; color:#fff; }}
        .race-result-card > strong,.race-goal-card > strong {{ display:block; font-size:29px; line-height:1; margin:10px 0 4px; letter-spacing:-.04em; }} .race-result-card > span {{ color:#6f7c88; font-size:10px; }} .race-result-card.is-selected .race-card-label,.race-result-card.is-selected > span,.race-result-card.is-selected p {{ color:#b9c7d3; }} .race-result-card p {{ color:#697683; font-size:9px; margin:9px 0 0; }}
        .race-transition {{ display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; background:#fff0e8; border:1px solid #f1d6c8; }} .race-transition span {{ font-size:8px; font-weight:800; letter-spacing:.1em; color:#9a664f; }} .race-transition strong {{ color:#f05a28; font-size:22px; margin:6px 0 2px; }} .race-transition small {{ color:#856d62; font-size:8px; }}
        .race-goal-card {{ background:linear-gradient(105deg,#fff0ca,#fff8e8); border:1px solid #efcf83; }} .race-goal-card > div:not(.race-card-label) {{ display:flex; justify-content:space-between; gap:8px; color:#75684f; font-size:9px; margin-top:5px; }} .race-goal-card b {{ color:#10263d; }}
        .race-factors {{ padding:18px 20px; }} .race-section-heading {{ display:flex; justify-content:space-between; align-items:flex-start; gap:14px; margin-bottom:12px; }} .race-section-heading h2 {{ color:#10263d!important; font-size:20px; line-height:1.1; margin:4px 0 0; }} .race-section-heading > span {{ color:#238a52; font-size:9px; font-weight:800; letter-spacing:.1em; }}
        .race-factor-grid {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:8px; }} .race-factor {{ padding:13px; border-radius:12px; background:#f8f5ef; border:1px solid #ebe4da; }} .race-factor > strong {{ display:block; font-size:21px; margin:9px 0 4px; }} .race-factor p {{ color:#63717e; font-size:9px; line-height:1.35; margin:0 0 8px; min-height:25px; }} .race-factor > span {{ display:block; color:#238a52; font-size:8px; font-weight:800; margin-bottom:5px; }} .race-factor small {{ color:#7a8792; font-size:8px; line-height:1.35; }}
        .race-method {{ padding:0 18px; }} .race-method summary {{ cursor:pointer; padding:14px 0; font-size:11px; font-weight:800; }} .race-method ul {{ margin:0 0 15px; padding-left:20px; }} .race-method li {{ color:#687582; font-size:9px; line-height:1.45; margin:5px 0; }}
        .race-empty {{ padding:24px; }} .race-empty p {{ color:#687582; }}
        @container (max-width:950px) {{ .race-comparison {{ grid-template-columns:1fr 130px 1fr; }} .race-goal-card {{ grid-column:1 / -1; }} .race-factor-grid {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} }}
        @container (max-width:650px) {{ .race-verdict {{ grid-template-columns:1fr; }} .race-confidence {{ max-width:280px; }} .race-comparison {{ grid-template-columns:1fr; }} .race-transition {{ min-height:90px; }} }}
        @container (max-width:430px) {{ .race-verdict,.race-factors {{ padding:16px; }} .race-factor-grid {{ grid-template-columns:1fr; }} .race-section-heading {{ flex-direction:column; }} }}
    </style>
    """


def _number_key(athlete_id: int, name: str) -> str:
    return f"race_outlook_{athlete_id}_{name}"


def _apply_preset(athlete_id: int, preset: dict) -> None:
    for name, value in preset.items():
        st.session_state[_number_key(athlete_id, name)] = value


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


def _goal_choice_label(goal: dict) -> str:
    target = _clock(goal.get("target_time_s"))
    target_text = f" · {target}" if target != "—" else ""
    date_text = (
        f" · {str(goal.get('target_date'))[:10]}"
        if goal.get("target_date")
        else ""
    )
    return (
        f"{goal.get('goal_name') or goal.get('race_name') or 'Saved goal'}"
        f"{target_text}{date_text} · {goal.get('priority') or 'Goal'}"
    )


@st.cache_data(ttl=300, show_spinner=False)
def _cached_race_predictions(
    athlete_id: int,
    goal_id: int | None,
    goal_name: str,
    goal_type: str,
    distance_m: float,
    target_time_s: float | None,
    target_date: str | None,
    cache_schema: int,
) -> HomePredictions:
    """Build an explicit-distance capability without changing the active goal."""
    _ = cache_schema
    return build_goal_predictions(
        athlete_id,
        {
            "id": goal_id,
            "athlete_id": athlete_id,
            "goal_name": goal_name,
            "goal_type": goal_type,
            "distance_m": distance_m,
            "target_time_s": target_time_s,
            "target_date": target_date,
        },
    )


def _prediction_basis(athlete_id: int) -> dict:
    goals = [
        goal
        for goal in get_goals_for_athlete(athlete_id)
        if goal.get("distance_m") and float(goal["distance_m"]) > 0
    ]
    modes = (
        ["Saved goal", "Explore a distance"]
        if goals
        else ["Explore a distance"]
    )

    st.markdown("#### 1. Choose what to predict")
    st.caption(
        "Use any saved goal without changing which goal drives Home, or explore "
        "another standard race distance."
    )
    mode = st.radio(
        "Prediction basis",
        modes,
        horizontal=True,
        key=_number_key(athlete_id, "prediction_basis"),
    )
    if mode == "Saved goal":
        goal_ids = [int(goal["id"]) for goal in goals]
        goals_by_id = {int(goal["id"]): goal for goal in goals}
        selected_id = st.selectbox(
            "Saved goal",
            goal_ids,
            format_func=lambda goal_id: _goal_choice_label(goals_by_id[goal_id]),
            key=_number_key(athlete_id, "saved_goal"),
        )
        goal = dict(goals_by_id[selected_id])
        st.caption(
            f"{goal.get('status') or 'Saved'} · {goal.get('goal_type') or 'Race'}"
            " · This is a read-only forecast; the active goal is unchanged."
        )
        return goal

    basis_columns = st.columns([1, 1])
    distance_label = basis_columns[0].selectbox(
        "Race distance",
        list(DISTANCE_OPTIONS),
        index=2,
        key=_number_key(athlete_id, "explore_distance"),
    )
    target_text = basis_columns[1].text_input(
        "Comparison target (optional)",
        placeholder="MM:SS or HH:MM:SS",
        key=_number_key(
            athlete_id,
            f"target_{distance_label.lower().replace(' ', '_')}",
        ),
    )
    target_seconds, target_valid = _parse_target_time(target_text)
    if not target_valid:
        st.warning("Use MM:SS or HH:MM:SS for the optional comparison target.")
        target_seconds = None
    return {
        "id": None,
        "athlete_id": athlete_id,
        "goal_name": f"{distance_label} exploration",
        "goal_type": distance_label,
        "distance_m": DISTANCE_OPTIONS[distance_label],
        "target_time_s": target_seconds,
        "target_date": None,
    }


def render_interactive_race_outlook(athlete_id: int) -> None:
    goal = _prediction_basis(athlete_id)
    with st.spinner("Loading current capability and personal responses…"):
        predictions = _cached_race_predictions(
            athlete_id,
            goal.get("id"),
            str(goal.get("goal_name") or "Race exploration"),
            str(goal.get("goal_type") or "Race"),
            float(goal["distance_m"]),
            goal.get("target_time_s"),
            goal.get("target_date"),
            RACE_OUTLOOK_CACHE_SCHEMA,
        )
    if not predictions.available:
        st.info(predictions.explanation)
        return

    st.markdown("#### 2. Quick-start scenarios")
    st.caption(
        "Load a useful starting set of conditions. Every value remains visible "
        "and adjustable below."
    )
    presets = (
        ("Ideal", dict(temperature=12, humidity=70, ascent=0, wind=5, exposure="Mixed", surface="Road")),
        ("Typical UK", dict(temperature=14, humidity=75, ascent=60, wind=12, exposure="Mixed", surface="Road")),
        ("Warm", dict(temperature=21, humidity=65, ascent=0, wind=5, exposure="Mixed", surface="Road")),
        ("Hot", dict(temperature=27, humidity=60, ascent=0, wind=5, exposure="Mixed", surface="Road")),
        ("Hilly", dict(temperature=12, humidity=70, ascent=200, wind=5, exposure="Mixed", surface="Road")),
        ("Trail", dict(temperature=12, humidity=70, ascent=150, wind=5, exposure="Mixed", surface="Firm trail")),
    )
    preset_columns = st.columns(len(presets))
    for column, (label, values) in zip(preset_columns, presets):
        if column.button(
            label,
            key=_number_key(athlete_id, f"preset_{label.lower().replace(' ', '_')}"),
            use_container_width=True,
        ):
            _apply_preset(athlete_id, values)

    st.markdown("#### 3. Fine-tune race conditions")
    st.caption(
        "Change the details to describe the course and likely race-day weather."
    )
    row_one = st.columns(3)
    temperature = row_one[0].slider(
        "Temperature (°C)",
        min_value=-5,
        max_value=35,
        value=12,
        step=1,
        key=_number_key(athlete_id, "temperature"),
    )
    humidity = row_one[1].slider(
        "Humidity (%)",
        min_value=20,
        max_value=100,
        value=70,
        step=5,
        key=_number_key(athlete_id, "humidity"),
    )
    ascent = row_one[2].number_input(
        "Total ascent (m)",
        min_value=0,
        max_value=2500,
        value=0,
        step=10,
        key=_number_key(athlete_id, "ascent"),
    )
    row_two = st.columns(3)
    wind = row_two[0].slider(
        "Wind speed (km/h)",
        min_value=0,
        max_value=50,
        value=5,
        step=1,
        key=_number_key(athlete_id, "wind"),
    )
    exposure = row_two[1].segmented_control(
        "Wind exposure",
        options=["Sheltered", "Mixed", "Exposed"],
        default="Mixed",
        key=_number_key(athlete_id, "exposure"),
    ) or "Mixed"
    surface = row_two[2].segmented_control(
        "Surface",
        options=["Road", "Firm trail"],
        default="Road",
        key=_number_key(athlete_id, "surface"),
    ) or "Road"

    outlook = build_interactive_race_outlook(
        predictions,
        RaceConditions(
            temperature_c=temperature,
            humidity_percent=humidity,
            total_ascent_m=ascent,
            wind_speed_kmh=wind,
            wind_exposure=exposure,
            surface=surface,
        ),
    )
    st.html(build_race_outlook_html(outlook))


def show_race_predictor_page() -> None:
    st.markdown(
        """
        <style>
            [data-testid="stMainBlockContainer"] { max-width:1450px; padding-top:4.25rem; padding-bottom:3rem; }
            [data-testid="stHeader"] { background:transparent; }
            [data-testid="stElementContainer"]:has(.race-selector-marker) { display:none; }
            [data-testid="stHorizontalBlock"]:has(.race-selector-marker) { align-items:flex-start; gap:8px; }
            .race-context-strip { min-height:40px; border:1px solid #e5ddd2; border-radius:12px; background:#fff; padding:0 15px; display:flex; align-items:center; justify-content:space-between; gap:14px; color:#10263d; box-shadow:0 5px 18px rgba(16,38,61,.035); }
            .race-context-strip strong { font-size:12px; letter-spacing:.12em; }
            .race-context-strip span { color:#6c7885; font-size:11px; }
            .race-context-strip em { color:#238a52; font-size:10px; font-style:normal; font-weight:800; letter-spacing:.08em; }
            @media (max-width:900px) { [data-testid="stHorizontalBlock"]:has(.race-selector-marker) [data-testid="stColumn"]:last-child { display:none; } [data-testid="stHorizontalBlock"]:has(.race-selector-marker) [data-testid="stColumn"]:first-child { flex:1 1 100%; width:100%; } }
        </style>
        """,
        unsafe_allow_html=True,
    )
    selector_col, context_col = st.columns([390, 1051], gap="small")
    with selector_col:
        st.markdown('<span class="race-selector-marker"></span>', unsafe_allow_html=True)
        athlete_id = render_athlete_id_selector(label_visibility="collapsed")
    with context_col:
        st.html('<div class="race-context-strip"><strong>RACE PREDICTOR</strong><span>What could I run?</span><em>CAPABILITY → CONDITIONS</em></div>')

    if athlete_id is None:
        st.info("Add an athlete before building a race forecast.")
        return

    st.markdown("### Race Outlook")
    st.caption(
        "Start from a supported current capability, then translate the same "
        "fitness into a chosen distance, course and set of conditions."
    )
    render_interactive_race_outlook(athlete_id)
