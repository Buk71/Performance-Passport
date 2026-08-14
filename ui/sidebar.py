import streamlit as st

from config import APP_NAME, VERSION, VERSION_NAME
from ui.activity_navigation import read_activity_review_request


PRIMARY_NAVIGATION = [
    "Home",
    "Journal",
    "Next Run",
    "Learning",
    "Activities",
    "Progress",
    "Race Predictor",
    "Goals",
    "Training Blocks",
    "Hall of Fame",
    "Passport",
]

MANAGEMENT_NAVIGATION = [
    "Athletes",
    "Import",
    "Diagnostics",
    "Settings",
]


def show_sidebar():
    """Display the Performance Passport navigation."""

    st.sidebar.markdown(
        f"""
        <div class="pp-brand">
            <svg class="pp-v21-pathmark" viewBox="0 0 48 48" aria-label="Performance Passport">
                <rect x="1" y="1" width="46" height="46" rx="14" fill="#10263D"/>
                <path d="M13 35V13h8.2c6.1 0 9.6 3.1 9.6 8.1 0 4.9-3.5 8-9.6 8H18" fill="none" stroke="#F7F3EC" stroke-width="4.2" stroke-linecap="round" stroke-linejoin="round"/>
                <path d="M24 35V13h7.2c5.5 0 8.8 2.8 8.8 7.3 0 4.4-3.3 7.2-8.8 7.2H29" fill="none" stroke="#F7F3EC" stroke-width="4.2" stroke-linecap="round" stroke-linejoin="round"/>
                <path d="M11 31C19 27 24 23 29 17c3-3.6 6-5.7 10-6.5" fill="none" stroke="#F05A28" stroke-width="3.2" stroke-linecap="round"/>
            </svg>
            <div>
                <div class="pp-brand-title">{APP_NAME}</div>
                <div class="pp-v21-motto">Every run has something to give.</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.sidebar.markdown(
        '<div class="pp-sidebar-section">Your running</div>',
        unsafe_allow_html=True,
    )

    # One-release migration for sessions saved before Coach Home was renamed.
    if st.session_state.get("primary_navigation") == "Coach":
        st.session_state["primary_navigation"] = "Home"

    requested_page = st.session_state.pop(
        "pp_navigation_request",
        None,
    )

    if read_activity_review_request(st.query_params) is not None:
        requested_page = "Activities"

    if requested_page == "Coach":
        requested_page = "Home"

    if (
        requested_page in PRIMARY_NAVIGATION
        and requested_page != st.session_state.get("primary_navigation")
    ):
        st.session_state["primary_navigation"] = requested_page

    primary_page = st.sidebar.radio(
        "Primary navigation",
        PRIMARY_NAVIGATION,
        key="primary_navigation",
    )

    st.sidebar.divider()

    st.sidebar.markdown(
        '<div class="pp-sidebar-section">Manage</div>',
        unsafe_allow_html=True,
    )

    management_page = st.sidebar.radio(
        "Management navigation",
        ["None", *MANAGEMENT_NAVIGATION],
        index=0,
        key="management_navigation",
        label_visibility="collapsed",
    )

    page = management_page if management_page != "None" else primary_page

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
