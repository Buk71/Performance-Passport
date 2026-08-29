from pathlib import Path

from ui.sidebar import (
    ALL_NAVIGATION,
    MANAGEMENT_NAVIGATION,
    NAVIGATION_LABELS,
    PRIMARY_NAVIGATION,
    athlete_image_data_uri,
    brand_logo_data_uri,
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


def test_navigation_has_one_coherent_route_and_no_visible_none_option():
    source = (ROOT / "ui" / "sidebar.py").read_text(encoding="utf-8")

    assert ALL_NAVIGATION == [*PRIMARY_NAVIGATION, *MANAGEMENT_NAVIGATION]
    assert source.count("st.sidebar.radio(") == 1
    assert '["None", *MANAGEMENT_NAVIGATION]' not in source
    assert PRIMARY_NAVIGATION[:4] == [
        "Home",
        "Coaching Team",
        "Next Run",
        "Journal",
    ]
    assert PRIMARY_NAVIGATION[4:8] == [
        "Activities",
        "Progress",
        "Race Predictor",
        "Hall of Fame",
    ]
    assert "Fuel Planner" in PRIMARY_NAVIGATION
    assert "Recovery Coach" in PRIMARY_NAVIGATION


def test_sidebar_visual_system_has_spacing_route_markers_and_focusable_selection():
    theme = (ROOT / "theme.py").read_text(encoding="utf-8")

    assert "label:nth-of-type(5)" in theme
    assert "label:nth-of-type(9)" in theme
    assert "label:nth-of-type(15)" in theme
    assert 'content: "Analyse"' not in theme
    assert "p::before" in theme
    assert 'label:has(input[type="radio"]:checked)' in theme
    assert "border-left-color: var(--pp-accent)" in theme
    assert ".pp-sidebar-logo" in theme


def test_sidebar_toggle_keeps_explicit_contrast_in_dark_browser_chrome():
    theme = (ROOT / "theme.py").read_text(encoding="utf-8")

    assert '[data-testid="stSidebarCollapseButton"] button' in theme
    assert '[data-testid="stSidebarCollapsedControl"] button' in theme
    assert "@media (prefers-color-scheme: dark)" in theme
    assert "background: #F7F3EC !important" in theme
    assert "background: #F05A28 !important" in theme
    assert "fill: currentColor !important" in theme
    assert "color-scheme: light !important" in theme
    assert '[data-baseweb="select"] span' in theme
    assert "-webkit-text-fill-color: #10263D !important" in theme
    assert '[role="option"][aria-selected="true"]' in theme
    assert '[data-testid="stSelectbox"] [data-baseweb="select"] div' in theme
    assert "opacity: 1 !important" in theme
    assert "fill: #536576 !important" in theme


def test_premium_labels_rename_coach_pages_without_changing_route_order():
    source = (ROOT / "ui" / "sidebar.py").read_text(encoding="utf-8")

    assert PRIMARY_NAVIGATION[:4] == ["Home", "Coaching Team", "Next Run", "Journal"]
    assert navigation_label("Home") == "Lead Coach"
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


def test_premium_navigation_uses_line_icons_sections_and_athlete_footer():
    theme = (ROOT / "theme.py").read_text(encoding="utf-8")
    richard = build_sidebar_account_html("Richard Burke")
    unknown = build_sidebar_account_html("Test Runner")

    assert theme.count("--pp-nav-icon:url") == len(ALL_NAVIGATION)
    assert "-webkit-mask-image: var(--pp-nav-icon)" in theme
    assert 'content: "Performance"' in theme
    assert 'content: "Plan & profile"' in theme
    assert 'content: "Manage"' in theme
    assert "pp-sidebar-account" in richard
    assert "Richard Burke" in richard
    assert "data:image/jpeg;base64," in richard
    assert athlete_image_data_uri("Richard Burke").startswith("data:image/jpeg;base64,")
    assert "TR" in unknown


def test_premium_navigation_and_dark_coaching_cards_resist_safari_auto_darkening():
    theme = (ROOT / "theme.py").read_text(encoding="utf-8")

    assert "-webkit-text-fill-color: #526679 !important" in theme
    assert ".lc-identity-copy h1,.lc-identity-copy h2" in theme
    assert ".learning-daily h1,.learning-daily h2" in theme
    assert "-webkit-text-fill-color:#FFFFFF!important" in theme
    assert "-webkit-text-fill-color:#D5E1E8!important" in theme
