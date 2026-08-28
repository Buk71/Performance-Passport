"""Coaching-led composition for longitudinal Progress evidence.

The established Progress engine remains the source for trends, rhythm, race
development, threshold and durability. This adapter adds athlete identity,
age grading and Hall of Fame achievements without inventing a second model.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime

from core.athlete_passport import build_athlete_passport
from core.home_best_runs import build_home_best_runs
from core.progress import ProgressSummary, build_progress_summary


@dataclass(frozen=True)
class ProgressAchievement:
    key: str
    label: str
    title: str
    value: str
    detail: str
    activity_date: str | None
    activity_id: int | None


@dataclass(frozen=True)
class ProgressCoachDetail:
    athlete_id: int
    athlete_name: str
    progress: ProgressSummary
    age_grade_all_time: float | None
    age_grade_last_12_months: float | None
    age_grade_summary: str
    pb_development_summary: str
    coach_message: str
    next_focus: str
    achievements: tuple[ProgressAchievement, ...]
    achievement_candidate_count: int
    model_version: int = 1


def _age_grade_summary(recent: float | None, all_time: float | None) -> str:
    if recent is None and all_time is None:
        return "Age-graded evidence will appear when a supported race result is available."
    if recent is None:
        return "An all-time age grade is available, but no supported result falls in the latest 12 months."
    if all_time is None or recent >= all_time - 0.05:
        return "The latest 12-month peak matches the best age-graded performance in the available record."
    return (
        f"The latest 12-month peak is {all_time - recent:.1f} percentage points "
        "below the available all-time age-grade peak."
    )


def _pb_development_summary(progress: ProgressSummary) -> str:
    supported = [event for event in progress.race.events if event.change_s is not None]
    improved = [event for event in supported if event.change_s is not None and event.change_s >= 5]
    softer = [event for event in supported if event.change_s is not None and event.change_s <= -10]
    if improved and not softer:
        labels = ", ".join(event.label for event in improved)
        return f"Recent trusted results improved at {labels}."
    if improved and softer:
        return (
            "PB development is mixed across distances, so the individual race "
            "cards matter more than one combined verdict."
        )
    if softer:
        return (
            "Recent results are softer at one or more distances; conditions and "
            "training phase remain context, while recorded PBs stay factual."
        )
    return "More comparable race results are needed to establish PB development."


def _next_focus(progress: ProgressSummary) -> str:
    if progress.threshold.confidence == "Limited":
        return (
            "Build threshold evidence through controlled, comparable work phases; "
            "warm-up and recovery pace should not influence the trend."
        )
    if progress.durability.confidence == "Limited":
        return (
            "Keep long runs continuous and controlled so durability can be compared "
            "without interrupted-run noise."
        )
    if progress.race.confidence == "Limited":
        return (
            "Use the next trusted race result to strengthen distance-specific PB "
            "development without rewriting historical times."
        )
    if (progress.aerobic.trend_percent or 0.0) >= 0.5:
        return (
            "Protect the current training rhythm. The aerobic evidence is moving in "
            "the right direction, so consistency is more useful than adding load."
        )
    return (
        "Keep the next block consistent and judge change across several comparable "
        "weeks rather than reacting to one run."
    )


def _achievements(athlete_id: int) -> tuple[tuple[ProgressAchievement, ...], int]:
    best_runs = build_home_best_runs(athlete_id)
    if not best_runs.available or best_runs.main is None:
        return (), best_runs.candidate_count

    achievements = [
        ProgressAchievement(
            key="overall",
            label="BEST RUN OVERALL",
            title=best_runs.main.title,
            value=f"{best_runs.main.score:.0f}/100",
            detail=(
                f"{best_runs.main.short_category} · "
                f"{best_runs.main.headline.lower()}"
            ),
            activity_date=best_runs.main.activity_date,
            activity_id=best_runs.main.activity_id,
        )
    ]
    seen = {(best_runs.main.activity_id, best_runs.main.category)}
    for award in best_runs.category_bests:
        identity = (award.activity_id, award.category)
        if identity in seen:
            continue
        seen.add(identity)
        achievements.append(
            ProgressAchievement(
                key=award.category.lower().replace(" ", "_"),
                label=award.category.upper(),
                title=award.title,
                value=f"{award.score:.0f}/100",
                detail=award.reason,
                activity_date=award.activity_date,
                activity_id=award.activity_id,
            )
        )
        if len(achievements) >= 4:
            break
    return tuple(achievements), best_runs.candidate_count


def build_progress_coach_detail(
    athlete_id: int,
    *,
    reference_date: datetime.date | None = None,
) -> ProgressCoachDetail | None:
    """Compose Progress, age grade and achievements for one athlete."""
    progress = build_progress_summary(athlete_id, reference_date=reference_date)
    if progress is None:
        return None
    effective_date = datetime.date.fromisoformat(progress.reference_date)
    passport = build_athlete_passport(athlete_id, reference_date=effective_date)
    if passport is None:
        return None
    achievements, candidate_count = _achievements(athlete_id)
    trend = progress.aerobic.trend_percent
    coach_message = (
        f"Adjusted aerobic efficiency is {trend:+.1f}% while the latest six "
        f"weeks average {progress.rhythm.reliable_miles_per_week:.1f} reliable "
        "miles. The direction is supported by comparable evidence."
        if trend is not None
        else (
            f"The latest six weeks average "
            f"{progress.rhythm.reliable_miles_per_week:.1f} reliable miles. "
            "More comparable easy runs are needed before calling a fitness trend."
        )
    )
    return ProgressCoachDetail(
        athlete_id=athlete_id,
        athlete_name=progress.athlete_name,
        progress=progress,
        age_grade_all_time=passport.age_grade_all_time,
        age_grade_last_12_months=passport.age_grade_last_12_months,
        age_grade_summary=_age_grade_summary(
            passport.age_grade_last_12_months,
            passport.age_grade_all_time,
        ),
        pb_development_summary=_pb_development_summary(progress),
        coach_message=coach_message,
        next_focus=_next_focus(progress),
        achievements=achievements,
        achievement_candidate_count=candidate_count,
    )
