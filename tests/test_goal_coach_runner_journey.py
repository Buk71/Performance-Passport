from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
SOURCE = (ROOT / "ui" / "goals.py").read_text(encoding="utf-8")

def test_goal_coach_imports_runner_journey_foundation():
    assert "CouchTo5KAssessment" in SOURCE
    assert "start_couch_to_5k_journey" in SOURCE

def test_goal_coach_uses_beginner_session_engine():
    assert "build_couch_to_5k_session" in SOURCE
    assert "_runner_journey_html" in SOURCE

def test_onboarding_creates_5k_primary_when_none_exists():
    assert 'goal_type="5K"' in SOURCE
    assert 'distance_m=5000.0' in SOURCE
    assert 'priority="Primary"' in SOURCE

def test_onboarding_collects_beginner_inputs():
    assert "comfortably walk for 30 minutes" in SOURCE
    assert "Longest continuous run" in SOURCE
    assert "How many days per week" in SOURCE

def test_existing_journey_renders_current_stage():
    assert "get_active_runner_journey(athlete_id)" in SOURCE
    assert "journey.current_stage" in SOURCE

def test_goal_coach_cache_schema_bumped():
    assert "GOAL_COACH_CACHE_SCHEMA = 3" in SOURCE
