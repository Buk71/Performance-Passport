from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNNER = (ROOT / "core" / "runner_journey.py").read_text(encoding="utf-8")
UI = (ROOT / "ui" / "training_blocks.py").read_text(encoding="utf-8")


def test_runner_journey_has_archive_action():
    assert "def archive_active_runner_journey(" in RUNNER
    assert "SET status='Archived'" in RUNNER


def test_archive_is_audited_not_hard_deleted():
    assert "'journey_archived'" in RUNNER
    assert "'archive'" in RUNNER
    assert "DELETE FROM athlete_runner_journeys" not in RUNNER


def test_training_blocks_imports_archive_action():
    assert "archive_active_runner_journey" in UI


def test_remove_plan_requires_confirmation():
    assert "I understand this will remove the active Couch → 5K plan" in UI
    assert "disabled=not confirm" in UI


def test_remove_plan_button_archives_and_reruns():
    assert "Remove Couch → 5K plan" in UI
    assert "archive_active_runner_journey(" in UI
    assert "st.cache_data.clear()" in UI
    assert "st.rerun()" in UI


def test_linked_goal_is_explicitly_kept():
    assert "The linked 5K goal is kept." in UI
    assert "Goal Coach" in UI


def test_archived_plan_stops_being_active():
    # Active lookup is intentionally unchanged, so Archived rows disappear
    # from the active Training Blocks branch.
    assert "WHERE athlete_id = ? AND status = 'Active'" in RUNNER
