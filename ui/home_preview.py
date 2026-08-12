"""Standalone preview for Performance Passport Home — Phase 3.

Run with:
    streamlit run ui/home_preview.py

This preview does not replace the existing Coach page. It combines the locked
Athlete Passport with real-data weekly coaching, Best Runs and Race Predictions.
"""

from __future__ import annotations

import datetime
import html
import importlib
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from core.home_summary import HomeSummary, build_home_summary
from core.home_best_runs import HomeBestRuns, build_home_best_runs
from core.home_latest_run import HomeLatestRun, build_home_latest_run
from core.home_predictions import HomePredictions, build_home_predictions
from ui.athlete_card import build_athlete_card_html
from ui.athlete_selection import render_athlete_selector


PREDICTIONS_CACHE_SCHEMA = 4


def _safe(value) -> str:
    return html.escape(str(value or ""))


def _clock(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    total = int(round(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, remaining = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{remaining:02d}"
    return f"{minutes}:{remaining:02d}"


def _session_label(family: str, title: str) -> str:
    labels = {
        "completed": "Completed",
        "easy": "Easy",
        "recovery": "Recovery",
        "endurance": "Long Run",
        "long": "Long Run",
        "threshold": "Threshold",
        "vo2": "VO₂",
        "speed": "Speed",
        "race_pace": "Race Pace",
        "rest": "Rest",
    }
    return labels.get(
        str(family or "").lower(),
        str(title or family or "Run").replace("_", " ").title(),
    )


def _compact_detail(value: str, limit: int = 52) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _format_date(value: str | None) -> str:
    if not value:
        return "Date unavailable"
    try:
        parsed = datetime.date.fromisoformat(str(value)[:10])
        return parsed.strftime("%-d %b %Y")
    except (TypeError, ValueError):
        return str(value)


def _pace_per_mile(seconds_per_km: float | None) -> str:
    if seconds_per_km is None:
        return "—"
    seconds = int(round(float(seconds_per_km) * 1.609344))
    return f"{seconds // 60}:{seconds % 60:02d}/mi"


def _distance_miles(distance_km: float | None) -> str:
    if distance_km is None:
        return "—"
    return f"{float(distance_km) / 1.609344:.1f} mi"


def _signed_gap(seconds: float | None) -> str:
    if seconds is None:
        return "Target gap building"
    value = int(round(abs(seconds)))
    clock = f"{value // 60}:{value % 60:02d}"
    if seconds <= 0:
        return f"{clock} inside target"
    return f"+{clock} to target"


def _prediction_icon(key: str) -> str:
    common = (
        'viewBox="0 0 24 24" aria-hidden="true" '
        'fill="none" stroke="currentColor" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round"'
    )
    paths = {
        "ideal": (
            '<path d="M12 2v20M4.9 4.9l14.2 14.2M2 12h20M4.9 19.1 19.1 4.9"/>'
            '<circle cx="12" cy="12" r="3"/>'
        ),
        "typical": (
            '<path d="M7 16.5h10a4 4 0 0 0 .5-8 5.5 5.5 0 0 0-10.6 1.7A3.2 3.2 0 0 0 7 16.5Z"/>'
            '<path d="M5 20h10M18 20h1"/>'
        ),
        "warm": (
            '<circle cx="12" cy="12" r="4"/>'
            '<path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>'
        ),
        "hilly": (
            '<path d="m3 19 6.2-10 3.2 4.3L15 9l6 10H3Z"/>'
            '<path d="m7.4 12 1.8 1.3 1.7-1.8"/>'
        ),
        "windy": (
            '<path d="M3 8h11c2.7 0 2.7-4 0-4-1.2 0-2 .7-2.2 1.5"/>'
            '<path d="M3 12h16c2.7 0 2.7 4 0 4-1.2 0-2-.7-2.2-1.5M3 16h8"/>'
        ),
    }
    return f'<svg {common}>{paths.get(key, paths["ideal"])}</svg>'


@st.cache_data(ttl=300, show_spinner=False)
def _cached_home_predictions(
    athlete_id: int,
    cache_schema: int,
) -> HomePredictions:
    """Cache predictions without reusing an older result contract."""
    _ = cache_schema
    return build_home_predictions(athlete_id)


@st.cache_data(ttl=300, show_spinner=False)
def _cached_home_latest_run(athlete_id: int) -> HomeLatestRun:
    return build_home_latest_run(athlete_id)


def _refresh_stale_predictions_contract(
    athlete_id: int,
    summary: HomePredictions,
) -> HomePredictions:
    """Rebuild once when Streamlit is still holding the pre-coaches object.

    Streamlit reruns the preview file but can retain an already imported core
    module in the same Python process.  That leaves the renderer with the old
    HomePredictions contract even after all replacement files are installed.
    Reloading only on a detected mismatch makes upgrades self-healing without
    adding work to normal page loads.
    """
    if (
        hasattr(summary, "coach_positions")
        and hasattr(summary, "environment_responses")
        and hasattr(summary, "performance_trait")
    ):
        return summary

    from core import home_predictions as predictions_module

    refreshed_module = importlib.reload(predictions_module)
    return refreshed_module.build_home_predictions(athlete_id)


def build_race_predictions_html(summary: HomePredictions) -> str:
    if not summary.available:
        return f"""
        <section class="rp-section rp-empty">
            <div class="rp-kicker">Predictions · {_safe(summary.distance_label)}</div>
            <div class="rp-empty-title">Race capability is still building</div>
            <div class="rp-empty-copy">{_safe(summary.explanation)}</div>
        </section>
        """

    scenario_cards = []
    for scenario in summary.scenarios:
        classes = ["rp-scenario", f"scenario-{scenario.key}"]
        if scenario.personalised:
            classes.append("personalised")
        personal_mark = (
            '<span class="rp-personal">Personal</span>'
            if scenario.personalised
            else ""
        )
        scenario_cards.append(
            f"""
            <article class="{' '.join(classes)}">
                <div class="rp-scenario-top">
                    <span class="rp-scenario-icon">{_prediction_icon(scenario.key)}</span>
                    <span class="rp-scenario-label">{_safe(scenario.label)}</span>
                    {personal_mark}
                </div>
                <div class="rp-scenario-reading">
                    <strong>{_safe(_clock(scenario.central_seconds))}</strong>
                    <span>{_safe(_pace_per_mile(scenario.pace_seconds_per_km))}</span>
                </div>
                <div class="rp-scenario-range">
                    {_safe(_clock(scenario.low_seconds))}–{_safe(_clock(scenario.high_seconds))}
                    <span>{scenario.confidence:.0%}</span>
                </div>
            </article>
            """
        )

    coach_cards = []
    for coach in getattr(summary, "coach_positions", ()):
        lead_mark = (
            '<span class="rp-coach-lead">Lead</span>'
            if coach.is_lead
            else ""
        )
        coach_cards.append(
            f"""
            <article class="rp-coach rp-coach-{_safe(coach.position)}">
                <div class="rp-coach-top">
                    <span class="rp-coach-name">{_safe(coach.title)}</span>
                    {lead_mark}
                </div>
                <div class="rp-coach-reading">
                    <strong>{_safe(_clock(coach.predicted_seconds))}</strong>
                    <span>{_safe(coach.position.title())}</span>
                </div>
                <div class="rp-coach-confidence">{coach.confidence:.0%} confidence</div>
            </article>
            """
        )

    probability = (
        f"{summary.target_probability:.0%}"
        if summary.target_probability is not None
        else "—"
    )
    target = _clock(summary.target_seconds)
    strongest = summary.strongest_system or "Still resolving"
    limiting = summary.limiting_system or "Still resolving"
    status_label = {
        "aligned": "Closely aligned",
        "balanced": "Broadly aligned",
        "mixed": "Mixed signals",
        "developing": "Developing",
        "building": "Building",
    }.get(summary.consensus_status, summary.consensus_status)

    return f"""
    <style>
        * {{ box-sizing: border-box; }}
        .rp-section {{
            container-type: inline-size;
            width: 100%;
            margin-top: 14px;
            padding: 10px 11px 11px;
            overflow: hidden;
            color: #0b2035;
            font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            background:
                radial-gradient(circle at 100% 100%, rgba(241,90,36,.07), transparent 24%),
                #fffdf9;
            border: 1px solid #ded8ce;
            border-radius: 18px;
            box-shadow: 0 18px 46px rgba(7,24,42,.10);
        }}
        .rp-head {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 14px;
            margin: 0 2px 8px;
        }}
        .rp-title {{
            font-size: 12.5px;
            font-weight: 900;
            letter-spacing: .11em;
            text-transform: uppercase;
        }}
        .rp-title span {{ color: #77818b; font-weight: 700; }}
        .rp-link {{
            color: #455666;
            font-size: 9px;
            font-weight: 850;
            letter-spacing: .08em;
            text-transform: uppercase;
            white-space: nowrap;
        }}
        .rp-panels {{
            display: grid;
            grid-template-columns: minmax(440px, .95fr) minmax(600px, 1.25fr);
            gap: 9px;
        }}
        .rp-panel {{
            min-width: 0;
            padding: 10px;
            border-radius: 13px;
        }}
        .rp-panel-head {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
            margin-bottom: 7px;
        }}
        .rp-panel-title {{
            font-size: 12px;
            font-weight: 900;
            letter-spacing: .09em;
            text-transform: uppercase;
        }}
        .rp-coaches {{
            color: #fff;
            background:
                radial-gradient(circle at 100% 0%, rgba(35,138,82,.24), transparent 35%),
                linear-gradient(145deg, #07182a, #0d2b47);
            border: 1px solid #173d5e;
            box-shadow: 0 10px 24px rgba(7,24,42,.16);
        }}
        .rp-coaches-status {{
            padding: 3px 7px;
            color: #bde8cf;
            font-size: 7px;
            font-weight: 900;
            letter-spacing: .08em;
            text-transform: uppercase;
            background: rgba(35,138,82,.22);
            border-radius: 999px;
        }}
        .rp-coaches-copy {{
            overflow: hidden;
            margin-bottom: 8px;
            color: #c4d0db;
            font-size: 10.5px;
            line-height: 1.25;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        .rp-coach-grid {{
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 6px;
        }}
        .rp-coach {{
            min-width: 0;
            padding: 8px 9px 7px;
            color: #0b2035;
            background: #fffdf9;
            border: 1px solid rgba(255,255,255,.28);
            border-radius: 9px;
        }}
        .rp-coach-top {{ display: flex; align-items: center; gap: 5px; min-width: 0; }}
        .rp-coach-name {{
            overflow: hidden;
            font-size: 10.5px;
            font-weight: 900;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        .rp-coach-lead {{
            margin-left: auto;
            padding: 2px 5px;
            color: #fff;
            font-size: 6px;
            font-weight: 900;
            letter-spacing: .07em;
            text-transform: uppercase;
            background: #f15a24;
            border-radius: 999px;
        }}
        .rp-coach-reading {{
            display: flex;
            align-items: baseline;
            justify-content: space-between;
            gap: 5px;
            margin-top: 5px;
        }}
        .rp-coach-reading strong {{ font-size: 25px; line-height: .95; letter-spacing: -.035em; }}
        .rp-coach-reading span {{
            overflow: hidden;
            color: #61707c;
            font-size: 8px;
            font-weight: 750;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        .rp-coach-confidence {{
            margin-top: 4px;
            color: #687783;
            font-size: 8px;
            font-weight: 750;
        }}
        .rp-coach-optimistic {{ border-top: 3px solid #238a52; }}
        .rp-coach-aligned {{ border-top: 3px solid #9aa5ad; }}
        .rp-coach-cautious {{ border-top: 3px solid #f15a24; }}
        .rp-coaches-signals {{
            margin-top: 7px;
            color: #aebdcc;
            font-size: 9px;
        }}
        .rp-coaches-signals strong {{ color: #fff; }}
        .rp-coaches-signals .focus {{ color: #f9a27f; }}
        .rp-outlook {{
            background: #f7f5f0;
            border: 1px solid #ded8ce;
        }}
        .rp-capability {{
            display: grid;
            grid-template-columns: minmax(205px, 1.25fr) repeat(2, minmax(72px, .45fr)) minmax(130px, .7fr);
            align-items: center;
            gap: 10px;
            min-width: 0;
            padding: 0 1px 8px;
            border-bottom: 1px solid #ddd7cd;
        }}
        .rp-cap-kicker {{
            color: #6b7781;
            font-size: 7.5px;
            font-weight: 900;
            letter-spacing: .13em;
            text-transform: uppercase;
        }}
        .rp-cap-range {{
            margin-top: 4px;
            font-size: clamp(23px, 1.75vw, 29px);
            line-height: 1;
            font-weight: 900;
            letter-spacing: -.04em;
            white-space: nowrap;
        }}
        .rp-cap-central {{
            margin-top: 4px;
            color: #d94b17;
            font-size: 9px;
            font-weight: 850;
        }}
        .rp-stat {{ padding-left: 9px; border-left: 1px solid #ddd7cd; }}
        .rp-stat strong {{ display: block; font-size: 17px; line-height: 1; }}
        .rp-stat span {{
            display: block;
            margin-top: 4px;
            color: #6c7882;
            font-size: 7.5px;
            font-weight: 850;
            letter-spacing: .09em;
            text-transform: uppercase;
        }}
        .rp-gap {{ color: #66737e; font-size: 8.5px; line-height: 1.25; }}
        .rp-scenarios {{
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: 6px;
            margin-top: 8px;
        }}
        .rp-scenario {{
            min-width: 0;
            padding: 7px 8px;
            background: rgba(255,255,255,.82);
            border: 1px solid #e4dfd7;
            border-radius: 9px;
        }}
        .rp-scenario.scenario-ideal {{
            background: linear-gradient(160deg, #fff5e6, #fffdf9);
            border-color: #efc18c;
        }}
        .rp-scenario.scenario-typical {{
            background: linear-gradient(160deg, #eef8f2, #fffdf9);
            border-color: #bfddca;
        }}
        .rp-scenario-top {{
            display: flex;
            align-items: center;
            min-width: 0;
            gap: 4px;
        }}
        .rp-scenario-icon {{ width: 13px; height: 13px; color: #687582; flex: 0 0 auto; }}
        .scenario-ideal .rp-scenario-icon {{ color: #f15a24; }}
        .scenario-typical .rp-scenario-icon {{ color: #238a52; }}
        .rp-scenario-icon svg {{ display: block; width: 100%; height: 100%; }}
        .rp-scenario-label {{
            min-width: 0;
            overflow: hidden;
            font-size: 10.5px;
            font-weight: 900;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        .rp-personal {{
            margin-left: auto;
            padding: 1px 4px;
            color: #287e51;
            font-size: 5.5px;
            font-weight: 900;
            letter-spacing: .06em;
            text-transform: uppercase;
            background: #e6f4ec;
            border-radius: 999px;
        }}
        .rp-scenario-reading {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 5px;
            margin-top: 4px;
        }}
        .rp-scenario-reading strong {{
            font-size: clamp(20px, 1.45vw, 24px);
            line-height: 1;
            letter-spacing: -.035em;
        }}
        .rp-scenario-reading span {{ color: #61707b; font-size: 7.5px; white-space: nowrap; }}
        .rp-scenario-range {{ margin-top: 4px; color: #697681; font-size: 7.5px; white-space: nowrap; }}
        .rp-scenario-range span {{ float: right; font-weight: 850; }}
        .rp-empty {{ padding: 24px; text-align: center; }}
        .rp-kicker {{ color: #7d8791; font-size: 9px; font-weight: 850; text-transform: uppercase; }}
        .rp-empty-title {{ margin-top: 5px; font-size: 18px; font-weight: 850; }}
        .rp-empty-copy {{ margin-top: 4px; color: #6f7984; font-size: 11px; }}

        @container (max-width: 1120px) {{
            .rp-panels {{ grid-template-columns: 1fr; }}
            .rp-capability {{
                grid-template-columns: minmax(205px, 1.25fr) repeat(2, minmax(80px, .45fr)) minmax(160px, .8fr);
            }}
        }}
        @container (max-width: 620px) {{
            .rp-section {{ padding: 8px; }}
            .rp-capability {{ grid-template-columns: 1fr 1fr; }}
            .rp-capability-main {{ grid-column: 1 / -1; }}
            .rp-gap {{ grid-column: 1 / -1; }}
            .rp-coach-grid {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
            .rp-scenarios {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
            .rp-coach-reading {{ display: block; }}
            .rp-coach-reading strong {{ font-size: 19px; }}
            .rp-coach-reading span {{ display: block; margin-top: 3px; }}
            .rp-coach-confidence {{ font-size: 7px; }}
        }}
        @container (max-width: 360px) {{
            .rp-head {{ align-items: flex-start; }}
            .rp-link {{ display: none; }}
            .rp-coach-grid {{ grid-template-columns: 1fr; }}
            .rp-coach-reading {{ display: flex; }}
            .rp-scenarios {{ grid-template-columns: 1fr; }}
        }}
    </style>

    <section class="rp-section" id="race-predictions">
        <div class="rp-head">
            <div class="rp-title">Predictions <span>· {_safe(summary.distance_label)} · {_safe(summary.goal_name)}</span></div>
            <div class="rp-link">View all predictions &nbsp;→</div>
        </div>
        <div class="rp-panels">
            <article class="rp-panel rp-coaches">
                <div class="rp-panel-head">
                    <div class="rp-panel-title">Coaches’ View</div>
                    <span class="rp-coaches-status">{_safe(status_label)}</span>
                </div>
                <div class="rp-coaches-copy">{_safe(summary.consensus_headline)}</div>
                <div class="rp-coach-grid">{''.join(coach_cards)}</div>
                <div class="rp-coaches-signals">
                    Strongest <strong>{_safe(strongest)}</strong> · Focus <strong class="focus">{_safe(limiting)}</strong>
                </div>
            </article>
            <article class="rp-panel rp-outlook">
                <div class="rp-panel-head">
                    <div class="rp-panel-title">Race Outlook</div>
                    <span class="rp-cap-kicker">Ideal → race conditions</span>
                </div>
                <div class="rp-capability">
                    <div class="rp-capability-main">
                        <div class="rp-cap-kicker">Current capability range</div>
                        <div class="rp-cap-range">{_safe(_clock(summary.low_seconds))}–{_safe(_clock(summary.high_seconds))}</div>
                        <div class="rp-cap-central">{_safe(_clock(summary.central_seconds))} central · {summary.confidence:.0%} confidence</div>
                    </div>
                    <div class="rp-stat"><strong>{_safe(target)}</strong><span>Goal</span></div>
                    <div class="rp-stat"><strong>{_safe(probability)}</strong><span>Goal likelihood</span></div>
                    <div class="rp-gap">{_safe(_signed_gap(summary.target_gap_seconds))}<br>Coaching estimate, not a guarantee</div>
                </div>
                <div class="rp-scenarios">{''.join(scenario_cards)}</div>
            </article>
        </div>
    </section>
    """


def _coach_evidence_copy(key: str) -> str:
    return {
        "race": "Race history · current competitive ceiling",
        "workout": "Quality sessions · repeatable training form",
        "threshold": "Sustainable pace · strongest confidence anchor",
    }.get(key, "Independent evidence · specialist view")


def _environment_icon(key: str) -> str:
    return {
        "heat": "☀",
        "hills": "△",
        "trail": "⌁",
    }.get(key, "·")


def build_home_intelligence_html(
    summary: HomePredictions,
    latest: HomeLatestRun,
) -> str:
    """Render Latest Run, Coaches and Race Outlook as one dense story."""
    if not summary.available:
        return f"""
        <section class="hi-section hi-empty" id="race-predictions">
            <div class="hi-title">Predictions · {_safe(summary.distance_label)}</div>
            <strong>Race capability is still building</strong>
            <span>{_safe(summary.explanation)}</span>
        </section>
        """

    coach_cards = []
    for coach in getattr(summary, "coach_positions", ()):
        lead_mark = (
            '<span class="hi-lead">Lead</span>' if coach.is_lead else ""
        )
        coach_cards.append(
            f"""
            <article class="hi-coach hi-{_safe(coach.position)}">
                <div class="hi-coach-head">
                    <strong>{_safe(coach.title)}</strong>{lead_mark}
                </div>
                <div class="hi-coach-time">
                    {_safe(_clock(coach.predicted_seconds))}
                    <span>{_safe(coach.position.title())}</span>
                </div>
                <div class="hi-coach-evidence">{_safe(_coach_evidence_copy(coach.key))}</div>
                <div class="hi-confidence">{coach.confidence:.0%} confidence</div>
            </article>
            """
        )

    response_chips = []
    for response in getattr(summary, "environment_responses", ()):
        chip_class = (
            "hi-response-strength"
            if response.confidence >= 0.25 and response.multiplier < 0.92
            else "hi-response-cost"
            if response.confidence >= 0.25 and response.multiplier > 1.08
            else "hi-response-neutral"
        )
        response_chips.append(
            f"""
            <span class="hi-response {chip_class}">
                <b>{_environment_icon(response.key)} {_safe(response.label)}</b>
                {_safe(response.response_label)}
            </span>
            """
        )

    trait = getattr(summary, "performance_trait", None)
    trait_markup = (
        f"""
        <div class="hi-trait">
            <span>Your edge</span>
            <strong>{_safe(trait.title)}</strong>
            <em>{_safe(trait.detail)}</em>
        </div>
        """
        if trait is not None
        else """
        <div class="hi-trait hi-trait-building">
            <span>Your edge</span>
            <strong>Still emerging</strong>
            <em>More comparable environmental runs will reveal a reliable strength.</em>
        </div>
        """
    )

    scenario_cards = []
    for scenario in summary.scenarios:
        personal_mark = (
            '<span class="hi-personal">Personal</span>'
            if scenario.personalised
            else ""
        )
        scenario_cards.append(
            f"""
            <article class="hi-scenario hi-scenario-{_safe(scenario.key)}">
                <div class="hi-scenario-head">
                    <strong>{_safe(scenario.label)}</strong>{personal_mark}
                </div>
                <div class="hi-scenario-time">{_safe(_clock(scenario.central_seconds))}</div>
                <div class="hi-scenario-copy">{_safe(scenario.description)}</div>
                <div class="hi-scenario-meta">
                    {_safe(_pace_per_mile(scenario.pace_seconds_per_km))}
                    <span>{scenario.confidence:.0%}</span>
                </div>
            </article>
            """
        )

    probability = (
        f"{summary.target_probability:.0%}"
        if summary.target_probability is not None
        else "—"
    )
    status_label = {
        "aligned": "Closely aligned",
        "balanced": "Broadly aligned",
        "mixed": "Mixed signals",
        "developing": "Developing",
        "building": "Building",
    }.get(summary.consensus_status, summary.consensus_status)

    if latest.available:
        rank_markup = (
            f'<strong>#{latest.rank}</strong><span>of {latest.comparison_count} {_safe(latest.category)}</span>'
            if latest.rank is not None and latest.comparison_count is not None
            else '<strong>—</strong><span>Rank building</span>'
        )
        condition_copy = (
            " · ".join(latest.environment_factors[:2])
            if latest.environment_factors
            else "Conditions recognised where data allows"
        )
        latest_markup = f"""
            <div class="hi-latest-head">
                <div>
                    <div class="hi-kicker">Latest run · {_safe(_format_date(latest.activity_date))}</div>
                    <h3>{_safe(latest.title)}</h3>
                </div>
                <div class="hi-rank">{rank_markup}</div>
            </div>
            <div class="hi-latest-win">{_safe(latest.headline)}</div>
            <div class="hi-latest-copy">{_safe(latest.explanation)}</div>
            <div class="hi-latest-stats">
                <span><b>{_safe(_distance_miles(latest.distance_km))}</b> distance</span>
                <span><b>{_safe(_clock(latest.moving_time_s))}</b> time</span>
                <span><b>{_safe(_pace_per_mile(latest.actual_pace_s_per_km))}</b> pace</span>
                <span><b>{_safe(f'{latest.avg_hr:.0f} bpm' if latest.avg_hr is not None else '—')}</b> avg HR</span>
            </div>
            <div class="hi-benefit">
                <span>What it gave you</span>
                <strong>{_safe(latest.benefit)}</strong>
            </div>
            <div class="hi-condition-note">{_safe(condition_copy)} · {latest.confidence:.0%} evidence confidence</div>
        """
    else:
        latest_markup = f"""
            <div class="hi-kicker">Latest run</div>
            <h3>{_safe(latest.title)}</h3>
            <div class="hi-latest-copy">{_safe(latest.explanation)}</div>
        """

    return f"""
    <style>
        * {{ box-sizing: border-box; }}
        .hi-section {{
            container-type: inline-size;
            width: 100%;
            margin-top: -2px;
            padding: 10px 11px 11px;
            overflow: hidden;
            color: #0b2035;
            font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            background: radial-gradient(circle at 100% 100%, rgba(241,90,36,.07), transparent 23%), #fffdf9;
            border: 1px solid #ded8ce;
            border-radius: 18px;
            box-shadow: 0 18px 46px rgba(7,24,42,.10);
        }}
        .hi-head {{ display:flex; align-items:center; justify-content:space-between; gap:12px; margin:0 2px 8px; }}
        .hi-title {{ font-size:13px; font-weight:900; letter-spacing:.11em; text-transform:uppercase; }}
        .hi-title span {{ color:#77818b; font-weight:700; }}
        .hi-link {{ color:#455666; font-size:9px; font-weight:850; letter-spacing:.08em; text-transform:uppercase; }}
        .hi-top {{ display:grid; grid-template-columns:minmax(360px,.78fr) minmax(610px,1.22fr); gap:9px; }}
        .hi-panel {{ min-width:0; padding:11px 12px; border-radius:13px; }}
        .hi-latest {{ background:#f7f5f0; border:1px solid #ded8ce; }}
        .hi-latest-head {{ display:flex; justify-content:space-between; align-items:flex-start; gap:12px; }}
        .hi-kicker {{ color:#6b7781; font-size:8px; font-weight:900; letter-spacing:.12em; text-transform:uppercase; }}
        .hi-latest h3 {{ margin:4px 0 0; font-size:18px; line-height:1.05; letter-spacing:-.025em; }}
        .hi-rank {{ flex:0 0 auto; min-width:66px; padding:5px 7px; text-align:right; background:#fffdf9; border:1px solid #ded8ce; border-radius:8px; }}
        .hi-rank strong {{ display:block; color:#238a52; font-size:18px; line-height:1; }}
        .hi-rank span {{ display:block; margin-top:2px; color:#687681; font-size:7px; }}
        .hi-latest-win {{ margin-top:8px; color:#0b2035; font-size:15px; line-height:1.1; font-weight:900; }}
        .hi-latest-copy {{ margin-top:3px; color:#596875; font-size:10.5px; line-height:1.3; }}
        .hi-latest-stats {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:5px; margin-top:8px; }}
        .hi-latest-stats span {{ min-width:0; color:#73808a; font-size:7.5px; text-transform:uppercase; }}
        .hi-latest-stats b {{ display:block; overflow:hidden; color:#0b2035; font-size:11px; text-transform:none; text-overflow:ellipsis; white-space:nowrap; }}
        .hi-benefit {{ display:grid; grid-template-columns:auto minmax(0,1fr); align-items:center; gap:9px; margin-top:8px; padding:7px 9px; background:#fff3e9; border-left:3px solid #f15a24; border-radius:7px; }}
        .hi-benefit span {{ color:#d94b17; font-size:7px; font-weight:900; letter-spacing:.08em; text-transform:uppercase; }}
        .hi-benefit strong {{ font-size:10px; line-height:1.25; }}
        .hi-condition-note {{ margin-top:6px; color:#77838d; font-size:8px; line-height:1.2; }}
        .hi-coaches {{ color:#fff; background:radial-gradient(circle at 100% 0%,rgba(35,138,82,.24),transparent 34%),linear-gradient(145deg,#07182a,#0d2b47); border:1px solid #173d5e; }}
        .hi-panel-head {{ display:flex; align-items:center; justify-content:space-between; gap:8px; }}
        .hi-panel-title {{ font-size:12.5px; font-weight:900; letter-spacing:.09em; text-transform:uppercase; }}
        .hi-status {{ padding:3px 7px; color:#bde8cf; font-size:7px; font-weight:900; letter-spacing:.08em; text-transform:uppercase; background:rgba(35,138,82,.22); border-radius:999px; }}
        .hi-coaches-copy {{ margin-top:4px; color:#c4d0db; font-size:10.5px; line-height:1.3; }}
        .hi-coach-grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:6px; margin-top:8px; }}
        .hi-coach {{ min-width:0; padding:8px 9px 7px; color:#0b2035; background:#fffdf9; border-radius:9px; border-top:3px solid #9aa5ad; }}
        .hi-coach.hi-optimistic {{ border-top-color:#238a52; }}
        .hi-coach.hi-cautious {{ border-top-color:#f15a24; }}
        .hi-coach-head {{ display:flex; align-items:center; gap:5px; min-width:0; }}
        .hi-coach-head strong {{ overflow:hidden; font-size:10.5px; text-overflow:ellipsis; white-space:nowrap; }}
        .hi-lead {{ margin-left:auto; padding:2px 5px; color:#fff; font-size:6px; font-weight:900; text-transform:uppercase; background:#f15a24; border-radius:999px; }}
        .hi-coach-time {{ margin-top:4px; font-size:23px; line-height:1; font-weight:900; letter-spacing:-.035em; }}
        .hi-coach-time span {{ margin-left:4px; color:#61707c; font-size:8.5px; font-weight:750; letter-spacing:0; }}
        .hi-coach-evidence {{ min-height:24px; margin-top:5px; color:#526470; font-size:8.5px; line-height:1.25; }}
        .hi-confidence {{ margin-top:3px; color:#71808b; font-size:8px; font-weight:750; }}
        .hi-coach-footer {{ display:grid; grid-template-columns:minmax(205px,.75fr) minmax(0,1.25fr); gap:7px; margin-top:7px; }}
        .hi-trait {{ display:grid; grid-template-columns:auto 1fr; column-gap:7px; align-items:center; padding:6px 8px; color:#0b2035; background:linear-gradient(135deg,#ffe2a8,#fff4d9); border:1px solid #e5b85e; border-radius:8px; }}
        .hi-trait span {{ grid-row:1/3; color:#a55a0b; font-size:7px; font-weight:900; letter-spacing:.08em; text-transform:uppercase; }}
        .hi-trait strong {{ font-size:12px; line-height:1; }}
        .hi-trait em {{ overflow:hidden; color:#785f3e; font-size:7.5px; font-style:normal; text-overflow:ellipsis; white-space:nowrap; }}
        .hi-responses {{ display:flex; align-items:stretch; gap:5px; min-width:0; }}
        .hi-response {{ flex:1 1 0; min-width:0; padding:5px 6px; color:#c9d4de; font-size:7px; line-height:1.15; text-align:center; background:rgba(255,255,255,.07); border:1px solid rgba(255,255,255,.10); border-radius:7px; }}
        .hi-response b {{ display:block; margin-bottom:2px; color:#fff; font-size:8.5px; }}
        .hi-response-strength b {{ color:#9fe0ba; }}
        .hi-response-cost b {{ color:#ffb294; }}
        .hi-outlook {{ margin-top:9px; padding:9px 10px; background:#f7f5f0; border:1px solid #ded8ce; border-radius:13px; }}
        .hi-outlook-grid {{ display:grid; grid-template-columns:minmax(205px,.95fr) repeat(5,minmax(100px,1fr)); gap:6px; align-items:stretch; }}
        .hi-capability {{ padding:7px 9px; background:#fffdf9; border:1px solid #e1dbd2; border-radius:9px; }}
        .hi-capability-range {{ margin-top:4px; font-size:22px; line-height:1; font-weight:900; letter-spacing:-.035em; white-space:nowrap; }}
        .hi-capability-central {{ margin-top:4px; color:#d94b17; font-size:9.5px; font-weight:850; }}
        .hi-capability-goal {{ display:flex; gap:9px; margin-top:6px; color:#65737f; font-size:8px; }}
        .hi-capability-goal b {{ color:#0b2035; font-size:10px; }}
        .hi-scenario {{ min-width:0; padding:7px 8px; background:rgba(255,255,255,.82); border:1px solid #e4dfd7; border-radius:9px; }}
        .hi-scenario-ideal {{ background:linear-gradient(160deg,#fff5e6,#fffdf9); border-color:#efc18c; }}
        .hi-scenario-typical {{ background:linear-gradient(160deg,#eef8f2,#fffdf9); border-color:#bfddca; }}
        .hi-scenario-head {{ display:flex; align-items:center; gap:4px; }}
        .hi-scenario-head strong {{ overflow:hidden; font-size:10.5px; text-overflow:ellipsis; white-space:nowrap; }}
        .hi-personal {{ margin-left:auto; padding:1px 4px; color:#287e51; font-size:5.5px; font-weight:900; text-transform:uppercase; background:#e6f4ec; border-radius:999px; }}
        .hi-scenario-time {{ margin-top:4px; font-size:20px; line-height:1; font-weight:900; letter-spacing:-.03em; }}
        .hi-scenario-copy {{ min-height:23px; margin-top:4px; color:#61707b; font-size:8.5px; line-height:1.22; }}
        .hi-scenario-meta {{ margin-top:4px; color:#697681; font-size:8px; }}
        .hi-scenario-meta span {{ float:right; font-weight:850; }}
        .hi-empty {{ padding:20px; }}
        .hi-empty strong,.hi-empty span {{ display:block; margin-top:5px; }}
        @container (max-width:1120px) {{
            .hi-top {{ grid-template-columns:1fr; }}
            .hi-outlook-grid {{ grid-template-columns:repeat(3,minmax(0,1fr)); }}
            .hi-capability {{ grid-column:1/-1; }}
        }}
        @container (max-width:650px) {{
            .hi-section {{ padding:8px; }}
            .hi-coach-grid {{ grid-template-columns:1fr; }}
            .hi-coach-evidence {{ min-height:0; }}
            .hi-coach-footer {{ grid-template-columns:1fr; }}
            .hi-outlook-grid {{ grid-template-columns:repeat(2,minmax(0,1fr)); }}
            .hi-latest-stats {{ grid-template-columns:repeat(2,minmax(0,1fr)); }}
        }}
        @container (max-width:380px) {{
            .hi-outlook-grid {{ grid-template-columns:1fr; }}
            .hi-capability {{ grid-column:auto; }}
            .hi-responses {{ flex-direction:column; }}
        }}
    </style>
    <section class="hi-section" id="race-predictions">
        <div class="hi-head">
            <div class="hi-title">Performance Intelligence <span>· {_safe(summary.distance_label)} · {_safe(summary.goal_name)}</span></div>
            <div class="hi-link">View full analysis &nbsp;→</div>
        </div>
        <div class="hi-top">
            <article class="hi-panel hi-latest">{latest_markup}</article>
            <article class="hi-panel hi-coaches">
                <div class="hi-panel-head">
                    <div class="hi-panel-title">Coaches’ View</div>
                    <span class="hi-status">{_safe(status_label)}</span>
                </div>
                <div class="hi-coaches-copy">{_safe(summary.consensus_headline)}</div>
                <div class="hi-coach-grid">{''.join(coach_cards)}</div>
                <div class="hi-coach-footer">
                    {trait_markup}
                    <div class="hi-responses">{''.join(response_chips)}</div>
                </div>
            </article>
        </div>
        <article class="hi-outlook">
            <div class="hi-panel-head" style="margin-bottom:7px;">
                <div class="hi-panel-title">Race Outlook</div>
                <span class="hi-kicker">Capability → race conditions</span>
            </div>
            <div class="hi-outlook-grid">
                <div class="hi-capability">
                    <div class="hi-kicker">Current capability</div>
                    <div class="hi-capability-range">{_safe(_clock(summary.low_seconds))}–{_safe(_clock(summary.high_seconds))}</div>
                    <div class="hi-capability-central">{_safe(_clock(summary.central_seconds))} central · {summary.confidence:.0%}</div>
                    <div class="hi-capability-goal">
                        <span><b>{_safe(_clock(summary.target_seconds))}</b> goal</span>
                        <span><b>{_safe(probability)}</b> likelihood</span>
                        <span>{_safe(_signed_gap(summary.target_gap_seconds))}</span>
                    </div>
                </div>
                {''.join(scenario_cards)}
            </div>
        </article>
    </section>
    """


def _run_icon(category: str, *, main: bool = False) -> str:
    common = (
        'viewBox="0 0 24 24" aria-hidden="true" '
        'fill="none" stroke="currentColor" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round"'
    )
    if main:
        paths = (
            '<path d="M8 4h8v4c0 3-1.8 5-4 5s-4-2-4-5V4Z"/>'
            '<path d="M8 6H5v1c0 2 1.2 3.5 3.4 3.8M16 6h3v1c0 2-1.2 3.5-3.4 3.8"/>'
            '<path d="M12 13v4M9 20h6M10 17h4"/>'
        )
    elif category == "Long Easy":
        paths = (
            '<path d="m3 18 6.4-9 3.1 4 2.3-3 6.2 8H3Z"/>'
            '<path d="m7.7 11.4 1.7 1.2 1.7-1.6"/>'
        )
    elif category == "Hot":
        paths = (
            '<circle cx="12" cy="12" r="3.5"/>'
            '<path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>'
        )
    elif category == "Trail":
        paths = (
            '<path d="M5 20c1-5 6-5 6-9s-3-4-2-8"/>'
            '<path d="M13 20c0-3 5-3 5-7 0-2-1-3-2-4"/>'
            '<circle cx="16" cy="6" r="2"/>'
        )
    elif category == "Hidden Gem":
        paths = (
            '<path d="m4 9 4-5h8l4 5-8 11L4 9Z"/>'
            '<path d="m4 9 8 3 8-3M8 4l4 8 4-8"/>'
        )
    else:
        paths = (
            '<path d="M7 16c2-4 3-8 3-12 3 2 5 5 6 8"/>'
            '<path d="M5 18c4-1 8-1 14 1M8 21h8"/>'
        )
    return f'<svg {common}>{paths}</svg>'


def build_best_runs_html(summary: HomeBestRuns) -> str:
    if not summary.available or summary.main is None:
        return """
        <section class="br-section br-empty">
            <div class="br-kicker">Best runs · Personal Hall of Fame</div>
            <div class="br-empty-title">Your greatest runs are still building</div>
            <div class="br-empty-copy">Import running history to reveal athlete-relative category bests.</div>
        </section>
        """

    main = summary.main
    main_stats = (
        ("Distance", _distance_miles(main.distance_km)),
        ("Time", _clock(main.moving_time_s)),
        ("Avg pace", _pace_per_mile(main.actual_pace_s_per_km)),
        ("Avg HR", f"{main.avg_hr:.0f} bpm" if main.avg_hr is not None else "—"),
        (
            "Moving",
            f"{main.moving_percent:.1f}%"
            if main.moving_percent is not None
            else "—",
        ),
    )
    stat_markup = "".join(
        f"""
        <div class="br-main-stat">
            <strong>{_safe(value)}</strong>
            <span>{_safe(label)}</span>
        </div>
        """
        for label, value in main_stats
    )

    category_cards = []
    for run in summary.category_bests:
        category_cards.append(
            f"""
            <article class="br-category-card">
                <div class="br-category-name">{_safe(run.short_category)}</div>
                <div class="br-category-date">{_safe(_format_date(run.activity_date))}</div>
                <div class="br-category-activity" title="{_safe(run.title)}">{_safe(run.title)}</div>
                <div class="br-category-performance">
                    <div class="br-category-icon">{_run_icon(run.short_category)}</div>
                    <div class="br-category-time">{_safe(_clock(run.moving_time_s))}</div>
                </div>
                <div class="br-category-meta">
                    <span>{_safe(_distance_miles(run.distance_km))}</span>
                    <span>{_safe(_pace_per_mile(run.actual_pace_s_per_km))}</span>
                    <span>{_safe(f'{run.avg_hr:.0f} bpm' if run.avg_hr is not None else 'HR unavailable')}</span>
                </div>
                <div class="br-category-score">
                    <span>No. 1</span>
                    <strong>{run.score:.1f}</strong>
                </div>
            </article>
            """
        )

    adjusted_gain = max(
        main.actual_pace_s_per_km - main.adjusted_pace_s_per_km,
        0.0,
    )
    adjusted_copy = (
        f"Adjusted {_pace_per_mile(main.adjusted_pace_s_per_km)}"
        if adjusted_gain >= 1
        else "Conditions recognised"
    )

    category_count = len(category_cards)
    grid_count = max(category_count, 1)

    return f"""
    <style>
        .br-section {{
            overflow: hidden;
            margin-top: 14px;
            padding: 10px 12px 12px;
            color: #0b2035;
            font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            background:
                radial-gradient(circle at 96% 100%, rgba(241,90,36,.07), transparent 22%),
                #fffdf9;
            border: 1px solid #ded8ce;
            border-radius: 20px;
            box-shadow: 0 18px 46px rgba(7, 24, 42, 0.10);
        }}

        .br-head {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 14px;
            margin: 0 3px 8px;
        }}

        .br-headline {{
            color: #0b2035;
            font-size: 13.5px;
            font-weight: 900;
            letter-spacing: .11em;
            text-transform: uppercase;
        }}

        .br-headline span {{ color: #77818b; font-weight: 650; }}

        .br-link {{
            color: #455666;
            font-size: 9.5px;
            font-weight: 850;
            letter-spacing: .08em;
            text-transform: uppercase;
            white-space: nowrap;
        }}

        .br-grid {{
            display: grid;
            grid-template-columns:
                minmax(330px, 2.75fr)
                repeat(var(--br-count), minmax(88px, 1fr));
            gap: 8px;
            align-items: stretch;
        }}

        .br-grid.br-count-0 {{ grid-template-columns: 1fr; }}

        .br-main {{
            position: relative;
            min-width: 0;
            min-height: 148px;
            padding: 9px 14px 8px;
            background:
                linear-gradient(120deg, rgba(255,255,255,.75), rgba(255,255,255,.20)),
                #fff0cf;
            border: 1px solid #eabf69;
            border-radius: 13px;
            box-shadow: inset 0 0 28px rgba(230,164,45,.08);
        }}

        .br-main-top {{
            display: flex;
            align-items: center;
            gap: 8px;
            padding-right: 50px;
        }}

        .br-main-icon {{ width: 22px; height: 22px; color: #dc8b14; flex: 0 0 auto; }}
        .br-main-icon svg, .br-category-icon svg {{ width: 100%; height: 100%; display: block; }}
        .br-main-kicker {{ font-size: 10px; font-weight: 900; letter-spacing: .09em; text-transform: uppercase; }}
        .br-main-date {{ margin-top: 1px; color: #826b47; font-size: 8.5px; font-weight: 700; }}

        .br-score-ribbon {{
            position: absolute;
            top: -5px;
            right: 12px;
            width: 38px;
            padding: 8px 3px 7px;
            color: #fff;
            text-align: center;
            background: linear-gradient(160deg, #e4a126, #c97c0b);
            border-radius: 3px 3px 9px 9px;
            box-shadow: 0 6px 13px rgba(174,108,14,.25);
        }}
        .br-score-ribbon strong {{ display: block; font-size: 13px; line-height: 1; }}
        .br-score-ribbon span {{ display: block; margin-top: 2px; font-size: 6px; font-weight: 800; letter-spacing: .07em; text-transform: uppercase; }}

        .br-main-title {{ margin-top: 5px; font-size: 17px; line-height: 1.05; font-weight: 900; letter-spacing: -.025em; }}
        .br-main-activity {{ margin-top: 2px; color: #6f6556; font-size: 9.5px; }}

        .br-main-stats {{
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            margin-top: 6px;
        }}
        .br-main-stat {{ min-width: 0; padding: 0 7px; border-left: 1px solid rgba(124,87,35,.18); }}
        .br-main-stat:first-child {{ padding-left: 0; border-left: 0; }}
        .br-main-stat strong {{ display: block; font-size: 11px; line-height: 1.1; white-space: nowrap; }}
        .br-main-stat span {{ display: block; margin-top: 2px; color: #8a7454; font-size: 7px; font-weight: 850; letter-spacing: .08em; text-transform: uppercase; }}

        .br-context {{
            display: flex;
            flex-wrap: wrap;
            gap: 5px 11px;
            margin-top: 5px;
            padding-top: 5px;
            color: #735f42;
            font-size: 8.5px;
            border-top: 1px solid rgba(124,87,35,.16);
        }}
        .br-context strong {{ color: #a04e14; font-weight: 850; }}
        .br-reason {{ margin-top: 4px; color: #574d40; font-size: 8px; line-height: 1.18; }}

        .br-category-card {{
            display: flex;
            min-width: 0;
            min-height: 148px;
            padding: 8px 9px 7px;
            flex-direction: column;
            background: rgba(255,255,255,.76);
            border: 1px solid #e6e0d8;
            border-radius: 12px;
        }}
        .br-category-name {{ font-size: 11.5px; line-height: 1.05; font-weight: 850; }}
        .br-category-date {{ margin-top: 2px; color: #7d8791; font-size: 8px; line-height: 1.2; text-transform: uppercase; }}
        .br-category-activity {{
            display: -webkit-box;
            min-height: 19px;
            margin-top: 4px;
            overflow: hidden;
            color: #526170;
            font-size: 8.5px;
            font-weight: 650;
            line-height: 1.15;
            -webkit-box-orient: vertical;
            -webkit-line-clamp: 2;
        }}
        .br-category-performance {{ display: flex; align-items: center; gap: 5px; margin-top: 5px; }}
        .br-category-icon {{ width: 17px; height: 17px; color: #687582; flex: 0 0 auto; }}
        .br-category-time {{ font-size: 14.5px; line-height: 1; font-weight: 900; letter-spacing: -.02em; }}
        .br-category-meta {{ margin-top: 3px; color: #5f6c78; font-size: 8.5px; line-height: 1.25; }}
        .br-category-meta span {{ display: block; }}
        .br-category-score {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 5px;
            margin-top: auto;
            padding-top: 5px;
            color: #6f7984;
            font-size: 8.5px;
            border-top: 1px solid #ebe6df;
        }}
        .br-category-score strong {{ color: #238a52; font-size: 11px; }}

        .br-empty {{ padding: 22px; text-align: center; }}
        .br-empty-title {{ margin-top: 5px; font-size: 18px; font-weight: 850; }}
        .br-empty-copy {{ margin-top: 4px; color: #6f7984; font-size: 11px; }}

        /* Keep every result on one continuous row throughout the desktop and
           stacked-tablet layouts. The grid uses the real award count, so four
           or five category cards always consume the complete available width. */
        @container (max-width: 980px) and (min-width: 761px) {{
            .br-section {{ padding: 9px 10px 10px; }}
            .br-head {{ margin-bottom: 6px; }}
            .br-grid {{
                grid-template-columns:
                    minmax(345px, 3.45fr)
                    repeat(var(--br-count), minmax(76px, 1fr));
                gap: 6px;
            }}
            .br-main {{ min-height: 132px; padding: 7px 12px 6px; }}
            .br-main-title {{ margin-top: 4px; font-size: 16px; }}
            .br-main-activity {{ font-size: 9px; }}
            .br-main-stats {{ margin-top: 5px; }}
            .br-context {{ margin-top: 5px; padding-top: 4px; }}
            .br-reason {{ margin-top: 4px; font-size: 8px; line-height: 1.18; }}
            .br-category-card {{ min-height: 132px; padding: 7px 7px 6px; }}
            .br-category-name {{ font-size: 11.5px; }}
            .br-category-date {{ font-size: 7.5px; }}
            .br-category-activity {{ min-height: 17px; margin-top: 3px; font-size: 7.8px; }}
            .br-category-performance {{ margin-top: 4px; gap: 4px; }}
            .br-category-icon {{ width: 15px; height: 15px; }}
            .br-category-time {{ font-size: 13.5px; }}
            .br-category-meta {{ margin-top: 3px; font-size: 8.5px; line-height: 1.25; }}
            .br-category-score {{ padding-top: 5px; }}
        }}

        @container (max-width: 760px) {{
            .br-section {{ padding: 9px 10px 10px; }}
            .br-head {{ margin-bottom: 6px; }}
            .br-grid {{ grid-template-columns: repeat(3, minmax(0, 1fr)); align-items: start; }}
            .br-main {{ grid-column: 1 / -1; min-height: 0; padding: 8px 12px 7px; }}
            .br-main-title {{ margin-top: 4px; font-size: 17px; }}
            .br-main-stats {{ margin-top: 5px; }}
            .br-context {{ margin-top: 5px; padding-top: 5px; }}
            .br-reason {{ margin-top: 4px; }}
            .br-category-card {{
                display: grid;
                grid-template-columns: 22px minmax(0, 1fr) auto;
                grid-template-areas:
                    "name name score"
                    "activity activity score"
                    "date date score"
                    "performance performance score"
                    "meta meta meta";
                column-gap: 7px;
                row-gap: 2px;
                align-items: center;
                min-height: 0;
                padding: 7px 9px 6px;
            }}
            .br-category-name {{ grid-area: name; }}
            .br-category-date {{ grid-area: date; margin-top: 0; min-height: 0; }}
            .br-category-activity {{
                grid-area: activity;
                min-height: 0;
                margin-top: 1px;
                font-size: 10px;
                -webkit-line-clamp: 1;
            }}
            .br-category-performance {{ grid-area: performance; margin-top: 2px; }}
            .br-category-icon {{ width: 18px; height: 18px; }}
            .br-category-time {{ font-size: 16px; }}
            .br-category-meta {{
                grid-area: meta;
                display: flex;
                flex-wrap: wrap;
                gap: 2px 8px;
                margin-top: 3px;
                padding-top: 5px;
                border-top: 1px solid #ebe6df;
            }}
            .br-category-meta span {{ display: inline; }}
            .br-category-score {{
                grid-area: score;
                display: block;
                align-self: start;
                min-width: 38px;
                margin-top: 0;
                padding: 3px 0 3px 7px;
                text-align: right;
                border-top: 0;
                border-left: 1px solid #ebe6df;
            }}
            .br-category-score span,
            .br-category-score strong {{ display: block; }}
            .br-category-score strong {{ margin-top: 3px; }}
            .br-category-name {{ font-size: 13px; }}
            .br-category-date {{ min-height: 0; font-size: 9.5px; }}
            .br-category-meta {{ font-size: 10px; }}
            .br-category-score {{ font-size: 9.5px; }}
            .br-category-score strong {{ font-size: 12px; }}
        }}

        @container (max-width: 520px) {{
            .br-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
        }}

        @container (max-width: 330px) {{
            .br-head {{ align-items: flex-start; }}
            .br-link {{ display: none; }}
            .br-grid {{ grid-template-columns: 1fr; }}
            .br-main {{ grid-column: auto; }}
            .br-main-stats {{ grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px 0; }}
            .br-main-stat:nth-child(4) {{ padding-left: 0; border-left: 0; }}
        }}
    </style>

    <section class="br-section" id="best-runs">
        <div class="br-head">
            <div class="br-headline">Best runs <span>· Personal Hall of Fame</span></div>
            <div class="br-link">View all runs &nbsp;→</div>
        </div>
        <div class="br-grid br-count-{category_count}" style="--br-count: {grid_count};">
            <article class="br-main">
                <div class="br-score-ribbon"><strong>{main.score:.1f}</strong><span>score</span></div>
                <div class="br-main-top">
                    <div class="br-main-icon">{_run_icon(main.category, main=True)}</div>
                    <div>
                        <div class="br-main-kicker">Best run ever</div>
                        <div class="br-main-date">{_safe(_format_date(main.activity_date))}</div>
                    </div>
                </div>
                <div class="br-main-title">{_safe(main.headline)}</div>
                <div class="br-main-activity">{_safe(main.title)}</div>
                <div class="br-main-stats">{stat_markup}</div>
                <div class="br-context">
                    <span>{_safe(main.environment_note)}</span>
                    <strong>{_safe(adjusted_copy)}</strong>
                </div>
                <div class="br-reason">
                    {_safe(main.reason)} · No. 1 category performance from
                    {summary.candidate_count:,} reviewed runs.
                </div>
            </article>
            {''.join(category_cards)}
        </div>
    </section>
    """


def build_home_panel_html(
    summary: HomeSummary,
    *,
    section: str = "all",
) -> str:
    """Build the goal context, weekly schedule, or complete coaching panel."""
    if section not in {"all", "context", "schedule"}:
        raise ValueError("section must be 'all', 'context', or 'schedule'")

    day_cards = []
    for day in summary.week_days:
        family = str(day.session_family or "easy").lower()
        classes = ["home-day", f"family-{_safe(family)}"]
        if day.is_today:
            classes.append("today")
        if family == "completed":
            classes.append("completed")

        day_cards.append(
            f"""
            <div class="{' '.join(classes)}">
                <div class="home-day-top">
                    <span>{_safe(day.day_name[:3])}</span>
                    <span class="home-day-dot"></span>
                </div>
                <div class="home-day-title">
                    {_safe(_session_label(family, day.title))}
                </div>
                <div class="home-day-detail">
                    {_safe(_compact_detail(day.detail))}
                </div>
            </div>
            """
        )

    if not day_cards:
        day_cards.append(
            """
            <div class="home-week-empty">
                Your weekly schedule will appear here as soon as an active
                goal and enough training context are available.
            </div>
            """
        )

    block_status = "Active block" if summary.block_is_saved else "Adaptive preview"

    context_markup = f"""
            <section class="home-context">
                <div>
                    <div class="home-kicker">Active goal</div>
                    <div class="home-goal-line">
                        <div class="home-goal">{_safe(summary.goal_name)}</div>
                        <div class="home-target">{_safe(_clock(summary.target_time_s))}</div>
                    </div>
                    <div class="home-context-copy">{_safe(summary.goal_context)}</div>
                </div>

                <div class="home-context-divider"></div>

                <div>
                    <div class="home-kicker">Training direction</div>
                    <div class="home-block-title">{_safe(summary.block_name)}</div>
                    <div class="home-block-meta">
                        <span>{_safe(summary.block_context)}</span>
                        <span class="home-block-status">{_safe(block_status)}</span>
                    </div>
                </div>
            </section>
    """

    schedule_markup = f"""
            <section class="home-week">
                <div class="home-week-head">
                    <div class="home-week-title">This week</div>
                    <div class="home-week-theme">{_safe(summary.week_theme)}</div>
                </div>
                <div class="home-days">{''.join(day_cards)}</div>
            </section>

            <section class="home-next">
                <div>
                    <div class="home-next-kicker">Up next</div>
                    <div class="home-next-title">{_safe(summary.next_label)}</div>
                    <div class="home-next-detail">{_safe(summary.next_detail)}</div>
                    <div class="home-next-source">{_safe(summary.next_source)}</div>
                </div>
                <div class="home-next-timing">{_safe(summary.next_timing)}</div>
            </section>
    """

    selected_markup = {
        "all": context_markup + schedule_markup,
        "context": context_markup,
        "schedule": schedule_markup,
    }[section]
    panel_class = f"home-panel home-panel-{section}"

    return f"""
    <style>
        * {{ box-sizing: border-box; }}
        body {{ margin: 0; }}

        .home-panel-shell {{
            width: 100%;
            max-width: none;
            margin: 0;
            font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            color: #0b2035;
        }}

        .home-panel {{
            overflow: hidden;
            background: #fffdf9;
            border: 1px solid #ded8ce;
            border-radius: 20px;
            box-shadow: 0 18px 46px rgba(7, 24, 42, 0.11);
        }}

        .home-panel-context {{
            width: calc(100% - 14px);
            border-radius: 14px;
            box-shadow: 0 12px 30px rgba(7, 24, 42, 0.09);
        }}

        .home-panel-context .home-context {{
            min-height: 64px;
            padding-top: 8px;
            padding-bottom: 8px;
            border-bottom: 0;
        }}

        .home-context {{
            display: grid;
            grid-template-columns: minmax(0, .92fr) 1px minmax(0, 1.25fr);
            gap: 16px;
            align-items: center;
            min-height: 74px;
            padding: 11px 18px;
            background:
                radial-gradient(circle at 96% 4%, rgba(241,90,36,.08), transparent 30%),
                #fffdf9;
            border-bottom: 1px solid #e8e1d7;
        }}

        .home-context-divider {{
            width: 1px;
            height: 42px;
            background: #ddd6cc;
        }}

        .home-kicker {{
            color: #6f7984;
            font-size: 10.5px;
            font-weight: 850;
            letter-spacing: .16em;
            text-transform: uppercase;
        }}

        .home-goal-line {{
            display: flex;
            align-items: baseline;
            gap: 10px;
            margin-top: 3px;
        }}

        .home-goal {{
            color: #081d32;
            font-size: clamp(22px, 2.25vw, 28px);
            line-height: 1;
            font-weight: 850;
            letter-spacing: -.035em;
        }}

        .home-target {{
            color: #f15a24;
            font-size: 15px;
            font-weight: 850;
            white-space: nowrap;
        }}

        .home-context-copy {{
            margin-top: 5px;
            color: #77818b;
            font-size: 11.5px;
            line-height: 1.28;
        }}

        .home-block-title {{
            margin-top: 3px;
            color: #238a52;
            font-size: clamp(19px, 1.9vw, 23px);
            line-height: 1.08;
            font-weight: 850;
            letter-spacing: -.025em;
        }}

        .home-block-meta {{
            display: flex;
            flex-wrap: wrap;
            gap: 7px;
            align-items: center;
            margin-top: 5px;
            color: #5e6c78;
            font-size: 11.5px;
        }}

        .home-block-status {{
            padding: 3px 7px;
            color: #287e51;
            font-size: 9px;
            font-weight: 850;
            letter-spacing: .08em;
            text-transform: uppercase;
            background: #e9f5ee;
            border-radius: 999px;
        }}

        .home-week {{
            padding: 11px 12px 9px;
        }}

        .home-week-head {{
            display: flex;
            align-items: flex-end;
            justify-content: space-between;
            gap: 18px;
            margin: 0 3px 7px;
        }}

        .home-week-title {{
            color: #0b2035;
            font-size: 13.5px;
            font-weight: 900;
            letter-spacing: .12em;
            text-transform: uppercase;
        }}

        .home-week-theme {{
            color: #7d8791;
            font-size: 10.5px;
            text-align: right;
        }}

        .home-days {{
            display: grid;
            grid-template-columns: repeat(7, minmax(0, 1fr));
            gap: 6px;
        }}

        .home-day {{
            position: relative;
            min-width: 0;
            min-height: 88px;
            padding: 9px;
            background: #ffffff;
            border: 1px solid #e4dfd7;
            border-radius: 12px;
        }}

        .home-day.today {{
            color: #ffffff;
            background:
                radial-gradient(circle at 95% 0%, rgba(241,90,36,.28), transparent 35%),
                linear-gradient(150deg, #07182a, #0d2b47);
            border-color: #173d5e;
            box-shadow: 0 10px 24px rgba(7,24,42,.20);
        }}

        .home-day.completed {{
            background: #edf7f1;
            border-color: #bddfcb;
        }}

        .home-day-top {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            color: #667483;
            font-size: 9.5px;
            font-weight: 850;
            letter-spacing: .12em;
            text-transform: uppercase;
        }}

        .home-day.today .home-day-top {{ color: #aebdcc; }}

        .home-day-dot {{
            width: 5px;
            height: 5px;
            background: #d4d8dc;
            border-radius: 50%;
        }}

        .home-day.today .home-day-dot {{ background: #ff6533; }}
        .home-day.completed .home-day-dot {{ background: #238a52; }}

        .home-day-title {{
            margin-top: 8px;
            color: #0b2035;
            font-size: 13.5px;
            line-height: 1.12;
            font-weight: 850;
            letter-spacing: -.015em;
        }}

        .home-day.today .home-day-title {{ color: #ffffff; }}

        .home-day-detail {{
            margin-top: 4px;
            color: #6c7782;
            font-size: 10.5px;
            line-height: 1.26;
            overflow-wrap: anywhere;
        }}

        .home-day.today .home-day-detail {{ color: #c6d1dc; }}

        .home-week-empty {{
            grid-column: 1 / -1;
            padding: 28px;
            color: #65727e;
            font-size: 11px;
            text-align: center;
            border: 1px dashed #d9d2c8;
            border-radius: 14px;
        }}

        .home-next {{
            display: grid;
            grid-template-columns: minmax(0, 1fr) auto;
            gap: 14px;
            align-items: center;
            margin: 0 12px 12px;
            padding: 9px 13px 9px 15px;
            background:
                linear-gradient(90deg, rgba(241,90,36,.10), transparent 58%),
                #faf6ef;
            border: 1px solid #ead8ca;
            border-left: 4px solid #f15a24;
            border-radius: 12px;
        }}

        .home-next-kicker {{
            color: #d94b17;
            font-size: 9.5px;
            font-weight: 900;
            letter-spacing: .14em;
            text-transform: uppercase;
        }}

        .home-next-title {{
            margin-top: 3px;
            color: #0a2035;
            font-size: 19px;
            line-height: 1.08;
            font-weight: 850;
            letter-spacing: -.025em;
        }}

        .home-next-detail {{
            margin-top: 4px;
            max-width: 620px;
            color: #63707c;
            font-size: 11px;
            line-height: 1.3;
        }}

        .home-next-source {{
            margin-top: 3px;
            color: #8a929a;
            font-size: 9.5px;
        }}

        .home-next-timing {{
            min-width: 84px;
            padding: 9px 11px;
            color: #ffffff;
            font-size: 12px;
            font-weight: 850;
            text-align: center;
            background: #0b2239;
            border-radius: 10px;
        }}

        @media (max-width: 1050px) {{
            .home-days {{ grid-template-columns: repeat(4, minmax(0, 1fr)); }}
            .home-day {{ min-height: 92px; }}
        }}

        @media (max-width: 700px) {{
            .home-panel {{ min-height: 0; }}
            .home-context {{
                grid-template-columns: 1fr;
                gap: 16px;
                padding: 20px;
            }}
            .home-context-divider {{ width: 100%; height: 1px; }}
            .home-days {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
            .home-week-head {{ display: block; }}
            .home-week-theme {{ margin-top: 5px; text-align: left; }}
            .home-next {{ grid-template-columns: 1fr; }}
            .home-next-timing {{ justify-self: start; }}
        }}
    </style>

    <div class="home-panel-shell">
        <article class="{panel_class}">
            {selected_markup}
        </article>
    </div>
    """


def render_home_panel(athlete_id: int) -> None:
    st.html(build_home_panel_html(build_home_summary(athlete_id)))


def build_home_composition_html(
    athlete_id: int,
    *,
    home_summary: HomeSummary | None = None,
    best_runs_summary: HomeBestRuns | None = None,
) -> str:
    """Combine the Passport and coaching panel in one responsive layout.

    Keeping both components in the same HTML surface gives the Home page direct
    control over the Passport rail width. The individual components retain
    their own visual styling and calculations.
    """
    passport_html = build_athlete_card_html(athlete_id)
    resolved_home_summary = home_summary or build_home_summary(athlete_id)
    resolved_best_runs = best_runs_summary or build_home_best_runs(athlete_id)
    panel_html = build_home_panel_html(resolved_home_summary, section="schedule")
    mobile_context_html = build_home_panel_html(
        resolved_home_summary,
        section="context",
    )
    best_runs_html = build_best_runs_html(resolved_best_runs)

    return f"""
    <style>
        .home-composition {{
            display: grid;
            grid-template-columns: minmax(0, 370px) minmax(0, 1fr);
            gap: 14px;
            align-items: start;
            width: 100%;
        }}

        .home-passport-rail,
        .home-coaching-area {{
            min-width: 0;
        }}

        .home-coaching-area {{
            container-type: inline-size;
        }}

        .home-mobile-context {{
            display: none;
        }}

        .home-passport-rail .pp-shell {{
            max-width: 370px;
            margin: 0;
        }}

        /* Home-only compression: the approved standalone Passport is untouched. */
        @media (min-width: 981px) {{
            .home-passport-rail .pp-top {{
                grid-template-columns: minmax(0, 1.08fr) minmax(150px, .92fr);
                min-height: 210px;
            }}

            .home-passport-rail .pp-identity {{
                padding: 15px 12px 15px 17px;
            }}

            .home-passport-rail .pp-logo {{
                width: 118px;
                height: 54px;
                margin-bottom: 6px;
            }}

            .home-passport-rail .pp-eyebrow {{ font-size: 9.5px; }}
            .home-passport-rail .pp-name {{ font-size: 27px; }}
            .home-passport-rail .pp-category {{ font-size: 10.5px; }}

            .home-passport-rail .pp-motto {{
                margin-top: 12px;
                font-size: 10.5px;
                line-height: 1.34;
            }}

            .home-passport-rail .pp-photo-wrap,
            .home-passport-rail .pp-photo-placeholder {{
                min-height: 210px;
            }}

            .home-passport-rail .pp-panel {{
                padding: 13px 11px 12px;
            }}

            .home-passport-rail .pp-section-title {{
                margin-bottom: 9px;
                font-size: 8.5px;
            }}

            .home-passport-rail .pp-grade-value {{ font-size: 22px; }}
            .home-passport-rail .pp-grade-label {{ font-size: 7.5px; }}
            .home-passport-rail .pb-header {{ font-size: 7.5px; }}
            .home-passport-rail .pb-event {{ font-size: 9.5px; }}

            .home-passport-rail .pb-row {{
                min-height: 26px;
            }}

            .home-passport-rail .pb-time {{
                font-size: 11.5px;
            }}

            .home-passport-rail .pp-development {{
                padding: 10px 14px 7px;
            }}

            .home-passport-rail .development-copy {{ font-size: 9.5px; }}
            .home-passport-rail .development-score span {{ font-size: 7.5px; }}

            .home-passport-rail .chart {{
                height: 30px;
                margin-top: 4px;
            }}
        }}

        @media (max-width: 980px) {{
            .home-composition {{
                grid-template-columns: 1fr;
                gap: 18px;
            }}

            .home-passport-rail .pp-shell {{
                max-width: 460px;
                margin: 0 auto;
            }}

            .home-mobile-context {{
                display: block;
                margin-bottom: 14px;
            }}

            .home-mobile-context .home-panel-context {{
                width: 100%;
            }}
        }}
    </style>

    <div class="home-composition">
        <div class="home-passport-rail">{passport_html}</div>
        <div class="home-coaching-area">
            <div class="home-mobile-context">{mobile_context_html}</div>
            {panel_html}
            {best_runs_html}
        </div>
    </div>
    """


def show_home_preview() -> None:
    st.markdown(
        """
        <style>
            [data-testid="stMainBlockContainer"] {
                max-width: 1450px;
                padding-top: 2rem;
                padding-bottom: 3rem;
            }
            [data-testid="stHeader"] { background: transparent; }
            .home-preview-kicker {
                margin-bottom: .75rem;
                color: #8a776a;
                font-size: .68rem;
                font-weight: 800;
                letter-spacing: .14em;
                text-transform: uppercase;
            }

            /* The two page columns must be independent. If Active Goal and
               the selector share a separate row, the taller goal card pushes
               the Passport down and leaves dead space beneath the selector. */
            [data-testid="stHorizontalBlock"]:has(.home-layout-left) {
                align-items: flex-start;
            }

            [data-testid="stColumn"]:has(.home-layout-left)
            [data-testid="stVerticalBlock"],
            [data-testid="stColumn"]:has(.home-layout-right)
            [data-testid="stVerticalBlock"] {
                gap: .75rem;
            }

            .home-layout-left,
            .home-layout-right {
                min-width: 0;
            }

            .home-layout-right {
                container-type: inline-size;
                display: grid;
                row-gap: 14px;
            }

            .home-layout-right-block {
                min-width: 0;
            }

            .home-layout-right-block .br-section {
                margin-top: 0;
            }

            .home-layout-right .home-panel-context {
                width: 100%;
            }

            .home-layout-left .pp-shell {
                width: 100%;
                max-width: 370px;
                margin: 0;
            }

            /* Home-only Passport compression. The standalone Passport remains
               unchanged, and the stacked layout restores its 460px treatment. */
            @media (min-width: 981px) {
                .home-layout-left .pp-top {
                    grid-template-columns: minmax(0, 1.08fr) minmax(150px, .92fr);
                    min-height: 210px;
                }
                .home-layout-left .pp-identity { padding: 15px 12px 15px 17px; }
                .home-layout-left .pp-logo {
                    width: 118px;
                    height: 54px;
                    margin-bottom: 6px;
                }
                .home-layout-left .pp-eyebrow { font-size: 9.5px; }
                .home-layout-left .pp-name { font-size: 27px; }
                .home-layout-left .pp-category { font-size: 10.5px; }
                .home-layout-left .pp-motto {
                    margin-top: 12px;
                    font-size: 10.5px;
                    line-height: 1.34;
                }
                .home-layout-left .pp-photo-wrap,
                .home-layout-left .pp-photo-placeholder { min-height: 210px; }
                .home-layout-left .pp-panel { padding: 13px 11px 12px; }
                .home-layout-left .pp-section-title {
                    margin-bottom: 9px;
                    font-size: 8.5px;
                }
                .home-layout-left .pp-grade-value { font-size: 22px; }
                .home-layout-left .pp-grade-label { font-size: 7.5px; }
                .home-layout-left .pb-header { font-size: 7.5px; }
                .home-layout-left .pb-event { font-size: 9.5px; }
                .home-layout-left .pb-row { min-height: 26px; }
                .home-layout-left .pb-time { font-size: 11.5px; }
                .home-layout-left .pp-development { padding: 10px 14px 7px; }
                .home-layout-left .development-copy { font-size: 9.5px; }
                .home-layout-left .development-score span { font-size: 7.5px; }
                .home-layout-left .chart {
                    height: 30px;
                    margin-top: 4px;
                }

                /* The Hall of Fame becomes a little shorter when fewer real
                   award cards are available: the yellow winner gains width,
                   so its evidence copy wraps onto fewer lines. Match that
                   content-driven height without changing the five-award
                   Richard layout or any stacked/mobile treatment. */
                .home-layout-left.home-passport-trim-1 .pp-top {
                    min-height: 204px;
                }
                .home-layout-left.home-passport-trim-1 .pp-photo-wrap,
                .home-layout-left.home-passport-trim-1 .pp-photo-placeholder {
                    min-height: 204px;
                }
                .home-layout-left.home-passport-trim-1 .pp-panel {
                    padding-top: 10px;
                    padding-bottom: 9px;
                }
                .home-layout-left.home-passport-trim-1 .pb-row {
                    min-height: 24px;
                }
                .home-layout-left.home-passport-trim-1 .pp-development {
                    padding-top: 8px;
                    padding-bottom: 5px;
                }
                .home-layout-left.home-passport-trim-1 .chart {
                    height: 28px;
                    margin-top: 3px;
                }

                /* A future athlete with three or fewer genuine categories
                   receives the same rule at a slightly denser setting. */
                .home-layout-left.home-passport-trim-2 .pp-top {
                    min-height: 198px;
                }
                .home-layout-left.home-passport-trim-2 .pp-photo-wrap,
                .home-layout-left.home-passport-trim-2 .pp-photo-placeholder {
                    min-height: 198px;
                }
                .home-layout-left.home-passport-trim-2 .pp-panel {
                    padding-top: 8px;
                    padding-bottom: 7px;
                }
                .home-layout-left.home-passport-trim-2 .pb-row {
                    min-height: 23px;
                }
                .home-layout-left.home-passport-trim-2 .pp-development {
                    padding-top: 7px;
                    padding-bottom: 4px;
                }
                .home-layout-left.home-passport-trim-2 .chart {
                    height: 26px;
                    margin-top: 2px;
                }
            }

            @media (max-width: 980px) {
                [data-testid="stHorizontalBlock"]:has(.home-layout-left) {
                    flex-wrap: wrap;
                }

                [data-testid="stHorizontalBlock"]:has(.home-layout-left)
                [data-testid="stColumn"] {
                    flex: 1 1 100%;
                    width: 100%;
                }

                .home-layout-left .pp-shell {
                    max-width: 460px;
                    margin: 0 auto;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="home-preview-kicker">Home preview · Phase 3</div>',
        unsafe_allow_html=True,
    )

    passport_col, coaching_col = st.columns([370, 1066], gap="small")
    with passport_col:
        athlete_id = render_athlete_selector(
            key="home_preview_athlete_selector",
            label="Athlete",
            label_visibility="collapsed",
        )

    if athlete_id is None:
        st.warning("No athletes found. Add an athlete first.")
        return

    home_summary = build_home_summary(athlete_id)
    best_runs_summary = build_home_best_runs(athlete_id)
    best_run_category_count = len(best_runs_summary.category_bests)
    passport_trim_class = (
        "home-passport-trim-0"
        if best_run_category_count >= 5
        else "home-passport-trim-1"
        if best_run_category_count == 4
        else "home-passport-trim-2"
    )

    with passport_col:
        st.html(
            '<div class="home-layout-left home-passport-rail '
            + passport_trim_class
            + '">'
            + build_athlete_card_html(athlete_id)
            + '</div>'
        )

    with coaching_col:
        st.html(
            '<div class="home-layout-right">'
            + '<div class="home-layout-right-block">'
            + build_home_panel_html(home_summary, section="context")
            + '</div>'
            + '<div class="home-layout-right-block">'
            + build_home_panel_html(home_summary, section="schedule")
            + '</div>'
            + '<div class="home-layout-right-block">'
            + build_best_runs_html(best_runs_summary)
            + '</div>'
            + '</div>'
        )

    with st.spinner("Analysing real race capability…"):
        predictions_summary = _cached_home_predictions(
            athlete_id,
            PREDICTIONS_CACHE_SCHEMA,
        )
        predictions_summary = _refresh_stale_predictions_contract(
            athlete_id,
            predictions_summary,
        )
        latest_run_summary = _cached_home_latest_run(athlete_id)
    st.html(
        build_home_intelligence_html(
            predictions_summary,
            latest_run_summary,
        )
    )


if __name__ == "__main__":
    st.set_page_config(
        page_title="Performance Passport · Home Preview",
        page_icon="P",
        layout="wide",
    )
    show_home_preview()
