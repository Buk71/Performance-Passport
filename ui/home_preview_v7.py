"""Experimental Home v7 preview for Performance Passport.

Run with:
    streamlit run ui/home_preview_v7.py

This is deliberately separate from ``ui/home_preview.py``.  It reuses the
approved v6 data adapters and renderers, but tests a different information
hierarchy: identity and goal first, performance intelligence beside the
Passport, then the weekly plan and Hall of Fame.
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
        "race": "Race history and your current competitive ceiling.",
        "workout": "Quality sessions and the form you can repeat in training.",
        "threshold": "Sustainable pace and your strongest confidence anchor.",
    }.get(key, "An independent specialist view of current race form.")


def build_compact_goal_html(summary: HomeSummary, *, mobile: bool = False) -> str:
    """Render the desktop goal strip at selector height, or its mobile copy."""
    block_status = "Active block" if summary.block_is_saved else "Adaptive preview"
    placement = " v7-goal-mobile" if mobile else " v7-goal-desktop"

    return f"""
    <style>
        * {{ box-sizing:border-box; }}
        body {{ margin:0; }}
        .v7-goal-strip {{
            width:100%; height:38px; min-height:38px; padding:4px 11px;
            display:grid; grid-template-columns:minmax(170px,.78fr) minmax(180px,.88fr) minmax(250px,1.34fr);
            gap:12px; align-items:center; overflow:hidden;
            color:#0b2035; font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
            background:radial-gradient(circle at 98% 0%,rgba(241,90,36,.09),transparent 30%),#fffdf9;
            border:1px solid #ded8ce; border-radius:10px; box-shadow:0 8px 22px rgba(7,24,42,.08);
        }}
        .v7-goal-primary,.v7-goal-direction {{ min-width:0; display:flex; align-items:center; gap:7px; }}
        .v7-goal-label {{ color:#707b85; font-size:7px; font-weight:900; letter-spacing:.13em; text-transform:uppercase; white-space:nowrap; }}
        .v7-goal-name {{ overflow:hidden; font-size:14px; line-height:1; font-weight:900; letter-spacing:-.02em; text-overflow:ellipsis; white-space:nowrap; }}
        .v7-goal-target {{ flex:0 0 auto; color:#f15a24; font-size:11.5px; font-weight:900; white-space:nowrap; }}
        .v7-goal-context {{ overflow:hidden; color:#697680; font-size:9.5px; text-overflow:ellipsis; white-space:nowrap; }}
        .v7-goal-direction {{ padding-left:12px; border-left:1px solid #ddd6cc; }}
        .v7-goal-direction strong {{ overflow:hidden; color:#238a52; font-size:11.5px; text-overflow:ellipsis; white-space:nowrap; }}
        .v7-goal-direction span:last-child {{ overflow:hidden; color:#64727e; font-size:8.5px; text-overflow:ellipsis; white-space:nowrap; }}
        .v7-goal-status {{ flex:0 0 auto; padding:2px 6px; color:#287e51!important; font-size:6.5px!important; font-weight:900; letter-spacing:.06em; text-transform:uppercase; background:#e9f5ee; border-radius:999px; }}
        .v7-goal-mobile {{ display:none; }}
        @media (max-width:980px) {{
            .v7-goal-desktop {{ display:none; }}
            .v7-goal-mobile {{
                display:grid; height:auto; min-height:58px;
                grid-template-columns:1fr; gap:4px; padding:9px 12px;
            }}
            .v7-goal-primary {{ flex-wrap:wrap; }}
            .v7-goal-context {{ white-space:normal; }}
            .v7-goal-direction {{ padding:5px 0 0; border-top:1px solid #e5ded5; border-left:0; }}
        }}
    </style>
    <section class="v7-goal-strip{placement}">
        <div class="v7-goal-primary">
            <span class="v7-goal-label">Active goal</span>
            <strong class="v7-goal-name">{v6._safe(summary.goal_name)}</strong>
            <span class="v7-goal-target">{v6._safe(v6._clock(summary.target_time_s))}</span>
        </div>
        <div class="v7-goal-context">{v6._safe(summary.goal_context)}</div>
        <div class="v7-goal-direction">
            <span class="v7-goal-label">Direction</span>
            <strong>{v6._safe(summary.block_name)}</strong>
            <span>{v6._safe(summary.block_context)}</span>
            <span class="v7-goal-status">{v6._safe(block_status)}</span>
        </div>
    </section>
    """


def build_v7_intelligence_html(summary, latest) -> str:
    """Render balanced Latest Run, Coaches' View and Race Outlook panels."""
    if not summary.available:
        return f"""
        <div class="v7-rail">
            <section class="v7-intelligence v7-empty">
                <div class="v7-title">Performance Intelligence</div>
                <strong>Race capability is still building</strong>
                <span>{v6._safe(summary.explanation)}</span>
            </section>
        </div>
        """

    coaches = []
    for coach in getattr(summary, "coach_positions", ()):
        lead = '<span class="v7-lead">Lead</span>' if coach.is_lead else ""
        coaches.append(
            f"""
            <article class="v7-coach v7-{v6._safe(coach.position)}">
                <div class="v7-coach-head"><strong>{v6._safe(coach.title)}</strong>{lead}</div>
                <div class="v7-coach-time">{v6._safe(v6._clock(coach.predicted_seconds))}</div>
                <div class="v7-coach-stance">{v6._safe(coach.position.title())} view</div>
                <div class="v7-coach-copy">{v6._safe(_coach_evidence(coach.key))}</div>
                <div class="v7-confidence">{coach.confidence:.0%} confidence</div>
            </article>
            """
        )

    responses = []
    for response in getattr(summary, "environment_responses", ()):
        response_class = (
            "v7-response-edge"
            if response.confidence >= 0.25 and response.multiplier < 0.92
            else "v7-response-cost"
            if response.confidence >= 0.25 and response.multiplier > 1.08
            else "v7-response-neutral"
        )
        responses.append(
            f"""
            <span class="v7-response {response_class}">
                <b>{v6._environment_icon(response.key)} {v6._safe(response.label)}</b>
                {v6._safe(response.response_label)}
            </span>
            """
        )

    trait = getattr(summary, "performance_trait", None)
    trait_markup = (
        f"""
        <div class="v7-trait">
            <span>Your edge</span>
            <strong>{v6._safe(trait.title)}</strong>
            <em>{v6._safe(trait.detail)}</em>
        </div>
        """
        if trait is not None
        else """
        <div class="v7-trait v7-trait-building">
            <span>Your edge</span><strong>Still emerging</strong>
            <em>Comparable runs will reveal a reliable environmental strength.</em>
        </div>
        """
    )

    if latest.available:
        rank = (
            f"<strong>#{latest.rank}</strong><span>of {latest.comparison_count} {v6._safe(latest.category)}</span>"
            if latest.rank is not None and latest.comparison_count is not None
            else "<strong>—</strong><span>Rank building</span>"
        )
        conditions = (
            " · ".join(latest.environment_factors[:2])
            if latest.environment_factors
            else "Conditions recognised where data allows"
        )
        latest_markup = f"""
            <div class="v7-latest-head">
                <div><div class="v7-kicker">Latest run · {v6._safe(v6._format_date(latest.activity_date))}</div><h3>{v6._safe(latest.title)}</h3></div>
                <div class="v7-rank">{rank}</div>
            </div>
            <div class="v7-latest-win">{v6._safe(latest.headline)}</div>
            <div class="v7-latest-copy">{v6._safe(latest.explanation)}</div>
            <div class="v7-latest-stats">
                <span><b>{v6._safe(v6._distance_miles(latest.distance_km))}</b>Distance</span>
                <span><b>{v6._safe(v6._clock(latest.moving_time_s))}</b>Time</span>
                <span><b>{v6._safe(v6._pace_per_mile(latest.actual_pace_s_per_km))}</b>Pace</span>
                <span><b>{v6._safe(f'{latest.avg_hr:.0f} bpm' if latest.avg_hr is not None else '—')}</b>Avg HR</span>
            </div>
            <div class="v7-benefit"><span>What it gave you</span><strong>{v6._safe(latest.benefit)}</strong></div>
            <div class="v7-condition-note">{v6._safe(conditions)} · {latest.confidence:.0%} evidence confidence</div>
        """
    else:
        latest_markup = f"""
            <div class="v7-kicker">Latest run</div><h3>{v6._safe(latest.title)}</h3>
            <div class="v7-latest-copy">{v6._safe(latest.explanation)}</div>
        """

    scenarios = []
    for scenario in summary.scenarios:
        personal = '<span class="v7-personal">Personal</span>' if scenario.personalised else ""
        scenarios.append(
            f"""
            <article class="v7-scenario v7-scenario-{v6._safe(scenario.key)}">
                <div class="v7-scenario-head"><strong>{v6._safe(scenario.label)}</strong>{personal}</div>
                <div class="v7-scenario-time">{v6._safe(v6._clock(scenario.central_seconds))}</div>
                <div class="v7-scenario-copy">{v6._safe(scenario.description)}</div>
                <div class="v7-scenario-meta">{v6._safe(v6._pace_per_mile(scenario.pace_seconds_per_km))}<span>{scenario.confidence:.0%}</span></div>
            </article>
            """
        )

    probability = f"{summary.target_probability:.0%}" if summary.target_probability is not None else "—"
    status = {
        "aligned": "Closely aligned", "balanced": "Broadly aligned",
        "mixed": "Mixed signals", "developing": "Developing", "building": "Building",
    }.get(summary.consensus_status, summary.consensus_status)

    return f"""
    <style>
        * {{ box-sizing:border-box; }}
        body {{ margin:0; }}
        .v7-rail {{ height:100%; min-width:0; display:grid; grid-template-rows:minmax(0,1fr) auto; gap:10px; color:#0b2035; font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
        .v7-intelligence,.v7-outlook {{ min-width:0; overflow:hidden; background:radial-gradient(circle at 100% 100%,rgba(241,90,36,.07),transparent 24%),#fffdf9; border:1px solid #ded8ce; border-radius:16px; box-shadow:0 14px 36px rgba(7,24,42,.09); }}
        .v7-intelligence {{ height:100%; padding:10px 11px 11px; display:flex; flex-direction:column; }}
        .v7-head,.v7-panel-head {{ display:flex; align-items:center; justify-content:space-between; gap:10px; }}
        .v7-head {{ margin:0 2px 8px; }}
        .v7-title {{ font-size:13px; font-weight:900; letter-spacing:.1em; text-transform:uppercase; }}
        .v7-title span {{ color:#77818b; font-weight:700; }}
        .v7-link {{ color:#526371; font-size:8.5px; font-weight:850; letter-spacing:.07em; text-transform:uppercase; white-space:nowrap; }}
        .v7-intelligence-grid {{ flex:1 1 auto; display:grid; grid-template-columns:minmax(320px,.84fr) minmax(510px,1.16fr); gap:9px; }}
        .v7-panel {{ min-width:0; padding:10px 11px; border-radius:12px; }}
        .v7-latest {{ background:#f7f5f0; border:1px solid #ded8ce; }}
        .v7-latest-head {{ display:flex; justify-content:space-between; align-items:flex-start; gap:10px; }}
        .v7-kicker {{ color:#6b7781; font-size:8.5px; font-weight:900; letter-spacing:.11em; text-transform:uppercase; }}
        .v7-latest h3 {{ margin:4px 0 0; font-size:19px; line-height:1.05; letter-spacing:-.025em; }}
        .v7-rank {{ flex:0 0 auto; min-width:70px; padding:5px 7px; text-align:right; background:#fffdf9; border:1px solid #ded8ce; border-radius:8px; }}
        .v7-rank strong {{ display:block; color:#238a52; font-size:18px; line-height:1; }}
        .v7-rank span {{ display:block; margin-top:2px; color:#687681; font-size:7.5px; }}
        .v7-latest-win {{ margin-top:7px; font-size:15px; line-height:1.1; font-weight:900; }}
        .v7-latest-copy {{ margin-top:4px; color:#566672; font-size:11px; line-height:1.32; }}
        .v7-latest-stats {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:6px; margin-top:8px; }}
        .v7-latest-stats span {{ min-width:0; color:#73808a; font-size:7.5px; text-transform:uppercase; }}
        .v7-latest-stats b {{ display:block; overflow:hidden; color:#0b2035; font-size:11.5px; text-transform:none; text-overflow:ellipsis; white-space:nowrap; }}
        .v7-benefit {{ display:grid; grid-template-columns:auto minmax(0,1fr); align-items:center; gap:9px; margin-top:8px; padding:7px 9px; background:#fff3e9; border-left:3px solid #f15a24; border-radius:7px; }}
        .v7-benefit span {{ color:#d94b17; font-size:7px; font-weight:900; letter-spacing:.08em; text-transform:uppercase; }}
        .v7-benefit strong {{ font-size:10.5px; line-height:1.28; }}
        .v7-condition-note {{ margin-top:6px; color:#77838d; font-size:8.5px; line-height:1.22; }}
        .v7-coaches {{ color:#fff; background:radial-gradient(circle at 100% 0%,rgba(35,138,82,.24),transparent 34%),linear-gradient(145deg,#07182a,#0d2b47); border:1px solid #173d5e; }}
        .v7-panel-title {{ font-size:12.5px; font-weight:900; letter-spacing:.09em; text-transform:uppercase; }}
        .v7-status {{ padding:3px 7px; color:#bde8cf; font-size:7px; font-weight:900; letter-spacing:.07em; text-transform:uppercase; background:rgba(35,138,82,.22); border-radius:999px; }}
        .v7-coaches-intro {{ margin-top:5px; color:#c8d4de; font-size:11px; line-height:1.3; }}
        .v7-coach-grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:6px; margin-top:8px; }}
        .v7-coach {{ min-width:0; padding:7px 8px; color:#0b2035; background:#fffdf9; border-radius:9px; border-top:3px solid #9aa5ad; }}
        .v7-coach.v7-optimistic {{ border-top-color:#238a52; }} .v7-coach.v7-cautious {{ border-top-color:#f15a24; }}
        .v7-coach-head {{ display:flex; align-items:center; gap:4px; min-width:0; }}
        .v7-coach-head strong {{ overflow:hidden; font-size:10.5px; text-overflow:ellipsis; white-space:nowrap; }}
        .v7-lead {{ margin-left:auto; padding:2px 5px; color:#fff; font-size:6px; font-weight:900; text-transform:uppercase; background:#f15a24; border-radius:999px; }}
        .v7-coach-time {{ margin-top:4px; font-size:21px; line-height:1; font-weight:900; letter-spacing:-.03em; }}
        .v7-coach-stance {{ margin-top:3px; color:#536572; font-size:9px; font-weight:800; }}
        .v7-coach-copy {{ min-height:25px; margin-top:3px; color:#536572; font-size:9px; line-height:1.28; }}
        .v7-confidence {{ margin-top:3px; color:#71808b; font-size:8.5px; font-weight:750; }}
        .v7-coach-footer {{ display:grid; grid-template-columns:minmax(210px,.8fr) minmax(0,1.2fr); gap:7px; margin-top:7px; }}
        .v7-trait {{ display:grid; grid-template-columns:auto 1fr; column-gap:7px; align-items:center; padding:6px 8px; color:#0b2035; background:linear-gradient(135deg,#ffe2a8,#fff4d9); border:1px solid #e5b85e; border-radius:8px; }}
        .v7-trait span {{ grid-row:1/3; color:#a55a0b; font-size:7px; font-weight:900; letter-spacing:.08em; text-transform:uppercase; }}
        .v7-trait strong {{ font-size:12px; line-height:1; }}
        .v7-trait em {{ overflow:hidden; color:#785f3e; font-size:8px; font-style:normal; text-overflow:ellipsis; white-space:nowrap; }}
        .v7-responses {{ display:flex; align-items:stretch; gap:5px; min-width:0; }}
        .v7-response {{ flex:1 1 0; min-width:0; padding:5px 6px; color:#c9d4de; font-size:7.5px; line-height:1.15; text-align:center; background:rgba(255,255,255,.07); border:1px solid rgba(255,255,255,.10); border-radius:7px; }}
        .v7-response b {{ display:block; margin-bottom:2px; color:#fff; font-size:8.5px; }}
        .v7-response-edge b {{ color:#9fe0ba; }} .v7-response-cost b {{ color:#ffb294; }}
        .v7-outlook {{ padding:9px 10px 10px; background:#f7f5f0; }}
        .v7-outlook-grid {{ display:grid; grid-template-columns:minmax(200px,1.05fr) repeat(5,minmax(94px,1fr)); gap:6px; margin-top:7px; }}
        .v7-capability,.v7-scenario {{ min-width:0; padding:7px 8px; background:#fffdf9; border:1px solid #e1dbd2; border-radius:9px; }}
        .v7-capability-range {{ margin-top:4px; font-size:20px; line-height:1; font-weight:900; letter-spacing:-.03em; white-space:nowrap; }}
        .v7-capability-central {{ margin-top:4px; color:#d94b17; font-size:9.5px; font-weight:850; }}
        .v7-capability-goal {{ display:flex; flex-wrap:wrap; gap:3px 9px; margin-top:5px; color:#65737f; font-size:8px; }}
        .v7-capability-goal b {{ color:#0b2035; font-size:9.5px; }}
        .v7-scenario-ideal {{ background:linear-gradient(160deg,#fff5e6,#fffdf9); border-color:#efc18c; }}
        .v7-scenario-typical {{ background:linear-gradient(160deg,#eef8f2,#fffdf9); border-color:#bfddca; }}
        .v7-scenario-head {{ display:flex; align-items:center; gap:4px; }}
        .v7-scenario-head strong {{ overflow:hidden; font-size:10.5px; text-overflow:ellipsis; white-space:nowrap; }}
        .v7-personal {{ margin-left:auto; padding:1px 4px; color:#287e51; font-size:5.5px; font-weight:900; text-transform:uppercase; background:#e6f4ec; border-radius:999px; }}
        .v7-scenario-time {{ margin-top:4px; font-size:18px; line-height:1; font-weight:900; letter-spacing:-.025em; }}
        .v7-scenario-copy {{ min-height:22px; margin-top:4px; color:#61707b; font-size:8.5px; line-height:1.22; }}
        .v7-scenario-meta {{ margin-top:4px; color:#697681; font-size:8.5px; }} .v7-scenario-meta span {{ float:right; font-weight:850; }}
        .v7-empty {{ padding:20px; }} .v7-empty strong,.v7-empty span {{ display:block; margin-top:5px; }}
        @container (max-width:1000px) {{
            .v7-intelligence-grid {{ grid-template-columns:1fr; }}
            .v7-outlook-grid {{ grid-template-columns:repeat(3,minmax(0,1fr)); }}
            .v7-capability {{ grid-column:1/-1; }}
        }}
        @container (max-width:620px) {{
            .v7-intelligence {{ padding:8px; }} .v7-coach-grid {{ grid-template-columns:1fr; }}
            .v7-coach-copy {{ min-height:0; }} .v7-coach-footer {{ grid-template-columns:1fr; }}
            .v7-outlook-grid {{ grid-template-columns:repeat(2,minmax(0,1fr)); }}
            .v7-latest-stats {{ grid-template-columns:repeat(2,minmax(0,1fr)); }}
        }}
        @container (max-width:360px) {{ .v7-outlook-grid {{ grid-template-columns:1fr; }} .v7-capability {{ grid-column:auto; }} .v7-responses {{ flex-direction:column; }} }}
    </style>
    <div class="v7-rail">
        <section class="v7-intelligence">
            <div class="v7-head">
                <div class="v7-title">Performance Intelligence <span>· {v6._safe(summary.distance_label)} · {v6._safe(summary.goal_name)}</span></div>
                <div class="v7-link">View full analysis &nbsp;→</div>
            </div>
            <div class="v7-intelligence-grid">
                <article class="v7-panel v7-latest">{latest_markup}</article>
                <article class="v7-panel v7-coaches">
                    <div class="v7-panel-head"><div class="v7-panel-title">Coaches’ View</div><span class="v7-status">{v6._safe(status)}</span></div>
                    <div class="v7-coaches-intro">{v6._safe(summary.consensus_headline)}</div>
                    <div class="v7-coach-grid">{''.join(coaches)}</div>
                    <div class="v7-coach-footer">{trait_markup}<div class="v7-responses">{''.join(responses)}</div></div>
                </article>
            </div>
        </section>
        <section class="v7-outlook">
            <div class="v7-panel-head"><div class="v7-panel-title">Race Outlook</div><span class="v7-kicker">Capability → race conditions</span></div>
            <div class="v7-outlook-grid">
                <div class="v7-capability">
                    <div class="v7-kicker">Current capability</div>
                    <div class="v7-capability-range">{v6._safe(v6._clock(summary.low_seconds))}–{v6._safe(v6._clock(summary.high_seconds))}</div>
                    <div class="v7-capability-central">{v6._safe(v6._clock(summary.central_seconds))} central · {summary.confidence:.0%}</div>
                    <div class="v7-capability-goal"><span><b>{v6._safe(v6._clock(summary.target_seconds))}</b> goal</span><span><b>{v6._safe(probability)}</b> likelihood</span><span>{v6._safe(v6._signed_gap(summary.target_gap_seconds))}</span></div>
                </div>
                {''.join(scenarios)}
            </div>
        </section>
    </div>
    """


def build_v7_hero_html(athlete_id: int, home_summary: HomeSummary, predictions, latest) -> str:
    """Place Passport and intelligence in one row with natural bottom alignment."""
    return f"""
    <style>
        .v7-hero {{ container-type:inline-size; display:grid; grid-template-columns:minmax(0,370px) minmax(0,1fr); gap:10px; align-items:stretch; width:100%; }}
        .v7-passport,.v7-hero-right {{ min-width:0; }}
        .v7-hero-right {{ container-type:inline-size; }}
        .v7-passport .pp-shell {{ width:100%; max-width:370px; margin:0; }}
        .v7-mobile-goal {{ display:none; }}
        @media (min-width:981px) {{
            .v7-passport .pp-top {{ grid-template-columns:minmax(0,1.08fr) minmax(150px,.92fr); min-height:210px; }}
            .v7-passport .pp-identity {{ padding:15px 12px 15px 17px; }}
            .v7-passport .pp-logo {{ width:118px; height:54px; margin-bottom:6px; }}
            .v7-passport .pp-eyebrow {{ font-size:9.5px; }} .v7-passport .pp-name {{ font-size:27px; }} .v7-passport .pp-category {{ font-size:10.5px; }}
            .v7-passport .pp-motto {{ margin-top:12px; font-size:10.5px; line-height:1.34; }}
            .v7-passport .pp-photo-wrap,.v7-passport .pp-photo-placeholder {{ min-height:210px; }}
            .v7-passport .pp-panel {{ padding:13px 11px 12px; }} .v7-passport .pp-section-title {{ margin-bottom:9px; font-size:8.5px; }}
            .v7-passport .pp-grade-value {{ font-size:22px; }} .v7-passport .pp-grade-label {{ font-size:7.5px; }}
            .v7-passport .pb-header {{ font-size:7.5px; }} .v7-passport .pb-event {{ font-size:9.5px; }} .v7-passport .pb-row {{ min-height:26px; }} .v7-passport .pb-time {{ font-size:11.5px; }}
            .v7-passport .pp-development {{ padding:10px 14px 7px; }} .v7-passport .development-copy {{ font-size:9.5px; }} .v7-passport .development-score span {{ font-size:7.5px; }}
            .v7-passport .chart {{ height:30px; margin-top:4px; }}
        }}
        @media (max-width:980px) {{
            .v7-hero {{ grid-template-columns:1fr; gap:10px; }}
            .v7-passport .pp-shell {{ max-width:460px; margin:0 auto; }}
            .v7-mobile-goal {{ display:block; }}
            .v7-hero-right .v7-rail {{ height:auto; margin-top:10px; }}
        }}
    </style>
    <div class="v7-hero">
        <div class="v7-passport">{build_athlete_card_html(athlete_id)}</div>
        <div class="v7-hero-right">
            <div class="v7-mobile-goal">{build_compact_goal_html(home_summary, mobile=True)}</div>
            {build_v7_intelligence_html(predictions, latest)}
        </div>
    </div>
    """


def build_v7_lower_html(home_summary: HomeSummary, best_runs) -> str:
    """Render the action layer before historical recognition."""
    return f"""
    <style>
        .v7-lower {{ container-type:inline-size; display:grid; gap:10px; width:100%; margin-top:0; }}
        .v7-lower .br-section {{ margin-top:0; }}
    </style>
    <div class="v7-lower">
        {v6.build_home_panel_html(home_summary, section="schedule")}
        {v6.build_best_runs_html(best_runs)}
    </div>
    """


def show_home_preview_v7() -> None:
    st.markdown(
        """
        <style>
            [data-testid="stMainBlockContainer"] { max-width:1450px; padding-top:2rem; padding-bottom:3rem; }
            [data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"],
            [data-testid="stMainBlockContainer"] > div > [data-testid="stVerticalBlock"] { gap:10px; }
            [data-testid="stHeader"] { background:transparent; }
            .v7-preview-kicker { margin-bottom:0; color:#8a776a; font-size:.68rem; font-weight:800; letter-spacing:.14em; text-transform:uppercase; }
            [data-testid="stHorizontalBlock"]:has(.v7-selector-marker) { align-items:flex-start; gap:10px; }
            [data-testid="stElementContainer"]:has(.v7-selector-marker) { display:none; }
            [data-testid="stHorizontalBlock"]:has(.v7-selector-marker) [data-testid="stVerticalBlock"] { gap:0; }
            @media (max-width:980px) {
                [data-testid="stHorizontalBlock"]:has(.v7-selector-marker) { flex-wrap:wrap; }
                [data-testid="stHorizontalBlock"]:has(.v7-selector-marker) [data-testid="stColumn"] { flex:1 1 100%; width:100%; }
                [data-testid="stColumn"]:has(.v7-goal-desktop) { display:none; }
            }
        </style>
        <div class="v7-preview-kicker">Home preview · Experimental v7 hierarchy</div>
        """,
        unsafe_allow_html=True,
    )

    selector_col, goal_col = st.columns([370, 1066], gap="small")
    with selector_col:
        st.markdown('<span class="v7-selector-marker"></span>', unsafe_allow_html=True)
        athlete_id = render_athlete_selector(
            key="home_preview_v7_athlete_selector",
            label="Athlete",
            label_visibility="collapsed",
        )

    if athlete_id is None:
        st.warning("No athletes found. Add an athlete first.")
        return

    home_summary = build_home_summary(athlete_id)
    with goal_col:
        st.html(build_compact_goal_html(home_summary))

    best_runs = build_home_best_runs(athlete_id)
    with st.spinner("Analysing real performance intelligence…"):
        predictions = v6._cached_home_predictions(athlete_id, v6.PREDICTIONS_CACHE_SCHEMA)
        predictions = v6._refresh_stale_predictions_contract(athlete_id, predictions)
        latest = v6._cached_home_latest_run(athlete_id)

    st.html(build_v7_hero_html(athlete_id, home_summary, predictions, latest))
    st.html(build_v7_lower_html(home_summary, best_runs))


if __name__ == "__main__":
    st.set_page_config(
        page_title="Performance Passport · Home v7 Preview",
        page_icon="P",
        layout="wide",
    )
    show_home_preview_v7()
