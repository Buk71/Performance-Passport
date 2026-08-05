import streamlit as st

from config import APP_NAME
from core.database import initialise_database
from theme import inject_global_theme, render_page_placeholder
from ui.athletes import show_athletes_page
from ui.dashboard import show_dashboard
from ui.diagnostics import show_diagnostics_page
from ui.import_page import show_import_page
from ui.hall_of_fame import show_hall_of_fame_page
from ui.sidebar import show_sidebar
from ui.settings import show_settings_page


st.set_page_config(
    page_title=APP_NAME,
    page_icon="🏃",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_global_theme()
initialise_database()

page = show_sidebar()

if page == "Coach":
    show_dashboard()

elif page == "Activities":
    render_page_placeholder(
        title="Activities",
        question="What happened?",
        description=(
            "Your running history will become a clean activity timeline, "
            "with every session summarised through performance, context and "
            "coaching meaning."
        ),
    )

elif page == "Progress":
    render_page_placeholder(
        title="Progress",
        question="Am I improving?",
        description=(
            "This screen will track aerobic fitness, threshold, running "
            "economy, consistency, durability and recovery—with direction, "
            "context and confidence."
        ),
    )

elif page == "Goal":
    render_page_placeholder(
        title="Goal",
        question="Am I getting closer?",
        description=(
            "Goal Progress will connect your training history to a chosen "
            "objective, showing current prediction, strengths, limiters and "
            "the next meaningful milestone."
        ),
    )

elif page == "Hall of Fame":
    show_hall_of_fame_page()

elif page == "Passport":
    render_page_placeholder(
        title="Passport",
        question="What has the app learned about me?",
        description=(
            "Your Performance Passport will bring together discoveries, "
            "personal tendencies, evidence levels, achievements and the "
            "unique patterns learned from your running history."
        ),
    )

elif page == "Athletes":
    show_athletes_page()

elif page == "Import":
    show_import_page()

elif page == "Diagnostics":
    show_diagnostics_page()

elif page == "Settings":
    show_settings_page()
