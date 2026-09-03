from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_decision_context_profiler_covers_major_dependencies():
    source = (
        ROOT / "tools" / "profile_v0658_decision_context.py"
    ).read_text(encoding="utf-8")

    for builder in (
        "build_home_summary",
        "build_home_predictions",
        "build_distance_prediction_outlook",
        "build_progress_coach_detail",
        "build_recovery_coach_detail",
        "build_learning_coach_detail",
        "build_coaching_team_detail",
        "build_recognition_index",
    ):
        assert builder in source


def test_decision_context_profiler_is_diagnostic_only():
    source = (
        ROOT / "tools" / "profile_v0658_decision_context.py"
    ).read_text(encoding="utf-8")
    assert "production behaviour is unchanged" in source
