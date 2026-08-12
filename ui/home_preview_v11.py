"""Final Home v11 responsive polish built from the approved v10 preview.

Run with:
    streamlit run ui/home_preview_v11.py

V11 preserves v10's desktop composition and calculations.  It only repairs the
compact Active Goal card so its multi-line content is allowed to grow instead
of being clipped by the desktop strip height.
"""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from core.home_best_runs import build_home_best_runs
from core.home_summary import build_home_summary
from ui import home_preview as v6
from ui import home_preview_v8 as v8
from ui import home_preview_v10 as v10


def build_v11_goal_html(summary, *, mobile: bool = False) -> str:
    """Keep v10 desktop intact and give the compact goal a natural height."""
    markup = v10.build_v10_goal_html(summary, mobile=mobile)
    if not mobile:
        return markup

    return f"""
    <div class="v11-mobile-goal-shell">
        {markup}
        <style>
            @media (max-width:1200px) {{
                .v11-mobile-goal-shell .v8-goal-mobile {{
                    height:auto;
                    min-height:0;
                    padding:10px 12px 11px;
                    gap:6px;
                    overflow:visible;
                }}
                .v11-mobile-goal-shell .v8-goal-primary {{
                    display:grid;
                    grid-template-columns:auto minmax(0,1fr);
                    gap:6px 10px;
                    align-items:baseline;
                }}
                .v11-mobile-goal-shell .v8-goal-name {{
                    overflow:visible;
                    font-size:16px;
                    line-height:1.15;
                    text-overflow:clip;
                    white-space:normal;
                }}
                .v11-mobile-goal-shell .v8-goal-context {{
                    overflow:visible;
                    font-size:11.5px;
                    line-height:1.3;
                    text-overflow:clip;
                    white-space:normal;
                }}
                .v11-mobile-goal-shell .v8-goal-direction {{
                    display:grid;
                    grid-template-columns:auto minmax(0,1fr) auto;
                    gap:5px 9px;
                    align-items:baseline;
                    padding-top:7px;
                }}
                .v11-mobile-goal-shell .v8-goal-direction strong {{
                    min-width:0;
                    font-size:12.5px;
                    line-height:1.2;
                    white-space:normal;
                }}
                .v11-mobile-goal-shell .v8-goal-direction-copy {{
                    grid-column:1/-1;
                    grid-row:2;
                    overflow:visible;
                    font-size:11px;
                    line-height:1.3;
                    text-overflow:clip;
                    white-space:normal;
                }}
                .v11-mobile-goal-shell .v8-goal-status {{
                    grid-column:3;
                    grid-row:1;
                }}
            }}
        </style>
    </div>
    """


def build_v11_hero_html(athlete_id: int, home_summary, predictions, latest) -> str:
    """Use the approved v10 hero with the repaired compact goal."""
    return f"""
    <style>
        .v11-hero {{
            container-type:inline-size; display:grid;
            grid-template-columns:minmax(0,390px) minmax(0,1fr);
            gap:8px; align-items:stretch; width:100%;
        }}
        .v11-passport,.v11-hero-right {{ min-width:0; }}
        .v11-passport {{ display:flex; }}
        .v11-passport .pp-shell,
        .v11-passport .pp-passport {{ height:100%; }}
        .v11-passport .pp-passport {{ display:flex; flex-direction:column; }}
        .v11-passport .pp-development {{
            flex:1 1 auto; display:flex; flex-direction:column;
        }}
        .v11-passport .chart {{
            flex:1 1 39px; min-height:39px; max-height:82px; height:auto;
        }}
        .v11-hero-right {{ container-type:inline-size; }}
        .v11-mobile-goal {{ display:none; }}
        @media (max-width:1200px) {{
            .v11-hero {{ grid-template-columns:1fr; }}
            .v11-passport {{ display:block; }}
            .v11-passport .pp-shell,
            .v11-passport .pp-passport {{ height:auto; }}
            .v11-mobile-goal {{ display:block; margin-bottom:8px; }}
        }}
    </style>
    <div class="v11-hero">
        <div class="v11-passport v8-passport">
            {v8.build_athlete_card_html(athlete_id)}
            {v8._v8_passport_overrides()}
        </div>
        <div class="v11-hero-right">
            <div class="v11-mobile-goal">{build_v11_goal_html(home_summary, mobile=True)}</div>
            {v10.build_v10_intelligence_html(predictions, latest)}
        </div>
    </div>
    """


def show_home_preview_v11() -> None:
    st.markdown(
        """
        <style>
            [data-testid="stMainBlockContainer"] { max-width:1450px; padding-top:1.6rem; padding-bottom:3rem; }
            [data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"],
            [data-testid="stMainBlockContainer"] > div > [data-testid="stVerticalBlock"] { gap:8px; }
            [data-testid="stHeader"] { background:transparent; }
            .v11-preview-kicker { margin-bottom:0; color:#8a776a; font-size:.72rem; font-weight:800; letter-spacing:.12em; text-transform:uppercase; }
            [data-testid="stHorizontalBlock"]:has(.v11-selector-marker) { align-items:flex-start; gap:8px; }
            [data-testid="stElementContainer"]:has(.v11-selector-marker) { display:none; }
            [data-testid="stHorizontalBlock"]:has(.v11-selector-marker) [data-testid="stVerticalBlock"] { gap:0; }
            @media (max-width:1200px) {
                [data-testid="stHorizontalBlock"]:has(.v11-selector-marker) [data-testid="stColumn"]:last-child { display:none; }
                [data-testid="stHorizontalBlock"]:has(.v11-selector-marker) [data-testid="stColumn"]:first-child { flex:1 1 100%; width:100%; }
            }
        </style>
        <div class="v11-preview-kicker">Home preview · Responsive v11 polish</div>
        """,
        unsafe_allow_html=True,
    )

    selector_col, goal_col = st.columns([390, 1051], gap="small")
    with selector_col:
        st.markdown('<span class="v11-selector-marker"></span>', unsafe_allow_html=True)
        athlete_id = v10.render_v10_athlete_selector(
            key="home_preview_v11_athlete_selector",
        )

    if athlete_id is None:
        st.warning("No athletes found. Add an athlete first.")
        return

    home_summary = build_home_summary(athlete_id)
    with goal_col:
        st.html(build_v11_goal_html(home_summary))

    best_runs = build_home_best_runs(athlete_id)
    with st.spinner("Analysing real performance intelligence…"):
        predictions = v6._cached_home_predictions(athlete_id, v6.PREDICTIONS_CACHE_SCHEMA)
        predictions = v6._refresh_stale_predictions_contract(athlete_id, predictions)
        latest = v6._cached_home_latest_run(athlete_id)

    st.html(build_v11_hero_html(athlete_id, home_summary, predictions, latest))
    st.html(v10.build_v10_lower_html(home_summary, best_runs))


if __name__ == "__main__":
    st.set_page_config(
        page_title="Performance Passport · Home v11 Preview",
        page_icon="P",
        layout="wide",
    )
    show_home_preview_v11()
