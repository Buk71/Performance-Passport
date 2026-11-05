from functools import lru_cache
from pathlib import Path

from core.athlete_passport import build_athlete_passport
from core.database import get_active_goal
from core.race_coach import build_race_coach_detail, build_race_pacing_guide
from core.home_predictions import build_home_predictions
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




def test_endurance_transfer_is_potential_not_selected_capability():
    detail = _paul_detail()
    half = _anchor("half_marathon")

    if half.potential_seconds is not None:
        assert half.potential_seconds < half.central_seconds
    if detail.predictions.distance_label == "Half marathon":
        assert detail.predictions.central_seconds == detail.raw_predictions.central_seconds

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



def test_richard_active_half_uses_exact_lead_coach_team_capability():
    goal = get_active_goal(1)
    detail = build_race_coach_detail(1, {
        "id": goal["id"],
        "athlete_id": 1,
        "goal_name": goal["goal_name"],
        "goal_type": goal["goal_type"],
        "distance_m": goal["distance_m"],
        "target_time_s": goal["target_time_s"],
        "target_date": goal["target_date"],
    })
    lead = build_home_predictions(1)
    race_view = next(item for item in detail.evidence if item.key == "recent_race")

    assert detail.predictions.central_seconds == lead.central_seconds
    assert detail.predictions.low_seconds == lead.low_seconds
    assert detail.predictions.high_seconds == lead.high_seconds
    assert detail.predictions.confidence == lead.confidence
    assert race_view.predicted_seconds != detail.predictions.central_seconds


def test_premium_race_coach_markup_exposes_capability_readiness_and_evidence():
    markup = build_race_coach_intro_html(_paul_detail())

    assert "YOUR RACE COACH" in markup
    assert "Team capability by distance" in markup
    assert "RACE COACH VIEW" in markup
    assert "TEAM CAPABILITY · LEAD COACH" in markup
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
