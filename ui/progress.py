"""Production Progress Foundation: honest longitudinal running evidence."""

from __future__ import annotations

import html

import streamlit as st

from core.progress import ProgressSummary, build_progress_summary
from ui.athlete_selection import render_athlete_id_selector


PROGRESS_CACHE_SCHEMA = 2


@st.cache_data(show_spinner=False, ttl=300)
def _cached_progress(athlete_id: int, schema: int) -> ProgressSummary | None:
    del schema
    return build_progress_summary(athlete_id)


def _escape(value) -> str:
    return html.escape(str(value or ""))


def _clock(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    rounded = int(round(seconds))
    hours, remainder = divmod(rounded, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def _pace(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    rounded = int(round(seconds * 1.609344))
    minutes, secs = divmod(rounded, 60)
    return f"{minutes}:{secs:02d}/mi"


def _pace_to_nearest_five(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    seconds_per_mile = seconds * 1.609344
    rounded = int(round(seconds_per_mile / 5.0) * 5)
    minutes, secs = divmod(rounded, 60)
    return f"{minutes}:{secs:02d}/mi"


def _pace_range(fast: float | None, slow: float | None) -> str:
    if fast is None or slow is None:
        return "—"
    fast_text = _pace_to_nearest_five(fast)
    slow_text = _pace_to_nearest_five(slow)
    if fast_text == slow_text:
        return fast_text
    return f"{fast_text.removesuffix('/mi')}–{slow_text}"


def _signed(value: float | None, suffix: str = "%") -> str:
    return "—" if value is None else f"{value:+.1f}{suffix}"


def _confidence_class(value: str) -> str:
    return {
        "Strong": "is-strong",
        "Moderate": "is-moderate",
    }.get(value, "is-limited")


def _aerobic_chart(summary: ProgressSummary) -> str:
    points = summary.aerobic.points
    available = [point.value for point in points if point.value is not None]
    if not available:
        return '<div class="progress-empty">A year of comparable easy runs will build this trend.</div>'

    low = min(min(available) - 1.0, 98.0)
    high = max(max(available) + 1.0, 102.0)
    span = max(high - low, 1.0)
    bars = []
    for point in points:
        if point.value is None:
            height = 0.0
            value = "—"
            tone = "is-missing"
        else:
            height = max((point.value - low) / span * 100.0, 3.0)
            value = f"{point.value:.1f}"
            tone = "is-positive" if point.value >= 100.0 else "is-below"
        bars.append(
            f"""
            <div class="progress-aerobic-item">
                <div class="progress-aerobic-value">{value}</div>
                <div class="progress-aerobic-track">
                    <div class="progress-aerobic-fill {tone}" style="height:{height:.1f}%" title="{_escape(point.label)}: {value} index from {point.sample_size} comparable runs"></div>
                </div>
                <div class="progress-aerobic-label">{_escape(point.label)}</div>
                <div class="progress-aerobic-sample">{point.sample_size}r</div>
            </div>
            """
        )
    return f"""
    <div class="progress-aerobic-chart" role="img" aria-label="Twelve month conditions-adjusted aerobic efficiency index">
        {''.join(bars)}
    </div>
    <div class="progress-chart-key"><span class="is-green"></span>Monthly efficiency index <strong>100 = opening baseline</strong></div>
    """


def _rhythm_bars(summary: ProgressSummary) -> str:
    points = summary.rhythm.points
    ceiling = max((point.reliable_miles for point in points), default=1.0) or 1.0
    bars = []
    for point in points:
        height = max(point.reliable_miles / ceiling * 100.0, 2.0)
        total = point.reliable_miles or 1.0
        easy_share = point.easy_miles / total * 100.0
        long_share = point.long_miles / total * 100.0
        quality_share = point.quality_miles / total * 100.0
        other_share = max(100.0 - easy_share - long_share - quality_share, 0.0)
        bars.append(
            f"""
            <div class="progress-bar-item">
                <div class="progress-bar-value">{point.reliable_miles:.0f}</div>
                <div class="progress-bar-track">
                    <div class="progress-bar-stack" style="height:{height:.1f}%" title="{point.reliable_miles:.1f} reliable miles: {point.easy_miles:.1f} easy, {point.long_miles:.1f} long, {point.quality_miles:.1f} sessions">
                        <div class="progress-bar-segment is-other" style="height:{other_share:.1f}%"></div>
                        <div class="progress-bar-segment is-quality" style="height:{quality_share:.1f}%"></div>
                        <div class="progress-bar-segment is-long" style="height:{long_share:.1f}%"></div>
                        <div class="progress-bar-segment is-easy" style="height:{easy_share:.1f}%"></div>
                    </div>
                </div>
                <div class="progress-bar-label">{_escape(point.label)}</div>
                <div class="progress-bar-days">{point.active_days}d</div>
            </div>
            """
        )
    return f"""
    <div class="progress-bars" aria-label="Twelve week reliable mileage split by training purpose and running days">{''.join(bars)}</div>
    <div class="progress-rhythm-legend">
        <span><i class="is-easy"></i>Easy</span>
        <span><i class="is-long"></i>Long run</span>
        <span><i class="is-quality"></i>Sessions</span>
        <span><i class="is-other"></i>Other</span>
    </div>
    """


def _race_cards(summary: ProgressSummary) -> str:
    cards = []
    for event in summary.race.events:
        if event.change_s is None:
            change = "Trend building"
            tone = ""
        elif event.change_s >= 5:
            change = f"{abs(event.change_s):.0f}s improvement"
            tone = "is-positive"
        elif event.change_s <= -10:
            change = f"{abs(event.change_s):.0f}s slower"
            tone = "is-caution"
        else:
            change = "Broadly stable"
            tone = ""
        cards.append(
            f"""
            <article class="progress-race-card">
                <div class="progress-card-label">{_escape(event.label)}</div>
                <div class="progress-race-time">{_clock(event.recent_best_s)}</div>
                <div class="progress-card-meta">Recent 6-month best</div>
                <div class="progress-race-previous">Previous 6-month best <strong>{_clock(event.prior_best_s)}</strong></div>
                <div class="progress-race-change {tone}">{_escape(change)}</div>
                <div class="progress-race-alltime">All-time best <strong>{_clock(event.all_time_best_s)}</strong></div>
                <div class="progress-card-meta">{event.evidence_count} trusted result{'s' if event.evidence_count != 1 else ''} in 12 months</div>
            </article>
            """
        )
    return "".join(cards)


def build_progress_html(summary: ProgressSummary) -> str:
    aerobic_value = _signed(summary.aerobic.trend_percent)
    threshold_value = _pace(summary.threshold.current_pace_s_per_km)
    threshold_equivalent = _pace_range(
        summary.threshold.standard_equivalent_fast_s_per_km,
        summary.threshold.standard_equivalent_slow_s_per_km,
    )
    durability_value = (
        f"{summary.durability.recent_decoupling_percent:.1f}%"
        if summary.durability.recent_decoupling_percent is not None
        else "—"
    )
    evidence_notes = "".join(
        f"<li>{_escape(note)}</li>" for note in summary.evidence_notes
    )
    threshold_samples = (
        f"{summary.threshold.recent_sample_size} recent · "
        f"{summary.threshold.comparison_sample_size} earlier"
    )
    durability_samples = (
        f"{summary.durability.recent_sample_size} recent · "
        f"{summary.durability.comparison_sample_size} earlier"
    )
    return f"""
    <main class="progress-shell">
        <section class="progress-verdict">
            <div>
                <div class="progress-eyebrow">PROGRESS REVIEW · TO {_escape(summary.reference_date)}</div>
                <div class="progress-verdict-row">
                    <h1>{_escape(summary.headline)}</h1>
                    <span class="progress-verdict-pill">{_escape(summary.verdict)}</span>
                </div>
                <p>{_escape(summary.summary)}</p>
            </div>
            <div class="progress-confidence {_confidence_class(summary.confidence)}">
                <span>OVERALL CONFIDENCE</span>
                <strong>{_escape(summary.confidence)}</strong>
                <small>led by comparable aerobic evidence</small>
            </div>
        </section>

        <section class="progress-status-grid" aria-label="Progress status overview">
            <article class="progress-status-card is-aerobic">
                <div class="progress-card-label">AEROBIC FITNESS</div>
                <div class="progress-card-value">{aerobic_value}</div>
                <div class="progress-card-status">{_escape(summary.aerobic.status)}</div>
                <p>{summary.aerobic.recent_sample_size} recent vs {summary.aerobic.comparison_sample_size} opening comparable runs.</p>
                <span class="progress-mini-confidence {_confidence_class(summary.aerobic.confidence)}">{_escape(summary.aerobic.confidence)} confidence</span>
            </article>
            <article class="progress-status-card">
                <div class="progress-card-label">TRAINING RHYTHM</div>
                <div class="progress-card-value">{summary.rhythm.active_days_per_week:.1f}<small> days/wk</small></div>
                <div class="progress-card-status">{_escape(summary.rhythm.status)}</div>
                <p>{summary.rhythm.moving_hours_per_week:.1f} hours · {summary.rhythm.reliable_miles_per_week:.1f} reliable miles per week.</p>
                <span class="progress-mini-confidence {_confidence_class(summary.rhythm.confidence)}">{_escape(summary.rhythm.confidence)} confidence</span>
            </article>
            <article class="progress-status-card">
                <div class="progress-card-label">THRESHOLD</div>
                <div class="progress-card-value">{threshold_value}</div>
                <div class="progress-card-status">{_escape(summary.threshold.status)}</div>
                <p>Observed trusted work-phase pace · {summary.threshold.total_sample_size} qualifying sessions.</p>
                <span class="progress-mini-confidence {_confidence_class(summary.threshold.confidence)}">{_escape(summary.threshold.confidence)} confidence</span>
            </article>
            <article class="progress-status-card">
                <div class="progress-card-label">DURABILITY</div>
                <div class="progress-card-value">{durability_value}<small> drift</small></div>
                <div class="progress-card-status">{_escape(summary.durability.status)}</div>
                <p>Recent median on uninterrupted Long Easy runs; lower is better.</p>
                <span class="progress-mini-confidence {_confidence_class(summary.durability.confidence)}">{_escape(summary.durability.confidence)} confidence</span>
            </article>
        </section>

        <section class="progress-chart-grid">
            <article class="progress-panel">
                <div class="progress-panel-heading">
                    <div><div class="progress-card-label">CONDITIONS-NORMALISED</div><h2>Aerobic efficiency</h2></div>
                    <div class="progress-panel-stat"><strong>{summary.aerobic.sample_size}</strong><span>comparable runs</span></div>
                </div>
                {_aerobic_chart(summary)}
                <p class="progress-explainer">Pace relative to heart rate, normalised for supported heat, humidity, climbing, wind and trail effects. A higher index is better.</p>
            </article>
            <article class="progress-panel">
                <div class="progress-panel-heading">
                    <div><div class="progress-card-label">LAST 12 WEEKS</div><h2>Training rhythm</h2></div>
                    <div class="progress-panel-stat"><strong>{summary.rhythm.reliable_miles_per_week:.1f}</strong><span>mi/week, latest 6</span></div>
                </div>
                {_rhythm_bars(summary)}
                <p class="progress-explainer">Bars show reliable distance split into Easy, Long Run and Sessions (threshold, intervals, speed or race effort). Day counts include every run. Time still counts when treadmill pace or distance is not trustworthy.</p>
            </article>
        </section>

        <section class="progress-panel progress-races">
            <div class="progress-panel-heading">
                <div><div class="progress-card-label">FACTUAL RESULTS</div><h2>Race progression</h2></div>
                <span class="progress-section-status">{_escape(summary.race.status)}</span>
            </div>
            <div class="progress-race-grid">{_race_cards(summary)}</div>
            <p class="progress-explainer">{_escape(summary.race.summary)}</p>
        </section>

        <section class="progress-evidence-grid">
            <article class="progress-panel progress-evidence-card">
                <div class="progress-card-label">SPEED YOU CAN SUSTAIN</div>
                <h2>Threshold evidence</h2>
                <div class="progress-evidence-value">{threshold_value}</div>
                <div class="progress-evidence-caption">Observed work pace · {_escape(summary.threshold.current_conditions)}</div>
                <div class="progress-threshold-equivalent"><span>Estimated 12°C flat-road equivalent</span><strong>{threshold_equivalent}</strong></div>
                <div class="progress-evidence-status">{_escape(summary.threshold.status)} · {_escape(threshold_samples)}</div>
                <p>{_escape(summary.threshold.summary)}</p>
                <div class="progress-rule">Rep/work-phase pace is used. Warm-up and recovery never dilute it. The equivalent is a cautious range, not a confirmed current threshold.</div>
            </article>
            <article class="progress-panel progress-evidence-card">
                <div class="progress-card-label">FITNESS THAT LASTS</div>
                <h2>Durability evidence</h2>
                <div class="progress-evidence-value">{durability_value}</div>
                <div class="progress-evidence-status">{_escape(summary.durability.status)} · {_escape(durability_samples)}</div>
                <p>{_escape(summary.durability.summary)}</p>
                <div class="progress-rule">{summary.durability.interrupted_exclusion_count} interrupted Long Easy runs excluded from the last-year trend.</div>
            </article>
        </section>

        <details class="progress-method">
            <summary>How Progress decides what counts</summary>
            <ul>{evidence_notes}</ul>
        </details>
    </main>
    <style>
        .progress-shell {{ color:#10263d; display:grid; gap:12px; container-type:inline-size; }}
        .progress-shell * {{ box-sizing:border-box; }}
        .progress-verdict,.progress-panel,.progress-status-card,.progress-method {{ background:#fff; border:1px solid #e5ddd2; border-radius:18px; box-shadow:0 8px 24px rgba(16,38,61,.045); }}
        .progress-verdict {{ padding:24px 26px; display:grid; grid-template-columns:minmax(0,1fr) 205px; gap:24px; align-items:center; }}
        .progress-eyebrow,.progress-card-label {{ color:#778594; font-size:11px; line-height:1.25; font-weight:800; letter-spacing:.13em; }}
        .progress-verdict-row {{ display:flex; gap:12px; align-items:center; flex-wrap:wrap; margin-top:6px; }}
        .progress-verdict h1 {{ color:#10263d!important; font-size:clamp(28px,3vw,42px); line-height:1.02; margin:0; letter-spacing:-.04em; }}
        .progress-verdict p {{ color:#5f6b78; font-size:14px; line-height:1.45; margin:10px 0 0; max-width:900px; }}
        .progress-verdict-pill,.progress-section-status {{ background:#e7f5ed; color:#238a52; border-radius:999px; padding:6px 11px; font-size:11px; line-height:1; font-weight:800; text-transform:uppercase; letter-spacing:.07em; white-space:nowrap; }}
        .progress-confidence {{ border-radius:14px; padding:16px; display:flex; flex-direction:column; gap:3px; background:#eef7f2; border:1px solid #d1eadc; }}
        .progress-confidence span {{ font-size:10px; font-weight:800; letter-spacing:.12em; color:#657482; }}
        .progress-confidence strong {{ font-size:25px; color:#238a52; }}
        .progress-confidence small {{ color:#657482; font-size:10px; line-height:1.3; }}
        .progress-confidence.is-moderate {{ background:#fff5e4; border-color:#f3dfba; }} .progress-confidence.is-moderate strong {{ color:#b86a00; }}
        .progress-confidence.is-limited {{ background:#fff0e8; border-color:#f4d8ca; }} .progress-confidence.is-limited strong {{ color:#d74714; }}
        .progress-status-grid {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px; }}
        .progress-status-card {{ padding:17px; min-width:0; position:relative; overflow:hidden; }}
        .progress-status-card.is-aerobic {{ border-top:3px solid #2e9b67; }}
        .progress-card-value {{ color:#10263d; font-size:29px; line-height:1; font-weight:800; letter-spacing:-.04em; margin:13px 0 6px; }}
        .progress-card-value small {{ font-size:12px; letter-spacing:0; color:#778594; font-weight:700; }}
        .progress-card-status {{ color:#10263d; font-size:14px; font-weight:750; }}
        .progress-status-card p {{ color:#687582; font-size:11px; line-height:1.35; min-height:30px; margin:6px 0 13px; }}
        .progress-mini-confidence {{ display:inline-block; padding:5px 8px; border-radius:999px; font-size:10px; font-weight:800; color:#238a52; background:#eaf6ef; }}
        .progress-mini-confidence.is-moderate {{ color:#a65f00; background:#fff5e4; }} .progress-mini-confidence.is-limited {{ color:#c94d20; background:#fff0e8; }}
        .progress-chart-grid,.progress-evidence-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; }}
        .progress-panel {{ padding:19px 20px; min-width:0; }}
        .progress-panel-heading {{ display:flex; justify-content:space-between; align-items:flex-start; gap:14px; margin-bottom:8px; }}
        .progress-panel h2,.progress-evidence-card h2 {{ color:#10263d!important; font-size:20px; line-height:1.1; margin:4px 0 0; letter-spacing:-.025em; }}
        .progress-panel-stat {{ text-align:right; display:flex; flex-direction:column; }}
        .progress-panel-stat strong {{ color:#238a52; font-size:22px; line-height:1; }} .progress-panel-stat span {{ color:#778594; font-size:10px; margin-top:3px; }}
        .progress-aerobic-chart {{ height:184px; display:flex; gap:5px; align-items:stretch; padding-top:17px; }}
        .progress-aerobic-item {{ flex:1; min-width:0; display:grid; grid-template-rows:15px 1fr 17px 14px; text-align:center; }}
        .progress-aerobic-value,.progress-aerobic-label,.progress-aerobic-sample {{ color:#7b8793; font-size:9px; white-space:nowrap; overflow:hidden; }}
        .progress-aerobic-sample {{ color:#238a52; font-weight:800; }}
        .progress-aerobic-track {{ background:#f1ede6; border-radius:5px 5px 2px 2px; display:flex; align-items:flex-end; overflow:hidden; }}
        .progress-aerobic-fill {{ width:100%; min-height:3px; background:linear-gradient(180deg,#46ad7a,#238a52); border-radius:5px 5px 2px 2px; }}
        .progress-aerobic-fill.is-below {{ background:linear-gradient(180deg,#f39a72,#e56b39); }}
        .progress-aerobic-fill.is-missing {{ background:#e7e1d8; }}
        .progress-chart-key {{ display:flex; align-items:center; gap:6px; color:#778594; font-size:9px; margin-top:4px; }}
        .progress-chart-key span {{ width:8px; height:8px; border-radius:2px; background:#2e9b67; }}
        .progress-chart-key strong {{ color:#5f6b78; margin-left:auto; font-weight:750; }}
        .progress-bars {{ height:190px; display:flex; gap:5px; align-items:stretch; padding-top:17px; }}
        .progress-bar-item {{ flex:1; min-width:0; display:grid; grid-template-rows:15px 1fr 17px 14px; text-align:center; }}
        .progress-bar-value,.progress-bar-label,.progress-bar-days {{ font-size:9px; color:#7b8793; white-space:nowrap; overflow:hidden; }}
        .progress-bar-days {{ color:#238a52; font-weight:800; }}
        .progress-bar-track {{ background:#f1ede6; border-radius:5px 5px 2px 2px; display:flex; align-items:flex-end; overflow:hidden; }}
        .progress-bar-stack {{ width:100%; min-height:2px; display:flex; flex-direction:column; justify-content:flex-end; overflow:hidden; border-radius:5px 5px 2px 2px; }}
        .progress-bar-segment {{ width:100%; min-height:0; }}
        .progress-bar-segment.is-easy,.progress-rhythm-legend i.is-easy {{ background:#3e8e72; }}
        .progress-bar-segment.is-long,.progress-rhythm-legend i.is-long {{ background:#10263d; }}
        .progress-bar-segment.is-quality,.progress-rhythm-legend i.is-quality {{ background:#f05a28; }}
        .progress-bar-segment.is-other,.progress-rhythm-legend i.is-other {{ background:#b9b1a5; }}
        .progress-rhythm-legend {{ display:flex; flex-wrap:wrap; gap:12px; margin-top:7px; color:#687582; font-size:9px; }}
        .progress-rhythm-legend span {{ display:flex; align-items:center; gap:4px; }}
        .progress-rhythm-legend i {{ display:block; width:8px; height:8px; border-radius:2px; }}
        .progress-explainer {{ color:#687582; font-size:10px; line-height:1.4; margin:7px 0 0; }}
        .progress-race-grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px; }}
        .progress-race-card {{ background:#f8f5ef; border:1px solid #ebe4da; border-radius:13px; padding:14px; }}
        .progress-race-time {{ font-size:28px; line-height:1; font-weight:800; margin:10px 0 3px; letter-spacing:-.04em; }}
        .progress-card-meta {{ color:#7b8793; font-size:10px; line-height:1.35; }}
        .progress-race-previous {{ color:#5f6b78; font-size:11px; margin-top:12px; }}
        .progress-race-alltime {{ color:#5f6b78; font-size:10px; margin:7px 0 4px; }}
        .progress-race-change {{ color:#566474; font-size:12px; font-weight:800; margin:8px 0 3px; }}
        .progress-race-change.is-positive {{ color:#238a52; }} .progress-race-change.is-caution {{ color:#d65a2c; }}
        .progress-evidence-card {{ border-left:4px solid #f05a28; }}
        .progress-evidence-value {{ font-size:32px; line-height:1; font-weight:800; margin:17px 0 7px; letter-spacing:-.04em; }}
        .progress-evidence-caption {{ color:#778594; font-size:10px; line-height:1.35; margin-bottom:10px; }}
        .progress-threshold-equivalent {{ display:flex; justify-content:space-between; align-items:center; gap:12px; background:#eef7f2; border:1px solid #d7eadf; border-radius:10px; padding:10px 11px; margin:10px 0; }}
        .progress-threshold-equivalent span {{ color:#667582; font-size:10px; line-height:1.3; }}
        .progress-threshold-equivalent strong {{ color:#238a52; font-size:15px; white-space:nowrap; }}
        .progress-evidence-status {{ color:#238a52; font-size:12px; font-weight:800; }}
        .progress-evidence-card p {{ color:#687582; font-size:11px; line-height:1.45; margin:10px 0; }}
        .progress-rule {{ background:#f8f5ef; border-radius:10px; padding:10px 11px; color:#5f6b78; font-size:10px; line-height:1.4; }}
        .progress-method {{ padding:0 18px; }}
        .progress-method summary {{ cursor:pointer; padding:15px 0; color:#10263d; font-size:12px; font-weight:800; }}
        .progress-method ul {{ margin:0 0 16px; padding-left:20px; }} .progress-method li {{ color:#687582; font-size:10px; line-height:1.45; margin:5px 0; }}
        .progress-empty {{ min-height:190px; display:flex; align-items:center; justify-content:center; color:#7b8793; font-size:11px; }}
        @container (max-width:900px) {{ .progress-status-grid {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} .progress-verdict {{ grid-template-columns:1fr; }} .progress-confidence {{ max-width:260px; }} }}
        @container (max-width:650px) {{ .progress-chart-grid,.progress-evidence-grid {{ grid-template-columns:1fr; }} .progress-race-grid {{ grid-template-columns:1fr; }} }}
        @container (max-width:430px) {{ .progress-status-grid {{ grid-template-columns:1fr; }} .progress-verdict,.progress-panel {{ padding:17px; }} .progress-bar-label {{ writing-mode:vertical-rl; height:30px; }} .progress-bars {{ height:210px; }} }}
    </style>
    """


def show_progress_page() -> None:
    """Render the Progress Foundation from the canonical selected athlete."""
    st.markdown(
        """
        <style>
            [data-testid="stMainBlockContainer"] { max-width:1450px; padding-top:4.25rem; padding-bottom:3rem; }
            [data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"],
            [data-testid="stMainBlockContainer"] > div > [data-testid="stVerticalBlock"] { gap:10px; }
            [data-testid="stHeader"] { background:transparent; }
            [data-testid="stElementContainer"]:has(.progress-selector-marker) { display:none; }
            [data-testid="stVerticalBlock"]:has(.progress-selector-marker) { gap:0; }
            [data-testid="stHorizontalBlock"]:has(.progress-selector-marker) { align-items:flex-start; gap:8px; }
            .progress-context-strip {
                min-height:40px; border:1px solid #e5ddd2; border-radius:12px;
                background:#fff; padding:0 15px; display:flex; align-items:center;
                justify-content:space-between; gap:14px; color:#10263d;
                box-shadow:0 5px 18px rgba(16,38,61,.035);
            }
            .progress-context-strip strong { font-size:12px; letter-spacing:.12em; }
            .progress-context-strip span { color:#6c7885; font-size:11px; }
            .progress-context-strip em { color:#238a52; font-size:10px; font-style:normal; font-weight:800; letter-spacing:.08em; }
            @media (max-width:900px) {
                [data-testid="stHorizontalBlock"]:has(.progress-selector-marker) [data-testid="stColumn"]:last-child { display:none; }
                [data-testid="stHorizontalBlock"]:has(.progress-selector-marker) [data-testid="stColumn"]:first-child { flex:1 1 100%; width:100%; }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )
    selector_col, context_col = st.columns([390, 1051], gap="small")
    with selector_col:
        st.markdown(
            '<span class="progress-selector-marker"></span>',
            unsafe_allow_html=True,
        )
        athlete_id = render_athlete_id_selector(label_visibility="collapsed")
    with context_col:
        st.html(
            '<div class="progress-context-strip"><strong>PROGRESS</strong>'
            '<span>Am I improving?</span><em>12 MONTH EVIDENCE</em></div>'
        )
    if athlete_id is None:
        st.warning("No athletes found. Add an athlete first.")
        return

    with st.spinner("Building longitudinal progress evidence…"):
        summary = _cached_progress(athlete_id, PROGRESS_CACHE_SCHEMA)
    if summary is None:
        st.info("Import running history to begin building Progress.")
        return
    st.html(build_progress_html(summary))
