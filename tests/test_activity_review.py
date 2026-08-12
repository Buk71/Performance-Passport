from functools import lru_cache
from pathlib import Path

from core.activity_review import build_activity_review, list_review_activities


ROOT = Path(__file__).resolve().parent.parent


@lru_cache(maxsize=8)
def _review(athlete_id: int, activity_id: int):
    result = build_activity_review(athlete_id, activity_id)
    assert result is not None
    return result


def test_latest_long_run_exposes_comparison_and_real_continuity():
    review = _review(1, 9366)

    assert review.title == "SLR 12 miles"
    assert review.session_type == "continuous_run"
    assert review.comparison is not None
    assert review.comparison.category == "Long Easy"
    assert (review.comparison.rank, review.comparison.total) == (10, 107)
    assert round(review.stopped_time_s) == 2023
    assert round(review.moving_percent, 1) == 74.8
    assert review.pace_reliable is True


def test_blizzard_session_uses_split_structure_not_whole_run_average():
    review = _review(1, 9358)

    assert review.session_type == "structured_workout"
    assert review.classification_confidence >= 0.98
    assert sum(split.role == "Work" for split in review.splits) == 6
    assert review.boundary_count == 8
    assert review.unknown_recovery_count == 3
    assert review.comparison is not None
    assert review.comparison.provisional is True
    assert review.reliability_label == "Rep pace preferred"


def test_august_2025_ladder_cannot_return_to_easy():
    review = _review(1, 3177)

    assert review.session_type == "structured_workout"
    assert review.classification_confidence >= 0.98
    assert review.boundary_count == 16
    assert review.recovery_count == 6
    assert review.unknown_recovery_count == 8
    assert review.comparison is not None
    assert review.comparison.category == "Structured Workout"


def test_treadmill_keeps_training_evidence_but_excludes_pace_comparison():
    review = _review(1, 3428)

    assert review.title == "Treadmill Running"
    assert review.moving_time_s == 1201.0
    assert review.avg_hr == 121.0
    assert review.pace_reliable is False
    assert review.pace_s_per_km is None
    assert review.comparison is None
    assert review.reliability_label == "Pace excluded"
    assert review.coaching_headline == "Training contribution recorded"


def test_jo_latest_run_keeps_moderate_race_evidence_conservative():
    review = _review(3, 5577)

    assert review.title == "Halton Run"
    assert review.session_type == "race"
    assert review.classification_confidence < 0.70
    assert review.confidence_label == "Review confidence"
    assert review.comparison is not None
    assert review.comparison.category == "Easy"
    assert "below the 70% shared-confidence threshold" in (
        review.comparison.basis_detail
    )
    assert "no stopped time" in review.structure_notes[0]
    assert "recovery segments were detected" not in review.structure_notes[0]


def test_activity_selector_contains_only_each_athletes_running_history():
    richard = list_review_activities(1)
    jo = list_review_activities(3)

    assert richard[0].activity_id == 9366
    assert jo[0].activity_id == 5577
    assert all(item.activity_id != 9365 for item in richard)
    assert all(item.activity_id != 5575 for item in jo)


def test_production_navigation_uses_home_and_real_activity_review():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    sidebar_source = (ROOT / "ui" / "sidebar.py").read_text(encoding="utf-8")

    assert 'if page == "Home":\n    show_home_page()' in app_source
    assert 'elif page == "Activities":\n    show_activities_page()' in app_source
    assert '"Home",' in sidebar_source
    assert '"Coach",\n    "Journal"' not in sidebar_source
