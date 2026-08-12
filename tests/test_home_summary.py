import datetime

from core.home_summary import build_home_summary


TEST_DATE = datetime.date(2026, 8, 11)


def test_richard_home_uses_goal_and_honest_adaptive_preview():
    summary = build_home_summary(1, today=TEST_DATE)

    assert summary.goal_name == "Sub 39:00"
    assert summary.target_time_s == 2340
    assert summary.block_is_saved is False
    assert "adaptive" in summary.block_name.lower()
    assert len(summary.week_days) == 7
    assert summary.week_days[1].is_today is True


def test_jo_home_uses_her_saved_active_block():
    summary = build_home_summary(3, today=TEST_DATE)

    assert summary.goal_name == "Sub 45"
    assert summary.target_time_s == 2700
    assert summary.block_is_saved is True
    assert summary.block_name == "10K Training Block"
    assert "Week 1 of 10" in summary.block_context
    assert len(summary.week_days) == 7


def test_home_summaries_do_not_cross_athletes():
    richard = build_home_summary(1, today=TEST_DATE)
    jo = build_home_summary(3, today=TEST_DATE)

    assert richard.goal_name != jo.goal_name
    assert richard.target_time_s != jo.target_time_s
    assert richard.block_is_saved != jo.block_is_saved
