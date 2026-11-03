from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _source(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_prediction_providers_use_shared_distance_boundary():
    for relative_path in (
        "core/evidence_providers/race.py",
        "core/evidence_providers/threshold.py",
        "core/evidence_providers/workout.py",
        "core/pb_shape.py",
        "core/workout_race_linker.py",
    ):
        source = _source(relative_path)
        assert "pp_distance_km(" in source


def test_shared_distance_boundary_is_registered_once():
    database = _source("core/database.py")
    units = _source("core/distance_units.py")

    assert '"pp_distance_km"' in database
    assert "normalize_activity_distance_km" in database
    assert "legacy Runalyze" in units

    # Validate capability rather than brittle comment wording.
    assert "_known_metres_source" in units
    assert "raw_json_text" in units
    assert "distance / 1000.0" in units


def test_old_inline_distance_heuristic_is_not_required_in_prediction_providers():
    old = "WHEN a.distance_m > 250 THEN a.distance_m / 1000.0"
    for relative_path in (
        "core/evidence_providers/race.py",
        "core/evidence_providers/threshold.py",
        "core/evidence_providers/workout.py",
        "core/pb_shape.py",
        "core/workout_race_linker.py",
    ):
        assert old not in _source(relative_path)
