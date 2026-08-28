"""Premium Recovery Coach page with explicit athlete-reported context."""

from __future__ import annotations

import datetime
import html

import streamlit as st

from core.recovery_coach import (
    RecoveryCoachDetail,
    build_recovery_coach_detail,
    save_recovery_checkin,
)
from ui.athlete_selection import (
    SESSION_ID_KEY,
    SESSION_NAME_KEY,
    athlete_name,
    get_athletes,
    render_athlete_id_selector,
)
from ui.recovery_coach_navigation import (
    clear_recovery_coach_params,
    read_recovery_coach_request,
)


RECOVERY_COACH_CACHE_SCHEMA = 2


def _safe(value) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _friendly_date(value: str) -> str:
    try:
        return datetime.date.fromisoformat(str(value)[:10]).strftime("%-d %B %Y")
    except (TypeError, ValueError):
        return str(value)


def _change(value: float | None) -> str:
    return "Baseline building" if value is None else f"{value:+.0f}%"


def _drift(detail: RecoveryCoachDetail) -> str:
    value = detail.durability.recent_decoupling_percent
    return "Building" if value is None else f"{value:.1f}%"


def _duration(value: float | None) -> str:
    if value is None:
        return "Building"
    minutes = max(0, round(value))
    return f"{minutes // 60}h {minutes % 60:02d}m"


def _metric(value: float | None, unit: str) -> str:
    return "Building" if value is None else f"{value:.1f}<small>{_safe(unit)}</small>"


def _checkin_values(detail: RecoveryCoachDetail) -> str:
    checkin = detail.checkin
    if checkin is None:
        return """
        <div class="rc-report-empty">
            <strong>Not reported today</strong>
            <span>Recovery Coach will not guess how the athlete feels.</span>
        </div>
        """
    values = (
        ("Sleep", checkin.sleep_quality, "Higher is better"),
        ("Fatigue", checkin.fatigue, "Lower is better"),
        ("Soreness", checkin.soreness, "Lower is better"),
        ("Motivation", checkin.motivation, "Higher is better"),
    )
    return '<div class="rc-report-grid">' + "".join(
        f"""
        <div><span>{_safe(label)}</span><strong>{value}<small>/5</small></strong><em>{_safe(note)}</em></div>
        """
        for label, value, note in values
    ) + "</div>"


def _signal_cards(detail: RecoveryCoachDetail) -> str:
    schedule_value = (
        f"{detail.schedule.recovery_support_days} days"
        if detail.schedule.available else "No block"
    )
    return f"""
    <section class="rc-signals" aria-label="Recovery evidence summary">
        <article class="rc-signal rc-reported">
            <span>Reported today</span>
            <strong>{_safe(detail.checkin_status)}</strong>
            <p>Athlete report only—never inferred from pace or heart rate.</p>
        </article>
        <article class="rc-signal">
            <span>Rolling seven-day load</span>
            <strong>{detail.load.current_miles:.1f} mi</strong>
            <p>{_safe(_change(detail.load.change_percent))} versus recent rolling weeks · {detail.load.active_days} running days.</p>
        </article>
        <article class="rc-signal">
            <span>Recovery support</span>
            <strong>{_safe(schedule_value)}</strong>
            <p>{_safe(detail.schedule.status)} in the athlete-approved week.</p>
        </article>
        <article class="rc-signal">
            <span>Long-run durability</span>
            <strong>{_safe(_drift(detail))}</strong>
            <p>{_safe(detail.durability.status)} · {detail.durability.sample_size} qualifying long runs.</p>
        </article>
    </section>
    """


def _health_cards(detail: RecoveryCoachDetail) -> str:
    health = detail.health
    if not health.available:
        return f"""
        <section class="rc-health rc-health-empty">
            <div><div class="rc-dark-eyebrow"><span></span>Wearable evidence</div><h2>Connect the athlete’s personal recovery baseline.</h2></div>
            <p>{_safe(health.explanation)} Use Import → Runalyze Health CSV.</p>
        </section>
        """
    hrv_change = (
        "Baseline building"
        if health.hrv_change_percent is None
        else f"{health.hrv_change_percent:+.1f}% vs baseline"
    )
    resting_change = (
        "Baseline building"
        if health.resting_hr_change is None
        else f"{health.resting_hr_change:+.1f} bpm vs baseline"
    )
    sleep_change = (
        "Baseline building"
        if health.sleep_change_minutes is None
        else f"{health.sleep_change_minutes:+.0f} min vs baseline"
    )
    metric_note = (
        f"Runalyze metric {health.hrv_metric_code} retained"
        if health.hrv_metric_code else "Runalyze metric retained"
    )
    return f"""
    <section class="rc-health">
        <div class="rc-health-heading">
            <div><div class="rc-dark-eyebrow"><span></span>Personal health baseline</div><h2>Seven recent days, compared with the previous 28.</h2></div>
            <div><strong>{_safe(health.confidence)} confidence</strong><span>Latest {_safe(_friendly_date(health.latest_date or ''))}</span></div>
        </div>
        <div class="rc-health-grid">
            <article><span>Nightly HRV</span><strong>{_metric(health.hrv_recent, 'ms')}</strong><b>{_safe(health.hrv_status)}</b><p>{_safe(hrv_change)} · {_safe(metric_note)}</p></article>
            <article><span>Resting heart rate</span><strong>{_metric(health.resting_hr_recent, 'bpm')}</strong><b>{_safe(health.resting_hr_status)}</b><p>{_safe(resting_change)}</p></article>
            <article><span>Sleep duration</span><strong>{_safe(_duration(health.sleep_recent_minutes))}</strong><b>{_safe(health.sleep_status)}</b><p>{_safe(sleep_change)} · quality {_safe(health.sleep_quality_recent if health.sleep_quality_recent is not None else 'building')}/100</p></article>
        </div>
        <p class="rc-health-note">{_safe(health.explanation)} These signals support the athlete’s report; they do not diagnose health or change the plan automatically.</p>
    </section>
    """


def build_recovery_coach_upper_html(detail: RecoveryCoachDetail) -> str:
    return f"""
    <div class="rc-home" id="recovery-coach">
        <section class="rc-hero">
            <div class="rc-hero-copy">
                <div class="rc-eyebrow"><span></span>Recovery Coach · {_safe(detail.athlete_name)}</div>
                <h1>{_safe(detail.headline)}</h1>
                <p>{_safe(detail.direction)}</p>
                <div class="rc-evidence-badges">
                    <span>Training balance</span>
                    <span>{_safe(detail.evidence_confidence)} evidence confidence</span>
                    <span>No hidden readiness score</span>
                </div>
            </div>
            <aside class="rc-report">
                <div class="rc-report-head"><span>Today’s check-in</span><b>{_safe(_friendly_date(detail.reference_date))}</b></div>
                {_checkin_values(detail)}
                <div class="rc-report-status"><i></i>{_safe(detail.checkin_status)}</div>
            </aside>
        </section>
        {_signal_cards(detail)}
        {_health_cards(detail)}
        <section class="rc-checkin-intro">
            <div><div class="rc-dark-eyebrow"><span></span>Your report</div><h2>How do you feel today?</h2></div>
            <p>Four quick answers give Recovery Coach context that training data cannot provide. Saving them records your report; it does not automatically change the plan.</p>
        </section>
        <style>
            .rc-home {{ --rc-navy:#08253e; --rc-ink:#10273d; --rc-muted:#607584; --rc-orange:#f15a2a; --rc-green:#279675; color:var(--rc-ink); font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
            .rc-home * {{ box-sizing:border-box; }}
            .rc-hero {{ position:relative; display:grid; grid-template-columns:minmax(0,1.35fr) minmax(390px,.65fr); gap:28px; overflow:hidden; padding:38px; border-radius:28px; background:radial-gradient(circle at 92% 8%,rgba(54,170,148,.25),transparent 34%),linear-gradient(125deg,#071f37,#0b304c 62%,#0d4b57); color:#fff!important; box-shadow:0 24px 55px rgba(10,33,53,.18); }}
            .rc-hero:after {{ content:""; position:absolute; right:-165px; bottom:-290px; width:560px; height:560px; border:60px solid rgba(255,255,255,.035); border-radius:50%; }}
            .rc-hero-copy,.rc-report {{ position:relative; z-index:1; }}
            .rc-eyebrow,.rc-dark-eyebrow {{ display:flex; align-items:center; gap:10px; color:#8ee2c4!important; font-size:12px; font-weight:850; letter-spacing:.17em; text-transform:uppercase; }}
            .rc-eyebrow span,.rc-dark-eyebrow span {{ width:29px; height:3px; border-radius:99px; background:var(--rc-orange); }}
            .rc-dark-eyebrow {{ color:#6a7b88!important; }}
            .rc-hero h1 {{ max-width:850px; margin:15px 0 0; color:#fff!important; font-size:clamp(40px,4.5vw,64px); line-height:.99; letter-spacing:-.052em; }}
            .rc-hero-copy>p {{ max-width:850px; margin:17px 0 0; color:#d4e0e7!important; font-size:18px; line-height:1.52; }}
            .rc-evidence-badges {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:23px; }}
            .rc-evidence-badges span {{ padding:7px 10px; border:1px solid rgba(255,255,255,.15); border-radius:999px; background:rgba(255,255,255,.07); color:#c2d3dc!important; font-size:11px; font-weight:750; }}
            .rc-report {{ align-self:stretch; padding:23px; border:1px solid rgba(255,255,255,.18); border-radius:21px; background:rgba(255,255,255,.09); backdrop-filter:blur(8px); }}
            .rc-report-head {{ display:flex; justify-content:space-between; gap:15px; padding-bottom:15px; border-bottom:1px solid rgba(255,255,255,.13); }}
            .rc-report-head span {{ color:#9ab0bd!important; font-size:11px; font-weight:850; letter-spacing:.13em; text-transform:uppercase; }}
            .rc-report-head b {{ color:#fff!important; font-size:11px; }}
            .rc-report-empty {{ min-height:125px; display:flex; flex-direction:column; justify-content:center; }}
            .rc-report-empty strong {{ color:#fff!important; font-size:23px; }}
            .rc-report-empty span {{ max-width:290px; margin-top:8px; color:#bdcdd7!important; font-size:13px; line-height:1.45; }}
            .rc-report-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:9px; margin-top:16px; }}
            .rc-report-grid>div {{ padding:12px; border-radius:13px; background:rgba(255,255,255,.07); }}
            .rc-report-grid span,.rc-report-grid strong,.rc-report-grid em {{ display:block; }}
            .rc-report-grid span {{ color:#a8bbc7!important; font-size:9px; font-weight:800; text-transform:uppercase; }}
            .rc-report-grid strong {{ margin-top:4px; color:#fff!important; font-size:22px; }}
            .rc-report-grid strong small {{ color:#a8bbc7!important; font-size:10px; }}
            .rc-report-grid em {{ margin-top:2px; color:#a8bbc7!important; font-size:8px; font-style:normal; }}
            .rc-report-status {{ display:flex; align-items:center; gap:8px; margin-top:15px; color:#8ee2c4!important; font-size:11px; font-weight:800; }}
            .rc-report-status i {{ width:8px; height:8px; border-radius:50%; background:#73dfb6; box-shadow:0 0 0 4px rgba(115,223,182,.13); }}
            .rc-signals {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:11px; margin-top:13px; }}
            .rc-signal {{ min-width:0; padding:20px; border:1px solid #dfd9d0; border-radius:17px; background:#fff; box-shadow:0 10px 27px rgba(36,44,50,.055); }}
            .rc-reported {{ border-top:3px solid var(--rc-orange); }}
            .rc-signal>span {{ color:#758794!important; font-size:10px; font-weight:820; letter-spacing:.11em; text-transform:uppercase; }}
            .rc-signal>strong {{ display:block; margin-top:8px; color:var(--rc-ink)!important; font-size:23px; line-height:1.1; letter-spacing:-.025em; }}
            .rc-signal>p {{ margin:8px 0 0; color:#657987!important; font-size:12px; line-height:1.45; }}
            .rc-health {{ margin-top:13px; padding:25px; border:1px solid #ded8cf; border-radius:22px; background:radial-gradient(circle at 100% 0,rgba(39,150,117,.08),transparent 37%),#fff; box-shadow:0 12px 31px rgba(36,44,50,.06); }}
            .rc-health-heading {{ display:flex; align-items:flex-end; justify-content:space-between; gap:25px; }}
            .rc-health-heading h2 {{ margin:8px 0 0; color:var(--rc-ink)!important; font-size:29px; line-height:1.08; letter-spacing:-.035em; }}
            .rc-health-heading>div:last-child {{ text-align:right; }}
            .rc-health-heading>div:last-child strong,.rc-health-heading>div:last-child span {{ display:block; }}
            .rc-health-heading>div:last-child strong {{ color:var(--rc-green)!important; font-size:13px; }}
            .rc-health-heading>div:last-child span {{ margin-top:4px; color:#718391!important; font-size:11px; }}
            .rc-health-grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; margin-top:20px; }}
            .rc-health-grid article {{ min-width:0; padding:18px; border:1px solid #e2ddd5; border-radius:16px; background:#faf8f4; }}
            .rc-health-grid article>span {{ color:#748692!important; font-size:10px; font-weight:820; letter-spacing:.11em; text-transform:uppercase; }}
            .rc-health-grid article>strong {{ display:block; margin-top:8px; color:var(--rc-ink)!important; font-size:29px; line-height:1; letter-spacing:-.03em; }}
            .rc-health-grid article>strong small {{ margin-left:4px; color:#6d7f8c!important; font-size:10px; font-weight:760; }}
            .rc-health-grid article>b {{ display:block; margin-top:11px; color:var(--rc-green)!important; font-size:12px; }}
            .rc-health-grid article>p,.rc-health-note,.rc-health-empty>p {{ margin:6px 0 0; color:#657987!important; font-size:12px; line-height:1.5; }}
            .rc-health-note {{ margin-top:15px; }}
            .rc-health-empty {{ display:flex; align-items:flex-end; justify-content:space-between; gap:28px; }}
            .rc-health-empty h2 {{ margin:8px 0 0; color:var(--rc-ink)!important; font-size:27px; }}
            .rc-health-empty>p {{ max-width:560px; text-align:right; }}
            .rc-checkin-intro {{ display:flex; align-items:end; justify-content:space-between; gap:30px; margin:30px 2px 13px; }}
            .rc-checkin-intro h2 {{ margin:7px 0 0; color:var(--rc-ink)!important; font-size:32px; line-height:1.06; letter-spacing:-.035em; }}
            .rc-checkin-intro>p {{ max-width:680px; margin:0; color:#607584!important; font-size:14px; line-height:1.48; text-align:right; }}
            [data-testid="stForm"] {{ padding:21px 22px 18px; border:1px solid #ded8cf; border-radius:20px; background:#fff; box-shadow:0 12px 31px rgba(36,44,50,.06); }}
            [data-testid="stForm"] [data-testid="stSlider"] p {{ color:#304b60!important; font-size:13px; font-weight:760; }}
            [data-testid="stForm"] [data-testid="stTextArea"] textarea {{ color:#10263d!important; background:#fff!important; }}
            @media (max-width:1100px) {{ .rc-hero {{ grid-template-columns:1fr; }} .rc-signals {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} .rc-health-grid {{ grid-template-columns:1fr; }} }}
            @media (max-width:720px) {{ .rc-hero {{ padding:26px; }} .rc-hero h1 {{ font-size:40px; }} .rc-signals {{ grid-template-columns:1fr; }} .rc-health-heading,.rc-health-empty,.rc-checkin-intro {{ align-items:flex-start; flex-direction:column; }} .rc-health-heading>div:last-child,.rc-health-empty>p,.rc-checkin-intro>p {{ text-align:left; }} }}
        </style>
    </div>
    """


def _week_strip(detail: RecoveryCoachDetail) -> str:
    if not detail.schedule.days:
        return '<div class="rc-empty">Save an approved Training Block to add planned recovery spacing.</div>'
    cards = []
    for day in detail.schedule.days:
        tone = (
            "is-today" if day.is_today
            else "is-demand" if day.is_demanding
            else "is-support" if day.is_recovery_support
            else ""
        )
        marker = "Demand" if day.is_demanding else "Support" if day.is_recovery_support else "Plan"
        cards.append(
            f"""
            <article class="rc-day {tone}">
                <div><span>{_safe(day.day[:3])}</span><b>{_safe(marker)}</b></div>
                <strong>{_safe(day.session_type)}</strong>
                <small>{_safe(day.status)}</small>
            </article>
            """
        )
    return '<div class="rc-week-strip">' + "".join(cards) + "</div>"


def _list(items: tuple[str, ...], empty: str) -> str:
    values = items or (empty,)
    return "".join(f"<li>{_safe(item)}</li>" for item in values)


def _priority_cards(detail: RecoveryCoachDetail) -> str:
    return "".join(
        f"""
        <article><span>{index:02d}</span><p>{_safe(item)}</p></article>
        """
        for index, item in enumerate(detail.priorities, start=1)
    )


def _mobility_cards(detail: RecoveryCoachDetail) -> str:
    return "".join(
        f"""
        <article class="rc-mobility-card">
            <div><span>{_safe(routine.duration)}</span><strong>{_safe(routine.title)}</strong></div>
            <p>{_safe(routine.purpose)}</p>
            <ul>{''.join(f'<li>{_safe(exercise)}</li>' for exercise in routine.exercises)}</ul>
            <small>{_safe(routine.caution)}</small>
        </article>
        """
        for routine in detail.mobility_routines
    )


def build_recovery_coach_lower_html(detail: RecoveryCoachDetail) -> str:
    cautions = detail.cautions or (
        "No additional caution is identified from the evidence currently connected.",
    )
    return f"""
    <div class="rc-lower">
        <section class="rc-section">
            <div class="rc-section-head">
                <div><div class="rc-kicker"><span></span>Approved training week</div><h2>Recovery has a place in the plan.</h2></div>
                <div class="rc-week-context"><strong>{_safe(detail.schedule.block_name)}</strong><span>{_safe(detail.schedule.week_label)} · {_safe(detail.schedule.status)}</span></div>
            </div>
            <p class="rc-section-copy">{_safe(detail.schedule.explanation)}</p>
            {_week_strip(detail)}
        </section>

        <section class="rc-evidence-grid">
            <article class="rc-section rc-evidence-good">
                <div class="rc-kicker"><span></span>What supports recovery</div>
                <h2>Useful space and durable habits.</h2>
                <ul>{_list(detail.strengths, 'Supportive evidence is still building.')}</ul>
            </article>
            <article class="rc-section rc-evidence-watch">
                <div class="rc-kicker"><span></span>What to watch</div>
                <h2>Reasons to stay responsive.</h2>
                <ul>{_list(tuple(cautions), 'No caution is currently recorded.')}</ul>
            </article>
        </section>

        <section class="rc-section">
            <div class="rc-section-head">
                <div><div class="rc-kicker"><span></span>Recovery priorities</div><h2>Do the next useful thing.</h2></div>
                <p>Clear choices for today—not another score to chase.</p>
            </div>
            <div class="rc-priorities">{_priority_cards(detail)}</div>
        </section>

        <section class="rc-section rc-mobility">
            <div class="rc-section-head">
                <div><div class="rc-kicker"><span></span>Gentle mobility</div><h2>Move enough to feel better—not worked.</h2></div>
                <p>Three short options for comfortable mobility. They are not injury treatment and should never reproduce pain.</p>
            </div>
            <div class="rc-mobility-grid">{_mobility_cards(detail)}</div>
        </section>

        <section class="rc-boundary">
            <div class="rc-boundary-mark">RC</div>
            <div><div class="rc-boundary-kicker">Evidence boundary</div><h2>Training balance, not invented physiology.</h2><ul>{_list(detail.limitations, 'No additional limitation recorded.')}</ul></div>
        </section>

        <style>
            .rc-lower {{ --rc-navy:#08253e; --rc-ink:#10273d; --rc-muted:#607584; --rc-orange:#f15a2a; --rc-green:#279675; color:var(--rc-ink); font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
            .rc-lower * {{ box-sizing:border-box; }}
            .rc-section {{ margin-top:18px; padding:29px; border:1px solid #ded8cf; border-radius:23px; background:#fff; box-shadow:0 14px 36px rgba(36,44,50,.06); }}
            .rc-section-head {{ display:flex; align-items:flex-end; justify-content:space-between; gap:26px; }}
            .rc-kicker {{ display:flex; align-items:center; gap:10px; color:#6b7d8b!important; font-size:11px; font-weight:850; letter-spacing:.15em; text-transform:uppercase; }}
            .rc-kicker span {{ width:28px; height:3px; border-radius:99px; background:var(--rc-orange); }}
            .rc-section h2 {{ margin:8px 0 0; color:var(--rc-ink)!important; font-size:31px; line-height:1.06; letter-spacing:-.035em; }}
            .rc-section-head>p {{ max-width:520px; margin:0; color:#647987!important; font-size:14px; line-height:1.48; text-align:right; }}
            .rc-week-context {{ text-align:right; }}
            .rc-week-context strong,.rc-week-context span {{ display:block; }}
            .rc-week-context strong {{ color:var(--rc-ink)!important; font-size:14px; }}
            .rc-week-context span {{ margin-top:5px; color:#718391!important; font-size:11px; }}
            .rc-section-copy {{ max-width:920px; margin:13px 0 0; color:#607584!important; font-size:14px; line-height:1.52; }}
            .rc-week-strip {{ display:grid; grid-template-columns:repeat(7,minmax(0,1fr)); gap:8px; margin-top:22px; }}
            .rc-day {{ min-width:0; min-height:145px; padding:15px; border:1px solid #e2ddd5; border-radius:15px; background:#faf8f4; }}
            .rc-day>div {{ display:flex; align-items:center; justify-content:space-between; gap:8px; }}
            .rc-day>div span {{ color:#6d7e8b!important; font-size:10px; font-weight:850; letter-spacing:.12em; text-transform:uppercase; }}
            .rc-day>div b {{ color:#88959e!important; font-size:8px; text-transform:uppercase; }}
            .rc-day>strong,.rc-day>small {{ display:block; }}
            .rc-day>strong {{ margin-top:24px; color:var(--rc-ink)!important; font-size:15px; line-height:1.18; }}
            .rc-day>small {{ margin-top:8px; color:#788894!important; font-size:10px; }}
            .rc-day.is-support {{ border-color:#cce4d9; background:#f1f8f4; }}
            .rc-day.is-support>div b {{ color:var(--rc-green)!important; }}
            .rc-day.is-demand {{ border-top:3px solid var(--rc-orange); background:#fff8f3; }}
            .rc-day.is-today {{ outline:2px solid var(--rc-green); outline-offset:2px; }}
            .rc-evidence-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:13px; }}
            .rc-evidence-grid .rc-section {{ min-height:260px; }}
            .rc-evidence-good {{ background:radial-gradient(circle at 100% 0,rgba(39,150,117,.10),transparent 38%),#fff; }}
            .rc-evidence-watch {{ background:radial-gradient(circle at 100% 0,rgba(241,90,42,.10),transparent 38%),#fff; }}
            .rc-evidence-grid ul {{ margin:20px 0 0; padding-left:20px; color:#536a79!important; font-size:14px; line-height:1.65; }}
            .rc-evidence-grid li {{ margin:7px 0; color:#536a79!important; }}
            .rc-priorities {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; margin-top:21px; }}
            .rc-priorities article {{ display:flex; min-height:125px; gap:15px; padding:20px; border:1px solid #e2ddd5; border-radius:17px; background:#faf8f4; }}
            .rc-priorities span {{ display:grid; place-items:center; flex:0 0 38px; width:38px; height:38px; border-radius:12px; background:var(--rc-navy); color:#fff!important; font-size:11px; font-weight:900; }}
            .rc-priorities p {{ margin:2px 0 0; color:#455e70!important; font-size:14px; line-height:1.5; }}
            .rc-mobility {{ background:radial-gradient(circle at 100% 0,rgba(72,129,164,.09),transparent 37%),#fff; }}
            .rc-mobility-grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; margin-top:21px; }}
            .rc-mobility-card {{ min-width:0; padding:20px; border:1px solid #e2ddd5; border-radius:17px; background:#faf8f4; }}
            .rc-mobility-card>div span,.rc-mobility-card>div strong {{ display:block; }}
            .rc-mobility-card>div span {{ color:var(--rc-green)!important; font-size:10px; font-weight:850; letter-spacing:.1em; text-transform:uppercase; }}
            .rc-mobility-card>div strong {{ margin-top:6px; color:var(--rc-ink)!important; font-size:20px; letter-spacing:-.02em; }}
            .rc-mobility-card>p {{ min-height:42px; margin:10px 0 0; color:#5d7280!important; font-size:13px; line-height:1.48; }}
            .rc-mobility-card>ul {{ margin:16px 0 0; padding-left:18px; }}
            .rc-mobility-card>li,.rc-mobility-card li {{ margin:7px 0; color:#455e70!important; font-size:12px; line-height:1.42; }}
            .rc-mobility-card>small {{ display:block; margin-top:16px; padding-top:13px; border-top:1px solid #e1dcd4; color:#748692!important; font-size:10px; line-height:1.45; }}
            .rc-boundary {{ display:grid; grid-template-columns:auto 1fr; gap:24px; margin:18px 0 8px; padding:28px 30px; border-radius:23px; background:radial-gradient(circle at 92% 10%,rgba(45,159,133,.24),transparent 35%),linear-gradient(125deg,#071f37,#0b344f); color:#fff!important; box-shadow:0 18px 42px rgba(8,36,61,.15); }}
            .rc-boundary-mark {{ display:grid; place-items:center; width:64px; height:64px; border:1px solid rgba(255,255,255,.2); border-radius:18px; background:rgba(255,255,255,.08); color:#fff!important; font-size:18px; font-weight:900; }}
            .rc-boundary-kicker {{ color:#8ee2c4!important; font-size:11px; font-weight:850; letter-spacing:.14em; text-transform:uppercase; }}
            .rc-boundary h2 {{ margin:7px 0 0; color:#fff!important; font-size:28px; line-height:1.08; }}
            .rc-boundary ul {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:6px 28px; margin:16px 0 0; padding-left:18px; }}
            .rc-boundary li {{ color:#c7d6de!important; font-size:12px; line-height:1.45; }}
            .rc-empty {{ margin-top:20px; padding:20px; border-radius:15px; background:#faf8f4; color:#657987!important; font-size:13px; }}
            @media (max-width:1100px) {{ .rc-week-strip {{ grid-template-columns:repeat(4,minmax(0,1fr)); }} .rc-priorities,.rc-mobility-grid {{ grid-template-columns:1fr; }} }}
            @media (max-width:720px) {{ .rc-section {{ padding:22px; }} .rc-section-head {{ align-items:flex-start; flex-direction:column; }} .rc-section-head>p,.rc-week-context {{ text-align:left; }} .rc-week-strip,.rc-evidence-grid {{ grid-template-columns:1fr; }} .rc-day {{ min-height:115px; }} .rc-boundary {{ grid-template-columns:1fr; padding:24px; }} .rc-boundary ul {{ grid-template-columns:1fr; }} }}
        </style>
    </div>
    """


def build_recovery_coach_html(detail: RecoveryCoachDetail) -> str:
    """Return complete testable markup around the interactive check-in."""
    return build_recovery_coach_upper_html(detail) + build_recovery_coach_lower_html(detail)


@st.cache_data(show_spinner=False, ttl=120)
def _cached_recovery_coach(
    athlete_id: int,
    today: datetime.date,
    schema: int,
) -> RecoveryCoachDetail | None:
    del schema
    return build_recovery_coach_detail(athlete_id, today=today)


def _apply_recovery_coach_request() -> None:
    request = read_recovery_coach_request(st.query_params)
    if request is None:
        return
    rows_by_id = {int(row[0]): row for row in get_athletes()}
    row = rows_by_id.get(request.athlete_id)
    if row is not None:
        st.session_state[SESSION_ID_KEY] = request.athlete_id
        st.session_state[SESSION_NAME_KEY] = athlete_name(row)
    clear_recovery_coach_params(st.query_params)


def _checkin_form(detail: RecoveryCoachDetail, today: datetime.date) -> None:
    current = detail.checkin
    with st.form(f"recovery_checkin_{detail.athlete_id}_{today.isoformat()}"):
        columns = st.columns(4)
        with columns[0]:
            sleep = st.slider(
                "Sleep quality",
                1,
                5,
                current.sleep_quality if current else 3,
                help="1 = very poor, 5 = excellent",
            )
        with columns[1]:
            fatigue = st.slider(
                "Fatigue",
                1,
                5,
                current.fatigue if current else 3,
                help="1 = fresh, 5 = very fatigued",
            )
        with columns[2]:
            soreness = st.slider(
                "Soreness",
                1,
                5,
                current.soreness if current else 2,
                help="1 = none, 5 = unusually high",
            )
        with columns[3]:
            motivation = st.slider(
                "Motivation",
                1,
                5,
                current.motivation if current else 4,
                help="1 = very low, 5 = very high",
            )
        notes = st.text_area(
            "Optional note",
            value=current.notes if current and current.notes else "",
            placeholder="For example: poor sleep, heavy legs, focal calf soreness…",
            max_chars=500,
        )
        submitted = st.form_submit_button(
            "Save today’s check-in",
            type="primary",
            use_container_width=True,
        )
    if submitted:
        save_recovery_checkin(
            detail.athlete_id,
            today,
            sleep_quality=sleep,
            fatigue=fatigue,
            soreness=soreness,
            motivation=motivation,
            notes=notes,
        )
        st.cache_data.clear()
        st.success("Today’s recovery check-in has been saved.")
        st.rerun()


def show_recovery_coach_page() -> None:
    st.markdown(
        """
        <style>
            [data-testid="stMainBlockContainer"] { max-width:1480px; padding-top:4rem; padding-bottom:3rem; }
            [data-testid="stSelectbox"] { max-width:430px; }
            [data-testid="stSelectbox"] > div > div { min-height:48px; border:1px solid #d9d3ca; border-radius:14px; background:#fff; box-shadow:0 8px 20px rgba(30,42,52,.055); }
        </style>
        """,
        unsafe_allow_html=True,
    )
    _apply_recovery_coach_request()
    athlete_id = render_athlete_id_selector(
        label="Athlete",
        label_visibility="collapsed",
    )
    if athlete_id is None:
        st.info("Add an athlete before asking the Recovery Coach.")
        return
    today = datetime.date.today()
    with st.spinner("Recovery Coach is separating training evidence from today’s report…"):
        detail = _cached_recovery_coach(
            athlete_id,
            today,
            RECOVERY_COACH_CACHE_SCHEMA,
        )
    if detail is None:
        st.warning("Recovery evidence is not available for this athlete yet.")
        return
    st.html(build_recovery_coach_upper_html(detail))
    _checkin_form(detail, today)
    st.html(build_recovery_coach_lower_html(detail))
    st.caption(
        "Recovery Coach provides training guidance, not medical diagnosis. "
        "Persistent, focal or worsening pain—and symptoms of illness—should "
        "take priority over the training plan and may need professional advice."
    )
