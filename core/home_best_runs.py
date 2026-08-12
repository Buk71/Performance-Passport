"""Real-data adapter for the Performance Passport Home Best Runs section.

The Hall of Fame engine remains the calculation source. This module only
turns its athlete-specific awards into the compact, presentation-ready shape
needed by Home.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.hall_of_fame import HallRun, build_hall_of_fame


@dataclass(frozen=True)
class HomeBestRun:
    activity_id: int
    activity_date: str | None
    category: str
    short_category: str
    title: str
    headline: str
    distance_km: float
    moving_time_s: float
    actual_pace_s_per_km: float
    adjusted_pace_s_per_km: float
    avg_hr: float | None
    moving_percent: float | None
    score: float
    reason: str
    environment_note: str


@dataclass(frozen=True)
class HomeBestRuns:
    athlete_id: int
    main: HomeBestRun | None
    category_bests: tuple[HomeBestRun, ...]
    candidate_count: int

    @property
    def available(self) -> bool:
        return self.main is not None


SHORT_CATEGORIES = {
    "Best Easy Run Ever": "Easy",
    "Best Long Easy Run": "Long Easy",
    "Best Hot Run": "Hot",
    "Best Trail Run": "Trail",
    "Hidden Gem": "Hidden Gem",
}


def _headline(award: HallRun) -> str:
    if award.score >= 90:
        return "Exceptional aerobic efficiency"
    if award.score >= 85:
        return "Outstanding aerobic efficiency"
    if award.score >= 80:
        return "Excellent aerobic efficiency"
    return "Strong athlete-relative performance"


def _moving_percent(award: HallRun) -> float | None:
    elapsed = award.elapsed_time_s
    moving = award.moving_time_s
    if elapsed is None or elapsed <= 0 or moving <= 0:
        return None
    return round(min(moving / elapsed * 100.0, 100.0), 1)


def _home_run(award: HallRun) -> HomeBestRun:
    return HomeBestRun(
        activity_id=award.activity_id,
        activity_date=award.activity_date,
        category=award.category,
        short_category=SHORT_CATEGORIES.get(award.category, award.category),
        title=award.title,
        headline=_headline(award),
        distance_km=award.distance_km,
        moving_time_s=award.moving_time_s,
        actual_pace_s_per_km=award.actual_pace_s_per_km,
        adjusted_pace_s_per_km=award.equivalent_pace_s_per_km,
        avg_hr=award.avg_hr,
        moving_percent=_moving_percent(award),
        score=award.score,
        reason=award.reason,
        environment_note=award.environment_note,
    )


def build_home_best_runs(athlete_id: int) -> HomeBestRuns:
    """Build the Home Best Runs summary for one athlete."""
    hall = build_hall_of_fame(athlete_id)
    awards = list(hall.awards)

    if not awards:
        return HomeBestRuns(
            athlete_id=athlete_id,
            main=None,
            category_bests=(),
            candidate_count=hall.candidate_count,
        )

    main_award = next(
        (
            award
            for award in awards
            if award.category == "Best Easy Run Ever"
        ),
        max(awards, key=lambda award: award.score),
    )
    # The highlighted winner is the best overall Home feature. Keep every
    # award in the category strip as well, so the winning run can honestly
    # carry both the overall and (for example) Easy category honours.
    supporting = tuple(_home_run(award) for award in awards)

    return HomeBestRuns(
        athlete_id=athlete_id,
        main=_home_run(main_award),
        category_bests=supporting,
        candidate_count=hall.candidate_count,
    )
