from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = (ROOT / "core" / "evidence_providers" / "race.py").read_text(encoding="utf-8")


def test_race_provider_preloads_scoring_history_once():
    assert "def _load_scoring_history(" in SOURCE
    assert "scoring_history = self._load_scoring_history" in SOURCE
    assert "scoring_history=scoring_history" in SOURCE


def test_race_scoring_helpers_accept_preloaded_history():
    assert "scoring_history: tuple[RaceScoringHistoryRow, ...] | None = None" in SOURCE
