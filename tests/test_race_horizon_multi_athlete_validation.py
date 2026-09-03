from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_multi_athlete_validator_covers_standard_distances():
    source = (ROOT / "tools" / "validate_v0651_race_horizon_all.py").read_text(encoding="utf-8")
    for distance in ("5K", "10K", "Half", "Marathon"):
        assert distance in source


def test_multi_athlete_validator_does_not_change_production():
    source = (ROOT / "tools" / "validate_v0651_race_horizon_all.py").read_text(encoding="utf-8")
    assert "RaceEvidenceProvider()" in source
    assert "history_days=args.days" in source
    assert "refresh_significant_pb_index" in source
