import ast
from functools import lru_cache
from pathlib import Path

from core.home_predictions import build_home_predictions
from core.race_outlook import RaceConditions, build_interactive_race_outlook
from ui.race_outlook import build_race_outlook_html


ROOT = Path(__file__).resolve().parent.parent


@lru_cache(maxsize=1)
def _markup():
    predictions = build_home_predictions(1)
    outlook = build_interactive_race_outlook(
        predictions,
        RaceConditions(
            temperature_c=23,
            humidity_percent=65,
            total_ascent_m=126,
            wind_speed_kmh=20,
            wind_exposure="Exposed",
            surface="Firm trail",
        ),
    )
    return build_race_outlook_html(outlook)


def test_race_outlook_surface_keeps_capability_conditions_and_goal_separate():
    markup = _markup()

    assert "CURRENT CAPABILITY" in markup
    assert "SELECTED RACE" in markup
    assert "CONDITION COST" in markup
    assert "COMPARISON · Sub 39:00" in markup
    assert "Estimated likelihood" in markup
    assert "What moved the prediction" in markup
    assert "HEAT &amp; HUMIDITY" in markup
    assert "CLIMBING" in markup
    assert "WIND" in markup
    assert "SURFACE" in markup
    assert "PERSONALISED" in markup
    assert "GENERIC" in markup


def test_race_outlook_ui_exposes_all_controls_and_canonical_athlete():
    goals_source = (ROOT / "ui" / "goals.py").read_text()
    outlook_source = (ROOT / "ui" / "race_outlook.py").read_text()
    sidebar_source = (ROOT / "ui" / "sidebar.py").read_text()
    app_source = (ROOT / "app.py").read_text()

    assert "render_interactive_race_outlook" not in goals_source
    assert "show_race_predictor_page" in outlook_source
    assert "render_athlete_id_selector" in outlook_source
    assert '"Race Predictor"' in sidebar_source
    assert 'page == "Race Predictor"' in app_source
    assert "show_race_predictor_page()" in app_source
    assert '"Saved goal"' in outlook_source
    assert '"Explore a distance"' in outlook_source
    assert '"Race distance"' in outlook_source
    assert '"Comparison target (optional)"' in outlook_source
    assert "Quick-start scenarios" in outlook_source
    assert "Fine-tune race conditions" in outlook_source
    assert '"Temperature (°C)"' in outlook_source
    assert '"Humidity (%)"' in outlook_source
    assert '"Total ascent (m)"' in outlook_source
    assert '"Wind speed (km/h)"' in outlook_source
    assert '"Wind exposure"' in outlook_source
    assert '"Surface"' in outlook_source
    assert "RACE_OUTLOOK_CACHE_SCHEMA" in outlook_source
    assert "_cached_race_predictions" in outlook_source
    assert "build_goal_predictions" in outlook_source
    for preset in ("Ideal", "Typical UK", "Warm", "Hot", "Hilly", "Trail"):
        assert f'(\"{preset}\", dict(' in outlook_source


def test_race_outlook_is_sidebar_and_mobile_responsive():
    markup = _markup()

    assert "container-type:inline-size" in markup
    assert "@container (max-width:950px)" in markup
    assert "@container (max-width:650px)" in markup
    assert "@container (max-width:430px)" in markup


def test_standard_exploration_distances_are_runner_friendly():
    outlook_source = (ROOT / "ui" / "race_outlook.py").read_text()

    for distance in (
        "5K",
        "5 miles",
        "10K",
        "10 miles",
        "Half marathon",
        "Marathon",
    ):
        assert f'"{distance}"' in outlook_source


def test_condition_widgets_have_one_session_state_default_source():
    source = (ROOT / "ui" / "race_outlook.py").read_text()

    assert "CONDITION_DEFAULTS" in source
    assert "_initialise_condition_state(athlete_id)" in source
    assert source.index("    _initialise_condition_state(athlete_id)\n") < source.index(
        'st.markdown("#### 2. Quick-start scenarios")'
    )

    condition_names = {
        "temperature", "humidity", "ascent", "wind", "exposure", "surface"
    }
    discovered = set()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in {"slider", "number_input", "segmented_control"}:
            continue
        key = next((item.value for item in node.keywords if item.arg == "key"), None)
        if not isinstance(key, ast.Call) or len(key.args) < 2:
            continue
        name = key.args[1]
        if not isinstance(name, ast.Constant) or name.value not in condition_names:
            continue
        discovered.add(name.value)
        assert not {item.arg for item in node.keywords} & {"value", "default"}

    assert discovered == condition_names
