from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_full_workout_coach_review_is_materialised():
    source = (ROOT / "core" / "workout_coach.py").read_text(encoding="utf-8")

    assert "_build_workout_coach_review_uncached" in source
    assert "get_training_intelligence_version" in source
    assert "get_or_build_typed_intelligence" in source
    assert "workout.coach_review.v1." in source


def test_full_workout_key_is_activity_and_day_specific():
    source = (ROOT / "core" / "workout_coach.py").read_text(encoding="utf-8")

    assert "activity_id" in source
    assert "effective_today.isoformat()" in source


def test_complete_review_still_composes_all_coaching_sections():
    source = (ROOT / "core" / "workout_coach.py").read_text(encoding="utf-8")

    assert "plan=_plan_context(review)" in source
    assert "heart_rate=_heart_rate_context(review)" in source
    assert "prediction=_prediction_contribution(review)" in source
    assert "next_direction=_next_direction(" in source
