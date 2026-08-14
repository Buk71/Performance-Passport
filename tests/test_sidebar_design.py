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
    assert PRIMARY_NAVIGATION[:3] == ["Home", "Next Run", "Journal"]
    assert PRIMARY_NAVIGATION[3:7] == [
        "Activities",
        "Progress",
        "Race Predictor",
        "Hall of Fame",
    ]
    assert "Fuel Planner" in PRIMARY_NAVIGATION


def test_sidebar_visual_system_has_spacing_route_markers_and_focusable_selection():
    theme = (ROOT / "theme.py").read_text(encoding="utf-8")

    assert "label:nth-of-type(4)" in theme
    assert "label:nth-of-type(8)" in theme
    assert "label:nth-of-type(13)" in theme
    assert 'content: "Analyse"' not in theme
    assert "p::before" in theme
    assert 'label:has(input[type="radio"]:checked)' in theme
    assert "border-left-color: var(--pp-accent)" in theme
    assert ".pp-sidebar-logo" in theme
