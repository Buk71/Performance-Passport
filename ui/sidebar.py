import base64
from functools import lru_cache
from html import escape
from pathlib import Path

import streamlit as st

from config import APP_NAME, VERSION
from ui.activity_navigation import read_activity_review_request
from ui.training_block_navigation import read_training_block_week_request
from ui.coaching_navigation import read_coaching_team_request
from ui.training_coach_navigation import read_training_coach_request
from ui.nutrition_coach_navigation import read_nutrition_coach_request
from ui.recovery_coach_navigation import read_recovery_coach_request


PRIMARY_NAVIGATION = [
    # Overview
    "Home",
    "Passport",
    "Journal",
    "Hall of Fame",
    # Running Team
    "Coaching Team",
    "Next Run",
    "Activities",
    "Progress",
    "Race Predictor",
    "Recovery Coach",
    "Learning",
    # Training Set Up
    "Goals",
    "Training Blocks",
    "Fuel Planner",
]

MANAGEMENT_NAVIGATION = [
    "Athletes",
    "Import",
    "Diagnostics",
    "Settings",
]

ALL_NAVIGATION = [*PRIMARY_NAVIGATION, *MANAGEMENT_NAVIGATION]

# Route values remain stable so existing links, AppTest navigation and
# bookmarks keep working. Only athlete-facing copy and order change here.
NAVIGATION_LABELS = {
    "Home": "Lead Coach",
    "Passport": "Athlete Passport",
    "Journal": "Journal",
    "Hall of Fame": "Hall of Fame",
    "Coaching Team": "Coaching Summary",
    "Next Run": "Training Coach",
    "Activities": "Workout Coach",
    "Progress": "Progress Coach",
    "Race Predictor": "Race Coach",
    "Recovery Coach": "Recovery Coach",
    "Learning": "Learning Coach",
    "Goals": "Goal Coach",
    "Training Blocks": "Training Blocks",
    "Fuel Planner": "Nutrition Coach",
    "Athletes": "Athletes",
    "Import": "Import Data",
    "Diagnostics": "Diagnostics",
    "Settings": "Settings",
}

NAVIGATION_DESCRIPTIONS = {
    "Home": "What matters most in your running right now.",
    "Passport": "Your performance profile, PBs and current potential.",
    "Journal": "Your running story, notes and key moments.",
    "Hall of Fame": "Celebrate the runs and achievements that stand out.",
    "Coaching Team": "See what your coaching team thinks matters most.",
    "Next Run": "Understand your training load and what to focus on next.",
    "Activities": "Review your latest run and its training impact.",
    "Progress": "See whether you are improving and what is driving it.",
    "Race Predictor": "See what you could race today and how to get faster.",
    "Recovery Coach": "Understand readiness, fatigue and when to ease off.",
    "Learning": "Discover what your running data is teaching us about you.",
    "Goals": "Set the outcome you are training towards.",
    "Training Blocks": "Turn your goal into a structured week-by-week plan.",
    "Fuel Planner": "Plan daily fuelling and your weekly food shop.",
    "Athletes": "Manage the runners using this Performance Passport.",
    "Import": "Bring in new activities and training data.",
    "Diagnostics": "Check data quality and coaching recognition.",
    "Settings": "Manage preferences and app configuration.",
}

NAVIGATION_SECTIONS = {
    "Overview": {
        "description": "Your running at a glance.",
        "routes": ["Home", "Passport", "Journal", "Hall of Fame"],
    },
    "Running Team": {
        "description": "Specialist coaches, each with a different job.",
        "routes": [
            "Coaching Team", "Next Run", "Activities", "Progress",
            "Race Predictor", "Recovery Coach", "Learning",
        ],
    },
    "Training Set Up": {
        "description": "Set the destination and build the plan.",
        "routes": ["Goals", "Training Blocks", "Fuel Planner"],
    },
    "Admin": {
        "description": "Athletes, data and app controls.",
        "routes": MANAGEMENT_NAVIGATION,
    },
}

NAVIGATION_ICONS = {
    "Home": "<svg viewBox='0 0 24 24' aria-hidden='true'><path d='M3 11.5 12 4l9 7.5M5.5 10v10h13V10M9 20v-6h6v6'/></svg>",
    "Passport": "<svg viewBox='0 0 24 24' aria-hidden='true'><rect x='4' y='3' width='16' height='18' rx='2'/><circle cx='9' cy='9' r='2'/><path d='M13 8h4m-4 4h4M7 16h10'/></svg>",
    "Journal": "<svg viewBox='0 0 24 24' aria-hidden='true'><path d='M5 4.5h11a3 3 0 0 1 3 3V20H8a3 3 0 0 1-3-3V4.5Zm0 12.5a3 3 0 0 1 3-3h11M9 8h6'/></svg>",
    "Hall of Fame": "<svg viewBox='0 0 24 24' aria-hidden='true'><path d='M8 3h8l1 5 4 3-3 4 .5 6L12 18l-6.5 3L6 15l-3-4 4-3 1-5Z'/><path d='m9.5 11.5 1.6 1.6 3.6-3.6'/></svg>",
    "Coaching Team": "<svg viewBox='0 0 24 24' aria-hidden='true'><circle cx='8' cy='8' r='3'/><path d='M3 20v-2a5 5 0 0 1 10 0v2'/><path d='M16 10a2.5 2.5 0 1 0 0-5M15 13a4 4 0 0 1 6 3.5V19'/></svg>",
    "Next Run": "<svg viewBox='0 0 24 24' aria-hidden='true'><path d='m13 2-8 12h7l-1 8 8-12h-7l1-8Z'/></svg>",
    "Activities": "<svg viewBox='0 0 24 24' aria-hidden='true'><path d='M3 12h4l2-6 4 12 2-6h6'/></svg>",
    "Progress": "<svg viewBox='0 0 24 24' aria-hidden='true'><path d='M4 18 10 12l4 4 6-9m-5 0h5v5'/></svg>",
    "Race Predictor": "<svg viewBox='0 0 24 24' aria-hidden='true'><path d='M5 21V4m0 1h12l-2 4 2 4H5'/></svg>",
    "Recovery Coach": "<svg viewBox='0 0 24 24' aria-hidden='true'><path d='M3 12h4l2-5 4 10 2-5h6'/><path d='M7 4.5A5 5 0 0 1 12 7a5 5 0 0 1 5-2.5'/></svg>",
    "Learning": "<svg viewBox='0 0 24 24' aria-hidden='true'><path d='M9 18h6m-5 3h4'/><path d='M18 10a6 6 0 1 0-12 0c0 2.4 1.2 3.8 2.5 5 .8.7 1.2 1.3 1.3 2h4.4c.1-.7.5-1.3 1.3-2 1.3-1.2 2.5-2.6 2.5-5Z'/></svg>",
    "Goals": "<svg viewBox='0 0 24 24' aria-hidden='true'><circle cx='12' cy='12' r='8'/><circle cx='12' cy='12' r='3'/><path d='m17.5 6.5 3-3'/></svg>",
    "Training Blocks": "<svg viewBox='0 0 24 24' aria-hidden='true'><rect x='3' y='5' width='18' height='16' rx='2'/><path d='M7 3v4m10-4v4M3 10h18M8 14h3m2 0h3m-8 3h3'/></svg>",
    "Fuel Planner": "<svg viewBox='0 0 24 24' aria-hidden='true'><circle cx='12' cy='12' r='8'/><path d='M12 7v10M7 12h10'/></svg>",
    "Athletes": "<svg viewBox='0 0 24 24' aria-hidden='true'><circle cx='9' cy='8' r='3'/><path d='M3 20v-2a6 6 0 0 1 12 0v2m3-8v6m-3-3h6'/></svg>",
    "Import": "<svg viewBox='0 0 24 24' aria-hidden='true'><path d='M12 3v12m-5-5 5 5 5-5M5 20h14'/></svg>",
    "Diagnostics": "<svg viewBox='0 0 24 24' aria-hidden='true'><circle cx='12' cy='12' r='8'/><path d='M12 8v4m0 4h.01'/></svg>",
    "Settings": "<svg viewBox='0 0 24 24' aria-hidden='true'><circle cx='12' cy='12' r='3'/><path d='M12 3v2m0 14v2M3 12h2m14 0h2M5.6 5.6 7 7m10 10 1.4 1.4M18.4 5.6 17 7M7 17l-1.4 1.4'/></svg>",
}


def build_navigation_card_html(route: str, active_route: str) -> str:
    """Build the visual card; Streamlit owns the actual click target."""
    active = " is-active" if route == active_route else ""
    return (
        f'<div class="pp-nav-card{active}">'
        f'<span class="pp-nav-card-icon">{NAVIGATION_ICONS.get(route, "")}</span>'
        '<span class="pp-nav-card-copy">'
        f'<strong>{escape(navigation_label(route))}</strong>'
        f'<span>{escape(NAVIGATION_DESCRIPTIONS[route])}</span>'
        '</span>'
        '<span class="pp-nav-card-arrow" aria-hidden="true">&rsaquo;</span>'
        '</div>'
    )


def build_navigation_html(active_route: str) -> str:
    """Build a static representation used by design tests and previews."""
    groups = []
    for section, data in NAVIGATION_SECTIONS.items():
        cards = [build_navigation_card_html(route, active_route) for route in data["routes"]]
        groups.append(
            '<section class="pp-nav-group">'
            f'<div class="pp-nav-group-heading">{escape(section)}</div>'
            f'<div class="pp-nav-group-description">{escape(data["description"])}</div>'
            f'<div class="pp-nav-card-list">{"".join(cards)}</div>'
            '</section>'
        )
    return '<nav class="pp-navigation" aria-label="Performance Passport navigation">' + ''.join(groups) + '</nav>'


def _navigation_widget_key(route: str) -> str:
    safe = ''.join(char.lower() if char.isalnum() else '_' for char in route).strip('_')
    return f"pp_nav_{safe}"


def _select_navigation(route: str) -> None:
    """Update the stable route before Streamlit performs its normal rerun."""
    st.session_state["primary_navigation"] = route


def render_navigation_cards(active_route: str) -> None:
    """Render premium cards with native Streamlit buttons overlaid on them.

    The visible card remains our authored HTML, while the invisible native
    button supplies the click event. Streamlit runs the callback before its
    normal widget rerun, so navigation stays in the same session with no
    browser reload and no extra explicit rerun.
    """
    for section_index, (section, data) in enumerate(NAVIGATION_SECTIONS.items()):
        first_class = " is-first" if section_index == 0 else ""
        st.sidebar.markdown(
            f'<div class="pp-nav-group-intro{first_class}">'
            f'<div class="pp-nav-group-heading">{escape(section)}</div>'
            f'<div class="pp-nav-group-description">{escape(data["description"])}</div>'
            '</div>',
            unsafe_allow_html=True,
        )

        for route in data["routes"]:
            widget_key = _navigation_widget_key(route)
            with st.sidebar.container(key=widget_key):
                st.markdown(
                    build_navigation_card_html(route, active_route),
                    unsafe_allow_html=True,
                )
                st.button(
                    f"{navigation_label(route)}. {NAVIGATION_DESCRIPTIONS[route]}",
                    key=f"{widget_key}_button",
                    use_container_width=True,
                    on_click=_select_navigation,
                    args=(route,),
                )

ROOT = Path(__file__).resolve().parent.parent
LOGO_PATH = ROOT / "assets" / "brand" / "pp_logo.png"
ATHLETE_IMAGE_PATHS = {
    "richard burke": ROOT / "assets" / "athletes" / "richard_burke.jpg",
    "jo burke": ROOT / "assets" / "athletes" / "joanne_burke.jpg",
    "joanne burke": ROOT / "assets" / "athletes" / "joanne_burke.jpg",
    "paul farrell": ROOT / "assets" / "athletes" / "paul_farrell.jpg",
}


@lru_cache(maxsize=1)
def brand_logo_data_uri() -> str:
    """Return the real Pathmark brand asset for the sidebar."""
    if not LOGO_PATH.exists():
        return ""
    encoded = base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def build_sidebar_brand_html() -> str:
    logo_uri = brand_logo_data_uri()
    logo = (
        f'<img class="pp-sidebar-logo" src="{logo_uri}" '
        'alt="Performance Passport Pathmark">'
        if logo_uri else '<div class="pp-sidebar-logo-fallback">PP</div>'
    )
    return f"""
        <div class="pp-brand">
            <div class="pp-sidebar-logo-wrap">{logo}</div>
            <div class="pp-brand-copy">
                <div class="pp-brand-title">{APP_NAME}</div>
                <div class="pp-v21-motto">Every run has something to give.</div>
            </div>
        </div>
    """


def navigation_label(route: str) -> str:
    """Return the premium display label without changing the stable route."""
    return NAVIGATION_LABELS.get(route, route)


@lru_cache(maxsize=8)
def athlete_image_data_uri(athlete_name: str) -> str:
    path = ATHLETE_IMAGE_PATHS.get(str(athlete_name or "").strip().lower())
    if path is None or not path.exists():
        return ""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def build_sidebar_account_html(athlete_name: str | None) -> str:
    """Build the lightweight athlete footer without another database call."""
    clean_name = " ".join(str(athlete_name or "").split()) or "Choose athlete"
    safe_name = escape(clean_name)
    initials = "".join(part[0] for part in clean_name.split()[:2]).upper() or "PP"
    image_uri = athlete_image_data_uri(clean_name)
    avatar = (
        f'<img src="{image_uri}" alt="" aria-hidden="true">'
        if image_uri
        else f'<span>{escape(initials)}</span>'
    )
    return f"""
        <div class="pp-sidebar-account">
            <div class="pp-sidebar-avatar">{avatar}</div>
            <div class="pp-sidebar-account-copy">
                <strong>{safe_name}</strong>
                <span>Current athlete</span>
            </div>
            <div class="pp-sidebar-live" title="Live athlete profile"></div>
        </div>
        <div class="pp-sidebar-release">Performance Passport · v{escape(VERSION)}</div>
    """


def show_sidebar():
    """Display the Performance Passport navigation."""

    st.sidebar.markdown(build_sidebar_brand_html(), unsafe_allow_html=True)

    # One-release migration for sessions saved before Coach Home was renamed.
    if st.session_state.get("primary_navigation") == "Coach":
        st.session_state["primary_navigation"] = "Home"

    legacy_management = st.session_state.pop("management_navigation", None)
    if legacy_management in MANAGEMENT_NAVIGATION:
        st.session_state["primary_navigation"] = legacy_management

    requested_page = st.session_state.pop(
        "pp_navigation_request",
        None,
    )

    if read_coaching_team_request(st.query_params) is not None:
        requested_page = "Coaching Team"
    elif read_training_coach_request(st.query_params) is not None:
        requested_page = "Next Run"
    elif read_nutrition_coach_request(st.query_params) is not None:
        requested_page = "Fuel Planner"
    elif read_recovery_coach_request(st.query_params) is not None:
        requested_page = "Recovery Coach"
    elif read_activity_review_request(st.query_params) is not None:
        requested_page = "Activities"
    elif read_training_block_week_request(st.query_params) is not None:
        requested_page = "Training Blocks"

    if requested_page == "Coach":
        requested_page = "Home"

    if (
        requested_page in ALL_NAVIGATION
        and requested_page != st.session_state.get("primary_navigation")
    ):
        st.session_state["primary_navigation"] = requested_page

    # The hidden radio remains the single source of truth for route state and
    # existing AppTest contracts. Visible cards below use native Streamlit
    # buttons, so changing page never leaves the current Streamlit session.
    page = st.sidebar.radio(
        "Primary navigation",
        ALL_NAVIGATION,
        key="primary_navigation",
        format_func=navigation_label,
        label_visibility="collapsed",
    )

    athlete_name = st.session_state.get("selected_athlete_name")
    if athlete_name:
        st.sidebar.markdown(
            build_sidebar_account_html(athlete_name),
            unsafe_allow_html=True,
        )

    render_navigation_cards(page)

    return page
