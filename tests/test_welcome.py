from pathlib import Path

from ui.welcome import (
    WELCOME_SESSION_KEY,
    build_welcome_page_html,
    product_entry_granted,
    welcome_logo_data_uri,
    welcome_runner_data_uri,
)


ROOT = Path(__file__).resolve().parent.parent


def test_welcome_uses_the_real_pathmark_and_reveals_no_athlete_data():
    markup = build_welcome_page_html()

    assert welcome_logo_data_uri().startswith("data:image/png;base64,")
    assert welcome_runner_data_uri().startswith("data:image/png;base64,")
    assert "Performance Passport Pathmark" in markup
    assert 'class="pp-welcome-stage-top"' in markup
    assert 'class="pp-welcome-runner-frame"' in markup
    assert 'class="pp-welcome-runner"' in markup
    assert "grid-template-columns:minmax(470px,1fr)" in markup
    assert (ROOT / "assets" / "brand" / "home_kit_runner.png").exists()
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
    assert '[data-testid="stHeader"]{display:none!important}' in markup
    assert ".pp-welcome-logo{width:100px;height:70px" in markup
    assert "width:96%;margin:18px 0 0 auto" in markup
    assert "width:94%;margin:18px auto 0" in markup
    assert "transform:rotate(1deg)" not in markup

    athlete_markup = build_welcome_page_html(
        ((1, "Richard", "Burke"), (3, "Joanne", "Burke"))
    )
    assert "CHOOSE YOUR PASSPORT" in athlete_markup
    assert "Richard Burke" in athlete_markup
    assert "Joanne Burke" in athlete_markup
    assert 'href="?pp_enter=1&amp;pp_athlete=1"' in athlete_markup
    assert 'href="?pp_enter=1&amp;pp_athlete=3"' in athlete_markup
    assert 'href="#athlete-entry"' in athlete_markup
    assert ".pp-athlete-choices{grid-template-columns:1fr}" in athlete_markup


def test_welcome_presents_current_differentiators_and_labels_future_work():
    markup = build_welcome_page_html()

    current_capabilities = (
        "THE LIVING PASSPORT",
        "TRUE RUN QUALITY",
        "CONDITIONS IN CONTEXT",
        "BEST RUNS, REDEFINED",
        "Capability → Ideal → Race Today",
        "HISTORY-LED TRAINING BLOCKS",
        "DELIBERATE ADAPTATION",
        "TRAINING-AWARE FUEL PLANNER",
        "Omnivore, pescatarian, vegetarian and vegan",
    )
    for capability in current_capabilities:
        assert capability in markup

    assert "ONE CONNECTED WEEK" in markup
    assert "BUILT ON TRUST" in markup
    assert "CONNECTED PRODUCT ROADMAP" in markup
    assert "Garmin-connected activities" in markup
    assert "not claims about the current development release" in markup
    assert markup.count('href="?pp_enter=1"') == 2


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

    athlete_state = {}
    athlete_query = {"pp_enter": "1", "pp_athlete": "3"}
    assert product_entry_granted(athlete_state, athlete_query) is True
    assert athlete_state["selected_athlete_id"] == 3
    assert "selected_athlete_name" not in athlete_state
    assert "pp_enter" not in athlete_query
    assert "pp_athlete" not in athlete_query


def test_app_places_welcome_gate_before_sidebar_routing():
    app = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "product_entry_granted(st.session_state, st.query_params)" in app
    assert "show_welcome_page()" in app
    assert app.index("show_welcome_page()") < app.index("page = show_sidebar()")
    assert app.index("st.stop()") < app.index("page = show_sidebar()")
