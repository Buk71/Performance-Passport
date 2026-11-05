from core.runner_profile_ui_contract import EXPERIENCE_CHOICES, STATUS_CHOICES, profile_defaults


def test_missing_profile_does_not_infer_experience_or_injury():
    assert profile_defaults(None) == {
        "experience": None, "training_status": None, "sessions_per_week": None
    }


def test_existing_profile_values_are_preserved():
    profile = {"experience": "experienced", "training_status": "returning", "sessions_per_week": 3}
    assert profile_defaults(profile) == profile
    assert "experienced" in EXPERIENCE_CHOICES
    assert "returning" in STATUS_CHOICES


def test_onboarding_does_not_import_goal_or_training_mutation_services():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "ui" / "runner_onboarding.py").read_text()
    assert "save_runner_profile(" in source
    assert "save_goal(" not in source
    assert "save_training_block(" not in source
