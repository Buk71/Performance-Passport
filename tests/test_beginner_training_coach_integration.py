import datetime
from unittest.mock import patch
from core.adaptive_coach_live import _beginner_live_decision
from core.beginner_sessions import build_couch_to_5k_session
from core.runner_journey import RunnerJourney
from core.training_coach import TrainingCoachDetail, TrainingAdjustment
from ui.next_run import build_training_coach_html, _beginner_block_sequence


def _journey(stage="run_walk_short", week=2, sessions=3):
    return RunnerJourney(
        id=1, athlete_id=99, journey_type="couch_to_5k", status="Active",
        goal_id=5, entry_stage=stage, current_stage=stage,
        sessions_per_week=sessions, started_at="2026-09-04", completed_at=None,
        baseline={}, preferences={"current_week": week, "plan_length_weeks": 12},
        created_at=None, updated_at=None,
    )


def _detail(stage="run_walk_short", week=2):
    journey = _journey(stage, week)
    decision = _beginner_live_decision(journey, today=datetime.date(2026, 9, 4))
    return TrainingCoachDetail(
        athlete_id=99, decision=decision, session=None,
        fuel_demand="Easy", fuel_focus="Simple",
        fuel_before="Normal familiar meal or snack.",
        fuel_during="Water as needed.", fuel_after="Normal balanced meal.",
        adjustments=(TrainingAdjustment("fatigue", "Fatigue", "Keep it easy."),),
        beginner_session=build_couch_to_5k_session(stage),
        beginner_week_number=week,
    )


def test_beginner_live_decision_uses_next_training_day():
    decision = _beginner_live_decision(_journey(), today=datetime.date(2026, 9, 4))
    assert decision.immediate_timing == "Sunday"
    assert decision.source == "Couch → 5K Runner Journey"
    assert decision.operational_week_number == 2


def test_beginner_ui_has_plan_level_and_no_pace_hr_targets():
    markup = build_training_coach_html("Jo Burke", _detail())
    assert "COUCH → 5K · LEVEL 2 OF 12" in markup
    assert "NO PACE TARGET" in markup
    assert "Exactly what to do" in markup
    assert "Heart rate" not in markup
    assert "Personal range" not in markup


def test_run_walk_sequence_is_alternating_and_exact():
    text = " | ".join(_beginner_block_sequence(build_couch_to_5k_session("run_walk_short")))
    assert "7 × (1 min run + 1:30 walk recovery)" in text
    assert text.startswith("5 min Easy walk")
    assert text.endswith("5 min Easy walk")


def test_feedback_questions_are_visible():
    markup = build_training_coach_html("Jo Burke", _detail()).lower()
    for expected in (
        "complete the session as planned", "how difficult", "pain or concerning",
        "longest continuous running block", "progress, repeat, hold or step back",
    ):
        assert expected in markup


def test_beginner_path_bypasses_session_designer():
    journey = _journey("continuous_20", 8)
    decision = _beginner_live_decision(journey, today=datetime.date(2026, 9, 4))
    with patch("core.training_coach.build_live_coach_decision", return_value=decision), \
         patch("core.training_coach.get_active_runner_journey", return_value=journey), \
         patch("core.training_coach.build_designed_session") as designer:
        from core.training_coach import _build_training_coach_detail_uncached
        detail = _build_training_coach_detail_uncached(99, today=datetime.date(2026, 9, 4))
    assert detail.beginner_session.stage == "continuous_20"
    designer.assert_not_called()


def test_5k_ready_does_not_claim_30_minute_5k():
    markup = build_training_coach_html("Jo Burke", _detail("5k_ready", 12))
    assert "Complete 5K at easy / controlled effort" in markup
    assert "30 min Easy 5K completion" not in markup
