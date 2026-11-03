from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOME = (ROOT / "core" / "home_summary.py").read_text(encoding="utf-8")
ADAPTIVE = (ROOT / "core" / "adaptive_coach_live.py").read_text(encoding="utf-8")
TRAINING = (ROOT / "core" / "training_coach.py").read_text(encoding="utf-8")
UI = (ROOT / "ui" / "next_run.py").read_text(encoding="utf-8")


def test_lead_coach_routes_active_5k10k_journey():
    assert "FIVE_TO_TEN_K" in HOME
    assert "_build_five_to_ten_home_summary" in HOME
    assert 'block_name="5K → 10K"' in HOME


def test_live_coach_routes_5k10k_before_history_led_coaching():
    assert "_five_to_ten_live_decision" in ADAPTIVE
    pos_route = ADAPTIVE.index("journey.journey_type == FIVE_TO_TEN_K")
    pos_history = ADAPTIVE.index("build_next_run_recommendation(", pos_route)
    assert pos_route < pos_history


def test_training_coach_uses_plan_session():
    assert "five_to_ten_level" in TRAINING
    assert "journey_session_title" in TRAINING
    assert "build_five_to_ten_k_plan(" in TRAINING


def test_training_coach_has_full_feedback_loop():
    assert "_render_five_to_ten_session_checkin" in UI
    assert "preview_five_to_ten_k_progress(" in UI
    assert "apply_five_to_ten_k_evidence(" in UI
    assert "Confirm this recommendation" in UI


def test_training_coach_uses_imported_activity_evidence():
    assert "find_latest_five_to_ten_k_activity_evidence" in UI
    assert "Use this imported run as objective evidence" in UI
