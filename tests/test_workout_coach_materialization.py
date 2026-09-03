from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_workout_review_uses_persistent_training_intelligence():
    source = (ROOT / "core" / "activity_review.py").read_text(encoding="utf-8")

    assert "_build_activity_review_uncached" in source
    assert "get_training_intelligence_version" in source
    assert "get_or_build_typed_intelligence" in source
    assert 'workout.activity_review.v1.' in source


def test_workout_review_key_is_activity_specific():
    source = (ROOT / "core" / "activity_review.py").read_text(encoding="utf-8")
    assert 'f"workout.activity_review.v1.{activity_id}"' in source
