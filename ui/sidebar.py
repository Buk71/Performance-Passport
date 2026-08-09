import streamlit as st

from config import APP_NAME, VERSION, VERSION_NAME


PRIMARY_NAVIGATION = [
    "Coach",
    "Journal",
    "Next Run",
    "Today's Session",
    "Activities",
    "Progress",
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
            <div class="pp-brand-mark">PP</div>
            <div>
                <div class="pp-brand-title">{APP_NAME}</div>
                <div class="pp-brand-subtitle">
                    Personal Running Intelligence
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.sidebar.markdown(
        '<div class="pp-sidebar-section">Your running</div>',
        unsafe_allow_html=True,
    )

    requested_page = st.session_state.pop(
        "pp_navigation_request",
        None,
    )

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
