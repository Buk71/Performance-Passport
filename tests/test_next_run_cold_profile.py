from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_next_run_profiler_isolated_and_restored():
    source = (
        ROOT / "tools" / "profile_v0656_next_run_cold_path.py"
    ).read_text(encoding="utf-8")
    assert "_clear(athlete_id)" in source
    assert "finally:" in source
    assert "_restore(" in source


def test_next_run_profiler_covers_visible_coaching_dependencies():
    source = (
        ROOT / "tools" / "profile_v0656_next_run_cold_path.py"
    ).read_text(encoding="utf-8")
    for builder in (
        "build_home_summary",
        "build_home_latest_run",
        "build_progress_coach_detail",
        "build_recovery_coach_detail",
        "build_learning_coach_detail",
        "build_next_run_recommendation",
    ):
        assert builder in source
