import datetime
from pathlib import Path

from core.goals import build_goal_hierarchy
from ui.goals import (
    _goal_card_html,
    _parse_target_time,
    build_goal_hierarchy_html,
)


ROOT = Path(__file__).resolve().parent.parent


def test_goal_centre_explains_hierarchy_and_current_block():
    richard = build_goal_hierarchy(
        1,
        reference_date=datetime.date(2026, 8, 14),
    )
    markup = build_goal_hierarchy_html(richard)

    assert "GOAL HIERARCHY" in markup
    assert "Sub 39:00 leads your coaching" in markup
    assert "PRIMARY" in markup
    assert "SECONDARY" in markup
    assert "FUTURE" in markup
    assert "No active block" in markup
    assert "container-type:inline-size" in markup
    assert "@container (max-width:720px)" in markup


def test_primary_goal_card_states_exact_coaching_influence():
    richard = build_goal_hierarchy(
        1,
        reference_date=datetime.date(2026, 8, 14),
    )
    markup = _goal_card_html(richard.primary)

    assert "PRIMARY · ACTIVE" in markup
    assert "Drives current coaching" in markup
    assert "Home, Next Run and the active Training Block" in markup
    assert "Training block not created" in markup
    assert "39:00" in markup
    assert "10K" in markup


def test_goal_management_actions_are_explicit_and_block_safe():
    source = (ROOT / "ui" / "goals.py").read_text()

    assert '"Make Primary"' in source
    assert '"Move to Future"' in source
    assert '"Use as Secondary"' in source
    assert '"Mark Complete"' in source
    assert '"Remove goal"' in source
    assert '"Confirm removal"' in source
    assert '"Keep goal"' in source
    assert '"Restore as Future"' in source
    assert '"Include in current Training Block"' in source
    assert "Its design has not been changed" in source
    assert "Block will not be deleted or redesigned" in source
    assert "history-led and customisable" in source
    assert '"Open Training Block Designer"' in source
    assert '"Create starting Training Block"' not in source
    assert "render_athlete_id_selector" in source


def test_goal_time_parser_rejects_invalid_clock_values():
    assert _parse_target_time("39:00") == (2340.0, True)
    assert _parse_target_time("1:29:20") == (5360.0, True)
    assert _parse_target_time("") == (None, True)
    assert _parse_target_time("39:75") == (None, False)
