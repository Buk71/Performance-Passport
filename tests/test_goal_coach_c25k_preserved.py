from pathlib import Path

SOURCE = (Path(__file__).resolve().parent.parent / "ui" / "goals.py").read_text(encoding="utf-8")


def test_c25k_and_5k_to_10k_onboarding_both_exist():
    assert "Start Couch → 5K journey" in SOURCE
    assert "Start 5K → 10K" in SOURCE
    assert "Can you comfortably walk for 30 minutes?" in SOURCE
    assert 'goal_type="5K"' in SOURCE
    assert 'goal_type="10K"' in SOURCE
