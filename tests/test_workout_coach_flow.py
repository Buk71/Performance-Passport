import datetime
from functools import lru_cache
from pathlib import Path

from core.activity_review import list_review_activities
from core.workout_coach import _families_align, build_workout_coach_review
from ui.activities import (
    build_plan_execution_html,
    build_workout_coach_hero_html,
    build_workout_direction_html,
    build_workout_intelligence_html,
)


ROOT = Path(__file__).resolve().parent.parent
REVIEW_DATE = datetime.date(2026, 8, 28)


@lru_cache(maxsize=8)
def _detail(athlete_id: int, activity_id: int):
    result = build_workout_coach_review(
        athlete_id,
        activity_id,
        today=REVIEW_DATE,
    )
    assert result is not None
    return result


@lru_cache(maxsize=3)
def _latest_detail(athlete_id: int):
    for item in list_review_activities(athlete_id):
        result = build_workout_coach_review(
            athlete_id,
            item.activity_id,
            today=REVIEW_DATE,
        )
        if result is not None:
            return result
    raise AssertionError(f"No reviewable activity exists for athlete {athlete_id}")


@lru_cache(maxsize=1)
def _richard_race_detail():
    candidates = list_review_activities(1)
    likely_races = tuple(
        item for item in candidates
        if any(token in item.title.lower() for token in (
            "parkrun", "race", "5k", "10k", "half", "marathon",
        ))
    )
    for item in likely_races:
        detail = build_workout_coach_review(
            1,
            item.activity_id,
            today=REVIEW_DATE,
        )
        if (
            detail is not None
            and detail.activity.session_type == "race"
            and detail.activity.classification_confidence >= 0.70
        ):
            return detail
    raise AssertionError("Richard has no confidently recognised race activity")


def test_richard_parkrun_is_direct_race_evidence_not_generic_workout_shape():
    detail = _richard_race_detail()

    assert detail.activity.athlete_id == 1
    assert detail.activity.session_type == "race"
    assert detail.prediction.status == "eligible"
    assert detail.prediction.coaches == ("Race Coach",)
    assert "Direct Race Coach evidence" in detail.prediction.headline


def test_plan_alignment_recognises_a_delivered_long_run_purpose():
    alignment, label = _families_align("long", "long")

    assert alignment == "matched"
    assert label == "Purpose delivered"


def test_paul_long_run_supports_context_without_becoming_a_race_prediction():
    detail = _detail(4, 10601)

    assert detail.activity.athlete_id == 4
    assert detail.prediction.status == "context"
    assert "Race Coach" not in detail.prediction.coaches
    assert "does not directly create a faster race prediction" in (
        detail.prediction.detail
    )


def test_trusted_decoded_session_can_support_workout_and_threshold_coaches():
    detail = _detail(1, 9358)

    assert detail.activity.session_type == "structured_workout"
    assert detail.prediction.status == "eligible"
    assert detail.prediction.headline == "Trusted workout evidence"
    assert detail.prediction.coaches == ("Workout Coach", "Threshold Coach")
    assert detail.prediction.execution_score is not None


def test_paul_easy_run_with_strides_cannot_become_prediction_workout_evidence():
    detail = _detail(4, 10599)

    assert detail.activity.session_type != "structured_workout"
    assert detail.prediction.status == "context"
    assert "Workout Coach" not in detail.prediction.coaches


def test_heart_rate_context_uses_each_athletes_existing_lt_boundaries():
    for athlete_id in (1, 3, 4):
        context = _latest_detail(athlete_id).heart_rate

        assert context.available is True
        assert context.lt1_hr < context.lt2_hr
        assert len(context.zones) == 3
        assert sum(zone.is_current for zone in context.zones) <= 1
        assert context.source != "Not set"


def test_plan_comparison_never_claims_an_unplanned_race_completed_recovery():
    alignment, label = _families_align("recovery", "race")

    assert alignment == "different"
    assert label == "Different stimulus"


def test_workout_coach_hero_is_coaching_led_and_prediction_explicit():
    markup = build_workout_coach_hero_html(_richard_race_detail())

    assert "YOUR WORKOUT COACH" in markup
    assert "RECOGNISED PURPOSE" in markup
    assert "PREDICTION STATUS" in markup
    assert "Direct Race Coach evidence" in markup
    assert "wc-hero" in markup


def test_plan_zones_prediction_and_next_direction_form_one_review_flow():
    detail = _latest_detail(3)
    markup = "".join(
        (
            build_plan_execution_html(detail),
            build_workout_intelligence_html(detail),
            build_workout_direction_html(detail),
        )
    )

    assert "PLAN → PERFORMANCE" in markup
    assert "PERSONAL EFFORT CONTEXT" in markup
    assert "WHAT CHANGES IN THE COACHING TEAM?" in markup
    assert "LEAD COACH · WHAT HAPPENS NEXT" in markup
    assert "Open Training Coach" in markup


def test_manual_classification_and_hr_corrections_remain_reversible():
    source = (ROOT / "ui" / "activities.py").read_text(encoding="utf-8")

    assert "Coach corrections · classification and heart-rate quality" in source
    assert "How should the coaches treat this activity?" in source
    assert "Recorded heart rate is trustworthy" in source
    assert "Save coach correction" in source
    assert "Restore automatic evidence" in source
    assert "clear_activity_override" in source


def test_activities_navigation_contract_is_preserved_while_page_becomes_workout_coach():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    sidebar_source = (ROOT / "ui" / "sidebar.py").read_text(encoding="utf-8")
    page_source = (ROOT / "ui" / "activities.py").read_text(encoding="utf-8")

    assert 'elif page == "Activities":\n    show_activities_page()' in app_source
    assert '"Activities",' in sidebar_source
    assert "read_activity_review_request(st.query_params)" in sidebar_source
    assert '<div class="pp-page-title">Workout Coach</div>' in page_source
    assert "_cached_workout_coach" in page_source
