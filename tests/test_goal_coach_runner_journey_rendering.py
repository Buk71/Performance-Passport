from pathlib import Path

SOURCE = (Path(__file__).resolve().parent.parent / "ui" / "goals.py").read_text(encoding="utf-8")


def test_5k_to_10k_renderer_does_not_call_c25k_session_builder():
    start = SOURCE.index('if journey.journey_type == "5k_to_10k":')
    c25k_start = SOURCE.index("if journey.journey_type == COUCH_TO_5K:", start)
    block = SOURCE[start:c25k_start]

    assert "build_five_to_ten_k_plan(" in block
    assert "build_couch_to_5k_session(" not in block


def test_c25k_renderer_remains_intact():
    c25k_start = SOURCE.index("if journey.journey_type == COUCH_TO_5K:")
    tail = SOURCE[c25k_start:]

    assert "Active Couch → 5K journey" in tail
    assert "build_couch_to_5k_session(journey.current_stage)" in tail
    assert "_runner_journey_html(journey, session)" in tail
