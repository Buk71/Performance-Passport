from pathlib import Path

SOURCE = (Path(__file__).resolve().parent.parent / "ui" / "goals.py").read_text(encoding="utf-8")

def test_runner_journey_renderer_branches_for_5k_to_10k():
    assert 'if journey.journey_type == "5k_to_10k":' in SOURCE
    assert "build_five_to_ten_k_plan(" in SOURCE
    assert "get_five_to_ten_k_current_level" in SOURCE

def test_5k_to_10k_renderer_does_not_call_c25k_session_builder():
    start = SOURCE.index('if journey.journey_type == "5k_to_10k":')
    end = SOURCE.index('if journey.journey_type != COUCH_TO_5K:', start)
    fragment = SOURCE[start:end]
    assert "build_couch_to_5k_session(" not in fragment

def test_c25k_renderer_remains_intact():
    assert "build_couch_to_5k_session(journey.current_stage)" in SOURCE
    assert "Active Couch → 5K journey" in SOURCE

def test_5k_to_10k_active_journey_summary_is_visible():
    assert "Active 5K → 10K journey" in SOURCE
    assert "Open Training Blocks to see the full 10-level progression." in SOURCE
