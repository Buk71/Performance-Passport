import datetime

from core.journal import (
    _block_applies_to_activity,
    _block_message,
)
from core.training_blocks import TrainingBlock


def _block(start="2026-09-01", end="2026-09-14"):
    return TrainingBlock(
        id=1,
        athlete_id=1,
        name="Autumn Half - Sub 90 Training Block",
        block_type="Half Marathon",
        purpose="Race prep",
        start_date=start,
        end_date=end,
        status="Active",
        primary_focus="Balanced",
        current_phase="Taper",
        notes=None,
        created_at=None,
        updated_at=None,
    )


def test_run_after_block_end_is_not_attributed_to_old_phase():
    block = _block()
    assert _block_applies_to_activity(
        block, activity_date="2026-11-03"
    ) is False

    headline, detail = _block_message(
        block, activity_date="2026-11-03"
    )

    assert headline == "Previous training block complete"
    assert "ended before this run" in detail
    assert "does not belong to that block or phase" in detail
    assert "Week 2 of 2" not in headline
    assert "taper phase" not in detail.lower()


def test_run_inside_block_still_gets_week_and_phase_context():
    block = _block()
    assert _block_applies_to_activity(
        block, activity_date="2026-09-08"
    ) is True

    headline, detail = _block_message(
        block, activity_date="2026-09-08"
    )

    assert "Week 2 of 2" in headline
    assert "taper phase" in detail.lower()
