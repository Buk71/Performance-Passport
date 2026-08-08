"""
Coach's Journal.

The Journal is the athlete-facing synthesis layer for a recent run.

It does not invent new performance analysis. It asks the existing engines:
- Recognition Engine: what deserves celebrating?
- Decision Engine: what is the clearest current opportunity?
- Training Blocks: why does this run matter in the current block?
- Decision Engine: what is the provisional next focus?

The result is deliberately short enough to read in roughly 30 seconds.

Recognition before recommendation.
Every run has something to celebrate.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime

from core.capability import build_capability
from core.coach_brain import CoachBrain
from core.coach_consensus import build_coach_consensus
from core.coaching import RunProfile
from core.database import (
    get_active_goal,
    get_connection,
    get_effective_athlete_thresholds,
)
from core.decision_engine import build_decision
from core.easy_run_coach import build_easy_run_coach
from core.evidence_engine import build_athlete_evidence_profile
from core.performance_dna import build_performance_dna
from core.performance_recognition import (
    Recognition,
    build_recognition_index,
    recognition_key,
)
from core.training_blocks import (
    TrainingBlock,
    block_progress,
    get_active_training_block,
)


@dataclass(frozen=True)
class JournalEntry:
    athlete_id: int
    activity_date: str | None
    activity_title: str
    category: str | None

    todays_win: str
    todays_win_detail: str

    next_opportunity: str
    next_opportunity_detail: str

    block_progress: str
    block_progress_detail: str

    next_focus: str
    next_focus_detail: str

    journal_title: str
    what_changed: tuple[str, ...]

    coach_note: str
    evidence_confidence: float

    recognition_rank: int | None
    recognition_total: int | None
    recognition_12m_rank: int | None

    model_version: int = 1


def _run_profiles(athlete_id: int) -> list[RunProfile]:
    thresholds = get_effective_athlete_thresholds(athlete_id)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            activity_date,
            title,
            distance_m,
            moving_time_s,
            avg_hr,
            max_hr,
            sport_id,
            elevation_up_m,
            temperature_c,
            humidity
        FROM activities
        WHERE athlete_id = ?
        ORDER BY activity_datetime DESC, id DESC
        """,
        (athlete_id,),
    )
    rows = cursor.fetchall()
    conn.close()

    profiles = []

    for (
        activity_date,
        title,
        distance_value,
        moving_time_s,
        avg_hr,
        max_hr,
        sport_id,
        elevation_m,
        temperature_c,
        humidity,
    ) in rows:
        try:
            distance_value = float(distance_value or 0.0)
        except (TypeError, ValueError):
            distance_value = 0.0

        # Historical Runalyze imports store km in the legacy distance_m field.
        distance_km = (
            distance_value / 1000.0
            if distance_value > 250.0
            else distance_value
        )

        profiles.append(
            RunProfile(
                athlete_id=athlete_id,
                activity_date=activity_date,
                title=title,
                distance_km=distance_km,
                moving_time_seconds=moving_time_s,
                avg_hr=avg_hr,
                run_max_hr=max_hr,
                sport_id=sport_id,
                elevation_m=elevation_m,
                temperature_c=temperature_c,
                humidity=humidity,
                lt1_hr=thresholds.get("lt1_hr"),
                lt2_hr=thresholds.get("lt2_hr"),
                athlete_max_hr=thresholds.get("athlete_max_hr"),
            )
        )

    return profiles


def _latest_recognised_run(
    runs: list[RunProfile],
    recognition_index: dict[str, Recognition],
) -> tuple[RunProfile | None, Recognition | None]:
    for run in runs:
        recognition = recognition_index.get(
            recognition_key(run)
        )
        if recognition is not None:
            return run, recognition

    return None, None


def _build_decision_context(
    athlete_id: int,
    runs: list[RunProfile],
    recognition_index: dict[str, Recognition],
):
    conn = get_connection()
    evidence_profile = build_athlete_evidence_profile(
        conn,
        athlete_id=athlete_id,
    )
    conn.close()

    brain = CoachBrain(athlete_id)
    evidence_bundle = brain.build_evidence()
    prediction = brain.goal_prediction()
    goal = get_active_goal(athlete_id)

    easy_result = build_easy_run_coach(
        runs,
        evidence_profile=evidence_profile,
    )

    prediction_seconds = (
        prediction.predicted_seconds
        if prediction.available
        else None
    )

    performance_dna = build_performance_dna(
        evidence_bundle,
        consensus_prediction_s=prediction_seconds,
        easy_run_coach=easy_result,
    )

    consensus = build_coach_consensus(
        performance_dna,
        consensus_prediction_s=prediction_seconds,
    )

    capability = build_capability(
        predicted_seconds=prediction_seconds,
        prediction_confidence=(
            prediction.confidence
            if prediction.available
            else 0.0
        ),
        performance_dna=performance_dna,
        coach_consensus=consensus,
        target_seconds=(
            goal["target_time_s"]
            if goal is not None
            else None
        ),
    )

    return build_decision(
        performance_dna=performance_dna,
        coach_consensus=consensus,
        capability=capability,
        recognition_index=recognition_index,
    )


def _block_message(
    block: TrainingBlock | None,
    *,
    activity_date: str | None,
) -> tuple[str, str]:
    if block is None:
        return (
            "Training context still open",
            (
                "This run still adds useful evidence. Once a Training Block "
                "is active, the Journal will connect each run to its purpose."
            ),
        )

    today = None
    if activity_date:
        try:
            today = datetime.date.fromisoformat(
                str(activity_date)[:10]
            )
        except (TypeError, ValueError):
            today = None

    progress = block_progress(
        block,
        today=today or datetime.date.today(),
    )

    if (
        progress.week_number is not None
        and progress.total_weeks is not None
        and progress.week_number > 0
    ):
        headline = (
            f"Week {progress.week_number} of "
            f"{progress.total_weeks}: {block.name}"
        )
    else:
        headline = block.name

    focus = block.primary_focus or "balanced development"
    phase = block.current_phase or "current"

    detail = (
        f"This session sits inside the {phase.lower()} phase. "
        f"The block's main focus is {focus.lower()}."
    )

    return headline, detail


def _coach_note(
    recognition: Recognition,
    *,
    opportunity_label: str | None,
    block: TrainingBlock | None,
) -> str:
    pieces = [recognition.positive_detail]

    if block is not None:
        pieces.append(
            (
                f"This run should be judged by how well it moves "
                f"{block.name} forward, not by pace alone."
            )
        )

    if opportunity_label:
        pieces.append(
            (
                f"The next gains are most likely to come from "
                f"{opportunity_label.lower()} development."
            )
        )

    return " ".join(pieces)


def _journal_title(
    recognition: Recognition,
    *,
    decision_direction: str | None,
    block: TrainingBlock | None,
) -> str:
    key = recognition.celebration.lower()
    factors = " ".join(recognition.environment_factors).lower()

    if recognition.rank == 1 and recognition.total >= 3:
        return "A new benchmark."

    if "heat" in factors or "dew point" in factors:
        if recognition.top_percent <= 10:
            return "Winning in the heat."
        return "Strong work in tough conditions."

    if "trail" in factors or "off-road" in factors:
        if recognition.top_percent <= 10:
            return "A standout trail day."
        return "Trail strength banked."

    if "aerobic control" in key or "controlled effort" in key:
        return "Patience paid off."

    if recognition.category_key == "long_easy":
        return "Endurance quietly building."

    if recognition.category_key == "threshold":
        return "Threshold work moving the needle."

    if recognition.category_key in {"vo2", "speed"}:
        return "Quality speed work banked."

    if decision_direction in {"Improving", "Positive"}:
        return "Momentum is building."

    if block is not None:
        return "Exactly what this block needed."

    return "Another useful step forward."


def _what_changed(
    recognition: Recognition,
    *,
    decision,
    block: TrainingBlock | None,
) -> tuple[str, ...]:
    items = []

    if recognition.rank == 1 and recognition.total >= 3:
        items.append(
            f"🏆 New #1 {recognition.category_label} performance in your history."
        )
    elif recognition.top_percent <= 10:
        items.append(
            f"⭐ This run now sits in your top "
            f"{max(int(round(recognition.top_percent)), 1)}% of "
            f"{recognition.category_label} sessions."
        )
    elif recognition.rank_12m is not None and recognition.total_12m >= 3:
        if recognition.rank_12m <= max(3, round(recognition.total_12m * 0.10)):
            items.append(
                f"📈 It is now #{recognition.rank_12m} of "
                f"{recognition.total_12m} comparable sessions in the last 12 months."
            )

    if recognition.environment_adjustment_s_per_km >= 5:
        context = ", ".join(recognition.environment_factors[:2])
        if context:
            items.append(
                f"🌦️ The ranking improved after recognising {context}."
            )
        else:
            items.append(
                "🌦️ Environmental difficulty was significant enough to change "
                "how the run is judged."
            )

    if recognition.moving_percent is not None and recognition.moving_percent >= 97:
        items.append(
            f"▶️ Continuity was strong at {recognition.moving_percent:.1f}% moving."
        )

    if recognition.trend_label in {"Trending stronger", "Positive trend"}:
        items.append(
            f"📈 {recognition.trend_label}: this run was stronger than your "
            "recent comparable baseline."
        )

    if decision.primary_opportunity_label:
        items.append(
            f"🎯 The broader coaching priority remains "
            f"{decision.primary_opportunity_label.lower()}."
        )

    if block is not None and block.current_phase:
        items.append(
            f"📅 This evidence now belongs to the {block.current_phase.lower()} "
            f"phase of {block.name}."
        )

    if not items:
        items.append(
            "✨ This run added another useful piece of evidence to your personal "
            "coaching picture."
        )

    return tuple(items[:4])


def build_latest_journal_entry(
    athlete_id: int,
) -> JournalEntry | None:
    runs = _run_profiles(athlete_id)

    if not runs:
        return None

    recognition_index = build_recognition_index(
        runs,
        athlete_id=athlete_id,
    )

    latest_run, recognition = _latest_recognised_run(
        runs,
        recognition_index,
    )

    if latest_run is None or recognition is None:
        return None

    decision = _build_decision_context(
        athlete_id,
        runs,
        recognition_index,
    )

    block = get_active_training_block(athlete_id)
    block_title, block_detail = _block_message(
        block,
        activity_date=latest_run.activity_date,
    )

    opportunity_label = (
        decision.primary_opportunity_label
        or "Development"
    )

    next_opportunity = (
        f"{opportunity_label} is the clearest next opportunity"
        if decision.primary_opportunity_label
        else "The next opportunity is still becoming clear"
    )

    next_opportunity_detail = (
        decision.summary
        if decision.summary
        else decision.direction_detail
    )

    if decision.provisional_next_session:
        next_focus = decision.provisional_next_session
        next_focus_detail = decision.recommendation_status
    else:
        next_focus = "Keep building evidence"
        next_focus_detail = (
            "The Decision Engine is not yet confident enough to name a "
            "specific session family."
        )

    journal_title = _journal_title(
        recognition,
        decision_direction=decision.direction,
        block=block,
    )
    what_changed = _what_changed(
        recognition,
        decision=decision,
        block=block,
    )

    return JournalEntry(
        athlete_id=athlete_id,
        activity_date=latest_run.activity_date,
        activity_title=latest_run.title or recognition.category_label,
        category=recognition.category_label,
        todays_win=recognition.celebration,
        todays_win_detail=recognition.positive_detail,
        next_opportunity=next_opportunity,
        next_opportunity_detail=next_opportunity_detail,
        block_progress=block_title,
        block_progress_detail=block_detail,
        next_focus=next_focus,
        next_focus_detail=next_focus_detail,
        journal_title=journal_title,
        what_changed=what_changed,
        coach_note=_coach_note(
            recognition,
            opportunity_label=decision.primary_opportunity_label,
            block=block,
        ),
        evidence_confidence=round(
            (
                recognition.confidence * 0.55
                + decision.confidence * 0.45
            ),
            4,
        ),
        recognition_rank=recognition.rank,
        recognition_total=recognition.total,
        recognition_12m_rank=recognition.rank_12m,
    )
