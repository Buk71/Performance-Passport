import streamlit as st

from config import APP_NAME
from core.database import initialise_database
from ui.dashboard import show_dashboard
from ui.sidebar import show_sidebar
from ui.athletes import show_athletes_page
from ui.import_page import show_import_page


st.set_page_config(
    page_title=APP_NAME,
    page_icon="🏃",
    layout="wide",
)

# Create the database if it doesn't exist
initialise_database()

# Sidebar navigation
page = show_sidebar()

# Page routing
if page == "Dashboard":
    show_dashboard()

elif page == "Athletes":
    show_athletes_page()

elif page == "Import":
    show_import_page()

elif page == "Activities":
    st.header("Activities")
    st.write("Your imported activity history will appear here.")