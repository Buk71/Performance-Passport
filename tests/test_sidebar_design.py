from pathlib import Path

from ui.sidebar import (
    ALL_NAVIGATION,
    MANAGEMENT_NAVIGATION,
    NAVIGATION_DESCRIPTIONS,
    NAVIGATION_LABELS,
    NAVIGATION_SECTIONS,
    PRIMARY_NAVIGATION,
    athlete_image_data_uri,
    brand_logo_data_uri,
    build_navigation_html,
    render_navigation_cards,
    build_sidebar_account_html,
    build_sidebar_brand_html,
    navigation_label,
)


ROOT = Path(__file__).resolve().parent.parent


def test_sidebar_uses_the_real_pathmark_asset_not_the_temporary_svg():
    asset = ROOT / "assets" / "brand" / "pp_logo.png"
    source = (ROOT / "ui" / "sidebar.py").read_text(encoding="utf-8")
    markup = build_sidebar_brand_html()

    assert asset.exists()
    assert asset.stat().st_size > 100_000
    assert brand_logo_data_uri().startswith("data:image/png;base64,")
    assert "Performance Passport Pathmark" in markup
    assert '<svg class="pp-v21-pathmark"' not in source


def test_navigation_routes_are_stable_but_grouped_for_humans():
    source = (ROOT / "ui" / "sidebar.py").read_text(encoding="utf-8")

    assert ALL_NAVIGATION == [*PRIMARY_NAVIGATION, *MANAGEMENT_NAVIGATION]
    assert source.count("st.sidebar.radio(") == 1
    assert PRIMARY_NAVIGATION[:4] == ["Home", "Passport", "Journal", "Hall of Fame"]
    assert PRIMARY_NAVIGATION[4:11] == [
        "Coaching Team", "Next Run", "Activities", "Progress",
        "Race Predictor", "Recovery Coach", "Learning",
    ]
    assert PRIMARY_NAVIGATION[11:] == ["Goals", "Training Blocks", "Fuel Planner"]
    assert MANAGEMENT_NAVIGATION == ["Athletes", "Import", "Diagnostics", "Settings"]


def test_navigation_sections_match_the_agreed_product_structure():
    assert list(NAVIGATION_SECTIONS) == ["Overview", "Running Team", "Training Set Up", "Admin"]
    assert NAVIGATION_SECTIONS["Overview"]["routes"] == PRIMARY_NAVIGATION[:4]
    assert NAVIGATION_SECTIONS["Running Team"]["routes"] == PRIMARY_NAVIGATION[4:11]
    assert NAVIGATION_SECTIONS["Training Set Up"]["routes"] == PRIMARY_NAVIGATION[11:]
    assert NAVIGATION_SECTIONS["Admin"]["routes"] == MANAGEMENT_NAVIGATION
    assert "different job" in NAVIGATION_SECTIONS["Running Team"]["description"]


def test_every_navigation_destination_explains_why_to_click_it():
    assert set(NAVIGATION_DESCRIPTIONS) == set(ALL_NAVIGATION)
    assert all(len(text) >= 24 for text in NAVIGATION_DESCRIPTIONS.values())
    assert "training load" in NAVIGATION_DESCRIPTIONS["Next Run"]
    assert "latest run" in NAVIGATION_DESCRIPTIONS["Activities"]
    assert NAVIGATION_DESCRIPTIONS["Next Run"] != NAVIGATION_DESCRIPTIONS["Activities"]


def test_premium_labels_keep_coach_names_clear_without_changing_routes():
    source = (ROOT / "ui" / "sidebar.py").read_text(encoding="utf-8")

    assert navigation_label("Home") == "Lead Coach"
    assert navigation_label("Coaching Team") == "Coaching Summary"
    assert navigation_label("Next Run") == "Training Coach"
    assert navigation_label("Activities") == "Workout Coach"
    assert navigation_label("Progress") == "Progress Coach"
    assert navigation_label("Race Predictor") == "Race Coach"
    assert navigation_label("Goals") == "Goal Coach"
    assert navigation_label("Fuel Planner") == "Nutrition Coach"
    assert navigation_label("Passport") == "Athlete Passport"
    assert navigation_label("Learning") == "Learning Coach"
    assert set(NAVIGATION_LABELS) == set(ALL_NAVIGATION)
    assert "format_func=navigation_label" in source


def test_visible_navigation_is_authored_cards_not_fragile_radio_pseudo_content():
    theme = (ROOT / "theme.py").read_text(encoding="utf-8")
    markup = build_navigation_html("Activities")

    actual_cards = (
        markup.count('<div class="pp-nav-card">')
        + markup.count('<div class="pp-nav-card is-active">')
    )
    assert actual_cards == len(ALL_NAVIGATION)
    assert markup.count('class="pp-nav-group"') == 4
    assert "Overview" in markup
    assert "Running Team" in markup
    assert "Training Set Up" in markup
    assert "Admin" in markup
    assert "Workout Coach" in markup
    assert "Review your latest run and its training impact." in markup
    assert 'pp-nav-card is-active' in markup
    assert '?pp_nav=' not in markup
    assert '.pp-nav-card-copy > span' in theme
    assert '[data-testid="stSidebar"] .stRadio {{ display: none !important; }}' in theme
    assert "p::after" not in theme
    assert "--pp-nav-description:" not in theme



def test_navigation_clicks_use_native_streamlit_buttons_and_preserve_session_state():
    source = (ROOT / "ui" / "sidebar.py").read_text(encoding="utf-8")
    theme = (ROOT / "theme.py").read_text(encoding="utf-8")

    assert "st.button(" in source
    assert "st.session_state[\"primary_navigation\"] = route" in source
    assert "on_click=_select_navigation" in source
    assert "st.rerun()" not in source
    assert "href=" not in build_navigation_html("Home")
    assert "target=\"_self\"" not in source
    assert "st.query_params.get(\"pp_nav\")" not in source
    assert '[class*="st-key-pp_nav_"] [data-testid="stButton"]' in theme
    assert '[data-testid="stElementContainer"]:has([data-testid="stButton"])' in theme
    assert "position:absolute !important" in theme
    assert "opacity:0 !important" in theme


def test_current_athlete_identity_is_only_rendered_when_a_real_name_exists():
    source = (ROOT / "ui" / "sidebar.py").read_text(encoding="utf-8")
    richard = build_sidebar_account_html("Richard Burke")
    unknown = build_sidebar_account_html("Test Runner")

    assert 'if athlete_name:' in source
    assert "pp-sidebar-account" in richard
    assert "Richard Burke" in richard
    assert "Current athlete" in richard
    assert "data:image/jpeg;base64," in richard
    assert athlete_image_data_uri("Richard Burke").startswith("data:image/jpeg;base64,")
    assert "TR" in unknown


def test_sidebar_toggle_and_text_keep_explicit_contrast_in_dark_browser_chrome():
    theme = (ROOT / "theme.py").read_text(encoding="utf-8")

    assert '[data-testid="stSidebarCollapseButton"] button' in theme
    assert '[data-testid="stSidebarCollapsedControl"] button' in theme
    assert "@media (prefers-color-scheme: dark)" in theme
    assert "background: #F7F3EC !important" in theme
    assert "background: #F05A28 !important" in theme
    assert "fill: currentColor !important" in theme
    assert "color-scheme: light !important" in theme
    assert "-webkit-text-fill-color:#20384D !important" in theme or "-webkit-text-fill-color: #20384D !important" in theme
    assert "-webkit-text-fill-color:#73828E !important" in theme or "-webkit-text-fill-color: #73828E !important" in theme


def test_dark_coaching_cards_still_resist_safari_auto_darkening():
    theme = (ROOT / "theme.py").read_text(encoding="utf-8")

    assert ".lc-identity-copy h1,.lc-identity-copy h2" in theme
    assert ".learning-daily h1,.learning-daily h2" in theme
    assert "-webkit-text-fill-color:#FFFFFF!important" in theme
    assert "-webkit-text-fill-color:#D5E1E8!important" in theme
