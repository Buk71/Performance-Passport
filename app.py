import streamlit as st
from core.database import initialise_database

APP_NAME = "Performance Passport"
VERSION = "0.1.0"

initialise_database()

st.set_page_config(
    page_title=APP_NAME,
    page_icon="🏃",
    layout="wide",
)


def metric_card(title, value, caption):
    st.metric(label=title, value=value)
    st.caption(caption)


with st.sidebar:
    st.title("🏃 Performance Passport")
    st.caption(f"Version {VERSION}")

    page = st.radio(
        "Navigation",
        ["Dashboard", "Import", "Activities", "Settings"],
    )

    st.divider()
    st.caption("Sprint 1: Data Foundation")


st.title("Performance Passport")
st.subheader("Personal Running Intelligence")

st.write(
    "A coaching dashboard built to interpret your running data, not just display it."
)

st.divider()

if page == "Dashboard":
    st.header("Dashboard")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        metric_card("Activities", "0", "Runs imported")

    with col2:
        metric_card("Weekly miles", "0.0", "Current week")

    with col3:
        metric_card("Fitness estimate", "--", "Waiting for data")

    with col4:
        metric_card("Next goal", "Sub-19 5K", "Primary target")

    st.divider()

    st.subheader("Morning briefing")
    st.info(
        "Import your running data to unlock personalised coaching insight."
    )

elif page == "Import":
    st.header("Import")
    st.write("Upload FIT files and Runalyze exports here.")

elif page == "Activities":
    st.header("Activities")
    st.write("Your imported activity history will appear here.")

elif page == "Settings":
    st.header("Settings")
    st.write("Your athlete profile, zones and preferences will live here.")