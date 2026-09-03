from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_race_intelligence_uses_persistent_store():
    home = (ROOT / "core" / "home_predictions.py").read_text(encoding="utf-8")
    outlook = (ROOT / "core" / "distance_prediction_outlook.py").read_text(encoding="utf-8")
    race = (ROOT / "core" / "race_coach.py").read_text(encoding="utf-8")

    assert "race.goal_predictions.v1." in home
    assert "race.distance_anchor.v1." in outlook
    assert "race.distance_outlook.v1." in outlook
    assert "race.coach_detail.v1." in race


def test_distance_anchors_are_materialised_individually():
    outlook = (ROOT / "core" / "distance_prediction_outlook.py").read_text(encoding="utf-8")
    assert "_build_distance_anchor_uncached" in outlook
    assert 'f"race.distance_anchor.v1.{key}"' in outlook


def test_materialised_intelligence_is_version_guarded():
    source = (ROOT / "core" / "materialized_intelligence.py").read_text(encoding="utf-8")
    assert "source_version=source_version" in source
    assert "load_intelligence(" in source
    assert "save_intelligence(" in source
