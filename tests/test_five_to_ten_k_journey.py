import pytest

from core.runner_journey import (
    FIVE_TO_TEN_K,
    FiveToTenKAssessment,
    JourneyProgressEvidence,
    choose_five_to_ten_k_entry_stage,
    decide_five_to_ten_k_progress,
)


def _assessment(**overrides):
    values = dict(
        can_complete_5k=True,
        recent_runs_per_week=3,
        recent_weekly_km=12.0,
        longest_recent_run_km=6.0,
        sessions_per_week=3,
    )
    values.update(overrides)
    return FiveToTenKAssessment(**values)


def test_journey_type_constant_uses_existing_schema_value():
    assert FIVE_TO_TEN_K == "5k_to_10k"


def test_requires_existing_5k_ability():
    with pytest.raises(ValueError):
        choose_five_to_ten_k_entry_stage(
            _assessment(can_complete_5k=False)
        )


def test_low_consistency_starts_at_5k_foundation():
    assert choose_five_to_ten_k_entry_stage(
        _assessment(
            recent_runs_per_week=1,
            recent_weekly_km=6,
            longest_recent_run_km=5.0,
        )
    ) == "5k_consistency"


def test_entry_point_uses_longest_run_and_weekly_durability():
    assert choose_five_to_ten_k_entry_stage(
        _assessment(
            recent_weekly_km=14,
            longest_recent_run_km=7.2,
        )
    ) == "build_7k"
    assert choose_five_to_ten_k_entry_stage(
        _assessment(
            recent_weekly_km=17,
            longest_recent_run_km=9.2,
        )
    ) == "build_9k"


def test_strong_runner_can_start_10k_ready():
    assert choose_five_to_ten_k_entry_stage(
        _assessment(
            recent_weekly_km=22,
            longest_recent_run_km=10.0,
        )
    ) == "10k_ready"


def test_one_controlled_success_holds():
    decision = decide_five_to_ten_k_progress(
        "build_7k",
        JourneyProgressEvidence(
            completed_as_planned=True,
            perceived_difficulty="Comfortable",
            sessions_completed_since_decision=1,
        ),
    )
    assert decision.decision == "hold"
    assert decision.stage_after == "build_7k"


def test_two_controlled_successes_progress():
    decision = decide_five_to_ten_k_progress(
        "build_7k",
        JourneyProgressEvidence(
            completed_as_planned=True,
            perceived_difficulty="Moderate",
            sessions_completed_since_decision=2,
        ),
    )
    assert decision.decision == "progress"
    assert decision.stage_after == "build_8k"


def test_hard_completed_session_repeats():
    decision = decide_five_to_ten_k_progress(
        "build_8k",
        JourneyProgressEvidence(
            completed_as_planned=True,
            perceived_difficulty="Hard",
            sessions_completed_since_decision=2,
        ),
    )
    assert decision.decision == "repeat"
    assert decision.stage_after == "build_8k"


def test_pain_never_progresses():
    decision = decide_five_to_ten_k_progress(
        "build_8k",
        JourneyProgressEvidence(
            completed_as_planned=True,
            perceived_difficulty="Comfortable",
            pain_or_concerning_symptoms=True,
            sessions_completed_since_decision=3,
        ),
    )
    assert decision.decision == "hold"


def test_failed_very_hard_session_steps_back():
    decision = decide_five_to_ten_k_progress(
        "build_9k",
        JourneyProgressEvidence(
            completed_as_planned=False,
            perceived_difficulty="Very hard",
            sessions_completed_since_decision=1,
        ),
    )
    assert decision.decision == "regress"
    assert decision.stage_after == "build_8k"


def test_10k_activity_graduates_from_any_stage():
    decision = decide_five_to_ten_k_progress(
        "build_8k",
        JourneyProgressEvidence(
            completed_as_planned=True,
            perceived_difficulty="Comfortable",
            sessions_completed_since_decision=2,
            activity_distance_km=10.01,
        ),
    )
    assert decision.decision == "graduate"
    assert decision.graduate is True
    assert decision.stage_after == "10k_ready"


def test_10k_ready_holds_until_distance_completed():
    decision = decide_five_to_ten_k_progress(
        "10k_ready",
        JourneyProgressEvidence(
            completed_as_planned=True,
            perceived_difficulty="Comfortable",
            sessions_completed_since_decision=2,
            activity_distance_km=9.0,
        ),
    )
    assert decision.decision == "hold"
    assert decision.graduate is False
