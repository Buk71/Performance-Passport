import datetime
from functools import lru_cache
from pathlib import Path

from core.goals import build_goal_hierarchy
from core.training_block_designer import (
    build_training_history_profile,
    design_training_block,
    recommend_preferences,
)
from ui.training_blocks import (
    _selected_week_number,
    build_operational_week_html,
    build_training_block_overview_html,
    build_week_timeline_html,
)
from core.operational_block import compose_operational_week, OperationalActivity


ROOT = Path(__file__).resolve().parent.parent
REFERENCE_DATE = datetime.date(2026, 8, 14)


@lru_cache(maxsize=2)
def _surface(athlete_id):
    history = build_training_history_profile(athlete_id)
    hierarchy = build_goal_hierarchy(athlete_id, reference_date=REFERENCE_DATE)
    design = design_training_block(
        history=history,
        hierarchy=hierarchy,
        preferences=recommend_preferences(history),
        reference_date=REFERENCE_DATE,
    )
    return (
        build_training_block_overview_html(history, hierarchy, design),
        build_week_timeline_html(design),
    )


def test_richard_surface_explains_history_goal_and_generated_direction():
    overview, timeline = _surface(1)

    assert "HISTORY-LED TRAINING BLOCK" in overview
    assert "Sub 39:00 Training Block" in overview
    assert "39.7" in overview
    assert "11.5 mi" in overview
    assert "2<i> sessions/wk" in overview
    assert "15 weeks" in overview
    assert "WHY THIS SHAPE" in overview
    assert "WEEK-BY-WEEK SHAPE" in timeline
    assert "CUTBACK" in timeline
    assert "SESSION DETAIL STAYS IN NEXT RUN" in timeline


def test_jo_surface_remains_independent():
    overview, _ = _surface(3)

    assert "Sub 45 Training Block" in overview
    assert "27.5" in overview
    assert "1<i> sessions/wk" in overview
    assert "8 weeks" in overview
    assert "39.7" not in overview


def test_training_block_surface_is_responsive_and_sidebar_safe():
    overview, timeline = _surface(1)

    assert "container-type:inline-size" in overview
    assert "@container (max-width:800px)" in overview
    assert "@container (max-width:560px)" in overview
    assert "grid-template-columns:repeat(4,minmax(0,1fr))" in timeline
    assert "@container (max-width:520px)" in timeline


def test_week_cards_are_clickable_and_selected_week_is_visible():
    history = build_training_history_profile(1)
    hierarchy = build_goal_hierarchy(1, reference_date=REFERENCE_DATE)
    design = design_training_block(
        history=history,
        hierarchy=hierarchy,
        preferences=recommend_preferences(history),
        reference_date=REFERENCE_DATE,
    )
    timeline = build_week_timeline_html(design, selected_week_number=2)

    assert 'href="?pp_page=Training+Blocks&amp;pp_athlete=1&amp;pp_training_week=1#training-week-detail"' in timeline
    assert 'aria-label="View Week 2 daily shape"' in timeline
    assert 'is-selected' in timeline
    assert "VIEW DAILY SHAPE" in timeline
    assert _selected_week_number(design, "2") == 2
    assert _selected_week_number(design, "999") == 1


def test_production_page_exposes_every_custom_constraint_and_persists_it():
    source = (ROOT / "ui" / "training_blocks.py").read_text()

    assert "render_athlete_id_selector" in source
    assert '"Days you want to run"' in source
    assert '"Long-run day"' in source
    assert '"Session days"' in source
    assert '"Strength days"' in source
    assert '"Maximum weekly volume (miles)"' in source
    assert '"A race replaces a session"' in source
    assert '"Recovery, injury or life constraint"' in source
    assert "save_training_block_design" in source
    assert "Next Run remains responsible" in source
    assert "Operational Block Coaching is not active" in source
    assert source.index("_apply_training_week_request()") < source.index(
        "render_athlete_id_selector("
    )


def test_operational_surface_shows_execution_and_preserves_approved_plan():
    plan = {
        "weeks": [{
            "week_number": 1, "start_date": "2026-08-10", "end_date": "2026-08-16",
            "target_miles": 30.0, "phase": "Build", "emphasis": "Threshold rhythm",
            "days": [
                {"day": "Monday", "session_type": "Rest", "detail": "Rest", "is_hard": False},
                {"day": "Tuesday", "session_type": "Easy", "detail": "5 mi easy", "is_hard": False},
                {"day": "Wednesday", "session_type": "Threshold", "detail": "6 mi total", "is_hard": True},
                {"day": "Thursday", "session_type": "Recovery", "detail": "4 mi easy", "is_hard": False},
                {"day": "Friday", "session_type": "Rest", "detail": "Rest", "is_hard": False},
                {"day": "Saturday", "session_type": "Easy", "detail": "5 mi easy", "is_hard": False},
                {"day": "Sunday", "session_type": "Long run", "detail": "10 mi", "is_hard": False},
            ],
        }]
    }
    activity = OperationalActivity(
        activity_id=1, activity_date="2026-08-11", title="Easy five",
        family="easy", family_label="Easy / aerobic", distance_miles=5.0,
        moving_time_s=2400.0, confidence=.9, distance_reliable=True,
    )
    week = compose_operational_week(
        athlete_id=1, training_block_id=2, block_name="Sub 39 block",
        plan=plan, activities=(activity,), today=datetime.date(2026, 8, 12),
    )
    markup = build_operational_week_html(week)

    assert "OPERATIONAL BLOCK COACHING" in markup
    assert "5.0<i> / 30.0 mi" in markup
    assert "QUALITY COMMITMENTS" in markup
    assert "Saved weekdays and mileage ceiling remain unchanged" in markup
    assert "container-type:inline-size" in markup
