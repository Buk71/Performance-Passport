from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = (ROOT / "core" / "cache_version.py").read_text(encoding="utf-8")


def test_general_cache_version_includes_runner_journeys():
    general = SOURCE[
        SOURCE.index("def get_athlete_cache_version"):
        SOURCE.index("def get_race_intelligence_version")
    ]
    assert "athlete_runner_journeys" in general
    assert "* 31" in general


def test_training_cache_version_includes_runner_journeys():
    training = SOURCE[SOURCE.index("def get_training_intelligence_version"):]
    assert "athlete_runner_journeys" in training
    assert "* 25" in training
