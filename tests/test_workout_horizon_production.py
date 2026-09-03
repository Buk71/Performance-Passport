from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_workout_provider_defaults_to_validated_365_day_horizon():
    source = (
        ROOT / "core" / "evidence_providers" / "workout.py"
    ).read_text(encoding="utf-8")
    assert "def __init__(self, history_days: int | None = RECENT_WINDOW_DAYS)" in source
    assert "RECENT_WINDOW_DAYS = 365" in source


def test_explicit_none_still_supports_full_history():
    source = (
        ROOT / "core" / "evidence_providers" / "workout.py"
    ).read_text(encoding="utf-8")
    assert "if self.history_days is not None" in source
    assert 'else ""' in source


def test_cutoff_is_applied_before_decode():
    source = (
        ROOT / "core" / "evidence_providers" / "workout.py"
    ).read_text(encoding="utf-8")
    cutoff = source.index("history_filter_sql")
    rows = source.index("rows = [")
    decode = source.index("workout = get_or_decode_workout")
    assert cutoff < rows < decode


def test_production_validator_checks_default_and_full_history_parity():
    source = (
        ROOT / "tools" / "validate_v0662_production_workout_horizon.py"
    ).read_text(encoding="utf-8")
    assert "WorkoutEvidenceProvider()" in source
    assert "WorkoutEvidenceProvider(history_days=365)" in source
    assert "WorkoutEvidenceProvider(history_days=None)" in source
    assert "Default == full critical output" in source
