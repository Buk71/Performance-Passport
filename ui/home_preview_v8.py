"""Experimental Home v8 density and typography preview.

Run with:
    streamlit run ui/home_preview_v8.py

V8 is deliberately separate from the approved v6 Home and the v7 hierarchy
preview. It preserves their real-data adapters and calculations while applying
one coherent density, typography, and responsive layout system.
"""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from core.home_best_runs import build_home_best_runs
from core.home_summary import HomeSummary, build_home_summary
from ui.athlete_card import build_athlete_card_html
from ui.athlete_selection import render_athlete_selector
from ui import home_preview as v6


def _coach_evidence(key: str) -> str:
    return {
        "race": "Race results reveal the competitive ceiling you have already proved.",
        "workout": "Quality sessions show the speed you can repeat in controlled training.",
        "threshold": "Sustained efforts anchor the pace you can currently hold with confidence.",
    }.get(key, "An independent specialist reading of your current race form.")


def build_v8_goal_html(summary: HomeSummary, *, mobile: bool = False) -> str:
    """Render a compact, readable goal strip aligned with the selector."""
    block_status = "Active block" if summary.block_is_saved else "Adaptive preview"
    placement = " v8-goal-mobile" if mobile else " v8-goal-desktop"

    return f"""
    <style>
        * {{ box-sizing:border-box; }}
        body {{ margin:0; }}
        .v8-goal-strip {{
            width:100%; height:38px; min-height:38px; padding:4px 12px;
            display:grid; grid-template-columns:minmax(220px,.88fr) minmax(210px,.82fr) minmax(330px,1.3fr);
            gap:14px; align-items:center; overflow:hidden;
            color:#10263d; font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
            background:radial-gradient(circle at 98% 0%,rgba(240,90,40,.09),transparent 30%),#fffdf9;
            border:1px solid #ded8ce; border-radius:11px; box-shadow:0 7px 20px rgba(7,24,42,.075);
        }}
        .v8-goal-primary,.v8-goal-direction {{ min-width:0; display:flex; align-items:center; gap:8px; }}
        .v8-goal-label {{ color:#6f7984; font-size:10px; line-height:1; font-weight:900; letter-spacing:.1em; text-transform:uppercase; white-space:nowrap; }}
        .v8-goal-name {{ overflow:hidden; font-size:15px; line-height:1; font-weight:900; letter-spacing:-.02em; text-overflow:ellipsis; white-space:nowrap; }}
        .v8-goal-target {{ flex:0 0 auto; color:#f05a28; font-size:13px; line-height:1; font-weight:900; white-space:nowrap; }}
        .v8-goal-context {{ overflow:hidden; color:#64727e; font-size:11.5px; line-height:1.2; text-overflow:ellipsis; white-space:nowrap; }}
        .v8-goal-direction {{ padding-left:14px; border-left:1px solid #ddd6cc; }}
        .v8-goal-direction strong {{ overflow:hidden; color:#3e8e72; font-size:12.5px; line-height:1; text-overflow:ellipsis; white-space:nowrap; }}
        .v8-goal-direction-copy {{ overflow:hidden; color:#64727e; font-size:11px; line-height:1.15; text-overflow:ellipsis; white-space:nowrap; }}
        .v8-goal-status {{ flex:0 0 auto; padding:3px 7px; color:#287e51; font-size:10px; line-height:1; font-weight:900; letter-spacing:.04em; text-transform:uppercase; background:#e9f5ee; border-radius:999px; }}
        .v8-goal-mobile {{ display:none; }}
        @media (max-width:1200px) {{
            .v8-goal-desktop {{ display:none; }}
            .v8-goal-mobile {{
                display:grid; min-height:0; grid-template-columns:1fr; gap:7px; padding:11px 13px;
            }}
            .v8-goal-primary {{ flex-wrap:wrap; }}
            .v8-goal-context {{ white-space:normal; }}
            .v8-goal-direction {{ flex-wrap:wrap; padding:7px 0 0; border-top:1px solid #e5ded5; border-left:0; }}
            .v8-goal-direction-copy {{ white-space:normal; }}
        }}
    </style>
    <section class="v8-goal-strip{placement}">
        <div class="v8-goal-primary">
            <span class="v8-goal-label">Active goal</span>
            <strong class="v8-goal-name">{v6._safe(summary.goal_name)}</strong>
            <span class="v8-goal-target">{v6._safe(v6._clock(summary.target_time_s))}</span>
        </div>
        <div class="v8-goal-context">{v6._safe(summary.goal_context)}</div>
        <div class="v8-goal-direction">
            <span class="v8-goal-label">Direction</span>
            <strong>{v6._safe(summary.block_name)}</strong>
            <span class="v8-goal-direction-copy">{v6._safe(summary.block_context)}</span>
            <span class="v8-goal-status">{v6._safe(block_status)}</span>
        </div>
    </section>
    """


def _latest_run_markup(latest) -> str:
    if not latest.available:
        return f"""
        <div class="v8-kicker">Latest run</div>
        <h3>{v6._safe(latest.title)}</h3>
        <div class="v8-latest-copy">{v6._safe(latest.explanation)}</div>
        """

    rank = (
        f"<strong>#{latest.rank}</strong><span>of {latest.comparison_count}<br>{v6._safe(latest.category)}</span>"
        if latest.rank is not None and latest.comparison_count is not None
        else "<strong>—</strong><span>Rank building</span>"
    )
    conditions = (
        " · ".join(latest.environment_factors[:2])
        if latest.environment_factors
        else "Conditions recognised where data allows"
    )
    return f"""
    <div class="v8-latest-head">
        <div>
            <div class="v8-kicker">Latest run · {v6._safe(v6._format_date(latest.activity_date))}</div>
            <h3>{v6._safe(latest.title)}</h3>
        </div>
        <div class="v8-rank">{rank}</div>
    </div>
    <div class="v8-latest-win">{v6._safe(latest.headline)}</div>
    <div class="v8-latest-copy">{v6._safe(latest.explanation)}</div>
    <div class="v8-latest-stats">
        <span><b>{v6._safe(v6._distance_miles(latest.distance_km))}</b>Distance</span>
        <span><b>{v6._safe(v6._clock(latest.moving_time_s))}</b>Time</span>
        <span><b>{v6._safe(v6._pace_per_mile(latest.actual_pace_s_per_km))}</b>Pace</span>
        <span><b>{v6._safe(f'{latest.avg_hr:.0f} bpm' if latest.avg_hr is not None else '—')}</b>Avg HR</span>
    </div>
    <div class="v8-benefit"><span>What it gave you</span><strong>{v6._safe(latest.benefit)}</strong></div>
    <div class="v8-condition-note">{v6._safe(conditions)} · {latest.confidence:.0%} evidence confidence</div>
    """


def build_v8_intelligence_html(summary, latest) -> str:
    """Render the natural-height intelligence panel and race outlook band."""
    if not summary.available:
        return f"""
        <div class="v8-rail">
            <section class="v8-intelligence v8-empty">
                <div class="v8-section-title">Performance Intelligence</div>
                <strong>Race capability is still building</strong>
                <span>{v6._safe(summary.explanation)}</span>
            </section>
        </div>
        """

    coaches = []
    for coach in getattr(summary, "coach_positions", ()):
        lead = '<span class="v8-lead">Lead</span>' if coach.is_lead else ""
        coaches.append(
            f"""
            <article class="v8-coach v8-{v6._safe(coach.position)}">
                <div class="v8-coach-head"><strong>{v6._safe(coach.title)}</strong>{lead}</div>
                <div class="v8-coach-result">
                    <span class="v8-coach-time">{v6._safe(v6._clock(coach.predicted_seconds))}</span>
                    <span class="v8-coach-stance">{v6._safe(coach.position.title())} view</span>
                </div>
                <div class="v8-coach-copy">{v6._safe(_coach_evidence(coach.key))}</div>
                <div class="v8-confidence">{coach.confidence:.0%} confidence</div>
            </article>
            """
        )

    responses = []
    for response in getattr(summary, "environment_responses", ()):
        response_class = (
            "v8-response-edge"
            if response.confidence >= 0.25 and response.multiplier < 0.92
            else "v8-response-cost"
            if response.confidence >= 0.25 and response.multiplier > 1.08
            else "v8-response-neutral"
        )
        responses.append(
            f"""
            <span class="v8-response {response_class}">
                <b>{v6._environment_icon(response.key)} {v6._safe(response.label)}</b>
                <span>{v6._safe(response.response_label)}</span>
            </span>
            """
        )

    trait = getattr(summary, "performance_trait", None)
    trait_markup = (
        f"""
        <div class="v8-trait">
            <span>Your edge</span>
            <strong>{v6._safe(trait.title)}</strong>
            <em>{v6._safe(trait.detail)}</em>
        </div>
        """
        if trait is not None
        else """
        <div class="v8-trait v8-trait-building">
            <span>Your edge</span>
            <strong>Still emerging</strong>
            <em>Comparable runs will reveal a reliable environmental strength.</em>
        </div>
        """
    )

    scenarios = []
    for scenario in summary.scenarios:
        personal = '<span class="v8-personal">Personal</span>' if scenario.personalised else ""
        scenarios.append(
            f"""
            <article class="v8-scenario v8-scenario-{v6._safe(scenario.key)}">
                <div class="v8-scenario-head"><strong>{v6._safe(scenario.label)}</strong>{personal}</div>
                <div class="v8-scenario-time">{v6._safe(v6._clock(scenario.central_seconds))}</div>
                <div class="v8-scenario-copy">{v6._safe(scenario.description)}</div>
                <div class="v8-scenario-meta">
                    <span>{v6._safe(v6._pace_per_mile(scenario.pace_seconds_per_km))}</span>
                    <b>{scenario.confidence:.0%}</b>
                </div>
            </article>
            """
        )

    probability = f"{summary.target_probability:.0%}" if summary.target_probability is not None else "—"
    status = {
        "aligned": "Closely aligned",
        "balanced": "Broadly aligned",
        "mixed": "Mixed signals",
        "developing": "Developing",
        "building": "Building",
    }.get(summary.consensus_status, summary.consensus_status)

    return f"""
    <style>
        * {{ box-sizing:border-box; }}
        body {{ margin:0; }}
        .v8-rail {{ min-width:0; display:grid; gap:9px; color:#10263d; font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
        .v8-intelligence,.v8-outlook {{ min-width:0; overflow:hidden; border:1px solid #ded8ce; border-radius:16px; box-shadow:0 12px 32px rgba(7,24,42,.085); }}
        .v8-intelligence {{ padding:11px 12px 12px; background:radial-gradient(circle at 100% 100%,rgba(240,90,40,.065),transparent 25%),#fffdf9; }}
        .v8-section-head,.v8-panel-head {{ display:flex; align-items:center; justify-content:space-between; gap:12px; }}
        .v8-section-head {{ margin:0 2px 9px; }}
        .v8-section-title {{ font-size:14px; line-height:1.1; font-weight:900; letter-spacing:.09em; text-transform:uppercase; }}
        .v8-section-title span {{ color:#6f7b86; font-size:11px; font-weight:700; letter-spacing:.04em; }}
        .v8-link {{ color:#526371; font-size:10px; line-height:1; font-weight:850; letter-spacing:.06em; text-transform:uppercase; white-space:nowrap; }}
        .v8-intelligence-grid {{ display:grid; grid-template-columns:minmax(300px,.86fr) minmax(470px,1.14fr); gap:9px; align-items:stretch; }}
        .v8-panel {{ min-width:0; padding:10px 11px; border-radius:12px; }}
        .v8-latest {{ background:#f7f5f0; border:1px solid #ded8ce; }}
        .v8-latest-head {{ display:flex; justify-content:space-between; align-items:flex-start; gap:12px; }}
        .v8-kicker {{ color:#64727e; font-size:10px; line-height:1.1; font-weight:900; letter-spacing:.09em; text-transform:uppercase; }}
        .v8-latest h3 {{ margin:4px 0 0; font-size:18px; line-height:1.05; letter-spacing:-.025em; }}
        .v8-rank {{ flex:0 0 auto; min-width:82px; padding:6px 8px; text-align:right; background:#fffdf9; border:1px solid #ded8ce; border-radius:9px; }}
        .v8-rank strong {{ display:block; color:#3e8e72; font-size:19px; line-height:1; }}
        .v8-rank span {{ display:block; margin-top:3px; color:#687681; font-size:10px; line-height:1.15; }}
        .v8-latest-win {{ margin-top:7px; font-size:15px; line-height:1.15; font-weight:900; }}
        .v8-latest-copy {{ margin-top:4px; color:#53636f; font-size:12px; line-height:1.34; }}
        .v8-latest-stats {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:7px; margin-top:8px; }}
        .v8-latest-stats span {{ min-width:0; color:#71808b; font-size:10px; line-height:1.15; text-transform:uppercase; }}
        .v8-latest-stats b {{ display:block; overflow:hidden; margin-bottom:2px; color:#10263d; font-size:12.5px; line-height:1.1; text-transform:none; text-overflow:ellipsis; white-space:nowrap; }}
        .v8-benefit {{ display:grid; grid-template-columns:auto minmax(0,1fr); align-items:center; gap:10px; margin-top:8px; padding:7px 9px; background:#fff1e7; border-left:3px solid #f05a28; border-radius:7px; }}
        .v8-benefit span {{ color:#d94b17; font-size:10px; line-height:1.1; font-weight:900; letter-spacing:.06em; text-transform:uppercase; }}
        .v8-benefit strong {{ font-size:11.5px; line-height:1.3; }}
        .v8-condition-note {{ margin-top:6px; color:#6f7c87; font-size:10.5px; line-height:1.25; }}
        .v8-coaches {{ color:#fff; background:radial-gradient(circle at 100% 0%,rgba(62,142,114,.25),transparent 35%),linear-gradient(145deg,#07182a,#102e49); border:1px solid #173d5e; }}
        .v8-panel-title {{ font-size:13.5px; line-height:1.1; font-weight:900; letter-spacing:.08em; text-transform:uppercase; }}
        .v8-status {{ padding:4px 8px; color:#bde8cf; font-size:10px; line-height:1; font-weight:900; letter-spacing:.05em; text-transform:uppercase; background:rgba(62,142,114,.23); border-radius:999px; }}
        .v8-coaches-intro {{ margin-top:5px; color:#cfdae4; font-size:12px; line-height:1.32; }}
        .v8-coach-grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:7px; margin-top:8px; }}
        .v8-coach {{ min-width:0; padding:8px 9px; color:#10263d; background:#fffdf9; border:1px solid rgba(255,255,255,.4); border-top:3px solid #9aa5ad; border-radius:9px; }}
        .v8-coach.v8-optimistic {{ border-top-color:#3e8e72; }}
        .v8-coach.v8-cautious {{ border-top-color:#f05a28; }}
        .v8-coach-head {{ display:flex; align-items:center; gap:5px; min-width:0; }}
        .v8-coach-head strong {{ overflow:hidden; font-size:11.5px; line-height:1.1; text-overflow:ellipsis; white-space:nowrap; }}
        .v8-lead {{ margin-left:auto; padding:2px 5px; color:#fff; font-size:10px; line-height:1; font-weight:900; text-transform:uppercase; background:#f05a28; border-radius:999px; }}
        .v8-coach-result {{ display:flex; flex-wrap:wrap; align-items:baseline; gap:5px 8px; margin-top:5px; }}
        .v8-coach-time {{ font-size:23px; line-height:1; font-weight:900; letter-spacing:-.03em; }}
        .v8-coach-stance {{ color:#51616d; font-size:10.5px; line-height:1.1; font-weight:800; }}
        .v8-coach-copy {{ margin-top:5px; color:#51616d; font-size:11px; line-height:1.3; }}
        .v8-confidence {{ margin-top:4px; color:#6e7c87; font-size:10px; line-height:1.15; font-weight:750; }}
        .v8-coach-footer {{ display:grid; grid-template-columns:minmax(245px,.9fr) minmax(0,1.1fr); gap:7px; margin-top:7px; }}
        .v8-trait {{ display:grid; grid-template-columns:auto 1fr; column-gap:8px; align-items:center; padding:7px 9px; color:#10263d; background:linear-gradient(135deg,#ffe2a8,#fff4d9); border:1px solid #e5b85e; border-radius:8px; }}
        .v8-trait span {{ grid-row:1/3; color:#a55a0b; font-size:10px; line-height:1; font-weight:900; letter-spacing:.06em; text-transform:uppercase; }}
        .v8-trait strong {{ font-size:13px; line-height:1.05; }}
        .v8-trait em {{ overflow:hidden; color:#70593b; font-size:10px; line-height:1.15; font-style:normal; text-overflow:ellipsis; white-space:nowrap; }}
        .v8-responses {{ display:flex; align-items:stretch; gap:5px; min-width:0; }}
        .v8-response {{ flex:1 1 0; min-width:0; padding:6px; color:#c9d4de; font-size:10px; line-height:1.15; text-align:center; background:rgba(255,255,255,.07); border:1px solid rgba(255,255,255,.11); border-radius:7px; }}
        .v8-response b {{ display:block; margin-bottom:3px; color:#fff; font-size:10.5px; line-height:1.05; }}
        .v8-response span {{ display:block; }}
        .v8-response-edge b {{ color:#9fe0ba; }}
        .v8-response-cost b {{ color:#ffb294; }}
        .v8-outlook {{ padding:9px 10px 10px; background:#f7f5f0; }}
        .v8-outlook-band {{ display:grid; grid-template-columns:minmax(220px,1.2fr) repeat(5,minmax(105px,1fr)); margin-top:7px; overflow:hidden; background:#fffdf9; border:1px solid #ded8ce; border-radius:11px; }}
        .v8-capability,.v8-scenario {{ min-width:0; padding:8px 10px; }}
        .v8-scenario {{ border-left:1px solid #e5ded5; }}
        .v8-capability {{ background:linear-gradient(145deg,#fff3e6,#fffdf9); }}
        .v8-capability-range {{ margin-top:4px; font-size:22px; line-height:1; font-weight:900; letter-spacing:-.03em; white-space:nowrap; }}
        .v8-capability-central {{ margin-top:4px; color:#d94b17; font-size:11px; line-height:1.15; font-weight:850; }}
        .v8-capability-goal {{ display:flex; flex-wrap:wrap; gap:4px 11px; margin-top:5px; color:#65737f; font-size:10px; line-height:1.15; }}
        .v8-capability-goal b {{ color:#10263d; font-size:11px; }}
        .v8-scenario-ideal {{ background:#fffaf2; }}
        .v8-scenario-typical {{ background:#f3faf6; }}
        .v8-scenario-head {{ display:flex; align-items:center; gap:5px; min-height:15px; }}
        .v8-scenario-head strong {{ overflow:hidden; font-size:11px; line-height:1.1; text-overflow:ellipsis; white-space:nowrap; }}
        .v8-personal {{ margin-left:auto; padding:2px 4px; color:#287e51; font-size:10px; line-height:1; font-weight:900; text-transform:uppercase; background:#e6f4ec; border-radius:999px; }}
        .v8-scenario-time {{ margin-top:4px; font-size:19px; line-height:1; font-weight:900; letter-spacing:-.025em; }}
        .v8-scenario-copy {{ margin-top:4px; color:#5c6b76; font-size:10.5px; line-height:1.23; }}
        .v8-scenario-meta {{ display:flex; justify-content:space-between; gap:6px; margin-top:5px; color:#697681; font-size:10px; line-height:1.1; }}
        .v8-scenario-meta b {{ font-weight:850; }}
        .v8-empty {{ padding:20px; }}
        .v8-empty strong,.v8-empty span {{ display:block; margin-top:5px; }}
        @container (max-width:780px) {{
            .v8-intelligence-grid {{ grid-template-columns:1fr; }}
            .v8-outlook-band {{ grid-template-columns:repeat(3,minmax(0,1fr)); }}
            .v8-capability {{ grid-column:1/-1; }}
            .v8-scenario:nth-child(3n+2) {{ border-left:0; }}
        }}
        @container (max-width:620px) {{
            .v8-coach-grid {{ grid-template-columns:1fr; }}
            .v8-coach-footer {{ grid-template-columns:1fr; }}
            .v8-outlook-band {{ grid-template-columns:repeat(2,minmax(0,1fr)); }}
            .v8-scenario:nth-child(3n+2) {{ border-left:1px solid #e5ded5; }}
            .v8-scenario:nth-child(even) {{ border-left:0; }}
            .v8-latest-stats {{ grid-template-columns:repeat(2,minmax(0,1fr)); }}
        }}
        @container (max-width:390px) {{
            .v8-section-head,.v8-panel-head {{ align-items:flex-start; }}
            .v8-link {{ display:none; }}
            .v8-outlook-band {{ grid-template-columns:1fr; }}
            .v8-capability {{ grid-column:auto; }}
            .v8-scenario {{ border-top:1px solid #e5ded5; border-left:0!important; }}
            .v8-responses {{ flex-direction:column; }}
        }}
    </style>
    <div class="v8-rail">
        <section class="v8-intelligence">
            <div class="v8-section-head">
                <div class="v8-section-title">Performance Intelligence <span>· {v6._safe(summary.distance_label)} · {v6._safe(summary.goal_name)}</span></div>
                <div class="v8-link">View full analysis &nbsp;→</div>
            </div>
            <div class="v8-intelligence-grid">
                <article class="v8-panel v8-latest">{_latest_run_markup(latest)}</article>
                <article class="v8-panel v8-coaches">
                    <div class="v8-panel-head"><div class="v8-panel-title">Coaches’ View</div><span class="v8-status">{v6._safe(status)}</span></div>
                    <div class="v8-coaches-intro">{v6._safe(summary.consensus_headline)}</div>
                    <div class="v8-coach-grid">{''.join(coaches)}</div>
                    <div class="v8-coach-footer">{trait_markup}<div class="v8-responses">{''.join(responses)}</div></div>
                </article>
            </div>
        </section>
        <section class="v8-outlook">
            <div class="v8-panel-head"><div class="v8-panel-title">Race Outlook</div><span class="v8-kicker">Capability → race conditions</span></div>
            <div class="v8-outlook-band">
                <div class="v8-capability">
                    <div class="v8-kicker">Current capability</div>
                    <div class="v8-capability-range">{v6._safe(v6._clock(summary.low_seconds))}–{v6._safe(v6._clock(summary.high_seconds))}</div>
                    <div class="v8-capability-central">{v6._safe(v6._clock(summary.central_seconds))} central · {summary.confidence:.0%} confidence</div>
                    <div class="v8-capability-goal"><span><b>{v6._safe(v6._clock(summary.target_seconds))}</b> goal</span><span><b>{v6._safe(probability)}</b> likelihood</span><span>{v6._safe(v6._signed_gap(summary.target_gap_seconds))}</span></div>
                </div>
                {''.join(scenarios)}
            </div>
        </section>
    </div>
    """


def _v8_passport_overrides() -> str:
    """Keep the Passport's identity while bringing all small type into scale."""
    return """
    <style>
        .v8-passport .pp-shell { width:100%; max-width:390px; margin:0; }
        .v8-passport .pp-passport { border-radius:17px; box-shadow:0 14px 36px rgba(7,24,42,.16); }
        .v8-passport .pp-top { grid-template-columns:minmax(0,1.08fr) minmax(160px,.92fr); min-height:188px; }
        .v8-passport .pp-identity { padding:12px 12px 12px 16px; }
        .v8-passport .pp-logo { width:112px; height:46px; margin:-2px 0 4px -2px; }
        .v8-passport .pp-eyebrow { margin-bottom:5px; font-size:10px; letter-spacing:.13em; }
        .v8-passport .pp-name { font-size:26px; }
        .v8-passport .pp-category { margin-top:6px; font-size:10.5px; letter-spacing:.1em; }
        .v8-passport .pp-motto { margin-top:9px; font-size:11.5px; line-height:1.32; }
        .v8-passport .pp-photo-wrap,.v8-passport .pp-photo-placeholder { min-height:188px; }
        .v8-passport .pp-panel { padding:10px 11px; }
        .v8-passport .pp-section-title { margin-bottom:7px; font-size:10px; letter-spacing:.13em; }
        .v8-passport .pp-grade-grid { gap:6px; }
        .v8-passport .pp-grade-value { font-size:22px; }
        .v8-passport .pp-grade-label { margin-top:4px; font-size:10px; line-height:1.2; letter-spacing:.08em; }
        .v8-passport .pb-header { padding-bottom:4px; font-size:10px; letter-spacing:.08em; }
        .v8-passport .pb-row { min-height:25px; }
        .v8-passport .pb-event { font-size:10.5px; }
        .v8-passport .pb-time { font-size:12px; }
        .v8-passport .pp-development { padding:9px 13px 7px; }
        .v8-passport .development-title { font-size:14px; }
        .v8-passport .development-copy { margin-top:3px; font-size:10.5px; }
        .v8-passport .development-score { font-size:19px; }
        .v8-passport .development-score span { margin-top:3px; font-size:10px; letter-spacing:.09em; }
        .v8-passport .chart { height:39px; margin-top:4px; }
        @media (max-width:1200px) {
            .v8-passport .pp-shell { max-width:460px; margin:0 auto; }
        }
    </style>
    """


def build_v8_hero_html(athlete_id: int, home_summary: HomeSummary, predictions, latest) -> str:
    """Place the compact Passport beside a natural-height intelligence rail."""
    return f"""
    <style>
        .v8-hero {{ container-type:inline-size; display:grid; grid-template-columns:minmax(0,390px) minmax(0,1fr); gap:9px; align-items:start; width:100%; }}
        .v8-passport,.v8-hero-right {{ min-width:0; }}
        .v8-hero-right {{ container-type:inline-size; }}
        .v8-mobile-goal {{ display:none; }}
        @media (max-width:1200px) {{
            .v8-hero {{ grid-template-columns:1fr; }}
            .v8-mobile-goal {{ display:block; margin-bottom:9px; }}
        }}
    </style>
    <div class="v8-hero">
        <div class="v8-passport">{build_athlete_card_html(athlete_id)}{_v8_passport_overrides()}</div>
        <div class="v8-hero-right">
            <div class="v8-mobile-goal">{build_v8_goal_html(home_summary, mobile=True)}</div>
            {build_v8_intelligence_html(predictions, latest)}
        </div>
    </div>
    """


def _v8_lower_overrides() -> str:
    """Apply the shared readable scale to This Week, Up Next, and Best Runs."""
    return """
    <style>
        .v8-lower .home-panel,.v8-lower .br-section { border-radius:16px; box-shadow:0 12px 32px rgba(7,24,42,.085); }
        .v8-lower .home-week { padding:9px 10px 8px; }
        .v8-lower .home-week-head { margin:0 3px 6px; }
        .v8-lower .home-week-title,.v8-lower .br-headline { font-size:14px; letter-spacing:.09em; }
        .v8-lower .home-week-theme { font-size:11.5px; }
        .v8-lower .home-days { gap:6px; }
        .v8-lower .home-day { min-height:72px; padding:7px 8px; border-radius:10px; }
        .v8-lower .home-day-top { font-size:10px; letter-spacing:.09em; }
        .v8-lower .home-day-title { margin-top:6px; font-size:12.5px; line-height:1.12; }
        .v8-lower .home-day-detail { margin-top:3px; font-size:10.5px; line-height:1.22; }
        .v8-lower .home-next { margin:0 10px 10px; padding:8px 11px 8px 13px; }
        .v8-lower .home-next-kicker { font-size:10px; letter-spacing:.1em; }
        .v8-lower .home-next-title { margin-top:2px; font-size:17px; }
        .v8-lower .home-next-detail { margin-top:3px; max-width:none; font-size:11.5px; line-height:1.25; }
        .v8-lower .home-next-source { font-size:10px; }
        .v8-lower .home-next-timing { min-width:82px; padding:8px 10px; font-size:11.5px; }
        .v8-lower .br-section { margin-top:0; padding:9px 10px 10px; }
        .v8-lower .br-head { margin:0 3px 7px; }
        .v8-lower .br-link { font-size:10px; }
        .v8-lower .br-grid { gap:7px; }
        .v8-lower .br-main { min-height:132px; padding:8px 12px 7px; }
        .v8-lower .br-main-kicker { font-size:10.5px; }
        .v8-lower .br-main-date { font-size:10px; }
        .v8-lower .br-score-ribbon { width:42px; }
        .v8-lower .br-score-ribbon strong { font-size:14px; }
        .v8-lower .br-score-ribbon span { font-size:10px; letter-spacing:.03em; }
        .v8-lower .br-main-title { font-size:17px; }
        .v8-lower .br-main-activity { font-size:10.5px; }
        .v8-lower .br-main-stat strong { font-size:12px; }
        .v8-lower .br-main-stat span { font-size:10px; letter-spacing:.05em; }
        .v8-lower .br-context { font-size:10px; }
        .v8-lower .br-reason { font-size:10px; line-height:1.22; }
        .v8-lower .br-category-card { min-height:132px; padding:8px; }
        .v8-lower .br-category-name { font-size:12px; }
        .v8-lower .br-category-date { font-size:10px; }
        .v8-lower .br-category-activity { min-height:23px; font-size:10px; line-height:1.15; }
        .v8-lower .br-category-time { font-size:15px; }
        .v8-lower .br-category-meta { font-size:10px; line-height:1.2; }
        .v8-lower .br-category-score { font-size:10px; }
        .v8-lower .br-category-score strong { font-size:12px; }
        @media (max-width:1050px) {
            .v8-lower .home-days { grid-template-columns:repeat(4,minmax(0,1fr)); }
            .v8-lower .home-day { min-height:76px; }
        }
        @media (max-width:700px) {
            .v8-lower .home-days { grid-template-columns:repeat(2,minmax(0,1fr)); }
        }
    </style>
    """


def build_v8_lower_html(home_summary: HomeSummary, best_runs) -> str:
    """Render the weekly action layer and Hall of Fame at full width."""
    return f"""
    <style>
        .v8-lower {{ container-type:inline-size; display:grid; gap:9px; width:100%; }}
    </style>
    <div class="v8-lower">
        {v6.build_home_panel_html(home_summary, section="schedule")}
        {v6.build_best_runs_html(best_runs)}
        {_v8_lower_overrides()}
    </div>
    """


def show_home_preview_v8() -> None:
    st.markdown(
        """
        <style>
            [data-testid="stMainBlockContainer"] { max-width:1450px; padding-top:1.6rem; padding-bottom:3rem; }
            [data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"],
            [data-testid="stMainBlockContainer"] > div > [data-testid="stVerticalBlock"] { gap:9px; }
            [data-testid="stHeader"] { background:transparent; }
            .v8-preview-kicker { margin-bottom:0; color:#8a776a; font-size:.72rem; font-weight:800; letter-spacing:.12em; text-transform:uppercase; }
            [data-testid="stHorizontalBlock"]:has(.v8-selector-marker) { align-items:flex-start; gap:9px; }
            [data-testid="stElementContainer"]:has(.v8-selector-marker) { display:none; }
            [data-testid="stHorizontalBlock"]:has(.v8-selector-marker) [data-testid="stVerticalBlock"] { gap:0; }
            @media (max-width:1200px) {
                [data-testid="stHorizontalBlock"]:has(.v8-selector-marker) [data-testid="stColumn"]:last-child { display:none; }
                [data-testid="stHorizontalBlock"]:has(.v8-selector-marker) [data-testid="stColumn"]:first-child { flex:1 1 100%; width:100%; }
            }
        </style>
        <div class="v8-preview-kicker">Home preview · Experimental v8 density system</div>
        """,
        unsafe_allow_html=True,
    )

    selector_col, goal_col = st.columns([390, 1051], gap="small")
    with selector_col:
        st.markdown('<span class="v8-selector-marker"></span>', unsafe_allow_html=True)
        athlete_id = render_athlete_selector(
            key="home_preview_v8_athlete_selector",
            label="Athlete",
            label_visibility="collapsed",
        )

    if athlete_id is None:
        st.warning("No athletes found. Add an athlete first.")
        return

    home_summary = build_home_summary(athlete_id)
    with goal_col:
        st.html(build_v8_goal_html(home_summary))

    best_runs = build_home_best_runs(athlete_id)
    with st.spinner("Analysing real performance intelligence…"):
        predictions = v6._cached_home_predictions(athlete_id, v6.PREDICTIONS_CACHE_SCHEMA)
        predictions = v6._refresh_stale_predictions_contract(athlete_id, predictions)
        latest = v6._cached_home_latest_run(athlete_id)

    st.html(build_v8_hero_html(athlete_id, home_summary, predictions, latest))
    st.html(build_v8_lower_html(home_summary, best_runs))


if __name__ == "__main__":
    st.set_page_config(
        page_title="Performance Passport · Home v8 Preview",
        page_icon="P",
        layout="wide",
    )
    show_home_preview_v8()
