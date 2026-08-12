"""Production Coach Home for Performance Passport v0.22.1.

This module promotes the approved v11 responsive Home composition without
changing its calculations, athlete-specific content, or layout. The earlier
preview modules remain available as the visual rollback history.
"""

from __future__ import annotations

import re

import streamlit as st

from core.home_best_runs import build_home_best_runs
from core.home_summary import build_home_summary
from ui import home_preview as home_components
from ui import home_preview_v8 as approved_v8
from ui import home_preview_v10 as approved_v10
from ui import home_preview_v11 as approved_v11


def build_production_goal_html(summary, *, mobile: bool = False) -> str:
    """Expose the approved goal treatment through the production module."""
    return approved_v11.build_v11_goal_html(summary, mobile=mobile)


def build_production_hero_html(athlete_id, summary, predictions, latest) -> str:
    """Expose the approved hero with a sidebar-aware intermediate layout."""
    intelligence_markup = approved_v10.build_v10_intelligence_html(
        predictions,
        latest,
    )

    # The approved intelligence renderer returns both sections as one rail.
    # Reuse its exact generated sections and styles in a second, hidden-by-
    # default composition so the intermediate layout can place Race Outlook
    # on a true full-width row without recalculating or rewriting content.
    styles = "\n".join(
        re.findall(r"<style>.*?</style>", intelligence_markup, re.DOTALL)
    )
    intelligence_section = re.search(
        r'<section class="v8-intelligence">.*?</section>',
        intelligence_markup,
        re.DOTALL,
    )
    outlook_section = re.search(
        r'<section class="v8-outlook">.*?</section>',
        intelligence_markup,
        re.DOTALL,
    )

    if intelligence_section is None or outlook_section is None:
        # Safe fallback: the approved v11 output remains fully functional if
        # a future renderer changes its internal HTML contract.
        return approved_v11.build_v11_hero_html(
            athlete_id,
            summary,
            predictions,
            latest,
        )

    return f"""
    <div class="production-home-hero-container">
        {styles}
        <div class="production-home-hero v9-intelligence-shell v10-intelligence-shell">
            <div class="production-home-passport v8-passport">
                {approved_v8.build_athlete_card_html(athlete_id)}
                {approved_v8._v8_passport_overrides()}
            </div>
            <div class="production-home-mobile-goal">
                {build_production_goal_html(summary, mobile=True)}
            </div>
            <div class="production-home-intelligence">
                {intelligence_section.group(0)}
            </div>
            <div class="production-home-outlook">
                {outlook_section.group(0)}
            </div>
        </div>
        <style>
            .production-home-hero-container {{
                container-type:inline-size;
                width:100%;
            }}
            .production-home-hero {{
                display:grid;
                height:auto;
                grid-template-columns:minmax(0,390px) minmax(0,1fr);
                grid-template-rows:auto auto;
                gap:8px;
                align-items:stretch;
                width:100%;
            }}
            .production-home-passport {{
                grid-column:1;
                grid-row:1 / 3;
                display:flex;
                min-width:0;
            }}
            .production-home-passport .pp-shell,
            .production-home-passport .pp-passport {{ height:100%; }}
            .production-home-mobile-goal {{ display:none; }}
            .production-home-intelligence {{
                grid-column:2;
                grid-row:1;
                min-width:0;
            }}
            .production-home-outlook {{
                grid-column:2;
                grid-row:2;
                min-width:0;
            }}

            /*
             * A wide browser with Streamlit's sidebar open has an
             * intermediate content width. Use an explicit two-row grid so
             * the Passport has a deliberate baseline and Race Outlook can
             * use the full available width. The approved wide and mobile
             * compositions remain untouched.
             */
            @media (min-width:1201px) {{
                @container (max-width:1200px) {{
                    .production-home-passport {{
                        grid-column:1;
                        grid-row:1;
                    }}
                    .production-home-intelligence {{
                        grid-column:2;
                        grid-row:1;
                    }}
                    .production-home-intelligence .v8-intelligence {{
                        display:flex;
                        flex-direction:column;
                        height:100%;
                    }}
                    .production-home-intelligence .v8-intelligence-grid {{
                        flex:1 1 auto;
                        grid-template-columns:minmax(245px,.82fr) minmax(0,1.18fr);
                    }}
                    .production-home-intelligence .v8-latest,
                    .production-home-intelligence .v8-coaches {{
                        display:flex;
                        flex-direction:column;
                    }}
                    .production-home-intelligence .v8-benefit,
                    .production-home-intelligence .v8-coach-footer {{
                        margin-top:auto;
                    }}
                    .production-home-intelligence .v8-coach-grid {{
                        grid-template-columns:repeat(3,minmax(0,1fr));
                        gap:5px;
                    }}
                    .production-home-intelligence .v8-coach {{
                        overflow:hidden;
                        padding:7px 6px;
                    }}
                    .production-home-intelligence .v8-coach-copy {{
                        font-size:10px;
                        line-height:1.2;
                    }}
                    .production-home-outlook {{
                        grid-column:1 / -1;
                        grid-row:2;
                    }}
                    .production-home-outlook .v8-outlook-band {{
                        grid-template-columns:minmax(220px,1.2fr) repeat(5,minmax(105px,1fr));
                    }}
                }}
            }}
            @media (max-width:1200px) {{
                .production-home-hero {{
                    grid-template-columns:1fr;
                    grid-template-rows:auto;
                }}
                .production-home-passport,
                .production-home-mobile-goal,
                .production-home-intelligence,
                .production-home-outlook {{
                    grid-column:1;
                    grid-row:auto;
                }}
                .production-home-passport {{ display:block; }}
                .production-home-passport .pp-shell,
                .production-home-passport .pp-passport {{ height:auto; }}
                .production-home-mobile-goal {{ display:block; }}
            }}
        </style>
    </div>
    """


def show_home_page() -> None:
    """Render the locked production Home using real athlete data."""
    st.markdown(
        """
        <style>
            [data-testid="stMainBlockContainer"] {
                max-width:1450px;
                padding-top:4.25rem;
                padding-bottom:3rem;
            }
            [data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"],
            [data-testid="stMainBlockContainer"] > div > [data-testid="stVerticalBlock"] {
                gap:8px;
            }
            [data-testid="stHeader"] { background:transparent; }
            [data-testid="stHorizontalBlock"]:has(.production-home-selector-marker) {
                align-items:flex-start;
                gap:8px;
            }
            [data-testid="stElementContainer"]:has(.production-home-selector-marker) {
                display:none;
            }
            [data-testid="stHorizontalBlock"]:has(.production-home-selector-marker)
            [data-testid="stVerticalBlock"] {
                gap:0;
            }
            @media (min-width:1201px) and (max-width:1550px) {
                [data-testid="stAppViewContainer"] .v8-goal-strip {
                    grid-template-columns:minmax(175px,.82fr) minmax(155px,.72fr) minmax(245px,1.2fr);
                    gap:8px;
                    padding-left:9px;
                    padding-right:9px;
                }
                [data-testid="stAppViewContainer"] .v8-goal-direction {
                    gap:6px;
                    padding-left:9px;
                }
                [data-testid="stAppViewContainer"] .v8-goal-status {
                    padding-left:5px;
                    padding-right:5px;
                    letter-spacing:.02em;
                }
            }
            @media (max-width:1200px) {
                [data-testid="stHorizontalBlock"]:has(.production-home-selector-marker)
                [data-testid="stColumn"]:last-child {
                    display:none;
                }
                [data-testid="stHorizontalBlock"]:has(.production-home-selector-marker)
                [data-testid="stColumn"]:first-child {
                    flex:1 1 100%;
                    width:100%;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    selector_col, goal_col = st.columns([390, 1051], gap="small")
    with selector_col:
        st.markdown(
            '<span class="production-home-selector-marker"></span>',
            unsafe_allow_html=True,
        )
        athlete_id = approved_v10.render_v10_athlete_selector(
            key="production_home_athlete_selector",
        )

    if athlete_id is None:
        st.warning("No athletes found. Add an athlete first.")
        return

    summary = build_home_summary(athlete_id)
    with goal_col:
        st.html(build_production_goal_html(summary))

    best_runs = build_home_best_runs(athlete_id)
    with st.spinner("Analysing real performance intelligence…"):
        predictions = home_components._cached_home_predictions(
            athlete_id,
            home_components.PREDICTIONS_CACHE_SCHEMA,
        )
        predictions = home_components._refresh_stale_predictions_contract(
            athlete_id,
            predictions,
        )
        latest = home_components._cached_home_latest_run(athlete_id)

    st.html(
        build_production_hero_html(
            athlete_id,
            summary,
            predictions,
            latest,
        )
    )
    st.html(approved_v10.build_v10_lower_html(summary, best_runs))
