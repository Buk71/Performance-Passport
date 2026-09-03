from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_workout_provider_production_default_is_validated_horizon():
    source = (
        ROOT / "core" / "evidence_providers" / "workout.py"
    ).read_text(encoding="utf-8")
    assert (
        "def __init__(self, history_days: int | None = RECENT_WINDOW_DAYS)"
        in source
    )
    assert "RECENT_WINDOW_DAYS = 365" in source


def test_explicit_none_preserves_full_history_diagnostic():
    source = (
        ROOT / "core" / "evidence_providers" / "workout.py"
    ).read_text(encoding="utf-8")
    assert "if self.history_days is not None" in source
    assert 'else ""' in source


def test_workout_provider_applies_cutoff_before_raw_decode_loop():
    source = (
        ROOT / "core" / "evidence_providers" / "workout.py"
    ).read_text(encoding="utf-8")
    cutoff_pos = source.index("history_filter_sql")
    rows_pos = source.index("rows = [")
    decode_pos = source.index("workout = get_or_decode_workout")
    assert cutoff_pos < rows_pos
    assert rows_pos < decode_pos


def test_shadow_metadata_reports_raw_rows_and_cutoff():
    source = (
        ROOT / "core" / "evidence_providers" / "workout.py"
    ).read_text(encoding="utf-8")
    assert '"history_horizon"' in source
    assert '"raw_rows_loaded": len(rows)' in source
    assert '"cutoff_date": history_cutoff' in source


def test_shadow_validator_requires_critical_output_parity():
    source = (
        ROOT / "tools" / "validate_v0661_workout_horizon.py"
    ).read_text(encoding="utf-8")
    assert "Exact critical parity" in source
    assert "top_workout_ids" in source
    assert "prediction_source" in source
    assert "predicted_seconds" in source
