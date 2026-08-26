"""Compose established goal, capability and training services for Goal Coach.

Goal Coach is an orchestration boundary only. It does not calculate a new race
prediction, alter goal hierarchy rules or silently redesign a saved block.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime

from core.goals import GoalHierarchy, build_goal_hierarchy
from core.home_predictions import HomePredictions, build_home_predictions
from core.home_summary import HomeSummary, build_home_summary


@dataclass(frozen=True)
class GoalCoachDetail:
    athlete_id: int
    hierarchy: GoalHierarchy
    predictions: HomePredictions
    home_summary: HomeSummary
    model_version: int = 1


def build_goal_coach_detail(
    athlete_id: int,
    *,
    today: datetime.date | None = None,
) -> GoalCoachDetail:
    """Build a single-athlete Goal Coach view from existing live services."""
    today = today or datetime.date.today()
    return GoalCoachDetail(
        athlete_id=athlete_id,
        hierarchy=build_goal_hierarchy(athlete_id, reference_date=today),
        predictions=build_home_predictions(athlete_id),
        home_summary=build_home_summary(athlete_id, today=today),
    )
