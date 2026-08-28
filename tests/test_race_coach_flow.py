from functools import lru_cache
from pathlib import Path

from core.athlete_passport import build_athlete_passport
from core.database import get_active_goal
from core.race_coach import build_race_coach_detail, build_race_pacing_guide
from core.race_outlook import RaceConditions, build_interactive_race_outlook
from ui.race_outlook import (
    build_race_coach_intro_html,
    build_race_pacing_html,
)


ROOT = Path(__file__).resolve().parent.parent


@lru_cache(maxsize=1)
def _paul_detail():
    return build_race_coach_detail(4, get_active_goal(4))


def _anchor(key):
    return next(item for item in _paul_detail().distance_outlook.anchors if item.key == key)


def test_race_coach_aligns_selected_standard_distance_with_home_anchor():
    detail = _paul_detail()

    assert detail.predictions.available is True
    assert detail.selected_anchor is not None
    assert detail.predictions.central_seconds == round(
        detail.selected_anchor.central_seconds, 1
    )
    assert len(detail.distance_outlook.anchors) == 4
    assert "matches Home" in detail.alignment_note or "directly" in detail.alignment_note


def test_paul_longer_distance_capability_is_ordered_and_endurance_explained():
    half = _anchor("half_marathon")
    marathon = _anchor("marathon")

    assert half.available and marathon.available
    assert 5_200 <= half.central_seconds <= 5_800
    assert marathon.central_seconds > half.central_seconds * 2
    assert half.readiness_label
    assert marathon.readiness_label
    assert "longest run" in half.endurance_summary


def test_recent_five_k_capability_does_not_ignore_the_verified_passport_best():
    passport = build_athlete_passport(4)
    five_k_pb = next(item for item in passport.personal_bests if item.key == "5k")
    five_k = _anchor("5k")

    assert five_k.available is True
    assert five_k.central_seconds <= five_k_pb.last_12_months_seconds + 35


def test_three_specialists_explain_the_combined_view_and_one_leads():
    evidence = _paul_detail().evidence

    assert {item.title for item in evidence} == {
        "Race Coach",
        "Workout Coach",
        "Threshold Coach",
    }
    assert sum(item.effective_weight_share for item in evidence) > 0.99
    assert sum(item.is_lead for item in evidence) == 1
    assert all(item.summary for item in evidence)


def test_premium_race_coach_markup_exposes_capability_readiness_and_evidence():
    markup = build_race_coach_intro_html(_paul_detail())

    assert "YOUR RACE COACH" in markup
    assert "Current capability by distance" in markup
    assert "Why the coaches believe it" in markup
    assert "DISTANCE READINESS" in markup
    assert "THREE INDEPENDENT VIEWS" in markup
    assert "Evidence audit" in markup
    assert "color:#fff!important" in markup
    assert "race-coach-mark" in markup


def test_selected_conditions_produce_a_restrained_three_part_pacing_guide():
    detail = _paul_detail()
    outlook = build_interactive_race_outlook(detail.predictions, RaceConditions())
    guide = build_race_pacing_guide(
        detail,
        selected_seconds=outlook.selected_seconds,
        selected_low_seconds=outlook.selected_low_seconds,
        selected_high_seconds=outlook.selected_high_seconds,
        target_probability=outlook.target_probability,
    )
    markup = build_race_pacing_html(guide)

    assert guide.available is True
    assert len(guide.segments) == 3
    assert [item.label for item in guide.segments] == ["Settle", "Hold", "Decide"]
    assert guide.segments[0].pace_low_s_per_km > guide.average_pace_s_per_km
    assert "how the athlete feels take precedence" in guide.caveat
    assert "Turn the forecast into a sensible start line plan" in markup


def test_race_coach_page_preserves_navigation_and_condition_controls():
    source = (ROOT / "ui" / "race_outlook.py").read_text(encoding="utf-8")
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    sidebar_source = (ROOT / "ui" / "sidebar.py").read_text(encoding="utf-8")

    assert "_cached_race_coach_detail" in source
    assert "build_race_coach_intro_html" in source
    assert "build_race_pacing_html" in source
    assert "Quick-start scenarios" in source
    assert "Fine-tune race conditions" in source
    assert 'page == "Race Predictor"' in app_source
    assert '"Race Predictor"' in sidebar_source
