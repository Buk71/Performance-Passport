from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = (ROOT / "core" / "distance_prediction_outlook.py").read_text(encoding="utf-8")


def test_distance_prediction_materialization_keys_are_v2():
    assert 'f"race.distance_anchor.v2.{key}"' in SOURCE
    assert 'f"race.distance_outlook.v2.{active_signature}"' in SOURCE


def test_old_v1_distance_anchor_key_is_not_used():
    assert 'f"race.distance_anchor.v1.{key}"' not in SOURCE
