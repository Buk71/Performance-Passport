from pathlib import Path

from ui.welcome import (
    WELCOME_SESSION_KEY,
    build_welcome_page_html,
    product_entry_granted,
    welcome_logo_data_uri,
)


ROOT = Path(__file__).resolve().parent.parent


def test_welcome_uses_the_real_pathmark_and_reveals_no_athlete_data():
    markup = build_welcome_page_html()

    assert welcome_logo_data_uri().startswith("data:image/png;base64,")
    assert "Performance Passport Pathmark" in markup
    assert "Every run has<br><em>something to give.</em>" in markup
    assert "Richard" not in markup
    assert "Joanne" not in markup
    assert "38:17" not in markup


def test_welcome_has_product_story_entry_and_responsive_contract():
    markup = build_welcome_page_html()

    assert 'href="?pp_enter=1"' in markup
    assert "UNDERSTAND" in markup
    assert "PLAN" in markup
    assert "ADAPT" in markup
    assert "@media(max-width:1050px)" in markup
    assert "@media(max-width:680px)" in markup
    assert "prefers-reduced-motion:reduce" in markup
    assert '[data-testid="stSidebar"]' in markup


def test_entry_gate_is_session_scoped_and_preserves_deep_links():
    state = {}
    query = {}
    assert product_entry_granted(state, query) is False

    query["pp_enter"] = "1"
    assert product_entry_granted(state, query) is True
    assert state[WELCOME_SESSION_KEY] is True
    assert "pp_enter" not in query

    deep_link_state = {}
    deep_link = {
        "pp_page": "Activities",
        "pp_athlete": "3",
        "pp_activity": "5043",
    }
    assert product_entry_granted(deep_link_state, deep_link) is True
    assert deep_link["pp_page"] == "Activities"
    assert deep_link["pp_activity"] == "5043"


def test_app_places_welcome_gate_before_sidebar_routing():
    app = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "product_entry_granted(st.session_state, st.query_params)" in app
    assert "show_welcome_page()" in app
    assert app.index("show_welcome_page()") < app.index("page = show_sidebar()")
    assert app.index("st.stop()") < app.index("page = show_sidebar()")
