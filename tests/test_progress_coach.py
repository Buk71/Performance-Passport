from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from core.progress_coach import build_progress_coach_detail
from ui.progress import build_progress_coach_html


ROOT = Path(__file__).resolve().parent.parent


@lru_cache(maxsize=3)
def _detail(athlete_id: int):
    detail = build_progress_coach_detail(athlete_id)
    assert detail is not None
    return detail


def test_progress_coach_composes_richards_real_progress_identity():
    detail = _detail(1)

    assert detail.athlete_name == "Richard Burke"
    assert 75.0 <= detail.age_grade_last_12_months <= 82.0
    assert detail.age_grade_all_time >= detail.age_grade_last_12_months
    assert detail.progress.aerobic.trend_percent is not None
    assert detail.achievement_candidate_count > 1_000
    assert len(detail.achievements) >= 3
    assert detail.achievements[0].label == "BEST RUN OVERALL"
    assert detail.achievements[0].activity_id is not None


def test_progress_coach_keeps_jo_and_paul_independent():
    richard = _detail(1)
    jo = _detail(3)
    paul = _detail(4)

    assert jo.athlete_name == "Joanne Burke"
    assert paul.athlete_name == "Paul Farrell"
    assert jo.age_grade_last_12_months != richard.age_grade_last_12_months
    assert paul.age_grade_last_12_months != richard.age_grade_last_12_months
    assert jo.progress.rhythm.reliable_miles_per_week != (
        richard.progress.rhythm.reliable_miles_per_week
    )
    assert paul.coach_message != richard.coach_message


def test_progress_coach_surface_leads_with_guidance_and_real_achievements():
    detail = _detail(1)
    markup = build_progress_coach_html(detail)

    assert "YOUR PROGRESS COACH" in markup
    assert "NEXT DEVELOPMENT FOCUS" in markup
    assert "AGE-GRADED PERFORMANCE" in markup
    assert "PB DEVELOPMENT" in markup
    assert "ATHLETE-RELATIVE ACHIEVEMENTS" in markup
    assert detail.achievements[0].title in markup
    assert f"pp_athlete={detail.athlete_id}" in markup
    assert "Evidence, not a readiness score" in markup
    assert "progress-coach-direction h2 { color:#fff!important" in markup


def test_cold_home_builds_independent_services_concurrently():
    home_source = (ROOT / "ui" / "lead_coach_home.py").read_text(
        encoding="utf-8"
    )
    distance_source = (ROOT / "core" / "distance_prediction_outlook.py").read_text(
        encoding="utf-8"
    )

    assert "ThreadPoolExecutor" in home_source
    assert 'thread_name_prefix="pp-home"' in home_source
    assert "ThreadPoolExecutor" in distance_source
    assert 'thread_name_prefix="pp-distance"' in distance_source
    assert "max_workers=min(len(missing_definitions), 3)" in distance_source
