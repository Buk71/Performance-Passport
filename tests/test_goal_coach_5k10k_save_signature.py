from pathlib import Path

SOURCE = (Path(__file__).resolve().parent.parent / "ui" / "goals.py").read_text(encoding="utf-8")

def test_5k_to_10k_uses_existing_save_goal_signature():
    start = SOURCE.index("Complete my first 10K")
    fragment = SOURCE[start:start+900]
    assert 'priority="Primary"' in fragment
    assert 'race_name=None' in fragment
    assert 'role="Primary"' not in fragment
