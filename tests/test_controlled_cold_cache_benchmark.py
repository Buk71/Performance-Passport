from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_controlled_cold_benchmark_backs_up_before_delete():
    source = (
        ROOT / "tools" / "benchmark_v0654_controlled_cold_cache.py"
    ).read_text(encoding="utf-8")

    backup_pos = source.index("_backup_rows(athlete_id)")
    delete_pos = source.index("_delete_intelligence(athlete_id)")
    assert backup_pos < delete_pos


def test_controlled_cold_benchmark_restores_in_finally():
    source = (
        ROOT / "tools" / "benchmark_v0654_controlled_cold_cache.py"
    ).read_text(encoding="utf-8")

    assert "finally:" in source
    assert "_restore_rows(" in source
    assert "Restore check: PASS" in source


def test_controlled_cold_benchmark_only_deletes_intelligence_table():
    source = (
        ROOT / "tools" / "benchmark_v0654_controlled_cold_cache.py"
    ).read_text(encoding="utf-8").lower()

    delete_statements = [
        line.strip()
        for line in source.splitlines()
        if "delete from" in line
    ]

    assert delete_statements
    assert all(
        "athlete_intelligence" in statement
        for statement in delete_statements
    )


def test_controlled_cold_benchmark_measures_public_training_coach_twice():
    source = (
        ROOT / "tools" / "benchmark_v0654_controlled_cold_cache.py"
    ).read_text(encoding="utf-8")

    assert "build_training_coach_detail" in source
    assert "TRUE COLD BUILD" in source
    assert "IMMEDIATE WARM BUILD" in source
