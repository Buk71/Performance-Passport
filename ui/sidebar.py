import base64
from functools import lru_cache
from html import escape
from pathlib import Path

import streamlit as st

from config import APP_NAME, VERSION
from ui.activity_navigation import read_activity_review_request
from ui.training_block_navigation import read_training_block_week_request
from ui.coaching_navigation import read_coaching_team_request
from ui.training_coach_navigation import read_training_coach_request
from ui.nutrition_coach_navigation import read_nutrition_coach_request
from ui.recovery_coach_navigation import read_recovery_coach_request


PRIMARY_NAVIGATION = [
    "Home",
    "Coaching Team",
    "Next Run",
    "Journal",
    "Activities",
    "Progress",
    "Race Predictor",
    "Hall of Fame",
    "Goals",
    "Training Blocks",
    "Fuel Planner",
    "Recovery Coach",
    "Passport",
    "Learning",
]

MANAGEMENT_NAVIGATION = [
    "Athletes",
    "Import",
    "Diagnostics",
    "Settings",
]

ALL_NAVIGATION = [*PRIMARY_NAVIGATION, *MANAGEMENT_NAVIGATION]

# The route values above are deliberately stable: existing Home links,
# bookmarks and AppTest navigation continue to use them.  The premium menu
# presents the athlete-facing coach names through ``format_func`` instead.
NAVIGATION_LABELS = {
    "Home": "Lead Coach",
    "Coaching Team": "Coaching Team",
    "Next Run": "Training Coach",
    "Journal": "Journal",
    "Activities": "Workout Coach",
    "Progress": "Progress Coach",
    "Race Predictor": "Race Coach",
    "Hall of Fame": "Hall of Fame",
    "Goals": "Goal Coach",
    "Training Blocks": "Training Blocks",
    "Fuel Planner": "Nutrition Coach",
    "Recovery Coach": "Recovery Coach",
    "Passport": "Athlete Passport",
    "Learning": "Learning Coach",
    "Athletes": "Athletes",
    "Import": "Import Data",
    "Diagnostics": "Diagnostics",
    "Settings": "Settings",
}
ROOT = Path(__file__).resolve().parent.parent
LOGO_PATH = ROOT / "assets" / "brand" / "pp_logo.png"
ATHLETE_IMAGE_PATHS = {
    "richard burke": ROOT / "assets" / "athletes" / "richard_burke.jpg",
    "jo burke": ROOT / "assets" / "athletes" / "joanne_burke.jpg",
    "joanne burke": ROOT / "assets" / "athletes" / "joanne_burke.jpg",
    "paul farrell": ROOT / "assets" / "athletes" / "paul_farrell.jpg",
}


@lru_cache(maxsize=1)
def brand_logo_data_uri() -> str:
    """Return the real Pathmark brand asset for the sidebar."""
    if not LOGO_PATH.exists():
        return ""
    encoded = base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def build_sidebar_brand_html() -> str:
    logo_uri = brand_logo_data_uri()
    logo = (
        f'<img class="pp-sidebar-logo" src="{logo_uri}" '
        'alt="Performance Passport Pathmark">'
        if logo_uri else '<div class="pp-sidebar-logo-fallback">PP</div>'
    )
    return f"""
        <div class="pp-brand">
            <div class="pp-sidebar-logo-wrap">{logo}</div>
            <div class="pp-brand-copy">
                <div class="pp-brand-title">{APP_NAME}</div>
                <div class="pp-v21-motto">Every run has something to give.</div>
            </div>
        </div>
    """


def navigation_label(route: str) -> str:
    """Return the premium display label without changing the stable route."""
    return NAVIGATION_LABELS.get(route, route)


@lru_cache(maxsize=8)
def athlete_image_data_uri(athlete_name: str) -> str:
    path = ATHLETE_IMAGE_PATHS.get(str(athlete_name or "").strip().lower())
    if path is None or not path.exists():
        return ""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def build_sidebar_account_html(athlete_name: str | None) -> str:
    """Build the lightweight athlete footer without another database call."""
    clean_name = " ".join(str(athlete_name or "").split()) or "Choose athlete"
    safe_name = escape(clean_name)
    initials = "".join(part[0] for part in clean_name.split()[:2]).upper() or "PP"
    image_uri = athlete_image_data_uri(clean_name)
    avatar = (
        f'<img src="{image_uri}" alt="" aria-hidden="true">'
        if image_uri
        else f'<span>{escape(initials)}</span>'
    )
    return f"""
        <div class="pp-sidebar-account">
            <div class="pp-sidebar-avatar">{avatar}</div>
            <div class="pp-sidebar-account-copy">
                <strong>{safe_name}</strong>
                <span>Athlete account</span>
            </div>
            <div class="pp-sidebar-live" title="Live athlete profile"></div>
        </div>
        <div class="pp-sidebar-release">Performance Passport · v{escape(VERSION)}</div>
    """


def show_sidebar():
    """Display the Performance Passport navigation."""

    st.sidebar.markdown(build_sidebar_brand_html(), unsafe_allow_html=True)

    st.sidebar.markdown(
        '<div class="pp-sidebar-section">Your coaching</div>',
        unsafe_allow_html=True,
    )

    # One-release migration for sessions saved before Coach Home was renamed.
    if st.session_state.get("primary_navigation") == "Coach":
        st.session_state["primary_navigation"] = "Home"

    legacy_management = st.session_state.pop("management_navigation", None)
    if legacy_management in MANAGEMENT_NAVIGATION:
        st.session_state["primary_navigation"] = legacy_management

    requested_page = st.session_state.pop(
        "pp_navigation_request",
        None,
    )

    if read_coaching_team_request(st.query_params) is not None:
        requested_page = "Coaching Team"
    elif read_training_coach_request(st.query_params) is not None:
        requested_page = "Next Run"
    elif read_nutrition_coach_request(st.query_params) is not None:
        requested_page = "Fuel Planner"
    elif read_recovery_coach_request(st.query_params) is not None:
        requested_page = "Recovery Coach"
    elif read_activity_review_request(st.query_params) is not None:
        requested_page = "Activities"
    elif read_training_block_week_request(st.query_params) is not None:
        requested_page = "Training Blocks"

    if requested_page == "Coach":
        requested_page = "Home"

    if (
        requested_page in ALL_NAVIGATION
        and requested_page != st.session_state.get("primary_navigation")
    ):
        st.session_state["primary_navigation"] = requested_page

    page = st.sidebar.radio(
        "Primary navigation",
        ALL_NAVIGATION,
        key="primary_navigation",
        format_func=navigation_label,
    )

    st.sidebar.markdown(
        build_sidebar_account_html(st.session_state.get("selected_athlete_name")),
        unsafe_allow_html=True,
    )

    return page
