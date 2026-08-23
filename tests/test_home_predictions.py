from functools import lru_cache
import ast
import math
from pathlib import Path
from types import SimpleNamespace

from core.home_predictions import build_home_predictions
from core.home_latest_run import build_home_latest_run
from ui.home_preview import (
    _refresh_stale_predictions_contract,
    build_home_intelligence_html,
    build_race_predictions_html,
)


@lru_cache(maxsize=2)
def _predictions(athlete_id):
    return build_home_predictions(athlete_id)


def test_richard_prediction_uses_real_consensus():
    result = _predictions(1)

    assert result.available is True
    assert result.goal_name == "Sub 39:00"
    assert result.distance_label == "10K"
    assert result.evidence_source_count == 3
    assert math.isclose(result.central_seconds, 2333.6, abs_tol=0.1)
    assert math.isclose(result.low_seconds, 2281.7, abs_tol=0.2)
    assert math.isclose(result.high_seconds, 2385.5, abs_tol=0.2)
    assert result.strongest_system == "Threshold"
    assert result.limiting_system == "Speed / VO₂"
    assert len(result.coach_positions) == 3
    assert [coach.title for coach in result.coach_positions] == [
        "Race Coach",
        "Workout Coach",
        "Threshold Coach",
    ]
    assert sum(coach.is_lead for coach in result.coach_positions) == 1
    lead = next(coach for coach in result.coach_positions if coach.is_lead)
    assert lead.title == "Threshold Coach"


def test_jo_prediction_is_independent_and_honest():
    result = _predictions(3)

    assert result.available is True
    assert result.goal_name == "Sub 45"
    assert result.distance_label == "10K"
    assert result.evidence_source_count == 3
    assert math.isclose(result.central_seconds, 2811.6, abs_tol=0.1)
    assert result.target_gap_seconds > 100
    assert result.target_probability < 0.10
    assert result.strongest_system == "Aerobic"
    assert len(result.coach_positions) == 3
    assert {coach.position for coach in result.coach_positions} == {
        "optimistic",
        "aligned",
        "cautious",
    }


def test_home_predictions_keep_athletes_separate():
    richard_predictions = _predictions(1)
    jo_predictions = _predictions(3)
    assert richard_predictions.athlete_id != jo_predictions.athlete_id
    assert richard_predictions.central_seconds != jo_predictions.central_seconds
    assert richard_predictions.target_seconds != jo_predictions.target_seconds


def test_prediction_scenarios_use_existing_environment_engine():
    richard_predictions = _predictions(1)
    scenarios = {item.key: item for item in richard_predictions.scenarios}

    assert tuple(scenarios) == ("ideal", "typical", "warm", "hilly", "windy")
    assert scenarios["ideal"].central_seconds == richard_predictions.central_seconds
    assert scenarios["typical"].central_seconds > scenarios["ideal"].central_seconds
    assert scenarios["warm"].personalised is True
    assert scenarios["hilly"].personalised is True


def test_richard_earns_trail_trait_from_real_environment_profile():
    result = _predictions(1)

    assert result.performance_trait is not None
    assert result.performance_trait.key == "trail"
    assert result.performance_trait.title == "Trail Warrior"
    assert result.performance_trait.confidence == 1.0
    responses = {item.key: item for item in result.environment_responses}
    assert responses["trail"].response_label == "35% less affected"
    assert responses["heat"].response_label == "47% more affected"
    assert responses["hills"].response_label == "60% more affected"


def test_jo_does_not_receive_an_unsupported_trait():
    result = _predictions(3)

    assert result.performance_trait is None
    responses = {item.key: item for item in result.environment_responses}
    assert responses["trail"].response_label == "Still learning"


def test_home_prediction_cache_is_schema_versioned():
    """Contract changes must not reuse Streamlit's serialized old result."""
    source = Path("ui/home_preview.py").read_text(encoding="utf-8")
    module = ast.parse(source)

    cache_function = next(
        node
        for node in module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "_cached_home_predictions"
    )
    argument_names = [argument.arg for argument in cache_function.args.args]

    assert "cache_schema" in argument_names
    assert "PREDICTIONS_CACHE_SCHEMA" in source


def test_stale_prediction_object_cannot_crash_renderer():
    """The pre-coaches cached contract must remain safe during an upgrade."""
    current = _predictions(1)
    stale = SimpleNamespace(
        **{
            key: value
            for key, value in vars(current).items()
            if key != "coach_positions"
        }
    )

    html = build_race_predictions_html(stale)

    assert 'id="race-predictions"' in html
    assert "Coaches’ View" in html


def test_stale_prediction_contract_is_rebuilt(monkeypatch):
    current = _predictions(1)
    stale = SimpleNamespace(
        **{
            key: value
            for key, value in vars(current).items()
            if key != "coach_positions"
        }
    )

    refreshed = _refresh_stale_predictions_contract(1, stale)

    assert len(refreshed.coach_positions) == 3


def test_compact_predictions_lead_with_coaches_in_two_panels():
    """Latest Run and coaching lead, with a compact outlook below."""
    html = build_home_intelligence_html(
        _predictions(1),
        build_home_latest_run(1),
    )

    assert 'class="hi-top"' in html
    assert 'class="hi-panel hi-latest"' in html
    assert 'class="hi-panel hi-coaches"' in html
    assert 'class="hi-outlook"' in html
    assert html.index("Latest run") < html.index("Coaches’ View")
    assert html.index("Coaches’ View") < html.index("Race Outlook")
    assert "What it gave you" in html
    assert "Trail Warrior" in html
    assert "Race history · current competitive ceiling" in html
