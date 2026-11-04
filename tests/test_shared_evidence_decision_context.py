from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_journal_materialisation_is_preserved():
    source = (ROOT / "core" / "journal.py").read_text(encoding="utf-8")

    assert "_build_latest_journal_entry_uncached" in source
    assert "get_or_build_typed_intelligence" in source
    assert '"journal.latest_entry.v2"' in source
    assert '"journal.latest_entry.v1"' not in source


def test_journal_still_builds_shared_decision_context():
    source = (ROOT / "core" / "journal.py").read_text(encoding="utf-8")

    assert "_build_decision_context" in source
    assert "build_athlete_evidence_profile" in source
    assert "build_performance_dna" in source
    assert "build_coach_consensus" in source
    assert "build_capability" in source
    assert "build_decision" in source
