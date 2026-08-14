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
    build_training_block_overview_html,
    build_week_timeline_html,
)


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
