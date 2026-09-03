from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_next_run_profiler_uses_real_builder_names():
    source = (
        ROOT / "tools" / "profile_v0656_next_run_cold_path.py"
    ).read_text(encoding="utf-8")

    assert "from core.home_summary import build_home_summary" in source
    assert "from core.home_latest_run import build_home_latest_run" in source
    assert "build_home_coaching_summary" not in source
    assert "build_latest_run_review" not in source


def test_next_run_profiler_still_restores_cache():
    source = (
        ROOT / "tools" / "profile_v0656_next_run_cold_path.py"
    ).read_text(encoding="utf-8")

    assert "finally:" in source
    assert "_restore(" in source
