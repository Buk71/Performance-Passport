from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _source(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


def test_prediction_sql_paths_use_shared_distance_udf():
    paths = (
        "core/evidence_providers/race.py",
        "core/evidence_providers/threshold.py",
        "core/evidence_providers/workout.py",
        "core/pb_shape.py",
        "core/workout_race_linker.py",
    )
    for path in paths:
        source = _source(path)
        assert "pp_distance_km(" in source, path
        assert "distance_m > 250" not in source, path


def test_endurance_uses_shared_python_normalizer():
    source = _source("core/endurance_transfer.py")
    assert "normalize_activity_distance_km" in source
    assert "return normalize_activity_distance_km(value, raw_json_text)" in source
