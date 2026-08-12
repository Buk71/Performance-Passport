"""Final Home v10 polish built from the approved v9 composition.

Run with:
    streamlit run ui/home_preview_v10.py

V10 preserves v9's calculations, hierarchy, dimensions, and exact Passport to
Race Outlook baseline.  It only tidies display copy, selector naming, and
small-card alignment before the Home design moves to its next element.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from core.home_best_runs import build_home_best_runs
from core.home_summary import build_home_summary
from ui import athlete_selection
from ui import home_preview as v6
from ui import home_preview_v8 as v8
from ui import home_preview_v9 as v9


def _athlete_display_name(row) -> str:
    """Use the athlete's preferred Home display name without changing data."""
    first_name = str(row[1] or "").strip()
    last_name = str(row[2] or "").strip()
    if first_name.casefold() == "joanne":
        first_name = "Jo"
    return f"{first_name} {last_name}".strip()


def _goal_already_contains_target(goal_name: str, target_time_s: float | None) -> bool:
    """Recognise goal names such as 'Sub 39:00' and 'Sub 45'."""
    if target_time_s is None:
        return False

    target = v6._clock(target_time_s)
    goal_text = str(goal_name or "").casefold()
    if target.casefold() in goal_text:
        return True

    minutes, seconds = divmod(int(round(float(target_time_s))), 60)
    if seconds != 0:
        return False
    return re.search(rf"\bsub\s*{minutes}(?::00)?\b", goal_text) is not None


def _display_block_name(block_name: str) -> str:
    """Turn engine terminology into natural athlete-facing wording."""
    return re.sub(
        r"\badaptive direction\b",
        "development plan",
        str(block_name or ""),
        flags=re.IGNORECASE,
    )


def build_v10_goal_html(summary, *, mobile: bool = False) -> str:
    """Retain v9's compact goal strip while removing repeated information."""
    display_summary = replace(
        summary,
        block_name=_display_block_name(summary.block_name),
    )
    markup = v9.build_v9_goal_html(display_summary, mobile=mobile)

    if _goal_already_contains_target(summary.goal_name, summary.target_time_s):
        target = v6._safe(v6._clock(summary.target_time_s))
        markup = markup.replace(
            f'<span class="v8-goal-target">{target}</span>',
            "",
            1,
        )

    return f"""
    <div class="v10-goal-shell">
        {markup}
        <style>
            .v10-goal-shell .v8-goal-primary {{ gap:9px; }}
            .v10-goal-shell .v8-goal-name,
            .v10-goal-shell .v8-goal-direction strong {{
                font-variant-numeric:tabular-nums;
            }}
        </style>
    </div>
    """


def build_v10_intelligence_html(predictions, latest) -> str:
    """Make repeated result cards share a clean internal baseline."""
    return f"""
    <div class="v10-intelligence-shell">
        {v9.build_v9_intelligence_html(predictions, latest)}
        <style>
            .v10-intelligence-shell .v8-coach-time,
            .v10-intelligence-shell .v8-capability-range,
            .v10-intelligence-shell .v8-scenario-time {{
                font-variant-numeric:tabular-nums;
            }}
            .v10-intelligence-shell .v8-scenario {{
                display:flex; flex-direction:column;
            }}
            .v10-intelligence-shell .v8-scenario-copy {{
                flex:1 1 auto;
            }}
            .v10-intelligence-shell .v8-scenario-meta {{
                align-items:baseline; margin-top:auto; padding-top:5px;
            }}
            .v10-intelligence-shell .v8-scenario-meta span:last-child {{
                text-align:right; white-space:nowrap;
            }}
        </style>
    </div>
    """


def build_v10_hero_html(athlete_id: int, home_summary, predictions, latest) -> str:
    """Keep v9's exact desktop baseline with the tidied v10 content."""
    return f"""
    <style>
        .v10-hero {{
            container-type:inline-size; display:grid;
            grid-template-columns:minmax(0,390px) minmax(0,1fr);
            gap:8px; align-items:stretch; width:100%;
        }}
        .v10-passport,.v10-hero-right {{ min-width:0; }}
        .v10-passport {{ display:flex; }}
        .v10-passport .pp-shell,
        .v10-passport .pp-passport {{ height:100%; }}
        .v10-passport .pp-passport {{ display:flex; flex-direction:column; }}
        .v10-passport .pp-development {{
            flex:1 1 auto; display:flex; flex-direction:column;
        }}
        .v10-passport .chart {{
            flex:1 1 39px; min-height:39px; max-height:82px; height:auto;
        }}
        .v10-hero-right {{ container-type:inline-size; }}
        .v10-mobile-goal {{ display:none; }}
        @media (max-width:1200px) {{
            .v10-hero {{ grid-template-columns:1fr; }}
            .v10-passport {{ display:block; }}
            .v10-passport .pp-shell,
            .v10-passport .pp-passport {{ height:auto; }}
            .v10-mobile-goal {{ display:block; margin-bottom:8px; }}
        }}
    </style>
    <div class="v10-hero">
        <div class="v10-passport v8-passport">
            {v8.build_athlete_card_html(athlete_id)}
            {v8._v8_passport_overrides()}
        </div>
        <div class="v10-hero-right">
            <div class="v10-mobile-goal">{build_v10_goal_html(home_summary, mobile=True)}</div>
            {build_v10_intelligence_html(predictions, latest)}
        </div>
    </div>
    """


def build_v10_lower_html(home_summary, best_runs) -> str:
    """Preserve v9's lower layout while allowing useful week copy to breathe."""
    return f"""
    <div class="v10-lower-shell">
        {v9.build_v9_lower_html(home_summary, best_runs)}
        <style>
            .v10-lower-shell .home-day {{
                display:flex; flex-direction:column;
            }}
            .v10-lower-shell .home-day-title {{ flex:0 0 auto; }}
            .v10-lower-shell .home-day-detail {{
                flex:1 1 auto; overflow:visible;
            }}
            .v10-lower-shell .home-week-theme {{
                max-width:70%; line-height:1.2;
            }}
            .v10-lower-shell .home-next-detail {{ overflow-wrap:anywhere; }}
        </style>
    </div>
    """


def render_v10_athlete_selector(*, key: str) -> int | None:
    """Render the temporary preview selector with preferred display names."""
    athletes = athlete_selection.get_athletes()
    if not athletes:
        return None

    athlete_selection.initialise_selected_athlete(athletes)
    rows_by_id = {int(row[0]): row for row in athletes}
    athlete_ids = list(rows_by_id)
    current_id = int(st.session_state[athlete_selection.SESSION_ID_KEY])

    if key not in st.session_state or st.session_state[key] not in rows_by_id:
        st.session_state[key] = current_id if current_id in rows_by_id else athlete_ids[0]

    selected_id = st.selectbox(
        "Athlete",
        athlete_ids,
        key=key,
        label_visibility="collapsed",
        format_func=lambda athlete_id: _athlete_display_name(rows_by_id[athlete_id]),
    )
    canonical_name = athlete_selection.athlete_name(rows_by_id[selected_id])
    st.session_state[athlete_selection.SESSION_NAME_KEY] = canonical_name
    st.session_state[athlete_selection.SESSION_ID_KEY] = selected_id
    return selected_id


def show_home_preview_v10() -> None:
    st.markdown(
        """
        <style>
            [data-testid="stMainBlockContainer"] { max-width:1450px; padding-top:1.6rem; padding-bottom:3rem; }
            [data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"],
            [data-testid="stMainBlockContainer"] > div > [data-testid="stVerticalBlock"] { gap:8px; }
            [data-testid="stHeader"] { background:transparent; }
            .v10-preview-kicker { margin-bottom:0; color:#8a776a; font-size:.72rem; font-weight:800; letter-spacing:.12em; text-transform:uppercase; }
            [data-testid="stHorizontalBlock"]:has(.v10-selector-marker) { align-items:flex-start; gap:8px; }
            [data-testid="stElementContainer"]:has(.v10-selector-marker) { display:none; }
            [data-testid="stHorizontalBlock"]:has(.v10-selector-marker) [data-testid="stVerticalBlock"] { gap:0; }
            @media (max-width:1200px) {
                [data-testid="stHorizontalBlock"]:has(.v10-selector-marker) [data-testid="stColumn"]:last-child { display:none; }
                [data-testid="stHorizontalBlock"]:has(.v10-selector-marker) [data-testid="stColumn"]:first-child { flex:1 1 100%; width:100%; }
            }
        </style>
        <div class="v10-preview-kicker">Home preview · Final v10 polish</div>
        """,
        unsafe_allow_html=True,
    )

    selector_col, goal_col = st.columns([390, 1051], gap="small")
    with selector_col:
        st.markdown('<span class="v10-selector-marker"></span>', unsafe_allow_html=True)
        athlete_id = render_v10_athlete_selector(
            key="home_preview_v10_athlete_selector",
        )

    if athlete_id is None:
        st.warning("No athletes found. Add an athlete first.")
        return

    home_summary = build_home_summary(athlete_id)
    with goal_col:
        st.html(build_v10_goal_html(home_summary))

    best_runs = build_home_best_runs(athlete_id)
    with st.spinner("Analysing real performance intelligence…"):
        predictions = v6._cached_home_predictions(athlete_id, v6.PREDICTIONS_CACHE_SCHEMA)
        predictions = v6._refresh_stale_predictions_contract(athlete_id, predictions)
        latest = v6._cached_home_latest_run(athlete_id)

    st.html(build_v10_hero_html(athlete_id, home_summary, predictions, latest))
    st.html(build_v10_lower_html(home_summary, best_runs))


if __name__ == "__main__":
    st.set_page_config(
        page_title="Performance Passport · Home v10 Preview",
        page_icon="P",
        layout="wide",
    )
    show_home_preview_v10()
