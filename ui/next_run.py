"""Premium Training Coach journey built from established coaching services."""

from __future__ import annotations

import html

import streamlit as st

from core.training_coach import TrainingCoachDetail, build_training_coach_detail
from ui.athlete_selection import (
    SESSION_ID_KEY,
    SESSION_NAME_KEY,
    athlete_name,
    get_athletes,
    render_athlete_id_selector,
)
from ui.training_coach_navigation import (
    clear_training_coach_params,
    read_training_coach_request,
)


TRAINING_COACH_CACHE_SCHEMA = 1
MILES_PER_KM = 0.621371192237334


def _safe(value) -> str:
    return html.escape(str(value or ""))


def _pace_per_mile(seconds_per_km: float | None) -> str:
    if seconds_per_km is None:
        return "—"
    seconds = float(seconds_per_km) / MILES_PER_KM
    minutes, remainder = divmod(int(round(seconds)), 60)
    return f"{minutes}:{remainder:02d}/mi"


def _pace_range(session) -> str:
    if session.pace_low_s_per_km is None or session.pace_high_s_per_km is None:
        return "Effort-led"
    faster = min(session.pace_low_s_per_km, session.pace_high_s_per_km)
    slower = max(session.pace_low_s_per_km, session.pace_high_s_per_km)
    return f"{_pace_per_mile(faster)}–{_pace_per_mile(slower)}"


def _heart_rate(session) -> str:
    if session.hr_low is not None and session.hr_high is not None:
        return f"{session.hr_low}–{session.hr_high} bpm"
    if session.hr_high is not None:
        return f"≤ {session.hr_high} bpm"
    return "RPE-led"


def _list(items) -> str:
    return "".join(f"<li>{_safe(item)}</li>" for item in items)


def _apply_training_coach_request() -> None:
    request = read_training_coach_request(st.query_params)
    if request is None:
        return
    rows_by_id = {int(row[0]): row for row in get_athletes()}
    row = rows_by_id.get(request.athlete_id)
    if row is not None:
        st.session_state[SESSION_ID_KEY] = request.athlete_id
        st.session_state[SESSION_NAME_KEY] = athlete_name(row)
    clear_training_coach_params(st.query_params)


@st.cache_data(show_spinner=False, ttl=120)
def _cached_training_coach_detail(
    athlete_id: int,
    schema: int,
) -> TrainingCoachDetail | None:
    del schema
    return build_training_coach_detail(athlete_id)


def _session_markup(detail: TrainingCoachDetail) -> str:
    session = detail.session
    if session is None:
        return """
            <section class="tc-section tc-empty">
                <div class="tc-eyebrow tc-dark"><span></span>Full prescription</div>
                <h2>Personal session detail is still building.</h2>
                <p>The immediate coaching decision remains available above. A full
                prescription will appear when enough session evidence is available.</p>
            </section>
        """

    due_today = str(session.earliest_timing or "").lower().startswith("today")
    heading = "Today’s full prescription" if due_today else "Upcoming key session"
    evidence = "".join(
        f"""
        <article class="tc-evidence-row">
            <div><strong>{_safe(item.activity_title)}</strong><span>{_safe(item.activity_date or 'Date unknown')}</span></div>
            <div><strong>{f'{item.execution_score:.0f}/100' if item.execution_score is not None else 'Not scored'}</strong><span>Execution</span></div>
            <div><strong>{item.evidence_score:.0%}</strong><span>Evidence</span></div>
        </article>
        """
        for item in session.historical_evidence[:3]
    ) or '<p class="tc-muted">Comparable personal sessions are still building.</p>'

    return f"""
        <section class="tc-section tc-prescription" id="training-prescription">
            <div class="tc-section-heading">
                <div>
                    <div class="tc-eyebrow tc-dark"><span></span>{_safe(heading)}</div>
                    <h2>{_safe(session.family_label)}</h2>
                    <p>{_safe(session.purpose)}</p>
                </div>
                <div class="tc-session-status">
                    <span>{_safe(session.earliest_timing)}</span>
                    <strong>{_safe(session.confidence_label)} · {session.confidence:.0%}</strong>
                </div>
            </div>
            <div class="tc-workout-grid">
                <article><div class="tc-step"><b>01</b><span>Prepare</span></div><h3>Warm-up</h3><ul>{_list(session.warmup)}</ul></article>
                <article class="tc-main-set"><div class="tc-step"><b>02</b><span>Purpose</span></div><h3>Main set</h3><ul>{_list(session.main_set)}</ul></article>
                <article><div class="tc-step"><b>03</b><span>Absorb</span></div><h3>Cool-down</h3><ul>{_list(session.cooldown)}</ul></article>
            </div>
            <div class="tc-target-grid">
                <article><span>Pace</span><strong>{_safe(_pace_range(session))}</strong><small>Personal range</small></article>
                <article><span>Heart rate</span><strong>{_safe(_heart_rate(session))}</strong><small>When reliable</small></article>
                <article><span>Effort</span><strong>{session.rpe_low:g}–{session.rpe_high:g}/10</strong><small>Always available</small></article>
                <article><span>Source</span><strong>{_safe(session.source)}</strong><small>Auditable evidence</small></article>
            </div>
            <div class="tc-execution-grid">
                <article class="tc-success"><span>Success looks like</span><h3>{_safe(session.success_looks_like)}</h3></article>
                <article><span>Coach’s cue</span><h3>{_safe(session.coach_tip)}</h3></article>
                <article class="tc-mistake"><span>Avoid</span><h3>{_safe(session.common_mistake)}</h3></article>
            </div>
        </section>
        <section class="tc-section tc-evidence">
            <div class="tc-section-heading">
                <div><div class="tc-eyebrow tc-dark"><span></span>Why this session</div><h2>Your evidence, translated into one useful run.</h2></div>
                <div class="tc-source">{_safe(session.block_name or session.goal_name or 'Personal direction')}</div>
            </div>
            <div class="tc-why-grid">
                <ul>{_list(session.why_this_session)}</ul>
                <article class="tc-history"><span>Personal history</span><h3>{_safe(session.historical_summary)}</h3>{evidence}</article>
            </div>
        </section>
    """


def build_training_coach_html(
    athlete_name_value: str,
    detail: TrainingCoachDetail,
) -> str:
    """Return the complete Training Coach markup for one real athlete."""
    decision = detail.decision
    progress = ""
    if decision.operational_week_number is not None:
        completed = decision.operational_completed_miles or 0.0
        planned = decision.operational_planned_miles or 0.0
        percent = min(100.0, completed / planned * 100.0) if planned > 0 else 0.0
        progress = f"""
            <div class="tc-week-progress">
                <div><span>Saved week</span><strong>Week {decision.operational_week_number}</strong></div>
                <div><span>Status</span><strong>{_safe(decision.operational_status or 'In progress')}</strong></div>
                <div class="tc-mileage"><span>Reliable mileage</span><strong>{completed:.1f} of {planned:.1f} mi</strong><i><b style="width:{percent:.0f}%"></b></i></div>
            </div>
        """

    adjustments = "".join(
        f'<article class="tc-adjust-{_safe(item.key)}"><span>{_safe(item.label)}</span><p>{_safe(item.direction)}</p></article>'
        for item in detail.adjustments
    )
    safety = "".join(f"<li>{_safe(note)}</li>" for note in decision.safety_notes)
    safety_markup = (
        f'<div class="tc-safety"><strong>Current safeguards</strong><ul>{safety}</ul></div>'
        if safety else ""
    )

    return f"""
    <main class="tc-home" id="training-coach">
        <section class="tc-hero">
            <div class="tc-hero-copy">
                <div class="tc-eyebrow"><span></span>Training Coach · {_safe(athlete_name_value)}</div>
                <h1>{_safe(decision.immediate_label)}</h1>
                <p class="tc-headline">{_safe(decision.headline)}</p>
                <div class="tc-immediate-detail">{_safe(decision.immediate_detail)}</div>
                <div class="tc-badges">
                    <span>{_safe(decision.immediate_timing)}</span>
                    <span>{_safe(decision.confidence_label)} · {decision.confidence:.0%} confidence</span>
                    <span>{_safe(decision.source)}</span>
                </div>
            </div>
            <aside class="tc-next-key">
                <div class="tc-next-label">Next key session</div>
                <h2>{_safe(decision.key_label or 'Direction building')}</h2>
                <p>{_safe(decision.key_prescription or 'The coaching engine is building the next key prescription.')}</p>
                <strong>{_safe(decision.key_day or 'Timing building')}</strong>
            </aside>
        </section>
        {progress}
        {_session_markup(detail)}
        <section class="tc-section tc-support-grid">
            <article class="tc-fuel">
                <div class="tc-eyebrow tc-dark"><span></span>Nutrition Coach · Immediate {_safe(detail.fuel_demand)} demand</div>
                <h2>Fuel the next run, then support recovery.</h2>
                <p class="tc-fuel-focus">{_safe(detail.fuel_focus)}</p>
                <div class="tc-fuel-steps">
                    <div><b>Before</b><p>{_safe(detail.fuel_before)}</p></div>
                    <div><b>During</b><p>{_safe(detail.fuel_during)}</p></div>
                    <div><b>After</b><p>{_safe(detail.fuel_after)}</p></div>
                </div>
            </article>
            <article class="tc-adapt">
                <div class="tc-eyebrow tc-dark"><span></span>Adapt if needed</div>
                <h2>Keep the purpose. Change the load when necessary.</h2>
                <div class="tc-adjustments">{adjustments}</div>
                <p class="tc-readiness-note">Readiness data is not connected. These are transparent safety choices, not a hidden score or automatic plan change.</p>
            </article>
        </section>
        {safety_markup}
        <style>
            .tc-home {{ --navy:#08253e; --ink:#10273d; --muted:#617482; --orange:#f15a2a; --green:#279675; color:var(--ink); font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
            .tc-home * {{ box-sizing:border-box; }}
            .tc-hero {{ position:relative; display:grid; grid-template-columns:minmax(0,1.35fr) minmax(320px,.65fr); gap:28px; overflow:hidden; padding:38px; border-radius:28px; background:radial-gradient(circle at 91% 10%,rgba(44,159,132,.27),transparent 34%),linear-gradient(125deg,#071f36,#0a304c 60%,#0c4356); box-shadow:0 24px 55px rgba(10,33,53,.18); color:#fff; }}
            .tc-hero:after {{ content:""; position:absolute; right:-150px; bottom:-260px; width:520px; height:520px; border:58px solid rgba(255,255,255,.04); border-radius:50%; }}
            .tc-hero-copy,.tc-next-key {{ position:relative; z-index:1; }}
            .tc-eyebrow {{ display:flex; align-items:center; gap:10px; color:#8ee2c4; font-size:12px; font-weight:850; letter-spacing:.17em; text-transform:uppercase; }}
            .tc-eyebrow span {{ width:28px; height:3px; border-radius:99px; background:var(--orange); }}
            .tc-eyebrow.tc-dark {{ color:#6c7d8b; }}
            .tc-hero h1 {{ margin:14px 0 0; color:#fff!important; font-size:54px; line-height:.98; letter-spacing:-.048em; }}
            .tc-headline {{ max-width:760px; margin:13px 0 0; color:#d3dee5; font-size:19px; line-height:1.4; }}
            .tc-immediate-detail {{ margin-top:21px; padding:17px 19px; border-left:4px solid var(--orange); border-radius:0 14px 14px 0; background:rgba(255,255,255,.08); font-size:17px; font-weight:750; line-height:1.45; }}
            .tc-badges {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:18px; }}
            .tc-badges span {{ padding:7px 10px; border:1px solid rgba(255,255,255,.14); border-radius:999px; background:rgba(255,255,255,.07); color:#bed0da; font-size:11px; font-weight:750; }}
            .tc-next-key {{ align-self:stretch; padding:24px; border:1px solid rgba(255,255,255,.17); border-radius:21px; background:rgba(255,255,255,.09); backdrop-filter:blur(8px); }}
            .tc-next-label {{ color:#91a9b8; font-size:11px; font-weight:850; letter-spacing:.14em; text-transform:uppercase; }}
            .tc-next-key h2 {{ margin:12px 0 0; color:#fff!important; font-size:29px; line-height:1.05; letter-spacing:-.035em; }}
            .tc-next-key p {{ margin:12px 0 20px; color:#c5d3dc; font-size:15px; line-height:1.45; }}
            .tc-next-key strong {{ display:inline-block; padding:8px 11px; border-radius:10px; background:#ecf8f2; color:#167a5e; font-size:12px; }}
            .tc-week-progress {{ display:grid; grid-template-columns:.65fr .8fr 2fr; gap:11px; margin-top:13px; }}
            .tc-week-progress>div {{ padding:16px 18px; border:1px solid #dfd9d0; border-radius:16px; background:#fff; box-shadow:0 8px 23px rgba(36,44,50,.05); }}
            .tc-week-progress span,.tc-week-progress strong {{ display:block; }}
            .tc-week-progress span {{ color:#778794; font-size:10px; font-weight:850; letter-spacing:.11em; text-transform:uppercase; }}
            .tc-week-progress strong {{ margin-top:5px; font-size:17px; }}
            .tc-mileage i {{ display:block; overflow:hidden; height:5px; margin-top:10px; border-radius:99px; background:#e6e3dd; }}
            .tc-mileage i b {{ display:block; height:100%; border-radius:99px; background:linear-gradient(90deg,var(--green),#6dcdb0); }}
            .tc-section {{ margin-top:18px; padding:30px; border:1px solid #ded8cf; border-radius:23px; background:#fff; box-shadow:0 14px 36px rgba(36,44,50,.065); }}
            .tc-section-heading {{ display:flex; align-items:flex-end; justify-content:space-between; gap:24px; }}
            .tc-section h2 {{ margin:7px 0 0; font-size:31px; line-height:1.08; letter-spacing:-.038em; }}
            .tc-section-heading p {{ max-width:820px; margin:8px 0 0; color:var(--muted); font-size:15px; line-height:1.48; }}
            .tc-session-status {{ min-width:170px; text-align:right; }}
            .tc-session-status span,.tc-session-status strong {{ display:block; }}
            .tc-session-status span {{ color:var(--green); font-size:18px; font-weight:900; }}
            .tc-session-status strong {{ margin-top:4px; color:#687b89; font-size:11px; }}
            .tc-workout-grid {{ display:grid; grid-template-columns:.9fr 1.25fr .9fr; gap:12px; margin-top:24px; }}
            .tc-workout-grid article {{ min-height:230px; padding:22px; border:1px solid #e2ddd5; border-radius:18px; background:#faf8f4; }}
            .tc-workout-grid .tc-main-set {{ border-color:#f0bda8; background:linear-gradient(145deg,#fff6ef,#fff); box-shadow:inset 0 4px 0 var(--orange); }}
            .tc-step {{ display:flex; align-items:center; gap:9px; color:#788894; font-size:10px; font-weight:800; letter-spacing:.09em; text-transform:uppercase; }}
            .tc-step b {{ display:grid; place-items:center; width:32px; height:32px; border-radius:10px; background:var(--navy); color:#fff; font-size:10px; }}
            .tc-main-set .tc-step b {{ background:var(--orange); }}
            .tc-workout-grid h3 {{ margin:16px 0 8px; font-size:22px; letter-spacing:-.025em; }}
            .tc-workout-grid ul,.tc-why-grid ul,.tc-safety ul {{ margin:0; padding-left:18px; color:#506574; font-size:14px; line-height:1.65; }}
            .tc-target-grid {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:9px; margin-top:12px; }}
            .tc-target-grid article {{ min-width:0; padding:17px; border:1px solid #e2ddd5; border-radius:15px; background:#fff; }}
            .tc-target-grid span,.tc-target-grid strong,.tc-target-grid small {{ display:block; }}
            .tc-target-grid span {{ color:#7b8a96; font-size:9px; font-weight:850; letter-spacing:.11em; text-transform:uppercase; }}
            .tc-target-grid strong {{ overflow-wrap:anywhere; margin-top:6px; font-size:19px; line-height:1.15; }}
            .tc-target-grid small {{ margin-top:5px; color:#82909a; font-size:9px; }}
            .tc-execution-grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; margin-top:18px; }}
            .tc-execution-grid article {{ padding:20px; border-radius:17px; background:#eef7f3; }}
            .tc-execution-grid article:nth-child(2) {{ background:var(--navy); color:#fff; }}
            .tc-execution-grid .tc-mistake {{ background:#fff1e9; }}
            .tc-execution-grid span {{ color:#5f7b75; font-size:10px; font-weight:850; letter-spacing:.12em; text-transform:uppercase; }}
            .tc-execution-grid article:nth-child(2) span {{ color:#8ee2c4; }}
            .tc-execution-grid h3 {{ margin:9px 0 0; font-size:16px; line-height:1.4; }}
            .tc-source {{ color:#718391; font-size:11px; font-weight:750; text-align:right; }}
            .tc-why-grid {{ display:grid; grid-template-columns:.85fr 1.15fr; gap:18px; margin-top:22px; }}
            .tc-why-grid>ul {{ padding:21px 21px 21px 38px; border-radius:17px; background:#faf8f4; }}
            .tc-history {{ padding:22px; border-radius:18px; background:var(--navy); color:#fff; }}
            .tc-history>span {{ color:#8ee2c4; font-size:10px; font-weight:850; letter-spacing:.12em; text-transform:uppercase; }}
            .tc-history>h3 {{ margin:9px 0 17px; color:#dce5eb; font-size:15px; line-height:1.45; }}
            .tc-evidence-row {{ display:grid; grid-template-columns:1fr auto auto; gap:13px; padding:10px 0; border-top:1px solid rgba(255,255,255,.12); }}
            .tc-evidence-row strong,.tc-evidence-row span {{ display:block; }}
            .tc-evidence-row strong {{ font-size:11px; }} .tc-evidence-row span {{ margin-top:3px; color:#97aab7; font-size:9px; }}
            .tc-muted {{ color:#adc0cc; font-size:12px; }}
            .tc-support-grid {{ display:grid; grid-template-columns:1.15fr .85fr; gap:13px; padding:0; border:0; background:transparent; box-shadow:none; }}
            .tc-support-grid>article {{ padding:28px; border:1px solid #ded8cf; border-radius:22px; background:#fff; box-shadow:0 14px 36px rgba(36,44,50,.065); }}
            .tc-support-grid h2 {{ font-size:27px; }}
            .tc-fuel {{ background:radial-gradient(circle at 100% 0,rgba(241,90,42,.13),transparent 35%),#fff!important; }}
            .tc-fuel-focus {{ color:#536878; font-size:15px; line-height:1.5; }}
            .tc-fuel-steps {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:9px; margin-top:18px; }}
            .tc-fuel-steps div {{ padding:16px; border-radius:14px; background:#f8f5ef; }}
            .tc-fuel-steps b {{ color:var(--orange); font-size:11px; text-transform:uppercase; }}
            .tc-fuel-steps p,.tc-adjustments p {{ margin:7px 0 0; color:#596d7c; font-size:12px; line-height:1.48; }}
            .tc-adjustments {{ display:grid; gap:8px; margin-top:18px; }}
            .tc-adjustments article {{ padding:13px 15px; border-left:3px solid var(--green); border-radius:0 12px 12px 0; background:#f5f7f4; }}
            .tc-adjust-pain {{ border-left-color:var(--orange)!important; }}
            .tc-adjustments span {{ font-size:13px; font-weight:900; }}
            .tc-readiness-note {{ margin:14px 0 0; color:#758591; font-size:10px; line-height:1.45; }}
            .tc-safety {{ margin-top:13px; padding:18px 22px; border:1px solid #efc1ad; border-radius:17px; background:#fff5ee; }}
            .tc-safety strong {{ color:#b94620; font-size:12px; text-transform:uppercase; }}
            .tc-safety ul {{ margin-top:8px; color:#6b5b52; }}
            .tc-empty p {{ color:var(--muted); }}
            @media (max-width:1100px) {{
                .tc-hero {{ grid-template-columns:1fr; }} .tc-week-progress {{ grid-template-columns:repeat(3,minmax(0,1fr)); }}
                .tc-workout-grid {{ grid-template-columns:1fr; }} .tc-workout-grid article {{ min-height:auto; }}
                .tc-target-grid {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} .tc-support-grid {{ grid-template-columns:1fr; }}
            }}
            @media (max-width:720px) {{
                .tc-hero {{ padding:26px; }} .tc-hero h1 {{ font-size:41px; }} .tc-headline {{ font-size:17px; }}
                .tc-week-progress,.tc-execution-grid,.tc-fuel-steps {{ grid-template-columns:1fr; }}
                .tc-section {{ padding:22px; }} .tc-section-heading {{ align-items:flex-start; flex-direction:column; }} .tc-session-status,.tc-source {{ text-align:left; }}
                .tc-target-grid,.tc-why-grid {{ grid-template-columns:1fr; }}
            }}
        </style>
    </main>
    """


def show_next_run_page() -> None:
    """Render the full Training Coach journey for the selected athlete."""
    st.markdown(
        """
        <style>
            [data-testid="stMainBlockContainer"] { max-width:1480px; padding-top:4rem; padding-bottom:3rem; }
            [data-testid="stSelectbox"] { max-width:410px; }
            [data-testid="stSelectbox"] > div > div { min-height:48px; border:1px solid #d9d3ca; border-radius:14px; background:#fff; box-shadow:0 8px 20px rgba(30,42,52,.055); }
        </style>
        """,
        unsafe_allow_html=True,
    )
    _apply_training_coach_request()
    athlete_id = render_athlete_id_selector(
        label="Athlete",
        label_visibility="collapsed",
    )
    if athlete_id is None:
        st.warning("No athletes found. Add an athlete before asking the Training Coach.")
        return

    with st.spinner("Training Coach is reviewing the latest evidence…"):
        detail = _cached_training_coach_detail(
            athlete_id,
            TRAINING_COACH_CACHE_SCHEMA,
        )
    if detail is None:
        st.info("Performance Passport needs enough recent evidence to coach the next run.")
        return

    st.html(
        build_training_coach_html(
            st.session_state.get(SESSION_NAME_KEY, "Athlete"),
            detail,
        )
    )
