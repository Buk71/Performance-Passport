from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = (ROOT / "core" / "runner_journey.py").read_text(encoding="utf-8")


def test_5k_to_10k_uses_shared_runner_journey_tables():
    assert "athlete_runner_journeys" in SOURCE
    assert "runner_journey_events" in SOURCE
    assert "start_five_to_ten_k_journey" in SOURCE
    assert "apply_five_to_ten_k_evidence" in SOURCE


def test_5k_to_10k_does_not_create_parallel_schema():
    assert "five_to_ten_k_journeys" not in SOURCE
    assert "ten_k_journeys" not in SOURCE
