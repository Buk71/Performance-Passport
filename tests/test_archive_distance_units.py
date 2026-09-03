from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_archive_distance_uses_existing_kilometre_semantics():
    source = (ROOT / "core" / "archive_intelligence.py").read_text(encoding="utf-8")

    assert "target_km = float(distance_km)" in source
    assert "target_m = float(distance_km) * 1000.0" not in source
    assert "total_distance_km=float(row[3] or 0.0)" in source
    assert "total_distance_km=float(row[3] or 0.0) / 1000.0" not in source


def test_archive_distance_note_documents_legacy_column_name():
    source = (ROOT / "core" / "archive_intelligence.py").read_text(encoding="utf-8")
    assert "despite its legacy name, activities.distance_m is stored" in source
