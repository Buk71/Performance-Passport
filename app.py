import streamlit as st

from config import APP_NAME
from core.database import initialise_database
from theme import inject_global_theme, render_page_placeholder
from ui.athletes import show_athletes_page
from ui.dashboard import show_dashboard
from ui.diagnostics import show_diagnostics_page
from ui.import_page import show_import_page
from ui.hall_of_fame import show_hall_of_fame_page
from ui.journal import show_journal_page
from ui.learning import show_learning_page
from ui.next_run import show_next_run_page
from ui.todays_session import show_todays_session_page
from ui.goals import show_goals_page
from ui.sidebar import show_sidebar
from ui.training_blocks import show_training_blocks_page
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

elif page == "Journal":
    show_journal_page()

elif page == "Next Run":
    show_next_run_page()

elif page == "Next Run":
    show_todays_session_page()

elif page == "Learning":
    show_learning_page()

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

elif page == "Goals":
    show_goals_page()

elif page == "Training Blocks":
    show_training_blocks_page()

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
