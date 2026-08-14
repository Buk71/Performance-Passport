import base64
from functools import lru_cache
from pathlib import Path

import streamlit as st

from config import APP_NAME, VERSION, VERSION_NAME
from ui.activity_navigation import read_activity_review_request
from ui.training_block_navigation import read_training_block_week_request


PRIMARY_NAVIGATION = [
    "Home",
    "Next Run",
    "Journal",
    "Activities",
    "Progress",
    "Race Predictor",
    "Hall of Fame",
    "Goals",
    "Training Blocks",
    "Fuel Planner",
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
ROOT = Path(__file__).resolve().parent.parent
LOGO_PATH = ROOT / "assets" / "brand" / "pp_logo.png"


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


def show_sidebar():
    """Display the Performance Passport navigation."""

    st.sidebar.markdown(build_sidebar_brand_html(), unsafe_allow_html=True)

    st.sidebar.markdown(
        '<div class="pp-sidebar-section">Your running</div>',
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

    if read_activity_review_request(st.query_params) is not None:
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
    )

    st.sidebar.markdown(
        f"""
        <div class="pp-sidebar-footer">
            <div class="pp-sidebar-footer-label">Current release</div>
            <div class="pp-sidebar-footer-title">{VERSION_NAME}</div>
            <div class="pp-sidebar-footer-meta">Version {VERSION}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    return page
