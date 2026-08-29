"""Athlete-facing Learning Coach composition.

The existing Learning Engine remains the source for athlete-specific
associations. This module adds a curated coaching library and selects one
timely lesson from the athlete's saved week and source-labelled recovery
context. General guidance is never presented as a personal finding.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import datetime

from core.database import get_connection
from core.learning_engine import AthleteLearningProfile, build_learning_profile
from core.operational_block import OperationalWeek, build_operational_block_week
from core.progress import ProgressSummary, build_progress_summary
from core.recovery_coach import RecoveryHealthSignal, build_recovery_health_signal


MODEL_VERSION = 1


@dataclass(frozen=True)
class LearningLibraryInsight:
    key: str
    topic: str
    coach: str
    headline: str
    explanation: str
    action: str
    families: tuple[str, ...]
    basis: str = "Curated coaching principle"


@dataclass(frozen=True)
class DailyLearningLesson:
    insight: LearningLibraryInsight
    why_today: str
    personal_evidence: str
    confidence: str


@dataclass(frozen=True)
class LearningCoachDetail:
    athlete_id: int
    athlete_name: str
    reference_date: str
    context_family: str
    context_label: str
    daily_lesson: DailyLearningLesson
    related_insights: tuple[LearningLibraryInsight, ...]
    library: tuple[LearningLibraryInsight, ...]
    topics: tuple[str, ...]
    profile: AthleteLearningProfile
    progress: ProgressSummary | None
    week: OperationalWeek | None
    health: RecoveryHealthSignal
    limitations: tuple[str, ...]
    model_version: int = MODEL_VERSION


def _item(
    key: str,
    topic: str,
    coach: str,
    headline: str,
    explanation: str,
    action: str,
    *families: str,
) -> LearningLibraryInsight:
    return LearningLibraryInsight(
        key=key,
        topic=topic,
        coach=coach,
        headline=headline,
        explanation=explanation,
        action=action,
        families=tuple(families) or ("all",),
    )


LEARNING_LIBRARY = (
    _item("easy-repeatable", "Easy running", "Training Coach", "Easy should be repeatable.", "Easy running supports the rest of the week when the effort remains conversational rather than drifting towards moderate work.", "Finish knowing you could comfortably have continued.", "easy", "recovery"),
    _item("easy-terrain", "Easy running", "Environment Coach", "Let terrain choose the pace.", "Hills, trail and weather can change pace without changing the purpose of an easy run.", "Use breathing and effort first when conditions are not neutral.", "easy", "recovery"),
    _item("easy-strides", "Easy running", "Training Coach", "Keep strides distinct from the run.", "Short relaxed strides can support coordination without turning the surrounding easy run into a hidden interval session.", "Run each stride smoothly and take enough recovery to preserve form.", "easy"),
    _item("easy-accumulation", "Easy running", "Lead Coach", "Aerobic development accumulates quietly.", "One easy run rarely proves fitness; repeated controlled weeks create the more trustworthy signal.", "Judge the trend over several comparable weeks.", "easy", "recovery"),

    _item("quality-first-rep", "Quality sessions", "Workout Coach", "Let the first repetition establish control.", "Starting a demanding session too hard can turn useful volume into survival before the final repetitions.", "Aim for the last useful repetition to resemble the first.", "threshold", "quality"),
    _item("quality-purpose", "Quality sessions", "Training Coach", "One session needs one main purpose.", "Threshold, VO₂ and speed sessions create different demands; combining every intensity can blur both execution and learning.", "Know the session's primary purpose before starting.", "threshold", "quality"),
    _item("quality-recovery", "Quality sessions", "Workout Coach", "Recovery is part of the prescription.", "Cutting recoveries to make a session harder can change the stimulus and reduce the quality of later work.", "Use the planned recovery unless the session explicitly calls for progression.", "threshold", "quality"),
    _item("quality-rpe", "Quality sessions", "Workout Coach", "Use more than pace alone.", "Wind, heat and gradients change pace, while heart rate can lag short repetitions.", "Combine pace with effort, breathing and repetition quality.", "threshold", "quality"),

    _item("long-start", "Long runs", "Endurance Coach", "A long run rewards a patient first half.", "Starting controlled protects form, fuel and decision-making for the later miles where durability becomes visible.", "Make the opening third feel deliberately comfortable.", "long"),
    _item("long-fuel", "Long runs", "Nutrition Coach", "Practise fuelling before race day.", "Selected long runs provide a low-pressure place to test familiar carbohydrate, fluid and carrying choices.", "Use products and timings already tolerated in training.", "long", "race"),
    _item("long-durability", "Long runs", "Endurance Coach", "Stable effort can matter more than average pace.", "A controlled finish and limited late-run drift often say more about endurance than forcing a faster average.", "Review how the final third compared with the opening third.", "long"),
    _item("long-continuity", "Long runs", "Lead Coach", "Missing one long run does not erase endurance.", "Endurance reflects accumulated training, while forcing a compromised run can create a larger interruption.", "Resume the useful sequence without trying to repay missed miles.", "long", "recovery"),

    _item("recovery-space", "Recovery", "Recovery Coach", "Easy days absorb demanding days.", "Adaptation occurs between hard sessions, so recovery running and rest are active parts of the programme.", "Protect the spacing before the next important session.", "rest", "recovery", "easy"),
    _item("recovery-feeling", "Recovery", "Recovery Coach", "Your own feeling takes precedence.", "Wearable trends provide context, but unusual fatigue, illness or focal pain should not be dismissed because a dashboard looks favourable.", "Reduce or stop if something feels meaningfully wrong.", "rest", "recovery", "health"),
    _item("recovery-hrv", "Recovery", "Recovery Coach", "HRV is personal context, not a competition.", "HRV values are most useful when compared with the same athlete's source-consistent baseline rather than another runner's number.", "Look for repeated change and compare it with how you feel.", "health", "recovery"),
    _item("recovery-sleep", "Recovery", "Recovery Coach", "Protect the routine before chasing a perfect night.", "A repeatable sleep opportunity usually provides more useful context than reacting strongly to one unusual reading.", "Keep bedtime and waking routines as consistent as practical.", "rest", "recovery", "health"),

    _item("race-start", "Race preparation", "Race Coach", "Race the opening kilometre with restraint.", "An ambitious start can borrow disproportionately from the final part of the race.", "Settle first, then make deliberate decisions after the early congestion clears.", "race"),
    _item("race-conditions", "Race preparation", "Environment Coach", "Translate capability into today's conditions.", "Wind, warmth, hills and trail can alter the clock without changing underlying fitness.", "Choose effort and pacing for the course actually in front of you.", "race"),
    _item("race-rehearsal", "Race preparation", "Race Coach", "Rehearse choices, not just pace.", "Kit, breakfast, warm-up and fuelling become more reliable when tested before the target event.", "Use one suitable session as a calm race-day rehearsal.", "race", "long"),
    _item("race-confidence", "Race preparation", "Lead Coach", "Use a prediction as a range, not a promise.", "A prediction combines evidence and uncertainty; it cannot know race-day weather, health or execution in advance.", "Build confidence from the evidence while retaining a sensible pacing range.", "race"),

    _item("fuel-normal", "Fuel and hydration", "Nutrition Coach", "Normal food does most of the work.", "Regular meals containing carbohydrate, protein and varied foods provide the foundation before specialist sports products matter.", "Build the day's meals around the training demand.", "all"),
    _item("fuel-before", "Fuel and hydration", "Nutrition Coach", "Practise the timing that suits you.", "Pre-run tolerance varies, so one universal meal timing is less useful than a familiar routine tested in training.", "Record what you ate, when, and how the run felt.", "quality", "long", "race"),
    _item("fuel-after", "Fuel and hydration", "Nutrition Coach", "Recovery starts with the next normal meal.", "After demanding or long running, carbohydrate, protein and fluid support the return to normal training.", "Eat a familiar balanced meal rather than waiting for a perfect product.", "quality", "threshold", "long", "race"),
    _item("fuel-thirst", "Fuel and hydration", "Nutrition Coach", "Hydration needs change with conditions.", "Duration, heat, sweat rate and access to fluid all affect what is practical; more is not automatically better.", "Start normally hydrated and practise a sensible plan on longer runs.", "long", "race", "quality"),

    _item("strength-consistency", "Strength and mobility", "Strength Coach", "Small consistent doses can be enough.", "Strength work supports running when it is repeatable and does not routinely compromise key sessions.", "Prioritise controlled movements and gradual progression.", "all"),
    _item("strength-pain", "Strength and mobility", "Strength Coach", "Pain changes the decision.", "Mobility or strength exercises are not tests to push through sharp, focal or worsening pain.", "Use a comfortable range and stop if symptoms worsen.", "recovery", "health"),
    _item("strength-calves", "Strength and mobility", "Strength Coach", "Compare control as well as repetitions.", "Calf raises are more informative when comfort, range and control are compared between sides.", "Note meaningful asymmetry rather than chasing a maximum count.", "all"),
    _item("strength-purpose", "Strength and mobility", "Strength Coach", "Strength should support the running week.", "Heavy leg work placed too close to a key run can change the quality of both sessions.", "Leave suitable space around the week's most important running demand.", "quality", "long", "race"),

    _item("data-trend", "Understanding data", "Lead Coach", "One run is evidence, not a verdict.", "A single unusually good or poor session can reflect route, weather, fatigue or measurement noise.", "Look for repeated change across comparable runs.", "all"),
    _item("data-confidence", "Understanding data", "Lead Coach", "Confidence belongs beside the number.", "The same prediction can be useful or misleading depending on the depth, relevance and recency of its evidence.", "Read the range and confidence before the central estimate.", "race", "all"),
    _item("data-purpose", "Understanding data", "Workout Coach", "Compare sessions with the same purpose.", "Warm-ups, recoveries and different workout types should not be mixed into one pace trend.", "Compare like with like before calling improvement.", "quality", "threshold", "all"),
    _item("data-device", "Understanding data", "Lead Coach", "A sensor can be wrong.", "Unusual heart rate, GPS or elevation values should be checked against the run itself before influencing coaching.", "Mark unreliable evidence rather than forcing an explanation.", "all"),
)


def _athlete_name(athlete_id: int, progress: ProgressSummary | None) -> str:
    if progress is not None:
        return progress.athlete_name
    connection = get_connection()
    row = connection.execute(
        "SELECT first_name, last_name FROM athletes WHERE id = ?",
        (int(athlete_id),),
    ).fetchone()
    connection.close()
    if row is None:
        return "Athlete"
    return f"{row[0] or ''} {row[1] or ''}".strip() or "Athlete"


def _context(
    week: OperationalWeek | None,
    today: datetime.date,
) -> tuple[str, str, str]:
    if week is None:
        return "all", "Current training", "No saved-week session is available, so today’s lesson is selected from general coaching guidance."
    current = next((day for day in week.days if day.date == today.isoformat()), None)
    if current is not None:
        family = current.planned_family or "all"
        return family, current.planned_type, f"Today’s saved direction is {current.planned_type.lower()}."
    next_run = week.next_run
    family = next_run.family or "all"
    return family, next_run.session_type or "Next run", f"The next saved direction is {str(next_run.session_type or 'running').lower()} {next_run.timing.lower()}."


def _health_caution(health: RecoveryHealthSignal) -> bool:
    return any((
        health.hrv_status == "Below recent HRV baseline",
        health.resting_hr_status == "Resting HR is above baseline",
        health.sleep_status == "Sleep duration is below baseline",
    ))


def _personal_evidence(profile: AthleteLearningProfile) -> str:
    if not profile.patterns:
        return "Personal workout-response evidence is still building; this lesson is general coaching guidance."
    pattern = profile.patterns[0]
    return (
        f"The learning engine currently has {pattern.trusted_session_count} trusted "
        f"{pattern.family_label.lower()} sessions and {pattern.response_observation_count} "
        "complete response windows. That association remains observational."
    )


def _select_lesson(
    *,
    athlete_id: int,
    today: datetime.date,
    family: str,
    context_reason: str,
    profile: AthleteLearningProfile,
    health: RecoveryHealthSignal,
) -> DailyLearningLesson:
    if _health_caution(health):
        insight = next(item for item in LEARNING_LIBRARY if item.key == "recovery-feeling")
        reason = "At least one connected recovery trend is outside its recent personal range. How the athlete feels must decide what happens next."
        confidence = health.confidence
    else:
        candidates = [
            item for item in LEARNING_LIBRARY
            if family in item.families or "all" in item.families
        ]
        insight = candidates[(today.toordinal() + int(athlete_id)) % len(candidates)]
        reason = context_reason
        confidence = "Personal context" if family != "all" else "General guidance"
    return DailyLearningLesson(
        insight=insight,
        why_today=reason,
        personal_evidence=_personal_evidence(profile),
        confidence=confidence,
    )


def build_learning_coach_detail(
    athlete_id: int,
    *,
    today: datetime.date | None = None,
) -> LearningCoachDetail:
    """Compose the athlete-facing lesson without changing training decisions."""
    today = today or datetime.date.today()
    with ThreadPoolExecutor(max_workers=4, thread_name_prefix="pp-learning") as executor:
        profile_future = executor.submit(build_learning_profile, athlete_id)
        progress_future = executor.submit(build_progress_summary, athlete_id, reference_date=today)
        week_future = executor.submit(build_operational_block_week, athlete_id, today=today)
        health_future = executor.submit(build_recovery_health_signal, athlete_id, today=today)
        profile = profile_future.result()
        progress = progress_future.result()
        week = week_future.result()
        health = health_future.result()

    family, label, context_reason = _context(week, today)
    lesson = _select_lesson(
        athlete_id=athlete_id,
        today=today,
        family=family,
        context_reason=context_reason,
        profile=profile,
        health=health,
    )
    related = tuple(
        item for item in LEARNING_LIBRARY
        if item.key != lesson.insight.key
        and (family in item.families or "all" in item.families)
    )[:3]
    topics = tuple(dict.fromkeys(item.topic for item in LEARNING_LIBRARY))
    return LearningCoachDetail(
        athlete_id=int(athlete_id),
        athlete_name=_athlete_name(athlete_id, progress),
        reference_date=today.isoformat(),
        context_family=family,
        context_label=label,
        daily_lesson=lesson,
        related_insights=related,
        library=LEARNING_LIBRARY,
        topics=topics,
        profile=profile,
        progress=progress,
        week=week,
        health=health,
        limitations=(
            "Daily lessons are coaching guidance, not medical diagnosis or treatment.",
            "Athlete-specific learning is observational and does not prove that one workout caused a later result.",
            "Learning Coach does not silently alter the approved Training Block or next-session prescription.",
            "Nutrition and hydration guidance stays general; individual medical needs require appropriate professional advice.",
        ),
    )
