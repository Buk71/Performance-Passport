from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = (ROOT / "ui" / "next_run.py").read_text(encoding="utf-8")


def test_training_coach_has_beginner_checkin_form():
    assert "How did it go?" in SOURCE
    assert "Did you complete the session as planned?" in SOURCE
    assert "How difficult did it feel?" in SOURCE
    assert "Any pain or concerning physical symptoms?" in SOURCE
    assert "Longest continuous running block (minutes)" in SOURCE


def test_checkin_previews_before_applying():
    assert "preview_couch_to_5k_progress(" in SOURCE
    assert "Nothing changes until you confirm the coach recommendation." in SOURCE
    assert "apply_couch_to_5k_evidence(" in SOURCE


def test_checkin_has_all_adaptive_outcomes():
    for text in (
        "Ready to progress",
        "Repeat this level",
        "Step back one level",
        "Hold this level",
        "5K journey complete",
    ):
        assert text in SOURCE


def test_checkin_only_renders_for_beginner_session():
    assert "if detail.beginner_session is not None:" in SOURCE
    assert "_render_beginner_session_checkin(athlete_id, detail)" in SOURCE
