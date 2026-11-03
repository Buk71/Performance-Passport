"""Premium Training Coach journey built from established coaching services."""

from __future__ import annotations

import html
import re

import streamlit as st

from core.cache_version import (
    NAVIGATION_CACHE_TTL_SECONDS,
    get_athlete_cache_version,
)
from core.training_coach import TrainingCoachDetail, build_training_coach_detail
from core.beginner_activity_evidence import find_latest_beginner_activity_evidence
from core.five_to_ten_k_activity_evidence import find_latest_five_to_ten_k_activity_evidence
from core.runner_journey import (
    JourneyProgressEvidence,
    apply_couch_to_5k_evidence,
    preview_couch_to_5k_progress,
    preview_five_to_ten_k_progress,
    apply_five_to_ten_k_evidence,
)
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


TRAINING_COACH_CACHE_SCHEMA = 2
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


@st.cache_data(show_spinner=False, ttl=NAVIGATION_CACHE_TTL_SECONDS)
def _cached_training_coach_detail(
    athlete_id: int,
    schema: int,
    data_version,
) -> TrainingCoachDetail | None:
    del schema, data_version
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



def _duration_text(seconds: int) -> str:
    total_seconds = int(seconds)
    minutes = total_seconds // 60
    seconds_left = total_seconds % 60
    return f"{minutes}:{seconds_left:02d}" if seconds_left else f"{minutes} min"



def _block_type_value(block) -> str:
    """Return a normalised block-type value from enum or restored JSON string."""
    value = getattr(block, "block_type", "")
    enum_value = getattr(value, "value", value)
    return str(enum_value or "").strip().lower()


def _beginner_block_sequence(session) -> tuple[str, ...]:
    blocks = session.blocks
    work = next((x for x in blocks if _block_type_value(x) == "work"), None)
    recovery = next((x for x in blocks if _block_type_value(x) == "recovery"), None)
    warm = next((x for x in blocks if _block_type_value(x) == "warmup"), None)
    cool = next((x for x in blocks if _block_type_value(x) == "cooldown"), None)
    continuous = next((x for x in blocks if _block_type_value(x) == "continuous"), None)
    sequence = []
    if warm:
        sequence.append(f"{_duration_text(warm.duration_s)} {warm.label}")
    if session.stage == "5k_ready":
        sequence.append("Complete 5K at easy / controlled effort")
    elif work and recovery:
        paired = min(max(work.repeat_count - 1, 0), recovery.repeat_count)
        if paired:
            sequence.append(
                f"{paired} × ({_duration_text(work.duration_s)} {work.label.lower()} + "
                f"{_duration_text(recovery.duration_s)} {recovery.label.lower()})"
            )
        sequence.append(f"{_duration_text(work.duration_s)} {work.label.lower()}")
    elif continuous:
        sequence.append(f"{_duration_text(continuous.duration_s)} {continuous.label}")
    if cool:
        sequence.append(f"{_duration_text(cool.duration_s)} {cool.label}")
    return tuple(sequence)


def build_beginner_training_coach_html(athlete_name_value: str, detail: TrainingCoachDetail) -> str:
    session = detail.beginner_session
    if session is None:
        return ""
    decision = detail.decision
    level = detail.beginner_week_number or decision.operational_week_number or 1
    sequence = "".join(
        f'<article class="btc-step"><b>{i:02d}</b><strong>{_safe(step)}</strong></article>'
        for i, step in enumerate(_beginner_block_sequence(session), 1)
    )
    success = _list(session.success_criteria)
    after = _list(session.collect_after)
    style = """
      <style>
        .btc { color:#10263D; font-family:Inter,system-ui,sans-serif; display:grid; gap:14px; }
        .btc * { box-sizing:border-box; }
        .btc-hero,.btc-card,.btc-grid>article { background:#fff; border:1px solid #DED8CE; border-radius:22px; box-shadow:0 12px 30px rgba(16,38,61,.06); }
        .btc-hero { padding:34px; display:grid; grid-template-columns:minmax(0,1fr) 310px; gap:28px; background:radial-gradient(circle at 100% 0,rgba(62,142,114,.14),transparent 38%),#fff; }
        .btc small { font-size:11px; letter-spacing:.14em; font-weight:900; color:#718091; }
        .btc-hero span { display:block; margin-top:15px; color:#3E8E72; font-size:12px; font-weight:900; letter-spacing:.12em; }
        .btc-hero h1 { font-size:48px; margin:7px 0 10px; letter-spacing:-.04em; }
        .btc-hero p,.btc-grid p,.btc-feedback p,.btc-fuel p { color:#617482; line-height:1.5; font-size:13px; }
        .btc-hero aside { background:#102E49; color:#fff; border-radius:17px; padding:21px; }
        .btc-hero aside small { color:#9FC4B4; }
        .btc-hero aside h2 { font-size:25px; }
        .btc-hero aside p { color:#DCE6EB; }
        .btc-tags { display:flex; gap:8px; flex-wrap:wrap; margin-top:18px; }
        .btc-tags b { font-size:10px; background:#E8F5EE; color:#28755B; padding:8px 10px; border-radius:999px; }
        .btc-card,.btc-grid>article { padding:25px; }
        .btc-card h2,.btc-grid h2 { font-size:26px; margin:5px 0 12px; }
        .btc-steps { display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:10px; }
        .btc-step { background:#F7F3EC; border:1px solid #E7E0D5; border-radius:14px; padding:16px; display:flex; gap:10px; }
        .btc-step b { color:#F05A28; font-size:11px; }
        .btc-step strong { font-size:14px; line-height:1.4; }
        .btc-grid { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
        .btc-grid ul,.btc-feedback ul { color:#536878; line-height:1.65; font-size:13px; }
        .btc-feedback { display:grid; grid-template-columns:1.1fr .9fr; gap:22px; border-top:3px solid #F05A28; }
        .btc-fuel { display:grid; grid-template-columns:repeat(3,1fr); gap:9px; }
        .btc-fuel article { background:#F8F5EF; border-radius:13px; padding:15px; }
        .btc-fuel b { font-size:11px; color:#F05A28; }
      </style>
    """
    return f"""
    <main class="btc" id="training-coach">
      <section class="btc-hero">
        <div><small>TRAINING COACH · {_safe(athlete_name_value)}</small><span>COUCH → 5K · LEVEL {level} OF 12</span><h1>{_safe(session.title)}</h1><p>{_safe(decision.headline)}</p><div class="btc-tags"><b>{_safe(decision.immediate_timing)}</b><b>PLAN-LED</b><b>NO PACE TARGET</b></div></div>
        <aside><small>THE JOB TODAY</small><h2>Complete, don’t compete.</h2><p>{_safe(session.pace_guidance)}</p></aside>
      </section>
      <section class="btc-card"><small>TODAY'S SESSION</small><h2>Exactly what to do</h2><div class="btc-steps">{sequence}</div></section>
      <section class="btc-grid"><article><small>SUCCESS LOOKS LIKE</small><h2>Finish controlled.</h2><ul>{success}</ul></article><article><small>WHY THIS SESSION</small><h2>{_safe(decision.why[0])}</h2><p>{_safe(session.progression_note)}</p></article></section>
      <section class="btc-card btc-feedback"><div><small>AFTER THE SESSION</small><h2>Your feedback decides what happens next.</h2><p>Performance Passport will use completion, difficulty, pain and your longest running block to recommend whether to progress, repeat, hold or step back.</p></div><ul>{after}</ul></section>
      <section class="btc-card"><small>NUTRITION COACH · EASY DEMAND</small><h2>Keep fuelling uncomplicated.</h2><div class="btc-fuel"><article><b>Before</b><p>{_safe(detail.fuel_before)}</p></article><article><b>During</b><p>{_safe(detail.fuel_during)}</p></article><article><b>After</b><p>{_safe(detail.fuel_after)}</p></article></div></section>
      {style}
    </main>
    """


def build_five_to_ten_training_coach_html(
    athlete_name_value: str,
    detail: TrainingCoachDetail,
) -> str:
    decision = detail.decision
    level = detail.five_to_ten_level or 1
    role = _safe(detail.journey_session_role or "Run")
    return f"""
    <main class="fttc">
      <section class="fttc-hero">
        <div>
          <small>TRAINING COACH · {_safe(athlete_name_value)}</small>
          <span>5K → 10K · LEVEL {level} OF 10</span>
          <h1>{_safe(detail.journey_session_title or decision.immediate_label)}</h1>
          <p>{_safe(detail.journey_session_detail or decision.immediate_detail)}</p>
          <div class="fttc-tags"><b>{_safe(decision.immediate_timing)}</b><b>{role}</b><b>PLAN-LED</b></div>
        </div>
        <aside>
          <small>CURRENT FOCUS</small>
          <h2>{_safe(detail.journey_level_title or "Build toward 10K")}</h2>
          <p>{_safe(detail.journey_level_emphasis or decision.headline)}</p>
          <strong>Long run: {(detail.journey_long_run_km or 0):g} km</strong>
        </aside>
      </section>
      <section class="fttc-grid">
        <article><small>THE JOB TODAY</small><h2>Controlled completion.</h2><p>{_safe(detail.journey_session_detail or "")}</p></article>
        <article><small>WHY THIS RUN</small><h2>{_safe(detail.journey_level_emphasis or "")}</h2><p>Build durability first. Pace is secondary unless the plan explicitly calls for controlled quality.</p></article>
      </section>
      <section class="fttc-card"><small>AFTER THE SESSION</small><h2>Your feedback decides what happens next.</h2><p>Performance Passport combines completion, difficulty, pain and imported activity evidence. It previews Progress, Repeat, Hold, Step Back or Graduate before changing the journey.</p></section>
      <section class="fttc-card"><small>NUTRITION COACH · {_safe(detail.fuel_demand.upper())} DEMAND</small><div class="fttc-fuel"><article><b>Before</b><p>{_safe(detail.fuel_before)}</p></article><article><b>During</b><p>{_safe(detail.fuel_during)}</p></article><article><b>After</b><p>{_safe(detail.fuel_after)}</p></article></div></section>
    </main>
    <style>
      .fttc{{color:#10263D;font-family:Inter,system-ui,sans-serif;display:grid;gap:14px}} .fttc *{{box-sizing:border-box}}
      .fttc-hero,.fttc-card,.fttc-grid>article{{background:#fff;border:1px solid #DED8CE;border-radius:22px;box-shadow:0 12px 30px rgba(16,38,61,.06)}}
      .fttc-hero{{padding:34px;display:grid;grid-template-columns:minmax(0,1fr) 310px;gap:28px;background:radial-gradient(circle at 100% 0,rgba(62,142,114,.14),transparent 38%),#fff}}
      .fttc small{{font-size:11px;letter-spacing:.14em;font-weight:900;color:#718091}} .fttc-hero span{{display:block;margin-top:15px;color:#3E8E72;font-size:12px;font-weight:900;letter-spacing:.12em}}
      .fttc-hero h1{{font-size:48px;margin:7px 0 10px;letter-spacing:-.04em}} .fttc-hero p,.fttc-grid p,.fttc-card p{{color:#617482;line-height:1.5;font-size:13px}}
      .fttc-hero aside{{background:#102E49;color:#fff;border-radius:17px;padding:21px}} .fttc-hero aside small{{color:#9FC4B4}} .fttc-hero aside h2{{font-size:25px}} .fttc-hero aside p{{color:#DCE6EB}} .fttc-hero aside strong{{color:#9FC4B4}}
      .fttc-tags{{display:flex;gap:8px;flex-wrap:wrap;margin-top:18px}} .fttc-tags b{{font-size:10px;background:#E8F5EE;color:#28755B;padding:8px 10px;border-radius:999px}}
      .fttc-grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px}} .fttc-grid>article,.fttc-card{{padding:25px}} .fttc-grid h2,.fttc-card h2{{font-size:26px;margin:5px 0 12px}}
      .fttc-fuel{{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin-top:12px}} .fttc-fuel article{{background:#F8F5EF;border-radius:13px;padding:15px}} .fttc-fuel b{{font-size:11px;color:#F05A28}}
      @media(max-width:760px){{.fttc-hero,.fttc-grid{{grid-template-columns:1fr}}.fttc-fuel{{grid-template-columns:1fr}}}}
    </style>
    """


def _render_five_to_ten_progress_recommendation(
    athlete_id: int,
    decision,
    evidence,
) -> None:
    labels = {
        "progress": "Progress",
        "repeat": "Repeat",
        "hold": "Hold",
        "regress": "Step Back",
        "graduate": "Graduate",
    }
    st.markdown(f"### Recommendation: {labels.get(decision.decision, decision.decision.title())}")
    st.info(decision.reason)
    if decision.week_before is not None:
        st.caption(
            f"Level {decision.week_before} → "
            f"{'Complete' if decision.graduate else f'Level {decision.week_after}'}"
        )
    confirm = st.button(
        "Confirm this recommendation",
        type="primary",
        use_container_width=True,
        key=f"5to10_confirm_{athlete_id}_{decision.decision}_{decision.week_after}",
    )
    if confirm:
        apply_five_to_ten_k_evidence(athlete_id, evidence)
        st.session_state.pop(f"5to10_review_preview_{athlete_id}", None)
        st.cache_data.clear()
        st.rerun()


def _planned_distance_from_detail(detail: TrainingCoachDetail) -> float | None:
    title = str(detail.journey_session_title or "")
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*K\b", title, flags=re.I)
    if match:
        return float(match.group(1))
    return None


def _render_five_to_ten_session_checkin(
    athlete_id: int,
    detail: TrainingCoachDetail,
) -> None:
    if detail.five_to_ten_level is None:
        return
    state_key = f"5to10_review_preview_{athlete_id}"
    activity = find_latest_five_to_ten_k_activity_evidence(
        athlete_id,
        planned_distance_km=_planned_distance_from_detail(detail),
    )

    st.markdown("### How did it go?")
    st.caption(
        "Performance Passport previews the coaching decision first. "
        "Nothing changes until you confirm it."
    )
    use_activity = False
    if activity is not None:
        st.success(
            f"Imported run found: {activity.title} · {activity.activity_date} · "
            f"{activity.distance_km:.2f} km · {round(activity.moving_time_s/60)} min"
        )
        st.caption(activity.match_reason)
        use_activity = st.checkbox(
            "Use this imported run as objective evidence",
            value=True,
            key=f"5to10_use_activity_{athlete_id}_{activity.activity_id}",
        )

    suggested_completed = (
        bool(activity.likely_completed_as_planned)
        if activity is not None and use_activity else True
    )

    with st.form(
        f"5to10_checkin_{athlete_id}_{detail.five_to_ten_level}",
        clear_on_submit=False,
    ):
        completed = st.radio(
            "Did you complete the session as planned?",
            ("Yes","No"),
            index=0 if suggested_completed else 1,
            horizontal=True,
            key=f"5to10_completed_{athlete_id}",
        )
        difficulty = st.select_slider(
            "How difficult did it feel?",
            options=("Comfortable","Moderate","Hard","Very hard"),
            value="Comfortable",
            key=f"5to10_difficulty_{athlete_id}",
        )
        pain = st.radio(
            "Any pain or concerning physical symptoms?",
            ("No","Yes"), horizontal=True,
            key=f"5to10_pain_{athlete_id}",
        )
        submitted = st.form_submit_button(
            "Review this session", type="primary", use_container_width=True
        )

    if submitted:
        linked = activity if activity is not None and use_activity else None
        evidence = JourneyProgressEvidence(
            completed_as_planned=completed == "Yes",
            perceived_difficulty=difficulty,
            pain_or_concerning_symptoms=pain == "Yes",
            activity_id=linked.activity_id if linked else None,
            activity_date=linked.activity_date if linked else None,
            activity_distance_km=linked.distance_km if linked else None,
            activity_moving_time_s=linked.moving_time_s if linked else None,
        )
        decision, prepared = preview_five_to_ten_k_progress(athlete_id, evidence)
        st.session_state[state_key] = (decision, prepared)

    preview = st.session_state.get(state_key)
    if preview is not None:
        decision, evidence = preview
        _render_five_to_ten_progress_recommendation(
            athlete_id, decision, evidence
        )


def build_training_coach_html(
    athlete_name_value: str,
    detail: TrainingCoachDetail,
) -> str:
    """Return the complete Training Coach markup for one real athlete."""
    if detail.beginner_session is not None:
        return build_beginner_training_coach_html(athlete_name_value, detail)
    if detail.five_to_ten_level is not None:
        return build_five_to_ten_training_coach_html(athlete_name_value, detail)

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
            .tc-execution-grid article:nth-child(2) span {{ color:#8ee2c4!important; }}
            .tc-execution-grid article:nth-child(2) h3 {{ color:#fff!important; }}
            .tc-execution-grid h3 {{ margin:9px 0 0; font-size:16px; line-height:1.4; }}
            .tc-source {{ color:#718391; font-size:11px; font-weight:750; text-align:right; }}
            .tc-why-grid {{ display:grid; grid-template-columns:.85fr 1.15fr; gap:18px; margin-top:22px; }}
            .tc-why-grid>ul {{ padding:21px 21px 21px 38px; border-radius:17px; background:#faf8f4; }}
            .tc-history {{ padding:22px; border-radius:18px; background:var(--navy); color:#fff; }}
            .tc-history>span {{ color:#8ee2c4; font-size:10px; font-weight:850; letter-spacing:.12em; text-transform:uppercase; }}
            .tc-history>h3 {{ margin:9px 0 17px; color:#dce5eb!important; font-size:15px; line-height:1.45; }}
            .tc-evidence-row {{ display:grid; grid-template-columns:1fr auto auto; gap:13px; padding:10px 0; border-top:1px solid rgba(255,255,255,.12); }}
            .tc-evidence-row strong,.tc-evidence-row span {{ display:block; }}
            .tc-evidence-row strong {{ color:#fff!important; font-size:11px; }} .tc-evidence-row span {{ margin-top:3px; color:#aebfca!important; font-size:10px; }}
            .tc-muted {{ color:#c2d1da!important; font-size:12px; }}
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



def _beginner_decision_label(decision: str) -> tuple[str, str]:
    labels = {
        "progress": ("Ready to progress", "Move to the next level"),
        "repeat": ("Repeat this level", "Give this level another go"),
        "regress": ("Step back one level", "Reduce the challenge"),
        "hold": ("Hold this level", "Stay here for now"),
        "graduate": ("5K journey complete", "Graduate Couch → 5K"),
    }
    return labels.get(decision, ("Review this level", "Apply recommendation"))


def _render_beginner_progress_recommendation(
    athlete_id: int,
    detail: TrainingCoachDetail,
    decision,
    evidence: JourneyProgressEvidence,
) -> None:
    title, action = _beginner_decision_label(decision.decision)
    before = decision.week_before or detail.beginner_week_number or 1
    after = decision.week_after or before

    movement = (
        f"Level {before} → Level {after}"
        if after != before
        else f"Remain on Level {before}"
    )
    success_count = evidence.sessions_completed_since_decision

    st.markdown(f"### {title}")
    st.caption(movement)
    st.info(decision.reason)

    if decision.decision == "hold" and success_count == 1:
        st.caption(
            "That is one controlled successful session at this level. "
            "A second controlled success can support progression."
        )
    if decision.decision == "graduate":
        st.success(
            "This recommendation completes the active Couch → 5K Runner Journey."
        )

    st.caption(
        "Nothing changes until you confirm the coach recommendation."
    )
    apply_col, keep_col = st.columns([1.35, 1])
    with apply_col:
        apply_now = st.button(
            action,
            type="primary",
            use_container_width=True,
            key=f"c25k_apply_review_{athlete_id}_{before}_{decision.decision}",
        )
    with keep_col:
        keep = st.button(
            "Not now",
            use_container_width=True,
            key=f"c25k_keep_review_{athlete_id}_{before}_{decision.decision}",
        )

    state_key = f"c25k_review_preview_{athlete_id}"
    if keep:
        st.session_state.pop(state_key, None)
        st.rerun()

    if apply_now:
        applied = apply_couch_to_5k_evidence(athlete_id, evidence)
        st.session_state.pop(state_key, None)
        st.cache_data.clear()
        applied_title, _ = _beginner_decision_label(applied.decision)
        st.success(f"{applied_title}. {applied.reason}")
        st.rerun()


def _render_beginner_session_checkin(
    athlete_id: int,
    detail: TrainingCoachDetail,
) -> None:
    if detail.beginner_session is None:
        return

    state_key = f"c25k_review_preview_{athlete_id}"
    activity = find_latest_beginner_activity_evidence(
        athlete_id,
        planned_duration_s=detail.beginner_session.total_duration_s,
    )

    st.markdown("### How did it go?")
    st.caption(
        "A short check-in lets Performance Passport recommend whether to "
        "progress, repeat, hold or step back. The plan never changes without "
        "your confirmation."
    )

    use_activity = False
    if activity is not None:
        st.success(
            f"Imported activity found: {activity.title} · "
            f"{activity.activity_date} · {activity.distance_km:.2f} km · "
            f"{round(activity.moving_time_s / 60.0)} min"
        )
        st.caption(activity.match_reason)
        use_activity = st.checkbox(
            "Use this imported activity to pre-fill objective evidence",
            value=True,
            key=f"c25k_use_activity_{athlete_id}_{activity.activity_id}",
            help=(
                "Performance Passport can suggest completion and 5K evidence "
                "from the recorded activity. You still confirm the answers."
            ),
        )

    suggested_completed = (
        bool(activity.likely_completed_as_planned)
        if activity is not None and use_activity
        else True
    )
    suggested_5k = (
        bool(activity.completed_5k)
        if activity is not None and use_activity
        else False
    )

    with st.form(
        f"c25k_session_checkin_{athlete_id}_{detail.beginner_week_number}",
        clear_on_submit=False,
    ):
        completed = st.radio(
            "Did you complete the session as planned?",
            ("Yes", "No"),
            index=0 if suggested_completed else 1,
            horizontal=True,
            key=f"c25k_completed_{athlete_id}",
        )
        difficulty = st.select_slider(
            "How difficult did it feel?",
            options=("Comfortable", "Moderate", "Hard", "Very hard"),
            value="Comfortable",
            key=f"c25k_difficulty_{athlete_id}",
        )
        pain = st.radio(
            "Any pain or concerning physical symptoms?",
            ("No", "Yes"),
            horizontal=True,
            key=f"c25k_pain_{athlete_id}",
        )
        continuous = st.number_input(
            "Longest continuous running block (minutes)",
            min_value=0.0,
            max_value=180.0,
            value=0.0,
            step=1.0,
            key=f"c25k_continuous_{athlete_id}",
            help=(
                "This remains athlete-confirmed. A normal activity summary "
                "cannot reliably distinguish every run/walk interval."
            ),
        )
        completed_5k = st.checkbox(
            "I completed a full 5K in this session",
            value=suggested_5k,
            key=f"c25k_completed_5k_{athlete_id}",
        )
        submitted = st.form_submit_button(
            "Review this session",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        linked = activity if activity is not None and use_activity else None
        evidence = JourneyProgressEvidence(
            completed_as_planned=completed == "Yes",
            perceived_difficulty=difficulty,
            pain_or_concerning_symptoms=pain == "Yes",
            continuous_run_minutes=float(continuous) if continuous > 0 else None,
            completed_5k=bool(completed_5k),
            activity_id=linked.activity_id if linked else None,
            activity_date=linked.activity_date if linked else None,
            activity_distance_km=linked.distance_km if linked else None,
            activity_moving_time_s=linked.moving_time_s if linked else None,
        )
        decision, prepared = preview_couch_to_5k_progress(
            athlete_id,
            evidence,
        )
        st.session_state[state_key] = (decision, prepared)

    preview = st.session_state.get(state_key)
    if preview is not None:
        decision, evidence = preview
        _render_beginner_progress_recommendation(
            athlete_id,
            detail,
            decision,
            evidence,
        )


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
            get_athlete_cache_version(athlete_id),
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
    if detail.beginner_session is not None:
        _render_beginner_session_checkin(athlete_id, detail)
    elif detail.five_to_ten_level is not None:
        _render_five_to_ten_session_checkin(athlete_id, detail)
