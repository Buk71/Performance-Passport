from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_deep_profile_uses_real_evidence_engine_import():
    source = (
        ROOT / "tools" / "profile_v0660_decision_context_deep.py"
    ).read_text(encoding="utf-8")
    assert "from core.evidence_engine import build_athlete_evidence_profile" in source
    assert "from core.athlete_evidence" not in source


def test_deep_profile_covers_specialist_providers():
    source = (
        ROOT / "tools" / "profile_v0660_decision_context_deep.py"
    ).read_text(encoding="utf-8")
    for name in (
        "WorkoutEvidenceProvider",
        "RaceEvidenceProvider",
        "ThresholdEvidenceProvider",
        "build_easy_run_coach",
        "build_performance_dna",
        "build_coach_consensus",
        "build_capability",
    ):
        assert name in source
