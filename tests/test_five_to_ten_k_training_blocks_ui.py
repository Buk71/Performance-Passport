from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = (ROOT / "ui" / "training_blocks.py").read_text(encoding="utf-8")


def test_training_blocks_supports_5k_to_10k_journey():
    assert "FIVE_TO_TEN_K" in SOURCE
    assert "_show_five_to_ten_k_plan" in SOURCE


def test_full_10_level_plan_is_visible():
    assert "10 adaptive progression levels" in SOURCE
    assert "FULL JOURNEY VISIBLE FROM DAY ONE" in SOURCE


def test_5k_to_10k_controls_exist():
    assert "Step back one level" in SOURCE
    assert "Repeat this level" in SOURCE
    assert "Progress to next level" in SOURCE
    assert "set_active_five_to_ten_k_level(" in SOURCE


def test_existing_couch_to_5k_and_history_led_paths_remain():
    assert "_show_beginner_training_plan" in SOURCE
    assert "design_training_block(" in SOURCE
