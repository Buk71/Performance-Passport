"""Production Passport Detail presentation."""

from __future__ import annotations

import html

import streamlit as st

from core.passport_detail import PassportDetail, build_passport_detail
from core.training_blueprint import BlueprintCategory
from ui.athlete_selection import render_athlete_id_selector


PASSPORT_CACHE_SCHEMA = 1


@st.cache_data(show_spinner=False, ttl=300)
def _cached_passport(athlete_id: int, schema: int) -> PassportDetail | None:
    del schema
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
    grade_all = f"{athlete.age_grade_all_time:.1f}%" if athlete.age_grade_all_time is not None else "—"
    grade_recent = f"{athlete.age_grade_last_12_months:.1f}%" if athlete.age_grade_last_12_months is not None else "—"
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
        <section class="passport-identity">
            <div class="passport-monogram">{_escape(athlete.initials)}</div>
            <div class="passport-identity-copy">
                <div class="passport-eyebrow">ATHLETE PASSPORT · CURRENT TO {_escape(detail.reference_date)}</div>
                <h1>{_escape(athlete.full_name)}</h1>
                <p>{_escape(athlete.category)} · An evidence-backed picture of how you currently run.</p>
            </div>
            <div class="passport-grade"><span>BEST AGE GRADE</span><strong>{grade_all}</strong><small>{grade_recent} in last 12 months</small></div>
            <div class="passport-confidence {_confidence_class(detail.confidence)}"><span>PASSPORT CONFIDENCE</span><strong>{_escape(detail.confidence)}</strong><small>{_escape(detail.confidence_summary)}</small></div>
        </section>

        <section class="passport-section">
            <div class="passport-section-heading"><div><div class="passport-eyebrow">CURRENT ANCHORS</div><h2>Your working reference points</h2></div><span>BOUNDARIES, EVIDENCE & DIRECTION</span></div>
            <div class="passport-anchor-grid">{anchors}</div>
        </section>

        <section class="passport-section">
            <div class="passport-section-heading"><div><div class="passport-eyebrow">TRAINING PROFILE</div><h2>How your strongest historical patterns look</h2></div><span>PACE IN MIN/MILE</span></div>
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

        <section class="passport-section">
            <div class="passport-section-heading"><div><div class="passport-eyebrow">ACHIEVEMENT LEDGER</div><h2>Factual results</h2></div><span>OFFICIAL TIMES ARE NEVER NORMALISED</span></div>
            <div class="passport-pb-grid">{_pb_cards(detail)}</div>
        </section>

        <details class="passport-method"><summary>How Passport decides what it knows</summary><ul>{notes}</ul></details>
    </main>
    <style>
        .passport-shell {{ color:#10263d; display:grid; gap:12px; container-type:inline-size; }}
        .passport-shell * {{ box-sizing:border-box; }}
        .passport-identity,.passport-section,.passport-method {{ background:#fff; border:1px solid #e5ddd2; border-radius:18px; box-shadow:0 8px 24px rgba(16,38,61,.045); }}
        .passport-identity {{ padding:22px 24px; display:grid; grid-template-columns:64px minmax(250px,1fr) 150px 220px; gap:20px; align-items:center; }}
        .passport-monogram {{ width:64px; height:64px; border-radius:17px; background:#10263d; color:#fff; display:grid; place-items:center; font-weight:850; font-size:24px; border-bottom:4px solid #f05a28; }}
        .passport-eyebrow,.passport-card-label {{ color:#778594; font-size:10px; line-height:1.25; font-weight:800; letter-spacing:.13em; }}
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
        .passport-anchor p {{ color:#697683; font-size:9px; line-height:1.35; min-height:26px; margin:0 0 8px; }}
        .passport-evidence {{ display:inline-flex; width:max-content; border-radius:999px; padding:4px 7px; color:#c94d20; background:#fff0e8; font-size:8px; line-height:1; font-weight:800; }}
        .passport-evidence.is-strong {{ color:#238a52; background:#e6f4ec; }} .passport-evidence.is-moderate {{ color:#a86000; background:#fff3dd; }}
        .passport-training-head,.passport-training-row {{ display:grid; grid-template-columns:1.25fr .7fr .78fr 1fr .8fr; gap:12px; align-items:center; }}
        .passport-training-head {{ padding:0 13px 6px; color:#86919c; font-size:8px; font-weight:800; letter-spacing:.1em; text-transform:uppercase; }}
        .passport-training-table {{ border:1px solid #ebe4da; border-radius:13px; overflow:hidden; }}
        .passport-training-row {{ min-height:73px; padding:11px 13px; border-bottom:1px solid #ebe4da; background:#fff; }} .passport-training-row:last-child {{ border-bottom:0; }}
        .passport-training-row.is-development {{ border-left:4px solid #f05a28; background:#fffaf7; }}
        .passport-training-row div {{ min-width:0; display:flex; flex-direction:column; gap:2px; }}
        .passport-training-row strong {{ font-size:13px; }} .passport-training-row b {{ font-size:13px; }}
        .passport-training-row small {{ color:#7a8793; font-size:8px; font-weight:800; letter-spacing:.09em; }}
        .passport-training-row span {{ color:#697683; font-size:9px; line-height:1.3; }} .passport-training-row span.passport-evidence {{ color:#238a52; margin-top:3px; }}
        .passport-threshold-audit {{ display:flex; align-items:center; flex-wrap:wrap; gap:8px 16px; margin-top:10px; padding:10px 12px; border-radius:10px; background:#f8f5ef; color:#687582; font-size:9px; }}
        .passport-threshold-audit > strong {{ color:#10263d; font-size:8px; letter-spacing:.09em; }} .passport-threshold-audit span b {{ color:#f05a28; font-size:11px; margin-right:3px; }}
        .passport-two-column {{ display:grid; grid-template-columns:1fr 1.25fr; gap:10px; align-items:stretch; }}
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
        .passport-section-note {{ color:#687582; font-size:9px; line-height:1.4; margin:10px 0 0; }}
        .passport-pb-grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px; }}
        .passport-pb-card {{ background:#f8f5ef; border:1px solid #ebe4da; border-radius:13px; padding:14px; }}
        .passport-pb-card > strong {{ display:block; font-size:27px; line-height:1; margin:9px 0 3px; letter-spacing:-.035em; }} .passport-pb-card > span {{ color:#778594; font-size:9px; }} .passport-pb-card p {{ color:#5f6c78; font-size:10px; margin:11px 0 0; }}
        .passport-method {{ padding:0 18px; }} .passport-method summary {{ cursor:pointer; padding:15px 0; color:#10263d; font-size:11px; font-weight:800; }}
        .passport-method ul {{ margin:0 0 16px; padding-left:20px; }} .passport-method li {{ color:#687582; font-size:9px; line-height:1.45; margin:5px 0; }}
        .passport-empty {{ color:#778594; font-size:10px; padding:20px; background:#f8f5ef; border-radius:12px; }}
        @container (max-width:1050px) {{ .passport-identity {{ grid-template-columns:64px 1fr 140px; }} .passport-confidence {{ grid-column:2 / -1; min-height:auto; }} .passport-anchor-grid {{ grid-template-columns:repeat(3,minmax(0,1fr)); }} }}
        @container (max-width:760px) {{ .passport-two-column {{ grid-template-columns:1fr; }} .passport-training-head {{ display:none; }} .passport-training-row {{ grid-template-columns:1fr 1fr; }} .passport-anchor-grid {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} }}
        @container (max-width:500px) {{ .passport-identity {{ grid-template-columns:55px 1fr; padding:17px; }} .passport-monogram {{ width:55px; height:55px; }} .passport-grade,.passport-confidence {{ grid-column:1 / -1; }} .passport-anchor-grid,.passport-pb-grid {{ grid-template-columns:1fr; }} .passport-training-row {{ grid-template-columns:1fr; }} .passport-environment-grid {{ grid-template-columns:1fr; }} .passport-section {{ padding:16px; }} .passport-section-heading {{ flex-direction:column; gap:6px; }} }}
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
        st.html('<div class="passport-context-strip"><strong>PASSPORT</strong><span>What has the app learned about me?</span><em>CURRENT ATHLETE IDENTITY</em></div>')

    if athlete_id is None:
        st.warning("No athletes found. Add an athlete first.")
        return
    with st.spinner("Assembling your evidence-backed Passport…"):
        detail = _cached_passport(athlete_id, PASSPORT_CACHE_SCHEMA)
    if detail is None:
        st.info("Import running history to begin building your Passport.")
        return
    st.html(build_passport_html(detail))
