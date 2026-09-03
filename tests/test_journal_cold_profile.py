from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_journal_profiler_covers_real_internal_stages():
    source = (
        ROOT / "tools" / "profile_v0657_journal_cold_path.py"
    ).read_text(encoding="utf-8")

    for name in (
        "_run_profiles",
        "build_recognition_index",
        "_latest_recognised_run",
        "_build_decision_context",
        "get_active_training_block",
    ):
        assert name in source


def test_journal_profiler_is_diagnostic_only():
    source = (
        ROOT / "tools" / "profile_v0657_journal_cold_path.py"
    ).read_text(encoding="utf-8")

    assert "production behaviour is unchanged" in source
