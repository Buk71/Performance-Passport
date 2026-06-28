import streamlit as st
from config import APP_NAME, APP_SUBTITLE


def show_dashboard():
    st.title(APP_NAME)
    st.subheader(APP_SUBTITLE)

    st.write(
        "A coaching dashboard built to interpret your running data, not just display it."
    )

    st.divider()

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Activities", "0")
    col2.metric("Weekly Miles", "0.0")
    col3.metric("Fitness", "--")
    col4.metric("Goal", "Sub-19")

    st.divider()

    st.subheader("Morning Briefing")

    st.info(
        "Import your first FIT file to begin building your Performance Passport."
    )