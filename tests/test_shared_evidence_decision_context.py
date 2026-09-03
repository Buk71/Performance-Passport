from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_goal_prediction_accepts_prebuilt_evidence():
    source = (ROOT / "core" / "coach_brain.py").read_text(encoding="utf-8")
    assert "evidence: EvidenceBundle | None = None" in source
    assert "if evidence is not None" in source
    assert "else self.build_evidence()" in source


def test_journal_reuses_prebuilt_evidence_bundle():
    source = (ROOT / "core" / "journal.py").read_text(encoding="utf-8")
    assert "evidence_bundle = brain.build_evidence()" in source
    assert "brain.goal_prediction(evidence=evidence_bundle)" in source
    assert "prediction = brain.goal_prediction()" not in source


def test_journal_materialisation_is_preserved():
    source = (ROOT / "core" / "journal.py").read_text(encoding="utf-8")
    assert "_build_latest_journal_entry_uncached" in source
    assert '"journal.latest_entry.v1"' in source
    assert "get_training_intelligence_version" in source
