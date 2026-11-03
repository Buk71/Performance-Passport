from pathlib import Path
SOURCE = (Path(__file__).resolve().parent.parent/"core"/"five_to_ten_k_activity_evidence.py").read_text()

def test_activity_evidence_uses_real_sport_role_mapping():
    assert "get_athlete_sport_roles" in SOURCE
    assert 'role == "running"' in SOURCE

def test_activity_is_not_reused_after_review():
    assert "_reviewed_activity_ids" in SOURCE
    assert "progress_review" in SOURCE

def test_10k_completion_threshold_is_recorded():
    assert "km >= 9.95" in SOURCE
