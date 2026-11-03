from core.runner_journey import (
    CouchTo5KAssessment,
    JourneyProgressEvidence,
    choose_couch_to_5k_entry_stage,
    decide_couch_to_5k_progress,
)


def test_true_beginner_starts_with_walking_foundation():
    assessment = CouchTo5KAssessment(
        can_walk_30_min=False,
        current_running=False,
        comfortable_continuous_run_min=0,
        sessions_per_week=3,
    )
    assert choose_couch_to_5k_entry_stage(assessment) == "walking_foundation"


def test_fit_beginner_does_not_have_to_start_at_stage_one():
    assessment = CouchTo5KAssessment(
        can_walk_30_min=True,
        current_running=True,
        comfortable_continuous_run_min=12,
        sessions_per_week=3,
    )
    assert choose_couch_to_5k_entry_stage(assessment) == "run_blocks_10"


def test_one_easy_completion_does_not_automatically_progress():
    decision = decide_couch_to_5k_progress(
        "run_walk_short",
        JourneyProgressEvidence(
            completed_as_planned=True,
            perceived_difficulty="comfortable",
            sessions_completed_since_decision=1,
        ),
    )
    assert decision.decision == "hold"
    assert decision.stage_after == "run_walk_short"


def test_two_controlled_completions_progress_one_stage():
    decision = decide_couch_to_5k_progress(
        "run_walk_short",
        JourneyProgressEvidence(
            completed_as_planned=True,
            perceived_difficulty="comfortable",
            sessions_completed_since_decision=2,
        ),
    )
    assert decision.decision == "progress"
    assert decision.stage_after == "run_walk_build"


def test_hard_completion_repeats_instead_of_progressing():
    decision = decide_couch_to_5k_progress(
        "run_blocks_5",
        JourneyProgressEvidence(
            completed_as_planned=True,
            perceived_difficulty="hard",
            sessions_completed_since_decision=3,
        ),
    )
    assert decision.decision == "repeat"
    assert decision.stage_after == "run_blocks_5"


def test_pain_never_progresses_running_load():
    decision = decide_couch_to_5k_progress(
        "continuous_20",
        JourneyProgressEvidence(
            completed_as_planned=True,
            perceived_difficulty="comfortable",
            pain_or_concerning_symptoms=True,
            sessions_completed_since_decision=3,
        ),
    )
    assert decision.decision == "hold"
    assert decision.stage_after == "continuous_20"


def test_long_gap_returns_conservatively():
    decision = decide_couch_to_5k_progress(
        "continuous_20",
        JourneyProgressEvidence(
            completed_as_planned=True,
            perceived_difficulty="comfortable",
            sessions_completed_since_decision=3,
            days_since_last_session=16,
        ),
    )
    assert decision.decision == "regress"
    assert decision.stage_after == "continuous_15"


def test_30_min_continuous_progresses_to_consolidation_before_graduation():
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
    assert decision.decision == "progress"
    assert decision.graduate is False
    assert decision.week_after == 11
    assert decision.stage_after == "continuous_30"


def test_actual_5k_completion_graduates():
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
    assert decision.decision == "graduate"
    assert decision.graduate is True
    assert decision.stage_after == "5k_ready"
