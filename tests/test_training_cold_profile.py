from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_training_cold_profiler_covers_major_services():
    source = (ROOT / "tools" / "profile_v0653_training_cold_build.py").read_text(
        encoding="utf-8"
    )
    for name in (
        "build_next_run_recommendation",
        "build_operational_block_week",
        "build_adaptive_coach_proposal",
        "build_coaching_arbitration",
        "build_live_coach_decision",
        "build_designed_session",
    ):
        assert name in source


def test_training_cold_profiler_is_diagnostic_only():
    source = (ROOT / "tools" / "profile_v0653_training_cold_build.py").read_text(
        encoding="utf-8"
    )
    assert "production behaviour is unchanged" in source
