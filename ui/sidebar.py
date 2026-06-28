import streamlit as st
from config import APP_NAME, VERSION


def show_sidebar():
    """Display the application sidebar."""

    st.sidebar.title(f"🏃 {APP_NAME}")
    st.sidebar.caption(f"Version {VERSION}")

    page = st.sidebar.radio(
        "Navigation",
        [
            "Dashboard",
            "Athletes",
            "Import",
            "Activities",
            "Settings",
        ],
    )

    st.sidebar.divider()
    st.sidebar.caption("Sprint 1 • Data Foundation")

    return page