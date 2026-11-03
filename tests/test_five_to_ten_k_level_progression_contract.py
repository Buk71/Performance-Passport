from core.runner_journey import JourneyProgressEvidence, decide_five_to_ten_k_progress
from core.five_to_ten_k_plan import stage_for_level

def test_plan_has_level_mapping_for_every_level():
    assert stage_for_level(1) == "5k_consistency"
    assert stage_for_level(10) == "10k_ready"

def test_existing_stage_safety_logic_still_holds_on_pain():
    decision = decide_five_to_ten_k_progress(
        "build_8k",
        JourneyProgressEvidence(
            completed_as_planned=True,
            perceived_difficulty="Comfortable",
            pain_or_concerning_symptoms=True,
            sessions_completed_since_decision=2,
        ),
    )
    assert decision.decision == "hold"

def test_recorded_10k_graduates_existing_stage_logic():
    decision = decide_five_to_ten_k_progress(
        "10k_ready",
        JourneyProgressEvidence(
            completed_as_planned=True,
            perceived_difficulty="Comfortable",
            activity_distance_km=10.0,
        ),
    )
    assert decision.graduate is True
