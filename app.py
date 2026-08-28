import streamlit as st

from config import APP_NAME
from core import database
from theme import inject_global_theme
from ui.athletes import show_athletes_page
from ui.activities import show_activities_page
from ui.home import show_home_page
from ui.coaching_team import show_coaching_team_page
from ui.progress import show_progress_page
from ui.race_outlook import show_race_predictor_page
from ui.passport import show_passport_page
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
from ui.fuel_planner import show_fuel_planner_page
from ui.recovery_coach import show_recovery_coach_page
from ui.welcome import product_entry_granted, show_welcome_page
from ui.settings import show_settings_page


st.set_page_config(
    page_title=APP_NAME,
    page_icon="P",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_global_theme()


@st.cache_resource(show_spinner=False)
def _initialise_database_once(database_path: str, schema_version: int) -> bool:
    """Run schema checks once for this database and schema within the server."""
    del database_path, schema_version
    database.initialise_database()
    return True


_initialise_database_once(
    str(database.DATABASE_PATH.resolve()),
    database.CURRENT_SCHEMA_VERSION,
)

if not product_entry_granted(st.session_state, st.query_params):
    show_welcome_page()
    st.stop()

page = show_sidebar()

if page == "Home":
    show_home_page()

elif page == "Coaching Team":
    show_coaching_team_page()

elif page == "Journal":
    show_journal_page()

elif page == "Next Run":
    show_next_run_page()

elif page == "Learning":
    show_learning_page()

elif page == "Activities":
    show_activities_page()

elif page == "Progress":
    show_progress_page()

elif page == "Race Predictor":
    show_race_predictor_page()

elif page == "Goals":
    show_goals_page()

elif page == "Training Blocks":
    show_training_blocks_page()

elif page == "Fuel Planner":
    show_fuel_planner_page()

elif page == "Recovery Coach":
    show_recovery_coach_page()

elif page == "Hall of Fame":
    show_hall_of_fame_page()

elif page == "Passport":
    show_passport_page()

elif page == "Athletes":
    show_athletes_page()

elif page == "Import":
    show_import_page()

elif page == "Diagnostics":
    show_diagnostics_page()

elif page == "Settings":
    show_settings_page()
