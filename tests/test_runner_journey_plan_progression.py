from core.runner_journey import (
    JourneyProgressEvidence,
    decide_couch_to_5k_progress,
)


def test_two_controlled_sessions_can_progress_early_one_level():
    decision = decide_couch_to_5k_progress(
        "run_blocks_5",
        JourneyProgressEvidence(
            completed_as_planned=True,
            perceived_difficulty="comfortable",
            sessions_completed_since_decision=2,
        ),
        current_week=4,
    )
    assert decision.decision == "progress"
    assert decision.week_after == 5
    assert decision.stage_after == "run_blocks_8"


def test_hard_week_is_repeated_not_advanced():
    decision = decide_couch_to_5k_progress(
        "run_blocks_8",
        JourneyProgressEvidence(
            completed_as_planned=True,
            perceived_difficulty="hard",
            sessions_completed_since_decision=3,
        ),
        current_week=5,
    )
    assert decision.decision == "repeat"
    assert decision.week_after == 5


def test_failed_very_hard_session_steps_back():
    decision = decide_couch_to_5k_progress(
        "continuous_20",
        JourneyProgressEvidence(
            completed_as_planned=False,
            perceived_difficulty="very hard",
            sessions_completed_since_decision=1,
        ),
        current_week=8,
    )
    assert decision.decision == "regress"
    assert decision.week_after == 7
    assert decision.stage_after == "continuous_15"


def test_week_10_can_progress_to_consolidation_without_stage_change():
    decision = decide_couch_to_5k_progress(
        "continuous_30",
        JourneyProgressEvidence(
            completed_as_planned=True,
            perceived_difficulty="comfortable",
            sessions_completed_since_decision=2,
        ),
        current_week=10,
    )
    assert decision.week_after == 11
    assert decision.stage_after == "continuous_30"
    assert decision.decision == "progress"


def test_30_minutes_does_not_graduate_before_consolidation_level():
    decision = decide_couch_to_5k_progress(
        "continuous_30",
        JourneyProgressEvidence(
            completed_as_planned=True,
            perceived_difficulty="comfortable",
            sessions_completed_since_decision=2,
            continuous_run_minutes=30,
        ),
        current_week=10,
    )
    assert decision.graduate is False
    assert decision.week_after == 11


def test_actual_5k_graduates_from_any_late_level():
    decision = decide_couch_to_5k_progress(
        "continuous_25",
        JourneyProgressEvidence(
            completed_as_planned=True,
            perceived_difficulty="comfortable",
            sessions_completed_since_decision=2,
            completed_5k=True,
        ),
        current_week=9,
    )
    assert decision.graduate is True
    assert decision.week_after == 12
