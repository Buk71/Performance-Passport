from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_archive_best_distance_evidence_is_running_only():
    source = (ROOT / "core" / "archive_intelligence.py").read_text(encoding="utf-8")
    best_like = source.split("def best_like", 1)[1].split("return ArchiveHistorySummary", 1)[0]

    assert "running_ids" in best_like
    assert "sport_id" in best_like
    assert "CAST(sport_id AS TEXT) IN" in best_like


def test_archive_best_distance_evidence_stays_supporting_only():
    source = (ROOT / "core" / "archive_intelligence.py").read_text(encoding="utf-8")
    best_like = source.split("def best_like", 1)[1].split("return ArchiveHistorySummary", 1)[0]

    assert "Verified PB logic" in best_like
