from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_journal_uses_persistent_training_intelligence():
    source = (ROOT / "core" / "journal.py").read_text(encoding="utf-8")

    assert "_build_latest_journal_entry_uncached" in source
    assert "get_training_intelligence_version" in source
    assert "get_or_build_typed_intelligence" in source
    assert '"journal.latest_entry.v1"' in source


def test_coaching_summary_uses_persistent_training_intelligence():
    source = (ROOT / "core" / "coaching_team.py").read_text(encoding="utf-8")

    assert "_build_coaching_team_detail_uncached" in source
    assert "get_training_intelligence_version" in source
    assert "get_or_build_typed_intelligence" in source
    assert '"coaching.team_detail.v1"' in source


def test_journal_and_summary_keep_separate_materialised_keys():
    journal = (ROOT / "core" / "journal.py").read_text(encoding="utf-8")
    coaching = (ROOT / "core" / "coaching_team.py").read_text(encoding="utf-8")

    assert "journal.latest_entry.v1" in journal
    assert "coaching.team_detail.v1" in coaching
    assert "journal.latest_entry.v1" not in coaching
    assert "coaching.team_detail.v1" not in journal
