from pathlib import Path

from ui.sidebar import (
    ALL_NAVIGATION,
    MANAGEMENT_NAVIGATION,
    PRIMARY_NAVIGATION,
    brand_logo_data_uri,
    build_sidebar_brand_html,
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
