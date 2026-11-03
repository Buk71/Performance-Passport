from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = (ROOT / "ui" / "next_run.py").read_text(encoding="utf-8")


def test_training_coach_looks_for_imported_beginner_activity():
    assert "find_latest_beginner_activity_evidence(" in SOURCE
    assert "Imported activity found:" in SOURCE


def test_imported_activity_can_prefill_but_athlete_confirms():
    assert "Use this imported activity to pre-fill objective evidence" in SOURCE
    assert "You still confirm the answers." in SOURCE
    assert "likely_completed_as_planned" in SOURCE
    assert "completed_5k" in SOURCE


def test_subjective_difficulty_and_pain_are_not_import_inferred():
    assert 'How difficult did it feel?' in SOURCE
    assert 'Any pain or concerning physical symptoms?' in SOURCE


def test_longest_continuous_block_stays_athlete_confirmed():
    assert "This remains athlete-confirmed." in SOURCE


def test_activity_identity_is_saved_into_progress_evidence():
    assert "activity_id=linked.activity_id if linked else None" in SOURCE
    assert "activity_distance_km=linked.distance_km if linked else None" in SOURCE
