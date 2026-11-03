from pathlib import Path
SOURCE = (Path(__file__).resolve().parent.parent / "ui" / "goals.py").read_text()

def test_goal_coach_has_5k_to_10k_onboarding():
    assert "Start 5K → 10K" in SOURCE
    assert "Create my 5K → 10K journey" in SOURCE
    assert "build_five_to_ten_k_assessment(" in SOURCE

def test_onboarding_uses_recent_real_evidence():
    assert "Recent evidence:" in SOURCE
    assert "recent_weekly_km" in SOURCE
    assert "longest_recent_run_km" in SOURCE

def test_onboarding_blocks_without_recent_5k():
    assert "I can't find a recent 5K completion" in SOURCE
    assert "Couch → 5K is the safer pathway" in SOURCE

def test_onboarding_creates_or_links_10k_goal():
    assert 'goal_type="10K"' in SOURCE
    assert "distance_m=10000.0" in SOURCE
    assert "abs(float(primary.distance_m) - 10000.0) <= 250.0" in SOURCE

def test_goal_coach_cache_schema_bumped():
    assert "GOAL_COACH_CACHE_SCHEMA = 3" in SOURCE
