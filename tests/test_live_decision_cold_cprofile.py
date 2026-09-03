from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_live_decision_profiler_profiles_real_entrypoint():
    source = (
        ROOT / "tools" / "profile_v0663_live_decision_cold.py"
    ).read_text(encoding="utf-8")
    assert "from core.adaptive_coach_live import build_live_coach_decision" in source
    assert "build_live_coach_decision(" in source
    assert "cProfile.Profile()" in source


def test_live_decision_profiler_is_cold_and_restores():
    source = (
        ROOT / "tools" / "profile_v0663_live_decision_cold.py"
    ).read_text(encoding="utf-8")
    assert "_clear(athlete_id)" in source
    assert "finally:" in source
    assert "_restore(athlete_id, columns, rows)" in source
    assert "Restore check:" in source


def test_live_decision_profiler_surfaces_repeated_calls():
    source = (
        ROOT / "tools" / "profile_v0663_live_decision_cold.py"
    ).read_text(encoding="utf-8")
    assert "REPEATED CORE CALLS" in source
    assert "total_calls" in source
    assert "cumulative_time" in source
