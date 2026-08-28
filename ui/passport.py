"""Production Passport Detail presentation."""

from __future__ import annotations

import html
from pathlib import Path
import re

import streamlit as st

from core.cache_version import (
    NAVIGATION_CACHE_TTL_SECONDS,
    get_athlete_cache_version,
)
from core.passport_detail import PassportDetail, build_passport_detail
from core.training_blueprint import BlueprintCategory
from ui.athlete_card import image_to_data_uri
from ui.athlete_selection import render_athlete_id_selector


PASSPORT_CACHE_SCHEMA = 2
ROOT = Path(__file__).resolve().parent.parent


@st.cache_data(show_spinner=False, ttl=NAVIGATION_CACHE_TTL_SECONDS)
def _cached_passport(
    athlete_id: int, schema: int, data_version
) -> PassportDetail | None:
    del schema, data_version
    return build_passport_detail(athlete_id)


def _escape(value) -> str:
    return html.escape(str(value or ""))


def _clock(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    total = int(round(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def _photo_path(first_name: str, last_name: str) -> Path | None:
    slug = re.sub(
        r"[^a-z0-9]+",
        "_",
        f"{first_name} {last_name}".strip().lower(),
    ).strip("_")
    for suffix in (".jpg", ".jpeg", ".png", ".webp"):
        candidate = ROOT / "assets" / "athletes" / f"{slug}{suffix}"
        if candidate.exists():
            return candidate
    return None


def _athlete_photo(detail: PassportDetail) -> str:
    athlete = detail.athlete
    path = _photo_path(athlete.first_name, athlete.last_name)
    if path is None:
        return f'<div class="passport-photo-fallback">{_escape(athlete.initials)}</div>'
    return (
        f'<img class="passport-athlete-photo" src="{image_to_data_uri(path)}" '
        f'alt="{_escape(athlete.full_name)}">'
    )


def _pace(seconds_per_km: float | None, *, nearest_five: bool = False) -> str:
    if seconds_per_km is None:
        return "—"
    total = seconds_per_km * 1.609344
    if nearest_five:
        total = round(total / 5.0) * 5
    total = int(round(total))
    minutes, secs = divmod(total, 60)
    return f"{minutes}:{secs:02d}/mi"


def _pace_range(category: BlueprintCategory) -> str:
    fast = category.pace_low_s_per_km
    slow = category.pace_high_s_per_km
    if fast is None or slow is None:
        return "—"
    fast_text = _pace(min(fast, slow), nearest_five=True).removesuffix("/mi")
    slow_text = _pace(max(fast, slow), nearest_five=True)
    return f"{fast_text}–{slow_text}"


def _rep_range(category: BlueprintCategory) -> str:
    fast = category.rep_pace_low_s_per_km
    slow = category.rep_pace_high_s_per_km
    if fast is None or slow is None:
        return "Still learning"
    fast_text = _pace(min(fast, slow), nearest_five=True).removesuffix("/mi")
    slow_text = _pace(max(fast, slow), nearest_five=True)
    return f"{fast_text}–{slow_text}"


def _hr_range(category: BlueprintCategory) -> str:
    if category.hr_low is None or category.hr_high is None:
        return "—"
    return f"{category.hr_low}–{category.hr_high} bpm"


def _distance_km_to_miles(distance_km: float | None) -> str:
    if distance_km is None:
        return "—"
    return f"{distance_km * 0.621371:.1f} mi"


def _development_distance(category: BlueprintCategory) -> str:
    rep_distance = category.rep_distance_typical_km
    rep_count = category.rep_count_typical
    quality_distance = category.quality_volume_typical_km
    if rep_distance is None:
        return "Still learning"
    rep_text = _distance_km_to_miles(rep_distance)
    if rep_count is not None:
        rep_text = f"{rep_count:g} × {rep_text}"
    if quality_distance is not None:
        return f"{rep_text} · {_distance_km_to_miles(quality_distance)} quality"
    return rep_text


def _confidence_class(value: str) -> str:
    return {
        "Strong": "is-strong",
        "Set": "is-strong",
        "Moderate": "is-moderate",
    }.get(value, "is-limited")


def _training_rows(detail: PassportDetail) -> str:
    training = detail.training
    rows = []
    definitions = (
        (
            training.recovery,
            "Recovery",
            _pace_range(training.recovery),
            _hr_range(training.recovery),
            _distance_km_to_miles(training.recovery.typical_distance_km),
            "Your most efficient low-intensity history",
            f"{training.recovery.sample_size} comparable runs",
            _confidence_label(training.recovery.confidence),
        ),
        (
            training.easy,
            "Easy aerobic",
            _pace_range(training.easy),
            _hr_range(training.easy),
            _distance_km_to_miles(training.easy.typical_distance_km),
            "Conversational aerobic pattern",
            f"{training.easy.sample_size} comparable runs",
            _confidence_label(training.easy.confidence),
        ),
        (
            training.long_easy,
            "Long Easy",
            _pace_range(training.long_easy),
            _hr_range(training.long_easy),
            _distance_km_to_miles(training.long_easy.typical_distance_km),
            "Endurance pattern; durability matters more than pace",
            f"{training.long_easy.sample_size} comparable runs",
            _confidence_label(training.long_easy.confidence),
        ),
        (
            training.threshold,
            "Threshold",
            _pace(detail.progress.threshold.current_pace_s_per_km),
            _hr_range(training.threshold),
            _distance_km_to_miles(
                detail.threshold_evidence.typical_work_distance_km
            ),
            "Observed trusted work-phase pace",
            f"{detail.threshold_evidence.decoded_workout_count} decoded workouts",
            detail.progress.threshold.confidence,
        ),
    )
    for category, label, pace, hr, distance, guidance, evidence, confidence in definitions:
        rows.append(
            f"""
            <div class="passport-training-row">
                <div><strong>{_escape(label)}</strong><span>{_escape(guidance)}</span></div>
                <div><small>PACE</small><b>{_escape(pace)}</b></div>
                <div><small>HEART RATE</small><b>{_escape(hr)}</b></div>
                <div><small>DISTANCE</small><b>{_escape(distance)}</b></div>
                <div><small>EVIDENCE</small><b>{_escape(evidence)}</b><span class="passport-evidence {_confidence_class(confidence)}">{confidence}</span></div>
            </div>
            """
        )

    for development, label in (
        (training.vo2, "VO₂ development"),
        (training.speed, "Speed development"),
    ):
        confidence = _confidence_label(development.confidence)
        rows.append(
            f"""
            <div class="passport-training-row is-development">
                <div><strong>{_escape(label)}</strong><span>Trusted repetition evidence</span></div>
                <div><small>REP PACE</small><b>{_escape(_rep_range(development))}</b></div>
                <div><small>EFFORT GUIDE</small><b>RPE-led</b><span>HR lags short work</span></div>
                <div><small>DISTANCE</small><b>{_escape(_development_distance(development))}</b></div>
                <div><small>EVIDENCE</small><b>{development.rep_metric_sample_size} decoded workouts</b><span class="passport-evidence {_confidence_class(confidence)}">{confidence}</span></div>
            </div>
            """
        )
    return "".join(rows)


def _confidence_label(value: float) -> str:
    if value >= 0.75:
        return "Strong"
    if value >= 0.45:
        return "Moderate"
    return "Limited"


def _environment_cards(detail: PassportDetail) -> str:
    cards = []
    for response in detail.environment:
        confidence = _confidence_label(response.confidence)
        cards.append(
            f"""
            <article class="passport-environment-card">
                <div class="passport-card-label">{_escape(response.label.upper())}</div>
                <strong>{_escape(response.response_label)}</strong>
                <p>{response.sample_size} comparable run{'s' if response.sample_size != 1 else ''}</p>
                <span class="passport-evidence {_confidence_class(confidence)}">{confidence} evidence</span>
            </article>
            """
        )
    return "".join(cards)


def _learning_cards(detail: PassportDetail) -> str:
    if not detail.learning_patterns:
        return '<div class="passport-empty">Trusted workout-response evidence is still building.</div>'
    cards = []
    for pattern in detail.learning_patterns:
        cards.append(
            f"""
            <article class="passport-learning-card">
                <div class="passport-card-label">{_escape(pattern.family_label.upper())}</div>
                <h3>{_escape(pattern.headline)}</h3>
                <p>{_escape(pattern.explanation)}</p>
                <div class="passport-learning-meta"><span>{pattern.trusted_session_count} trusted sessions</span><span>{pattern.response_observation_count} response windows</span><b>{_escape(pattern.confidence_label)}</b></div>
            </article>
            """
        )
    return "".join(cards)


def _pb_cards(detail: PassportDetail) -> str:
    return "".join(
        f"""
        <article class="passport-pb-card">
            <div class="passport-card-label">{_escape(pb.label)}</div>
            <strong>{_clock(pb.all_time_seconds)}</strong>
            <span>All-time best</span>
            <p>Last 12 months <b>{_clock(pb.last_12_months_seconds)}</b></p>
        </article>
        """
        for pb in detail.athlete.personal_bests
    )


def _hero_performance_cards(detail: PassportDetail) -> str:
    athlete = detail.athlete
    grade = (
        f"{athlete.age_grade_all_time:.1f}%"
        if athlete.age_grade_all_time is not None else "—"
    )
    values = [("AGE GRADE", grade, "Best performance")]
    values.extend(
        (pb.label, _clock(pb.all_time_seconds), "Official or trusted result")
        for pb in athlete.personal_bests
    )
    return "".join(
        f"""
        <div class="passport-hero-stat">
            <span>{_escape(label)}</span>
            <strong>{_escape(value)}</strong>
            <small>{_escape(detail_text)}</small>
        </div>
        """
        for label, value, detail_text in values
    )


def _metric(value: float | None, suffix: str = "") -> str:
    return "—" if value is None else f"{value:.1f}{suffix}"


def _health_panel(detail: PassportDetail) -> str:
    health = detail.health
    history = detail.health_history
    if not history.available:
        return """
        <article class="passport-health-card is-empty">
            <div class="passport-card-label">PERSONAL HEALTH HISTORY</div>
            <h3>Connected context is ready when you are.</h3>
            <p>Import source-labelled HRV, resting-heart-rate or sleep data to compare recent values only with this athlete’s own history.</p>
            <span>Not a medical record or readiness score</span>
        </article>
        """
    source = health.source if health.available else ", ".join(history.sources)
    hrv_change = _metric(health.hrv_change_percent, "%")
    resting_change = _metric(health.resting_hr_change, " bpm")
    sleep_change = _metric(health.sleep_change_minutes, " min")
    return f"""
        <article class="passport-health-card">
            <div class="passport-health-heading">
                <div><div class="passport-card-label">PERSONAL HEALTH HISTORY</div><h3>Recent context against your own baseline</h3></div>
                <span>{_escape(health.confidence)} evidence</span>
            </div>
            <div class="passport-health-metrics">
                <div><small>HRV</small><strong>{_escape(hrv_change)}</strong><span>{_escape(health.hrv_status)}</span></div>
                <div><small>RESTING HR</small><strong>{_escape(resting_change)}</strong><span>{_escape(health.resting_hr_status)}</span></div>
                <div><small>SLEEP</small><strong>{_escape(sleep_change)}</strong><span>{_escape(health.sleep_status)}</span></div>
            </div>
            <div class="passport-health-coverage">
                <strong>{history.calendar_days} calendar days</strong>
                <span>{history.hrv_days} HRV · {history.resting_hr_days} resting HR · {history.sleep_days} sleep</span>
                <small>{_escape(source)} · latest {_escape(history.latest_date)}</small>
            </div>
            <p>Seven recent days are compared with the preceding personal baseline. Trends support a conversation about recovery; they do not diagnose health or overrule how the athlete feels.</p>
        </article>
    """


def _share_panel(detail: PassportDetail) -> str:
    share = detail.share_profile
    included = "".join(
        f"<li>{_escape(item)}</li>" for item in share.included
    )
    excluded = "".join(
        f"<li>{_escape(item)}</li>" for item in share.excluded
    )
    return f"""
        <article class="passport-share-card">
            <div class="passport-share-top">
                <div><div class="passport-card-label">SHAREABLE PERFORMANCE PROFILE</div><h3>A useful public story, with private evidence protected.</h3></div>
                <span>{_escape(share.status)}</span>
            </div>
            <p>{_escape(share.explanation)}</p>
            <div class="passport-share-columns">
                <div><strong>INCLUDED IN THE PREVIEW</strong><ul>{included}</ul></div>
                <div><strong>ALWAYS PRIVATE BY DEFAULT</strong><ul>{excluded}</ul></div>
            </div>
            <div class="passport-share-foot"><b>PREVIEW ONLY</b><span>No public URL exists and no health data leaves this private athlete view.</span></div>
        </article>
    """


def build_passport_html(detail: PassportDetail) -> str:
    athlete = detail.athlete
    anchors = "".join(
        f"""
        <article class="passport-anchor">
            <div class="passport-card-label">{_escape(anchor.label.upper())}</div>
            <strong>{_escape(anchor.value)}</strong>
            <p>{_escape(anchor.detail)}</p>
            <span class="passport-evidence {_confidence_class(anchor.confidence)}">{_escape(anchor.confidence)}</span>
        </article>
        """
        for anchor in detail.anchors
    )
    aerobic = (
        f"{athlete.aerobic_trend_percent:+.1f}%"
        if athlete.aerobic_trend_percent is not None else "—"
    )
    trait = detail.performance_trait
    trait_html = (
        f"""
        <div class="passport-trait">
            <div class="passport-card-label">DISTINCTIVE TRAIT</div>
            <strong>{_escape(trait.title)}</strong>
            <p>{_escape(trait.detail)}</p>
        </div>
        """
        if trait is not None
        else """
        <div class="passport-trait is-building">
            <div class="passport-card-label">DISTINCTIVE TRAIT</div>
            <strong>Still emerging</strong>
            <p>More varied comparable runs are needed before one environmental strength stands out.</p>
        </div>
        """
    )
    notes = "".join(f"<li>{_escape(note)}</li>" for note in detail.evidence_notes)
    return f"""
    <main class="passport-shell">
        <section class="passport-hero">
            <div class="passport-photo-panel">
                {_athlete_photo(detail)}
                <div class="passport-live"><i></i> Live profile</div>
                <div class="passport-photo-copy">
                    <span>ATHLETE PASSPORT</span>
                    <strong>{_escape(athlete.full_name)}</strong>
                    <small>{_escape(athlete.category)}</small>
                </div>
            </div>
            <div class="passport-hero-performance">
                <div class="passport-eyebrow">YOUR RUNNING IDENTITY · CURRENT TO {_escape(detail.reference_date)}</div>
                <h1>{_escape(athlete.first_name)}’s performance passport.</h1>
                <p>Factual achievements, personal training anchors and the evidence the coaching team currently trusts.</p>
                <div class="passport-hero-stat-grid">{_hero_performance_cards(detail)}</div>
                <div class="passport-hero-direction"><span>Aerobic direction <b>{_escape(aerobic)}</b></span><span>{athlete.aerobic_run_count} comparable aerobic runs</span></div>
            </div>
            <aside class="passport-hero-confidence">
                <div class="passport-eyebrow">WHAT THIS PASSPORT KNOWS</div>
                <h2>{_escape(detail.confidence)} evidence. Clear boundaries.</h2>
                <p>{_escape(detail.confidence_summary)}</p>
                <div><span>Configured physiology</span><b>{_escape(detail.threshold_source)}</b></div>
                <div><span>Training profiles</span><b>{detail.available_training_profiles} of 6 supported</b></div>
                <div><span>Privacy</span><b>Health and notes remain private</b></div>
                <small>Identity is evidence-backed, not a medical assessment.</small>
            </aside>
        </section>

        <section class="passport-section">
            <div class="passport-section-heading"><div><div class="passport-eyebrow">CURRENT ANCHORS</div><h2>Your working reference points</h2></div><span>BOUNDARIES, EVIDENCE & DIRECTION</span></div>
            <div class="passport-anchor-grid">{anchors}</div>
        </section>

        <section class="passport-section">
            <div class="passport-section-heading"><div><div class="passport-eyebrow">TRAINING PROFILE</div><h2>Your running zones and development ranges</h2></div><span>PACE IN MIN/MILE</span></div>
            <div class="passport-training-head"><span>Purpose</span><span>Pace</span><span>Heart rate / effort</span><span>Typical distance</span><span>Support</span></div>
            <div class="passport-training-table">{_training_rows(detail)}</div>
            <p class="passport-section-note">Easy-run pace ranges are conditions-normalised historical patterns, not prescriptions. Threshold leads with observed work-phase pace; use its Current Anchor for the cautious 12°C flat-road equivalent.</p>
            <div class="passport-threshold-audit"><strong>THRESHOLD EVIDENCE, EXPLAINED</strong><span><b>{detail.threshold_evidence.decoded_workout_count}</b> high-confidence decoded threshold workouts</span><span><b>{detail.threshold_evidence.strict_progress_count}</b> in the strict 12-month pace-trend set</span><span><b>{detail.threshold_evidence.response_window_count}</b> with complete before/after response windows</span></div>
        </section>

        <section class="passport-two-column">
            <article class="passport-section">
                <div class="passport-section-heading"><div><div class="passport-eyebrow">WHAT MAKES YOU DISTINCTIVE</div><h2>Environmental response</h2></div></div>
                {trait_html}
                <div class="passport-environment-grid">{_environment_cards(detail)}</div>
                <p class="passport-section-note">These values scale the app's standard environmental model. They do not mean your total running pace changes by the displayed percentage.</p>
            </article>
            <article class="passport-section">
                <div class="passport-section-heading"><div><div class="passport-eyebrow">WHAT THE APP HAS LEARNED</div><h2>Workout-response associations</h2></div><span>{detail.trusted_workout_count} TRUSTED WORKOUTS</span></div>
                <div class="passport-learning-grid">{_learning_cards(detail)}</div>
                <p class="passport-section-note">{_escape(detail.learning_summary)} Association is evidence, not proof of causation.</p>
            </article>
        </section>

        <section class="passport-private-grid">
            {_health_panel(detail)}
            {_share_panel(detail)}
        </section>

        <section class="passport-section">
            <div class="passport-section-heading"><div><div class="passport-eyebrow">ACHIEVEMENT LEDGER</div><h2>Factual results</h2></div><span>OFFICIAL TIMES ARE NEVER NORMALISED</span></div>
            <div class="passport-pb-grid">{_pb_cards(detail)}</div>
        </section>

        <details class="passport-method"><summary>How Passport decides what it knows</summary><ul>{notes}</ul></details>
    </main>
    <style>
        .passport-shell {{ color:#10263d; display:grid; gap:12px; container-type:inline-size; }}
        .passport-shell * {{ box-sizing:border-box; }}
        .passport-hero,.passport-identity,.passport-section,.passport-method,.passport-health-card,.passport-share-card {{ background:#fff; border:1px solid #e5ddd2; border-radius:18px; box-shadow:0 8px 24px rgba(16,38,61,.045); }}
        .passport-hero {{ min-height:390px; overflow:hidden; display:grid; grid-template-columns:minmax(230px,.78fr) minmax(430px,1.5fr) minmax(280px,.88fr); }}
        .passport-photo-panel {{ position:relative; min-height:390px; overflow:hidden; background:#0b2b45; }}
        .passport-athlete-photo {{ position:absolute; inset:0; width:100%; height:100%; object-fit:cover; object-position:center 24%; filter:saturate(.92) contrast(1.04); }}
        .passport-photo-panel:after {{ content:""; position:absolute; inset:0; background:linear-gradient(180deg,rgba(4,24,40,.05) 18%,rgba(4,24,40,.30) 52%,rgba(4,24,40,.98) 100%); }}
        .passport-photo-fallback {{ height:100%; display:grid; place-items:center; color:rgba(255,255,255,.5); font-size:52px; font-weight:900; }}
        .passport-live {{ position:absolute; z-index:2; top:18px; right:16px; display:flex; align-items:center; gap:7px; padding:7px 10px; border:1px solid rgba(255,255,255,.22); border-radius:999px; background:rgba(5,31,50,.72); color:#fff!important; font-size:10px; font-weight:850; letter-spacing:.1em; text-transform:uppercase; }}
        .passport-live i {{ width:7px; height:7px; border-radius:50%; background:#73dfb6; box-shadow:0 0 0 4px rgba(115,223,182,.14); }}
        .passport-photo-copy {{ position:absolute; z-index:2; left:23px; right:20px; bottom:25px; color:#fff!important; display:flex; flex-direction:column; }}
        .passport-photo-copy span {{ color:#f89a72!important; font-size:11px; font-weight:850; letter-spacing:.12em; }}
        .passport-photo-copy strong {{ color:#fff!important; font-size:clamp(29px,3vw,42px); line-height:.94; margin:8px 0 10px; letter-spacing:-.045em; }}
        .passport-photo-copy small {{ color:#e9f0f4!important; font-size:12px; font-weight:800; letter-spacing:.12em; }}
        .passport-hero-performance {{ padding:30px 32px 23px; min-width:0; display:flex; flex-direction:column; }}
        .passport-hero-performance h1 {{ color:#10263d!important; font-size:clamp(28px,3vw,43px); line-height:1; margin:10px 0 8px; letter-spacing:-.045em; }}
        .passport-hero-performance > p {{ color:#657483; font-size:13px; line-height:1.45; margin:0; max-width:650px; }}
        .passport-hero-stat-grid {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); margin-top:24px; border-top:1px solid #e8e1d8; border-bottom:1px solid #e8e1d8; }}
        .passport-hero-stat {{ min-width:0; padding:16px 13px; border-right:1px solid #e8e1d8; display:flex; flex-direction:column; gap:4px; }} .passport-hero-stat:first-child {{ padding-left:0; }} .passport-hero-stat:last-child {{ border-right:0; }}
        .passport-hero-stat span {{ color:#778594; font-size:9px; font-weight:850; letter-spacing:.11em; }}
        .passport-hero-stat strong {{ color:#10263d; font-size:clamp(20px,2.1vw,29px); line-height:1; letter-spacing:-.035em; }}
        .passport-hero-stat small {{ color:#84909b; font-size:9px; line-height:1.3; }}
        .passport-hero-direction {{ margin-top:auto; padding-top:21px; display:flex; justify-content:space-between; flex-wrap:wrap; gap:8px; color:#71808c; font-size:11px; }}
        .passport-hero-direction b {{ color:#238a52; font-size:14px; margin-left:4px; }}
        .passport-hero-confidence {{ padding:30px 27px; color:#fff!important; background:radial-gradient(circle at 100% 0,rgba(42,121,127,.32),transparent 38%),linear-gradient(145deg,#082743,#0b3548); display:flex; flex-direction:column; }}
        .passport-hero-confidence .passport-eyebrow {{ color:#75dcb7!important; }}
        .passport-hero-confidence h2 {{ color:#fff!important; font-size:27px; line-height:1.05; margin:18px 0 11px; letter-spacing:-.035em; }}
        .passport-hero-confidence > p {{ color:#d8e4ea!important; font-size:12px; line-height:1.5; margin:0 0 20px; }}
        .passport-hero-confidence > div:not(.passport-eyebrow) {{ border-top:1px solid rgba(255,255,255,.14); padding:11px 0; display:flex; flex-direction:column; gap:3px; }}
        .passport-hero-confidence div span {{ color:#9bb0bd!important; font-size:9px; font-weight:800; letter-spacing:.09em; text-transform:uppercase; }}
        .passport-hero-confidence div b {{ color:#fff!important; font-size:12px; line-height:1.35; }}
        .passport-hero-confidence > small {{ color:#b8cad3!important; font-size:9px; line-height:1.4; margin-top:auto; padding-top:15px; }}
        .passport-identity {{ padding:22px 24px; display:grid; grid-template-columns:64px minmax(250px,1fr) 150px 220px; gap:20px; align-items:center; }}
        .passport-monogram {{ width:64px; height:64px; border-radius:17px; background:#10263d; color:#fff; display:grid; place-items:center; font-weight:850; font-size:24px; border-bottom:4px solid #f05a28; }}
        .passport-eyebrow,.passport-card-label {{ color:#778594; font-size:11px; line-height:1.25; font-weight:800; letter-spacing:.13em; }}
        .passport-identity h1 {{ color:#10263d!important; font-size:clamp(29px,3vw,42px); line-height:1; margin:5px 0 7px; letter-spacing:-.045em; }}
        .passport-identity-copy p {{ color:#647180; font-size:12px; margin:0; }}
        .passport-grade,.passport-confidence {{ min-height:84px; border-radius:14px; padding:13px; display:flex; flex-direction:column; gap:2px; background:#f8f5ef; border:1px solid #ebe4da; }}
        .passport-grade span,.passport-confidence span {{ color:#71808d; font-size:9px; font-weight:800; letter-spacing:.1em; }}
        .passport-grade strong,.passport-confidence strong {{ font-size:24px; line-height:1.1; color:#10263d; }}
        .passport-grade small,.passport-confidence small {{ color:#71808d; font-size:9px; line-height:1.3; }}
        .passport-confidence.is-strong {{ background:#eaf6ef; border-color:#d2e9dc; }} .passport-confidence.is-strong strong {{ color:#238a52; }}
        .passport-confidence.is-moderate {{ background:#fff5e4; border-color:#f1dfbd; }} .passport-confidence.is-moderate strong {{ color:#ad6500; }}
        .passport-section {{ padding:18px 20px; min-width:0; }}
        .passport-section-heading {{ display:flex; justify-content:space-between; align-items:flex-start; gap:16px; margin-bottom:14px; }}
        .passport-section-heading h2 {{ color:#10263d!important; font-size:20px; line-height:1.1; margin:4px 0 0; letter-spacing:-.025em; }}
        .passport-section-heading > span {{ color:#238a52; font-size:9px; font-weight:800; letter-spacing:.1em; white-space:nowrap; }}
        .passport-anchor-grid {{ display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:8px; }}
        .passport-anchor {{ background:#f8f5ef; border:1px solid #ebe4da; border-radius:13px; padding:13px; min-width:0; }}
        .passport-anchor > strong {{ display:block; color:#10263d; font-size:21px; line-height:1; margin:10px 0 5px; letter-spacing:-.03em; }}
        .passport-anchor p {{ color:#697683; font-size:10px; line-height:1.4; min-height:28px; margin:0 0 8px; }}
        .passport-evidence {{ display:inline-flex; width:max-content; border-radius:999px; padding:5px 8px; color:#c94d20; background:#fff0e8; font-size:9px; line-height:1; font-weight:800; }}
        .passport-evidence.is-strong {{ color:#238a52; background:#e6f4ec; }} .passport-evidence.is-moderate {{ color:#a86000; background:#fff3dd; }}
        .passport-training-head,.passport-training-row {{ display:grid; grid-template-columns:1.25fr .7fr .78fr 1fr .8fr; gap:12px; align-items:center; }}
        .passport-training-head {{ padding:0 13px 7px; color:#86919c; font-size:9px; font-weight:800; letter-spacing:.1em; text-transform:uppercase; }}
        .passport-training-table {{ border:1px solid #ebe4da; border-radius:13px; overflow:hidden; }}
        .passport-training-row {{ min-height:73px; padding:11px 13px; border-bottom:1px solid #ebe4da; background:#fff; }} .passport-training-row:last-child {{ border-bottom:0; }}
        .passport-training-row.is-development {{ border-left:4px solid #f05a28; background:#fffaf7; }}
        .passport-training-row div {{ min-width:0; display:flex; flex-direction:column; gap:2px; }}
        .passport-training-row strong {{ font-size:13px; }} .passport-training-row b {{ font-size:13px; }}
        .passport-training-row small {{ color:#7a8793; font-size:9px; font-weight:800; letter-spacing:.09em; }}
        .passport-training-row span {{ color:#697683; font-size:10px; line-height:1.35; }} .passport-training-row span.passport-evidence {{ color:#238a52; margin-top:3px; }}
        .passport-threshold-audit {{ display:flex; align-items:center; flex-wrap:wrap; gap:8px 16px; margin-top:10px; padding:10px 12px; border-radius:10px; background:#f8f5ef; color:#687582; font-size:9px; }}
        .passport-threshold-audit > strong {{ color:#10263d; font-size:8px; letter-spacing:.09em; }} .passport-threshold-audit span b {{ color:#f05a28; font-size:11px; margin-right:3px; }}
        .passport-two-column {{ display:grid; grid-template-columns:1fr 1.25fr; gap:10px; align-items:stretch; }}
        .passport-private-grid {{ display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1.15fr); gap:10px; }}
        .passport-health-card,.passport-share-card {{ padding:21px; min-width:0; }}
        .passport-health-heading,.passport-share-top {{ display:flex; justify-content:space-between; align-items:flex-start; gap:15px; }}
        .passport-health-card h3,.passport-share-card h3 {{ color:#10263d!important; font-size:19px; line-height:1.15; margin:5px 0 0; letter-spacing:-.025em; }}
        .passport-health-heading > span,.passport-share-top > span {{ border-radius:999px; padding:6px 9px; background:#eaf6ef; color:#238a52; font-size:9px; font-weight:850; white-space:nowrap; }}
        .passport-share-top > span {{ background:#fff0e8; color:#c94d20; }}
        .passport-health-metrics {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:7px; margin-top:17px; }}
        .passport-health-metrics > div {{ border:1px solid #e5ddd2; border-radius:12px; padding:12px; display:flex; flex-direction:column; min-width:0; }}
        .passport-health-metrics small {{ color:#7d8994; font-size:9px; font-weight:850; letter-spacing:.09em; }} .passport-health-metrics strong {{ color:#10263d; font-size:20px; margin:7px 0 4px; }} .passport-health-metrics span {{ color:#687582; font-size:9px; line-height:1.35; }}
        .passport-health-coverage {{ margin-top:8px; padding:11px 12px; border-radius:11px; background:#eef7f2; display:grid; grid-template-columns:auto 1fr; gap:3px 13px; }}
        .passport-health-coverage strong {{ color:#238a52; font-size:12px; }} .passport-health-coverage span {{ color:#526f63; font-size:10px; text-align:right; }} .passport-health-coverage small {{ color:#71837c; font-size:9px; grid-column:1/-1; }}
        .passport-health-card > p,.passport-share-card > p {{ color:#687582; font-size:10px; line-height:1.45; margin:11px 0 0; }}
        .passport-health-card.is-empty {{ display:flex; flex-direction:column; justify-content:center; background:#f8f5ef; }} .passport-health-card.is-empty h3 {{ margin:12px 0 4px; }} .passport-health-card.is-empty > span {{ color:#238a52; font-size:10px; font-weight:800; margin-top:15px; }}
        .passport-share-columns {{ display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-top:14px; }}
        .passport-share-columns > div {{ border:1px solid #e5ddd2; border-radius:12px; padding:12px; background:#fbf9f5; }}
        .passport-share-columns strong {{ color:#10263d; font-size:9px; letter-spacing:.08em; }} .passport-share-columns ul {{ padding-left:16px; margin:8px 0 0; }} .passport-share-columns li {{ color:#687582; font-size:9px; line-height:1.4; margin:4px 0; }}
        .passport-share-foot {{ display:flex; align-items:center; gap:9px; margin-top:9px; padding:9px 11px; border-radius:10px; background:#0b2b45; }} .passport-share-foot b {{ color:#77ddb8!important; font-size:9px; letter-spacing:.09em; }} .passport-share-foot span {{ color:#e1ebf0!important; font-size:9px; line-height:1.35; }}
        .passport-trait {{ border-radius:13px; padding:13px; margin-bottom:8px; background:linear-gradient(105deg,#fff0ca,#fff8e8); border:1px solid #efcf83; }}
        .passport-trait strong {{ display:block; margin:6px 0 3px; font-size:17px; }} .passport-trait p {{ margin:0; color:#6d614d; font-size:10px; line-height:1.4; }}
        .passport-trait.is-building {{ background:#f8f5ef; border-color:#ebe4da; }}
        .passport-environment-grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:7px; }}
        .passport-environment-card {{ border:1px solid #e5ddd2; border-radius:12px; padding:11px; min-width:0; }}
        .passport-environment-card > strong {{ display:block; font-size:13px; line-height:1.1; margin:8px 0 5px; }} .passport-environment-card p {{ color:#75818d; font-size:9px; margin:0 0 8px; }}
        .passport-learning-grid {{ display:grid; gap:8px; }}
        .passport-learning-card {{ padding:13px; border:1px solid #e5ddd2; border-radius:12px; background:#f8f5ef; }}
        .passport-learning-card h3 {{ font-size:13px; margin:6px 0 4px; }} .passport-learning-card p {{ color:#697683; font-size:9px; line-height:1.4; margin:0; }}
        .passport-learning-meta {{ display:flex; gap:10px; flex-wrap:wrap; margin-top:9px; color:#788591; font-size:8px; }} .passport-learning-meta b {{ color:#238a52; margin-left:auto; }}
        .passport-section-note {{ color:#687582; font-size:10px; line-height:1.45; margin:10px 0 0; }}
        .passport-pb-grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px; }}
        .passport-pb-card {{ background:#f8f5ef; border:1px solid #ebe4da; border-radius:13px; padding:14px; }}
        .passport-pb-card > strong {{ display:block; font-size:27px; line-height:1; margin:9px 0 3px; letter-spacing:-.035em; }} .passport-pb-card > span {{ color:#778594; font-size:9px; }} .passport-pb-card p {{ color:#5f6c78; font-size:10px; margin:11px 0 0; }}
        .passport-method {{ padding:0 18px; }} .passport-method summary {{ cursor:pointer; padding:15px 0; color:#10263d; font-size:11px; font-weight:800; }}
        .passport-method ul {{ margin:0 0 16px; padding-left:20px; }} .passport-method li {{ color:#687582; font-size:10px; line-height:1.45; margin:5px 0; }}
        .passport-empty {{ color:#778594; font-size:10px; padding:20px; background:#f8f5ef; border-radius:12px; }}
        @container (max-width:1050px) {{ .passport-hero {{ grid-template-columns:minmax(220px,.72fr) minmax(430px,1.28fr); }} .passport-hero-confidence {{ grid-column:1/-1; min-height:220px; display:grid; grid-template-columns:1fr 1fr; column-gap:24px; }} .passport-hero-confidence h2,.passport-hero-confidence > p {{ grid-column:1; }} .passport-hero-confidence > div:not(.passport-eyebrow),.passport-hero-confidence > small {{ grid-column:2; }} .passport-anchor-grid {{ grid-template-columns:repeat(3,minmax(0,1fr)); }} }}
        @container (max-width:760px) {{ .passport-hero {{ grid-template-columns:1fr; }} .passport-photo-panel {{ min-height:360px; }} .passport-hero-confidence {{ grid-column:auto; display:flex; min-height:320px; }} .passport-private-grid,.passport-two-column {{ grid-template-columns:1fr; }} .passport-training-head {{ display:none; }} .passport-training-row {{ grid-template-columns:1fr 1fr; }} .passport-anchor-grid {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} }}
        @container (max-width:500px) {{ .passport-hero-performance,.passport-hero-confidence {{ padding:23px 20px; }} .passport-hero-stat-grid {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} .passport-hero-stat {{ border-bottom:1px solid #e8e1d8; }} .passport-hero-stat:nth-child(2) {{ border-right:0; }} .passport-hero-stat:first-child {{ padding-left:13px; }} .passport-anchor-grid,.passport-pb-grid,.passport-health-metrics,.passport-share-columns {{ grid-template-columns:1fr; }} .passport-training-row {{ grid-template-columns:1fr; }} .passport-environment-grid {{ grid-template-columns:1fr; }} .passport-section {{ padding:16px; }} .passport-section-heading,.passport-health-heading,.passport-share-top {{ flex-direction:column; gap:6px; }} .passport-health-coverage {{ grid-template-columns:1fr; }} .passport-health-coverage span {{ text-align:left; }} }}
    </style>
    """


def show_passport_page() -> None:
    st.markdown(
        """
        <style>
            [data-testid="stMainBlockContainer"] { max-width:1450px; padding-top:4.25rem; padding-bottom:3rem; }
            [data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"],
            [data-testid="stMainBlockContainer"] > div > [data-testid="stVerticalBlock"] { gap:10px; }
            [data-testid="stHeader"] { background:transparent; }
            [data-testid="stElementContainer"]:has(.passport-selector-marker) { display:none; }
            [data-testid="stHorizontalBlock"]:has(.passport-selector-marker) { align-items:flex-start; gap:8px; }
            .passport-context-strip { min-height:40px; border:1px solid #e5ddd2; border-radius:12px; background:#fff; padding:0 15px; display:flex; align-items:center; justify-content:space-between; gap:14px; color:#10263d; box-shadow:0 5px 18px rgba(16,38,61,.035); }
            .passport-context-strip strong { font-size:12px; letter-spacing:.12em; }
            .passport-context-strip span { color:#6c7885; font-size:11px; }
            .passport-context-strip em { color:#238a52; font-size:10px; font-style:normal; font-weight:800; letter-spacing:.08em; }
            @media (max-width:900px) { [data-testid="stHorizontalBlock"]:has(.passport-selector-marker) [data-testid="stColumn"]:last-child { display:none; } [data-testid="stHorizontalBlock"]:has(.passport-selector-marker) [data-testid="stColumn"]:first-child { flex:1 1 100%; width:100%; } }
        </style>
        """,
        unsafe_allow_html=True,
    )
    selector_col, context_col = st.columns([390, 1051], gap="small")
    with selector_col:
        st.markdown('<span class="passport-selector-marker"></span>', unsafe_allow_html=True)
        athlete_id = render_athlete_id_selector(label_visibility="collapsed")
    with context_col:
        st.html('<div class="passport-context-strip"><strong>ATHLETE PASSPORT</strong><span>Identity, achievements, zones and private health context.</span><em>PRIVATE BY DEFAULT</em></div>')

    if athlete_id is None:
        st.warning("No athletes found. Add an athlete first.")
        return
    with st.spinner("Assembling your evidence-backed Passport…"):
        detail = _cached_passport(
            athlete_id,
            PASSPORT_CACHE_SCHEMA,
            get_athlete_cache_version(athlete_id),
        )
    if detail is None:
        st.info("Import running history to begin building your Passport.")
        return
    st.html(build_passport_html(detail))
