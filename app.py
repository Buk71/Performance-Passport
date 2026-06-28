import streamlit as st

from config import APP_NAME
from core.database import initialise_database
from ui.dashboard import show_dashboard
from ui.sidebar import show_sidebar
from ui.athletes import show_athletes_page


st.set_page_config(
    page_title=APP_NAME,
    page_icon="🏃",
    layout="wide",
)

initialise_database()

page = show_sidebar()

if page == "Dashboard":
    show_dashboard()

elif page == "Athletes":
    show_athletes_page()

elif page == "Import":
    st.header("Import")
    st.write("Upload FIT files and Runalyze exports here.")

elif page == "Activities":
    st.header("Activities")
    st.write("Your imported activity history will appear here.")

elif page == "Settings":
    st.header("Settings")
    st.write("Your athlete profile, zones and preferences will live here.")