from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_profile_clears_cache_before_each_component():
    source = (
        ROOT / "tools" / "profile_v0655_isolated_cold_components.py"
    ).read_text(encoding="utf-8")
    assert "def _time_isolated" in source
    assert "_clear(athlete_id)" in source
    assert "Every measurement starts with zero athlete_intelligence rows" in source


def test_profile_restores_original_rows_in_finally():
    source = (
        ROOT / "tools" / "profile_v0655_isolated_cold_components.py"
    ).read_text(encoding="utf-8")
    assert "finally:" in source
    assert "_restore(" in source
    assert "Restore check:" in source


def test_profile_only_deletes_derived_intelligence():
    source = (
        ROOT / "tools" / "profile_v0655_isolated_cold_components.py"
    ).read_text(encoding="utf-8").lower()
    delete_lines = [
        line.strip()
        for line in source.splitlines()
        if "delete from" in line
    ]
    assert delete_lines
    assert all("athlete_intelligence" in line for line in delete_lines)
