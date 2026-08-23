from functools import lru_cache
import math

from core.home_predictions import build_goal_predictions, build_home_predictions
from core.evidence import EvidenceBundle, EvidenceItem, EvidenceStatus
from core.prediction import PredictionEngine
from core.race_outlook import RaceConditions, build_interactive_race_outlook


@lru_cache(maxsize=2)
def _predictions(athlete_id: int):
    return build_home_predictions(athlete_id)


def test_ideal_conditions_do_not_rewrite_richard_capability():
    predictions = _predictions(1)
    outlook = build_interactive_race_outlook(
        predictions,
        RaceConditions(),
    )

    assert outlook.available is True
    assert outlook.goal_name == "Sub 39:00"
    assert outlook.distance_label == "10K"
    assert outlook.ideal_seconds == predictions.central_seconds
    assert outlook.selected_seconds == predictions.central_seconds
    assert outlook.condition_cost_seconds == 0.0
    assert outlook.selected_pace_s_per_km == 233.4


def test_combined_conditions_are_auditable_and_personalised():
    outlook = build_interactive_race_outlook(
        _predictions(1),
        RaceConditions(
            temperature_c=23,
            humidity_percent=65,
            total_ascent_m=126,
            wind_speed_kmh=20,
            wind_exposure="Exposed",
            surface="Firm trail",
        ),
    )
    factors = {factor.key: factor for factor in outlook.factors}

    assert outlook.selected_seconds > outlook.ideal_seconds
    assert math.isclose(
        sum(factor.total_seconds for factor in outlook.factors),
        outlook.condition_cost_seconds,
        abs_tol=0.2,
    )
    assert factors["heat"].personalised is True
    assert factors["hills"].personalised is True
    assert factors["surface"].personalised is True
    assert factors["wind"].personalised is False
    assert factors["surface"].total_seconds < 60.0
    assert outlook.target_probability < 0.10


def test_jo_uses_her_own_responses_and_keeps_trail_generic():
    richard = build_interactive_race_outlook(
        _predictions(1),
        RaceConditions(surface="Firm trail"),
    )
    jo = build_interactive_race_outlook(
        _predictions(3),
        RaceConditions(surface="Firm trail"),
    )
    richard_factors = {factor.key: factor for factor in richard.factors}
    jo_factors = {factor.key: factor for factor in jo.factors}

    assert jo.goal_name == "Sub 45"
    assert jo.ideal_seconds != richard.ideal_seconds
    assert richard_factors["surface"].personalised is True
    assert jo_factors["surface"].personalised is False
    assert richard_factors["surface"].total_seconds < jo_factors["surface"].total_seconds


def test_condition_cost_never_exceeds_safety_cap():
    outlook = build_interactive_race_outlook(
        _predictions(1),
        RaceConditions(
            temperature_c=35,
            humidity_percent=100,
            total_ascent_m=1000,
            wind_speed_kmh=50,
            wind_exposure="Exposed",
            surface="Firm trail",
        ),
    )
    ideal_pace = outlook.ideal_seconds / outlook.distance_km

    assert outlook.condition_cost_seconds <= ideal_pace * 0.18 * outlook.distance_km + 0.1


def test_prediction_engine_can_estimate_a_distance_without_a_target():
    item = EvidenceItem(
        key="race",
        title="Race Coach",
        summary="Supported estimate",
        status=EvidenceStatus.AVAILABLE,
        confidence=0.8,
        sample_size=1,
        predicted_seconds=1200.0,
        weight=1.0,
        metadata={},
    )
    result = PredictionEngine().predict_goal(
        athlete_id=1,
        goal={"id": None, "distance_m": 5000.0, "target_time_s": None},
        evidence=EvidenceBundle(
            athlete_id=1,
            purpose="goal_prediction",
            items=(item,),
        ),
    )

    assert result.available is True
    assert result.predicted_seconds == 1200.0
    assert result.target_seconds is None
    assert result.gap_seconds is None


def test_explicit_distance_recalculates_capability_without_active_goal_mutation():
    active_before = _predictions(1)
    five_k = build_goal_predictions(
        1,
        {
            "id": None,
            "goal_name": "5K exploration",
            "goal_type": "5K",
            "distance_m": 5000.0,
            "target_time_s": None,
        },
    )
    active_after = build_home_predictions(1)

    assert five_k.available is True
    assert five_k.distance_label == "5K"
    assert five_k.target_seconds is None
    assert five_k.evidence_source_count == 3
    assert five_k.central_seconds < active_before.central_seconds
    assert active_after.goal_name == active_before.goal_name
    assert active_after.target_seconds == active_before.target_seconds
