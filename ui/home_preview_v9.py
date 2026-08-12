"""Polished Home v9 preview built from the approved v8 design system.

Run with:
    streamlit run ui/home_preview_v9.py

V9 preserves every v8 calculation and component.  It tightens presentation
copy, resolves visible truncation, and gives the Passport and Race Outlook one
shared desktop baseline.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from core.home_best_runs import build_home_best_runs
from core.home_summary import build_home_summary
from ui.athlete_selection import render_athlete_selector
from ui import home_preview as v6
from ui import home_preview_v8 as v8


COACH_LABELS = {
    "race": "Race",
    "workout": "Workout",
    "threshold": "Threshold",
}

COACH_EVIDENCE = {
    "race": "Proven race results set your competitive ceiling.",
    "workout": "Quality sessions show your repeatable training speed.",
    "threshold": "Sustained efforts anchor your holdable race pace.",
}

SCENARIO_DESCRIPTIONS = {
    "ideal": "Cool · flat · light wind",
    "typical": "Mild · normal road course",
    "warm": "20–22°C · moderate humidity",
    "hilly": "Rolling course · sustained climbs",
    "windy": "Exposed · noticeable headwind",
}


def _display_predictions(predictions):
    """Create a presentation-only copy without altering prediction values."""
    coaches = tuple(
        replace(coach, title=COACH_LABELS.get(coach.key, coach.title))
        for coach in getattr(predictions, "coach_positions", ())
    )
    scenarios = tuple(
        replace(
            scenario,
            description=SCENARIO_DESCRIPTIONS.get(
                scenario.key,
                scenario.description,
            ),
        )
        for scenario in getattr(predictions, "scenarios", ())
    )

    trait = getattr(predictions, "performance_trait", None)
    if trait is not None:
        matching_response = next(
            (
                response
                for response in getattr(predictions, "environment_responses", ())
                if response.key == trait.key
            ),
            None,
        )
        if matching_response is not None:
            response = matching_response.response_label.replace(" affected", "")
            trait = replace(
                trait,
                detail=(
                    f"{matching_response.label} costs you {response} than "
                    "the standard model."
                ),
            )

    return replace(
        predictions,
        coach_positions=coaches,
        scenarios=scenarios,
        performance_trait=trait,
    )


def _replace_coach_evidence(markup: str) -> str:
    for key, concise_copy in COACH_EVIDENCE.items():
        markup = markup.replace(v8._coach_evidence(key), concise_copy)
    return markup


def build_v9_goal_html(summary, *, mobile: bool = False) -> str:
    """Keep the v8 goal content while making every desktop item readable."""
    markup = v8.build_v8_goal_html(summary, mobile=mobile)
    return f"""
    <div class="v9-goal">
        {markup}
        <style>
            .v9-goal .v8-goal-strip {{ gap:12px; }}
            .v9-goal .v8-goal-direction {{ gap:7px; }}
            .v9-goal .v8-goal-direction strong {{ flex:1 1 auto; overflow:visible; text-overflow:clip; }}
            .v9-goal .v8-goal-direction-copy {{ display:none; }}
            @media (max-width:1200px) {{
                .v9-goal .v8-goal-direction-copy {{ display:inline; }}
            }}
        </style>
    </div>
    """


def build_v9_intelligence_html(predictions, latest) -> str:
    """Render the v8 intelligence with concise, untruncated display copy."""
    display_predictions = _display_predictions(predictions)
    markup = _replace_coach_evidence(
        v8.build_v8_intelligence_html(display_predictions, latest)
    )
    return f"""
    <div class="v9-intelligence-shell">
        {markup}
        <style>
            .v9-intelligence-shell,
            .v9-intelligence-shell > .v8-rail {{ height:100%; }}
            .v9-intelligence-shell .v8-rail {{ gap:8px; }}
            .v9-intelligence-shell .v8-intelligence {{ padding:10px 11px 11px; }}
            .v9-intelligence-shell .v8-section-head {{ margin-bottom:8px; }}
            .v9-intelligence-shell .v8-intelligence-grid {{ gap:8px; }}
            .v9-intelligence-shell .v8-panel {{ padding:9px 10px; }}
            .v9-intelligence-shell .v8-coaches-intro {{ font-size:11.5px; }}
            .v9-intelligence-shell .v8-coach-grid {{ gap:6px; margin-top:7px; }}
            .v9-intelligence-shell .v8-coach {{ padding:7px 8px; }}
            .v9-intelligence-shell .v8-coach-head strong {{
                overflow:visible; font-size:11.5px; text-overflow:clip;
            }}
            .v9-intelligence-shell .v8-coach-time {{ font-size:22px; }}
            .v9-intelligence-shell .v8-coach-copy {{ font-size:11px; line-height:1.25; }}
            .v9-intelligence-shell .v8-coach-footer {{
                grid-template-columns:minmax(250px,.95fr) minmax(0,1.05fr);
                gap:6px; margin-top:6px;
            }}
            .v9-intelligence-shell .v8-trait {{
                grid-template-columns:auto minmax(0,1fr);
                align-content:center; padding:6px 8px;
            }}
            .v9-intelligence-shell .v8-trait span {{ grid-row:auto; }}
            .v9-intelligence-shell .v8-trait em {{
                grid-column:1/-1; margin-top:3px; overflow:visible;
                font-size:10.5px; line-height:1.2; text-overflow:clip; white-space:normal;
            }}
            .v9-intelligence-shell .v8-response {{ padding:5px; }}
            .v9-intelligence-shell .v8-outlook {{ padding:8px 9px 9px; }}
            .v9-intelligence-shell .v8-outlook-band {{ margin-top:6px; }}
            .v9-intelligence-shell .v8-capability,
            .v9-intelligence-shell .v8-scenario {{ padding:7px 9px; }}
            .v9-intelligence-shell .v8-scenario-copy {{
                min-height:26px; font-size:11px; line-height:1.18;
            }}
            .v9-intelligence-shell .v8-scenario-meta {{ font-size:10.5px; }}
            @container (max-width:780px) {{
                .v9-intelligence-shell .v8-coach-footer {{ grid-template-columns:1fr; }}
            }}
        </style>
    </div>
    """


def build_v9_hero_html(athlete_id: int, home_summary, predictions, latest) -> str:
    """Align the Passport and Race Outlook while using the added card height."""
    return f"""
    <style>
        .v9-hero {{
            container-type:inline-size; display:grid;
            grid-template-columns:minmax(0,390px) minmax(0,1fr);
            gap:8px; align-items:stretch; width:100%;
        }}
        .v9-passport,.v9-hero-right {{ min-width:0; }}
        .v9-passport {{ display:flex; }}
        .v9-passport .pp-shell,
        .v9-passport .pp-passport {{ height:100%; }}
        .v9-passport .pp-passport {{ display:flex; flex-direction:column; }}
        .v9-passport .pp-development {{
            flex:1 1 auto; display:flex; flex-direction:column;
        }}
        .v9-passport .chart {{ flex:1 1 39px; min-height:39px; max-height:82px; height:auto; }}
        .v9-hero-right {{ container-type:inline-size; }}
        .v9-mobile-goal {{ display:none; }}
        @media (max-width:1200px) {{
            .v9-hero {{ grid-template-columns:1fr; }}
            .v9-passport {{ display:block; }}
            .v9-passport .pp-shell,
            .v9-passport .pp-passport {{ height:auto; }}
            .v9-mobile-goal {{ display:block; margin-bottom:8px; }}
        }}
    </style>
    <div class="v9-hero">
        <div class="v9-passport v8-passport">
            {v8.build_athlete_card_html(athlete_id)}
            {v8._v8_passport_overrides()}
        </div>
        <div class="v9-hero-right">
            <div class="v9-mobile-goal">{build_v9_goal_html(home_summary, mobile=True)}</div>
            {build_v9_intelligence_html(predictions, latest)}
        </div>
    </div>
    """


def build_v9_lower_html(home_summary, best_runs) -> str:
    """Retain v8's successful lower section with the refined 8px rhythm."""
    return f"""
    <div class="v9-lower-shell">
        {v8.build_v8_lower_html(home_summary, best_runs)}
        <style>
            .v9-lower-shell .v8-lower {{ gap:8px; }}
        </style>
    </div>
    """


def show_home_preview_v9() -> None:
    st.markdown(
        """
        <style>
            [data-testid="stMainBlockContainer"] { max-width:1450px; padding-top:1.6rem; padding-bottom:3rem; }
            [data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"],
            [data-testid="stMainBlockContainer"] > div > [data-testid="stVerticalBlock"] { gap:8px; }
            [data-testid="stHeader"] { background:transparent; }
            .v9-preview-kicker { margin-bottom:0; color:#8a776a; font-size:.72rem; font-weight:800; letter-spacing:.12em; text-transform:uppercase; }
            [data-testid="stHorizontalBlock"]:has(.v9-selector-marker) { align-items:flex-start; gap:8px; }
            [data-testid="stElementContainer"]:has(.v9-selector-marker) { display:none; }
            [data-testid="stHorizontalBlock"]:has(.v9-selector-marker) [data-testid="stVerticalBlock"] { gap:0; }
            @media (max-width:1200px) {
                [data-testid="stHorizontalBlock"]:has(.v9-selector-marker) [data-testid="stColumn"]:last-child { display:none; }
                [data-testid="stHorizontalBlock"]:has(.v9-selector-marker) [data-testid="stColumn"]:first-child { flex:1 1 100%; width:100%; }
            }
        </style>
        <div class="v9-preview-kicker">Home preview · Polished v9 alignment system</div>
        """,
        unsafe_allow_html=True,
    )

    selector_col, goal_col = st.columns([390, 1051], gap="small")
    with selector_col:
        st.markdown('<span class="v9-selector-marker"></span>', unsafe_allow_html=True)
        athlete_id = render_athlete_selector(
            key="home_preview_v9_athlete_selector",
            label="Athlete",
            label_visibility="collapsed",
        )

    if athlete_id is None:
        st.warning("No athletes found. Add an athlete first.")
        return

    home_summary = build_home_summary(athlete_id)
    with goal_col:
        st.html(build_v9_goal_html(home_summary))

    best_runs = build_home_best_runs(athlete_id)
    with st.spinner("Analysing real performance intelligence…"):
        predictions = v6._cached_home_predictions(athlete_id, v6.PREDICTIONS_CACHE_SCHEMA)
        predictions = v6._refresh_stale_predictions_contract(athlete_id, predictions)
        latest = v6._cached_home_latest_run(athlete_id)

    st.html(build_v9_hero_html(athlete_id, home_summary, predictions, latest))
    st.html(build_v9_lower_html(home_summary, best_runs))


if __name__ == "__main__":
    st.set_page_config(
        page_title="Performance Passport · Home v9 Preview",
        page_icon="P",
        layout="wide",
    )
    show_home_preview_v9()
