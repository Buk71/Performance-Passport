"""Runner Journey foundation with adaptive plan-week control."""

from __future__ import annotations

from dataclasses import dataclass
import datetime
import json
from typing import Any

from core.database import create_runner_journey_tables, get_connection


COUCH_TO_5K = "couch_to_5k"
FIVE_TO_TEN_K = "5k_to_10k"

C25K_STAGES = (
    "walking_foundation",
    "run_walk_short",
    "run_walk_build",
    "run_blocks_5",
    "run_blocks_8",
    "run_blocks_10",
    "continuous_15",
    "continuous_20",
    "continuous_25",
    "continuous_30",
    "5k_ready",
)


FIVE_TO_TEN_K_STAGES = (
    "5k_consistency",
    "build_6k",
    "build_7k",
    "build_8k",
    "build_9k",
    "10k_ready",
)

JOURNEY_STATUSES = ("Active", "Paused", "Complete", "Archived")
PROGRESSION_DECISIONS = ("progress", "repeat", "regress", "hold", "graduate")


@dataclass(frozen=True)
class CouchTo5KAssessment:
    can_walk_30_min: bool
    current_running: bool
    comfortable_continuous_run_min: float
    sessions_per_week: int
    goal_mode: str = "complete_5k"
    target_date: str | None = None



@dataclass(frozen=True)
class FiveToTenKAssessment:
    """Starting evidence for the 5K -> 10K journey.

    This pathway is for runners who can already complete 5K. It starts from
    demonstrated durability rather than a target pace.
    """

    can_complete_5k: bool
    recent_runs_per_week: int
    recent_weekly_km: float
    longest_recent_run_km: float
    sessions_per_week: int
    goal_mode: str = "complete_10k"
    target_date: str | None = None


@dataclass(frozen=True)
class RunnerJourney:
    id: int
    athlete_id: int
    journey_type: str
    status: str
    goal_id: int | None
    entry_stage: str
    current_stage: str
    sessions_per_week: int
    started_at: str
    completed_at: str | None
    baseline: dict[str, Any]
    preferences: dict[str, Any]
    created_at: str | None
    updated_at: str | None


@dataclass(frozen=True)
class JourneyProgressEvidence:
    completed_as_planned: bool
    perceived_difficulty: str
    pain_or_concerning_symptoms: bool = False
    sessions_completed_since_decision: int = 1
    continuous_run_minutes: float | None = None
    completed_5k: bool = False
    days_since_last_session: int | None = None
    activity_id: int | None = None
    activity_date: str | None = None
    activity_distance_km: float | None = None
    activity_moving_time_s: float | None = None


@dataclass(frozen=True)
class JourneyDecision:
    decision: str
    stage_before: str
    stage_after: str
    reason: str
    graduate: bool = False
    week_before: int | None = None
    week_after: int | None = None


def _stage_index(stage: str) -> int:
    try:
        return C25K_STAGES.index(stage)
    except ValueError as exc:
        raise ValueError(f"Unsupported Couch -> 5K stage: {stage}") from exc



def _five_to_ten_stage_index(stage: str) -> int:
    try:
        return FIVE_TO_TEN_K_STAGES.index(stage)
    except ValueError as exc:
        raise ValueError(f"Unsupported 5K -> 10K stage: {stage}") from exc


def choose_five_to_ten_k_entry_stage(
    assessment: FiveToTenKAssessment,
) -> str:
    """Choose the first durability stage from demonstrated recent running."""
    if not assessment.can_complete_5k:
        raise ValueError(
            "5K -> 10K requires a demonstrated 5K completion. "
            "Use Couch -> 5K first."
        )
    if assessment.sessions_per_week < 2:
        raise ValueError("5K -> 10K requires at least two training days per week.")

    longest = max(float(assessment.longest_recent_run_km or 0.0), 0.0)
    weekly = max(float(assessment.recent_weekly_km or 0.0), 0.0)
    days = max(int(assessment.recent_runs_per_week or 0), 0)

    # Conservative entry: longest-run durability is primary, with weekly
    # consistency used to stop a one-off long run skipping too far ahead.
    if days < 2 or weekly < 8.0 or longest < 5.5:
        return "5k_consistency"
    if longest < 6.5 or weekly < 10.0:
        return "build_6k"
    if longest < 7.5 or weekly < 12.0:
        return "build_7k"
    if longest < 8.5 or weekly < 14.0:
        return "build_8k"
    if longest < 9.5 or weekly < 16.0:
        return "build_9k"
    return "10k_ready"


def decide_five_to_ten_k_progress(
    current_stage: str,
    evidence: JourneyProgressEvidence,
) -> JourneyDecision:
    """Evidence-led 5K -> 10K progression.

    The same safety rules apply as Couch -> 5K: pain never increases load,
    a hard/incomplete session repeats or steps back, and controlled successful
    sessions are required before progressing.
    """
    index = _five_to_ten_stage_index(current_stage)

    if evidence.completed_5k and current_stage == "10k_ready":
        # `completed_5k` is retained for backwards compatibility in the shared
        # evidence model. 10K graduation is handled by the dedicated distance
        # field below when present.
        pass

    completed_distance_km = float(evidence.activity_distance_km or 0.0)
    if completed_distance_km >= 9.95:
        return JourneyDecision(
            decision="graduate",
            stage_before=current_stage,
            stage_after="10k_ready",
            reason="The athlete has completed 10K and met the journey goal.",
            graduate=True,
        )

    if evidence.pain_or_concerning_symptoms:
        return JourneyDecision(
            decision="hold",
            stage_before=current_stage,
            stage_after=current_stage,
            reason=(
                "Do not increase running load while pain or concerning "
                "symptoms are reported."
            ),
        )

    if evidence.days_since_last_session is not None and evidence.days_since_last_session >= 14:
        after = FIVE_TO_TEN_K_STAGES[max(index - 1, 0)]
        return JourneyDecision(
            decision="regress" if after != current_stage else "repeat",
            stage_before=current_stage,
            stage_after=after,
            reason=(
                "A two-week or longer gap warrants returning conservatively."
            ),
        )

    difficulty = str(evidence.perceived_difficulty or "").strip().lower()

    if not evidence.completed_as_planned:
        if difficulty in {"very hard", "maximal"} and index > 0:
            return JourneyDecision(
                decision="regress",
                stage_before=current_stage,
                stage_after=FIVE_TO_TEN_K_STAGES[index - 1],
                reason=(
                    "The planned session was not completed and felt very hard, "
                    "so step back one stage."
                ),
            )
        return JourneyDecision(
            decision="repeat",
            stage_before=current_stage,
            stage_after=current_stage,
            reason="The planned session was not completed; repeat this stage.",
        )

    if difficulty in {"hard", "very hard", "maximal"}:
        return JourneyDecision(
            decision="repeat",
            stage_before=current_stage,
            stage_after=current_stage,
            reason=(
                "The session was completed but difficult; consolidate this "
                "stage before increasing distance."
            ),
        )

    if evidence.sessions_completed_since_decision < 2:
        return JourneyDecision(
            decision="hold",
            stage_before=current_stage,
            stage_after=current_stage,
            reason=(
                "One controlled successful session is useful evidence; "
                "two are required before progressing."
            ),
        )

    if current_stage == "10k_ready":
        return JourneyDecision(
            decision="hold",
            stage_before=current_stage,
            stage_after=current_stage,
            reason=(
                "The athlete is ready for a controlled 10K completion. "
                "Complete the distance to graduate."
            ),
        )

    return JourneyDecision(
        decision="progress",
        stage_before=current_stage,
        stage_after=FIVE_TO_TEN_K_STAGES[index + 1],
        reason=(
            "Two controlled successful sessions support progressing the "
            "distance-building stage."
        ),
    )


def start_five_to_ten_k_journey(
    athlete_id: int,
    assessment: FiveToTenKAssessment,
    *,
    goal_id: int | None = None,
    started_at: datetime.date | None = None,
) -> RunnerJourney:
    """Persist an Active 5K -> 10K journey in the shared Runner Journey tables."""
    started_at = started_at or datetime.date.today()
    stage = choose_five_to_ten_k_entry_stage(assessment)

    baseline = {
        "can_complete_5k": bool(assessment.can_complete_5k),
        "recent_runs_per_week": int(assessment.recent_runs_per_week or 0),
        "recent_weekly_km": float(assessment.recent_weekly_km or 0.0),
        "longest_recent_run_km": float(assessment.longest_recent_run_km or 0.0),
    }
    from core.five_to_ten_k_plan import entry_level_for_stage

    current_level = entry_level_for_stage(stage)
    preferences = {
        "goal_mode": assessment.goal_mode,
        "target_date": assessment.target_date,
        "current_level": current_level,
        "plan_length_levels": 10,
    }

    conn = get_connection()
    cursor = conn.cursor()
    try:
        create_runner_journey_tables(cursor)
        existing = cursor.execute(
            "SELECT id FROM athlete_runner_journeys "
            "WHERE athlete_id=? AND status='Active' LIMIT 1",
            (int(athlete_id),),
        ).fetchone()
        if existing:
            raise ValueError("This athlete already has an Active Runner Journey.")

        cursor.execute(
            """INSERT INTO athlete_runner_journeys (
                   athlete_id, journey_type, status, goal_id, entry_stage,
                   current_stage, sessions_per_week, started_at,
                   baseline_json, preferences_json
               ) VALUES (?, ?, 'Active', ?, ?, ?, ?, ?, ?, ?)""",
            (
                int(athlete_id),
                FIVE_TO_TEN_K,
                goal_id,
                stage,
                stage,
                int(assessment.sessions_per_week),
                started_at.isoformat(),
                json.dumps(baseline, sort_keys=True),
                json.dumps(preferences, sort_keys=True),
            ),
        )
        journey_id = int(cursor.lastrowid)
        cursor.execute(
            """INSERT INTO runner_journey_events (
                   journey_id, athlete_id, event_type, stage_before,
                   stage_after, decision, evidence_json, reason
               ) VALUES (?, ?, 'journey_started', NULL, ?, 'start', ?, ?)""",
            (
                journey_id,
                int(athlete_id),
                stage,
                json.dumps(baseline, sort_keys=True),
                f"5K -> 10K entry assessment selected stage: {stage}.",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    journey = get_active_runner_journey(int(athlete_id))
    if journey is None:
        raise RuntimeError("Runner Journey was saved but could not be reloaded.")
    return journey



def get_five_to_ten_k_current_level(journey: RunnerJourney) -> int:
    from core.five_to_ten_k_plan import entry_level_for_stage

    value = journey.preferences.get("current_level")
    try:
        level = int(value)
    except (TypeError, ValueError):
        level = entry_level_for_stage(journey.current_stage)
    return min(max(level, 1), 10)


def set_active_five_to_ten_k_level(
    athlete_id: int,
    level_number: int,
    *,
    decision: str,
    reason: str,
) -> RunnerJourney:
    from core.five_to_ten_k_plan import stage_for_level

    if decision not in {"progress", "progress_early", "repeat", "step_back"}:
        raise ValueError("Unsupported 5K -> 10K level decision.")

    journey = get_active_runner_journey(int(athlete_id))
    if journey is None or journey.journey_type != FIVE_TO_TEN_K:
        raise ValueError("No Active 5K -> 10K journey exists.")

    level_before = get_five_to_ten_k_current_level(journey)
    level_after = min(max(int(level_number), 1), 10)
    stage_after = stage_for_level(level_after)
    preferences = dict(journey.preferences)
    preferences["current_level"] = level_after
    preferences["plan_length_levels"] = 10

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """UPDATE athlete_runner_journeys
               SET current_stage=?, preferences_json=?, updated_at=CURRENT_TIMESTAMP
               WHERE id=? AND athlete_id=?""",
            (
                stage_after,
                json.dumps(preferences, sort_keys=True),
                journey.id,
                int(athlete_id),
            ),
        )
        cursor.execute(
            """INSERT INTO runner_journey_events (
                   journey_id, athlete_id, event_type, stage_before, stage_after,
                   decision, evidence_json, reason
               ) VALUES (?, ?, 'plan_level_decision', ?, ?, ?, ?, ?)""",
            (
                journey.id,
                int(athlete_id),
                journey.current_stage,
                stage_after,
                decision,
                json.dumps(
                    {
                        "level_before": level_before,
                        "level_after": level_after,
                    },
                    sort_keys=True,
                ),
                reason,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    updated = get_active_runner_journey(int(athlete_id))
    if updated is None:
        raise RuntimeError("5K -> 10K journey update could not be reloaded.")
    return updated



def _five_to_ten_controlled_success(evidence: JourneyProgressEvidence) -> bool:
    return (
        evidence.completed_as_planned
        and not evidence.pain_or_concerning_symptoms
        and str(evidence.perceived_difficulty or "").strip().lower()
            in {"comfortable", "moderate"}
    )


def get_five_to_ten_k_successes_since_decision(athlete_id: int) -> int:
    journey = get_active_runner_journey(int(athlete_id))
    if journey is None or journey.journey_type != FIVE_TO_TEN_K:
        return 0
    current_level = get_five_to_ten_k_current_level(journey)
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT event_type, decision, evidence_json
               FROM runner_journey_events
               WHERE journey_id=? AND athlete_id=?
               ORDER BY id DESC""",
            (journey.id, int(athlete_id)),
        ).fetchall()
    finally:
        conn.close()

    successes = 0
    for event_type, decision, text in rows:
        event_type = str(event_type or "")
        decision = str(decision or "")
        if event_type == "plan_level_decision":
            break
        if event_type != "progress_review":
            continue
        try:
            payload = json.loads(text or "{}")
        except (TypeError, json.JSONDecodeError):
            break
        if int(payload.get("level_before") or current_level) != current_level:
            break
        if decision in {"progress", "regress", "graduate", "repeat"}:
            break
        previous = JourneyProgressEvidence(
            completed_as_planned=bool(payload.get("completed_as_planned")),
            perceived_difficulty=str(payload.get("perceived_difficulty") or ""),
            pain_or_concerning_symptoms=bool(payload.get("pain_or_concerning_symptoms")),
            activity_distance_km=payload.get("activity_distance_km"),
        )
        if _five_to_ten_controlled_success(previous):
            successes += 1
        else:
            break
    return successes


def prepare_five_to_ten_k_evidence(
    athlete_id: int,
    evidence: JourneyProgressEvidence,
) -> JourneyProgressEvidence:
    prior = get_five_to_ten_k_successes_since_decision(int(athlete_id))
    current = 1 if _five_to_ten_controlled_success(evidence) else 0
    return JourneyProgressEvidence(
        completed_as_planned=evidence.completed_as_planned,
        perceived_difficulty=evidence.perceived_difficulty,
        pain_or_concerning_symptoms=evidence.pain_or_concerning_symptoms,
        sessions_completed_since_decision=prior + current,
        continuous_run_minutes=evidence.continuous_run_minutes,
        completed_5k=evidence.completed_5k,
        days_since_last_session=evidence.days_since_last_session,
        activity_id=evidence.activity_id,
        activity_date=evidence.activity_date,
        activity_distance_km=evidence.activity_distance_km,
        activity_moving_time_s=evidence.activity_moving_time_s,
    )


def preview_five_to_ten_k_progress(
    athlete_id: int,
    evidence: JourneyProgressEvidence,
) -> tuple[JourneyDecision, JourneyProgressEvidence]:
    from core.five_to_ten_k_plan import stage_for_level
    journey = get_active_runner_journey(int(athlete_id))
    if journey is None or journey.journey_type != FIVE_TO_TEN_K:
        raise ValueError("No Active 5K -> 10K journey exists.")
    prepared = prepare_five_to_ten_k_evidence(int(athlete_id), evidence)
    level = get_five_to_ten_k_current_level(journey)

    distance = float(prepared.activity_distance_km or 0.0)
    difficulty = str(prepared.perceived_difficulty or "").strip().lower()

    if distance >= 9.95:
        decision = JourneyDecision(
            "graduate", journey.current_stage, "10k_ready",
            "A recorded 10K completion meets the journey goal.", True,
            level, 10,
        )
    elif prepared.pain_or_concerning_symptoms:
        decision = JourneyDecision(
            "hold", journey.current_stage, journey.current_stage,
            "Do not increase running load while pain or concerning symptoms are reported.",
            False, level, level,
        )
    elif prepared.days_since_last_session is not None and prepared.days_since_last_session >= 14:
        after = max(1, level - 1)
        decision = JourneyDecision(
            "regress", journey.current_stage, stage_for_level(after),
            "A two-week or longer gap warrants stepping back one level.",
            False, level, after,
        )
    elif not prepared.completed_as_planned:
        after = max(1, level - 1) if difficulty in {"very hard","maximal"} else level
        kind = "regress" if after < level else "repeat"
        decision = JourneyDecision(
            kind, journey.current_stage, stage_for_level(after),
            "The planned session was not completed; reduce or repeat before progressing.",
            False, level, after,
        )
    elif difficulty in {"hard","very hard","maximal"}:
        decision = JourneyDecision(
            "repeat", journey.current_stage, journey.current_stage,
            "The session was completed but difficult; consolidate this level.",
            False, level, level,
        )
    elif prepared.sessions_completed_since_decision < 2:
        decision = JourneyDecision(
            "hold", journey.current_stage, journey.current_stage,
            "One controlled successful session is useful evidence; two are required before progressing.",
            False, level, level,
        )
    elif level >= 10:
        decision = JourneyDecision(
            "hold", journey.current_stage, journey.current_stage,
            "The athlete is 10K-ready. Complete a recorded 10K to graduate.",
            False, level, level,
        )
    else:
        after = level + 1
        decision = JourneyDecision(
            "progress", journey.current_stage, stage_for_level(after),
            "Two controlled successful sessions support progression to the next level.",
            False, level, after,
        )
    return decision, prepared


def apply_five_to_ten_k_evidence(
    athlete_id: int,
    evidence: JourneyProgressEvidence,
) -> JourneyDecision:
    journey = get_active_runner_journey(int(athlete_id))
    if journey is None or journey.journey_type != FIVE_TO_TEN_K:
        raise ValueError("No Active 5K -> 10K journey exists.")

    decision, prepared = preview_five_to_ten_k_progress(int(athlete_id), evidence)
    current_level = get_five_to_ten_k_current_level(journey)
    level_after = int(decision.week_after or current_level)
    preferences = dict(journey.preferences)
    preferences["current_level"] = level_after
    preferences["plan_length_levels"] = 10

    payload = {
        "completed_as_planned": prepared.completed_as_planned,
        "perceived_difficulty": prepared.perceived_difficulty,
        "pain_or_concerning_symptoms": prepared.pain_or_concerning_symptoms,
        "sessions_completed_since_decision": prepared.sessions_completed_since_decision,
        "days_since_last_session": prepared.days_since_last_session,
        "activity_id": prepared.activity_id,
        "activity_date": prepared.activity_date,
        "activity_distance_km": prepared.activity_distance_km,
        "activity_moving_time_s": prepared.activity_moving_time_s,
        "level_before": decision.week_before,
        "level_after": decision.week_after,
    }

    conn = get_connection()
    cursor = conn.cursor()
    try:
        create_runner_journey_tables(cursor)
        if decision.graduate:
            cursor.execute(
                """UPDATE athlete_runner_journeys
                   SET current_stage=?, status='Complete',
                       completed_at=CURRENT_TIMESTAMP, preferences_json=?,
                       updated_at=CURRENT_TIMESTAMP
                   WHERE id=? AND athlete_id=?""",
                (decision.stage_after, json.dumps(preferences, sort_keys=True),
                 journey.id, int(athlete_id)),
            )
        else:
            cursor.execute(
                """UPDATE athlete_runner_journeys
                   SET current_stage=?, preferences_json=?,
                       updated_at=CURRENT_TIMESTAMP
                   WHERE id=? AND athlete_id=?""",
                (decision.stage_after, json.dumps(preferences, sort_keys=True),
                 journey.id, int(athlete_id)),
            )
        cursor.execute(
            """INSERT INTO runner_journey_events (
                   journey_id, athlete_id, event_type, stage_before, stage_after,
                   decision, evidence_json, reason
               ) VALUES (?, ?, 'progress_review', ?, ?, ?, ?, ?)""",
            (journey.id, int(athlete_id), decision.stage_before,
             decision.stage_after, decision.decision,
             json.dumps(payload, sort_keys=True), decision.reason),
        )
        conn.commit()
    finally:
        conn.close()
    return decision


def choose_couch_to_5k_entry_stage(assessment: CouchTo5KAssessment) -> str:
    if assessment.sessions_per_week < 2:
        raise ValueError("Couch -> 5K requires at least two sessions per week.")
    minutes = max(float(assessment.comfortable_continuous_run_min or 0.0), 0.0)
    if not assessment.can_walk_30_min:
        return "walking_foundation"
    if not assessment.current_running or minutes < 2:
        return "run_walk_short"
    if minutes < 5:
        return "run_walk_build"
    if minutes < 8:
        return "run_blocks_5"
    if minutes < 10:
        return "run_blocks_8"
    if minutes < 15:
        return "run_blocks_10"
    if minutes < 20:
        return "continuous_15"
    if minutes < 25:
        return "continuous_20"
    if minutes < 30:
        return "continuous_25"
    return "continuous_30"


def _plan_week_for_stage(stage: str) -> int:
    from core.beginner_training_plan import entry_week_for_stage
    return entry_week_for_stage(stage)


def _stage_for_plan_week(week_number: int) -> str:
    from core.beginner_training_plan import stage_for_week
    return stage_for_week(week_number)


def get_journey_current_week(journey: RunnerJourney) -> int:
    value = journey.preferences.get("current_week")
    try:
        week = int(value)
    except (TypeError, ValueError):
        week = _plan_week_for_stage(journey.current_stage)
    return min(max(week, 1), 12)


def decide_couch_to_5k_progress(
    current_stage: str,
    evidence: JourneyProgressEvidence,
    *,
    current_week: int | None = None,
) -> JourneyDecision:
    index = _stage_index(current_stage)
    week_before = int(current_week or _plan_week_for_stage(current_stage))

    if evidence.completed_5k or (
        evidence.continuous_run_minutes is not None
        and float(evidence.continuous_run_minutes) >= 30.0
        and current_stage in {"continuous_30", "5k_ready"}
        and week_before >= 11
    ):
        return JourneyDecision(
            decision="graduate", stage_before=current_stage, stage_after="5k_ready",
            reason="The athlete has met the Couch -> 5K graduation standard.",
            graduate=True, week_before=week_before, week_after=12,
        )

    if evidence.pain_or_concerning_symptoms:
        return JourneyDecision(
            decision="hold", stage_before=current_stage, stage_after=current_stage,
            reason="Do not increase running load while pain or concerning symptoms are reported.",
            week_before=week_before, week_after=week_before,
        )

    if evidence.days_since_last_session is not None and evidence.days_since_last_session >= 14:
        week_after = max(1, week_before - 1)
        return JourneyDecision(
            decision="regress",
            stage_before=current_stage,
            stage_after=_stage_for_plan_week(week_after),
            reason="A two-week or longer gap warrants stepping back one plan level.",
            week_before=week_before, week_after=week_after,
        )

    difficulty = str(evidence.perceived_difficulty or "").strip().lower()
    if not evidence.completed_as_planned:
        if difficulty in {"very hard", "maximal"}:
            week_after = max(1, week_before - 1)
            return JourneyDecision(
                decision="regress", stage_before=current_stage,
                stage_after=_stage_for_plan_week(week_after),
                reason="The session was not completed and felt very hard, so step back one level.",
                week_before=week_before, week_after=week_after,
            )
        return JourneyDecision(
            decision="repeat", stage_before=current_stage, stage_after=current_stage,
            reason="The planned session was not completed; repeat this level.",
            week_before=week_before, week_after=week_before,
        )

    if difficulty in {"hard", "very hard", "maximal"}:
        return JourneyDecision(
            decision="repeat", stage_before=current_stage, stage_after=current_stage,
            reason="The session was completed but difficult; consolidate this level.",
            week_before=week_before, week_after=week_before,
        )

    if evidence.sessions_completed_since_decision < 2:
        return JourneyDecision(
            decision="hold", stage_before=current_stage, stage_after=current_stage,
            reason="One successful session is useful evidence; two are required for early progression.",
            week_before=week_before, week_after=week_before,
        )

    week_after = min(12, week_before + 1)
    return JourneyDecision(
        decision="progress", stage_before=current_stage,
        stage_after=_stage_for_plan_week(week_after),
        reason="Two controlled successful sessions support progression to the next plan level.",
        week_before=week_before, week_after=week_after,
    )


def _journey_from_row(row) -> RunnerJourney:
    return RunnerJourney(
        id=int(row[0]), athlete_id=int(row[1]), journey_type=str(row[2]),
        status=str(row[3]), goal_id=int(row[4]) if row[4] is not None else None,
        entry_stage=str(row[5]), current_stage=str(row[6]),
        sessions_per_week=int(row[7]), started_at=str(row[8]),
        completed_at=row[9], baseline=json.loads(row[10] or "{}"),
        preferences=json.loads(row[11] or "{}"),
        created_at=row[12], updated_at=row[13],
    )


def get_active_runner_journey(athlete_id: int) -> RunnerJourney | None:
    conn = get_connection()
    try:
        create_runner_journey_tables(conn.cursor())
        row = conn.execute(
            """SELECT id, athlete_id, journey_type, status, goal_id,
                      entry_stage, current_stage, sessions_per_week,
                      started_at, completed_at, baseline_json,
                      preferences_json, created_at, updated_at
               FROM athlete_runner_journeys
               WHERE athlete_id = ? AND status = 'Active'
               ORDER BY updated_at DESC, id DESC LIMIT 1""",
            (int(athlete_id),),
        ).fetchone()
    finally:
        conn.close()
    return _journey_from_row(row) if row else None


def start_couch_to_5k_journey(
    athlete_id: int,
    assessment: CouchTo5KAssessment,
    *,
    goal_id: int | None = None,
    started_at: datetime.date | None = None,
) -> RunnerJourney:
    started_at = started_at or datetime.date.today()
    stage = choose_couch_to_5k_entry_stage(assessment)
    current_week = _plan_week_for_stage(stage)
    baseline = {
        "can_walk_30_min": bool(assessment.can_walk_30_min),
        "current_running": bool(assessment.current_running),
        "comfortable_continuous_run_min": float(assessment.comfortable_continuous_run_min or 0.0),
    }
    preferences = {
        "goal_mode": assessment.goal_mode,
        "target_date": assessment.target_date,
        "current_week": current_week,
        "plan_length_weeks": 12,
    }

    conn = get_connection()
    cursor = conn.cursor()
    try:
        create_runner_journey_tables(cursor)
        existing = cursor.execute(
            "SELECT id FROM athlete_runner_journeys WHERE athlete_id=? AND status='Active' LIMIT 1",
            (int(athlete_id),),
        ).fetchone()
        if existing:
            raise ValueError("This athlete already has an Active Runner Journey.")
        cursor.execute(
            """INSERT INTO athlete_runner_journeys (
                   athlete_id, journey_type, status, goal_id, entry_stage,
                   current_stage, sessions_per_week, started_at,
                   baseline_json, preferences_json
               ) VALUES (?, ?, 'Active', ?, ?, ?, ?, ?, ?, ?)""",
            (
                int(athlete_id), COUCH_TO_5K, goal_id, stage, stage,
                int(assessment.sessions_per_week), started_at.isoformat(),
                json.dumps(baseline, sort_keys=True),
                json.dumps(preferences, sort_keys=True),
            ),
        )
        journey_id = int(cursor.lastrowid)
        cursor.execute(
            """INSERT INTO runner_journey_events (
                   journey_id, athlete_id, event_type, stage_before,
                   stage_after, decision, evidence_json, reason
               ) VALUES (?, ?, 'journey_started', NULL, ?, 'start', ?, ?)""",
            (
                journey_id, int(athlete_id), stage,
                json.dumps({"entry_week": current_week, **baseline}, sort_keys=True),
                f"Entry assessment selected plan level {current_week}: {stage}.",
            ),
        )
        conn.commit()
    finally:
        conn.close()
    journey = get_active_runner_journey(int(athlete_id))
    if journey is None:
        raise RuntimeError("Runner Journey was saved but could not be reloaded.")
    return journey


def set_active_journey_week(
    athlete_id: int,
    week_number: int,
    *,
    decision: str,
    reason: str,
) -> RunnerJourney:
    """Explicitly move/repeat a Couch -> 5K plan level and audit the choice."""
    if decision not in {"progress", "progress_early", "repeat", "step_back"}:
        raise ValueError("Unsupported journey week decision.")
    journey = get_active_runner_journey(int(athlete_id))
    if journey is None or journey.journey_type != COUCH_TO_5K:
        raise ValueError("No Active Couch -> 5K journey exists.")
    week_before = get_journey_current_week(journey)
    week_after = min(max(int(week_number), 1), 12)
    stage_after = _stage_for_plan_week(week_after)
    preferences = dict(journey.preferences)
    preferences["current_week"] = week_after

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """UPDATE athlete_runner_journeys
               SET current_stage=?, preferences_json=?, updated_at=CURRENT_TIMESTAMP
               WHERE id=? AND athlete_id=?""",
            (
                stage_after, json.dumps(preferences, sort_keys=True),
                journey.id, int(athlete_id),
            ),
        )
        cursor.execute(
            """INSERT INTO runner_journey_events (
                   journey_id, athlete_id, event_type, stage_before, stage_after,
                   decision, evidence_json, reason
               ) VALUES (?, ?, 'plan_week_decision', ?, ?, ?, ?, ?)""",
            (
                journey.id, int(athlete_id), journey.current_stage, stage_after,
                decision,
                json.dumps({"week_before": week_before, "week_after": week_after}, sort_keys=True),
                reason,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    updated = get_active_runner_journey(int(athlete_id))
    if updated is None:
        raise RuntimeError("Journey update could not be reloaded.")
    return updated



def archive_active_runner_journey(
    athlete_id: int,
    *,
    reason: str = "Athlete removed the active Runner Journey.",
) -> RunnerJourney:
    """Archive, rather than hard-delete, the athlete's active Runner Journey.

    The journey and its event history remain available for audit/history, but
    it no longer participates in active coaching or Training Blocks.
    """
    journey = get_active_runner_journey(int(athlete_id))
    if journey is None:
        raise ValueError("No Active Runner Journey exists for this athlete.")

    conn = get_connection()
    cursor = conn.cursor()
    try:
        create_runner_journey_tables(cursor)
        cursor.execute(
            """UPDATE athlete_runner_journeys
               SET status='Archived', updated_at=CURRENT_TIMESTAMP
               WHERE id=? AND athlete_id=? AND status='Active'""",
            (journey.id, int(athlete_id)),
        )
        cursor.execute(
            """INSERT INTO runner_journey_events (
                   journey_id, athlete_id, event_type, stage_before, stage_after,
                   decision, evidence_json, reason
               ) VALUES (?, ?, 'journey_archived', ?, ?, 'archive', ?, ?)""",
            (
                journey.id,
                int(athlete_id),
                journey.current_stage,
                journey.current_stage,
                json.dumps(
                    {"current_week": get_journey_current_week(journey)},
                    sort_keys=True,
                ),
                reason,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return RunnerJourney(
        id=journey.id,
        athlete_id=journey.athlete_id,
        journey_type=journey.journey_type,
        status="Archived",
        goal_id=journey.goal_id,
        entry_stage=journey.entry_stage,
        current_stage=journey.current_stage,
        sessions_per_week=journey.sessions_per_week,
        started_at=journey.started_at,
        completed_at=journey.completed_at,
        baseline=dict(journey.baseline),
        preferences=dict(journey.preferences),
        created_at=journey.created_at,
        updated_at=journey.updated_at,
    )



def _controlled_success(evidence: JourneyProgressEvidence) -> bool:
    difficulty = str(evidence.perceived_difficulty or "").strip().lower()
    return (
        bool(evidence.completed_as_planned)
        and not evidence.pain_or_concerning_symptoms
        and difficulty not in {"hard", "very hard", "maximal"}
    )


def get_couch_to_5k_successes_since_decision(athlete_id: int) -> int:
    """Count controlled successful reviews in the current level.

    A manual level decision, a repeat/step-back/progress outcome, or a
    non-controlled hold resets the evidence window. A first controlled
    successful session normally produces a HOLD and remains useful evidence
    for the second session.
    """
    journey = get_active_runner_journey(int(athlete_id))
    if journey is None or journey.journey_type != COUCH_TO_5K:
        return 0

    current_week = get_journey_current_week(journey)
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT event_type, decision, evidence_json
               FROM runner_journey_events
               WHERE journey_id = ? AND athlete_id = ?
               ORDER BY id DESC""",
            (journey.id, int(athlete_id)),
        ).fetchall()
    finally:
        conn.close()

    successes = 0
    for event_type, decision, evidence_json in rows:
        event_type = str(event_type or "")
        decision = str(decision or "")

        if event_type == "plan_week_decision":
            break
        if event_type != "progress_review":
            continue

        try:
            payload = json.loads(evidence_json or "{}")
        except (TypeError, json.JSONDecodeError):
            break

        if int(payload.get("week_before") or current_week) != current_week:
            break

        if decision in {"progress", "regress", "graduate", "repeat"}:
            break

        previous = JourneyProgressEvidence(
            completed_as_planned=bool(payload.get("completed_as_planned")),
            perceived_difficulty=str(payload.get("perceived_difficulty") or ""),
            pain_or_concerning_symptoms=bool(
                payload.get("pain_or_concerning_symptoms")
            ),
            sessions_completed_since_decision=int(
                payload.get("sessions_completed_since_decision") or 1
            ),
            continuous_run_minutes=payload.get("continuous_run_minutes"),
            completed_5k=bool(payload.get("completed_5k")),
            days_since_last_session=payload.get("days_since_last_session"),
            activity_id=payload.get("activity_id"),
            activity_date=payload.get("activity_date"),
            activity_distance_km=payload.get("activity_distance_km"),
            activity_moving_time_s=payload.get("activity_moving_time_s"),
        )
        if _controlled_success(previous):
            successes += 1
            continue

        # A hold caused by pain/poor evidence starts a fresh evidence window.
        break

    return successes


def prepare_couch_to_5k_evidence(
    athlete_id: int,
    evidence: JourneyProgressEvidence,
) -> JourneyProgressEvidence:
    """Attach the real successful-session count to a new check-in."""
    prior = get_couch_to_5k_successes_since_decision(int(athlete_id))
    current = 1 if _controlled_success(evidence) else 0
    return JourneyProgressEvidence(
        completed_as_planned=evidence.completed_as_planned,
        perceived_difficulty=evidence.perceived_difficulty,
        pain_or_concerning_symptoms=evidence.pain_or_concerning_symptoms,
        sessions_completed_since_decision=prior + current,
        continuous_run_minutes=evidence.continuous_run_minutes,
        completed_5k=evidence.completed_5k,
        days_since_last_session=evidence.days_since_last_session,
        activity_id=evidence.activity_id,
        activity_date=evidence.activity_date,
        activity_distance_km=evidence.activity_distance_km,
        activity_moving_time_s=evidence.activity_moving_time_s,
    )


def preview_couch_to_5k_progress(
    athlete_id: int,
    evidence: JourneyProgressEvidence,
) -> tuple[JourneyDecision, JourneyProgressEvidence]:
    """Recommend an outcome without changing the saved Runner Journey."""
    journey = get_active_runner_journey(int(athlete_id))
    if journey is None:
        raise ValueError("No Active Runner Journey exists for this athlete.")
    if journey.journey_type != COUCH_TO_5K:
        raise ValueError("The active journey is not Couch -> 5K.")

    prepared = prepare_couch_to_5k_evidence(int(athlete_id), evidence)
    decision = decide_couch_to_5k_progress(
        journey.current_stage,
        prepared,
        current_week=get_journey_current_week(journey),
    )
    return decision, prepared


def apply_couch_to_5k_evidence(
    athlete_id: int,
    evidence: JourneyProgressEvidence,
) -> JourneyDecision:
    journey = get_active_runner_journey(int(athlete_id))
    if journey is None:
        raise ValueError("No Active Runner Journey exists for this athlete.")
    if journey.journey_type != COUCH_TO_5K:
        raise ValueError("The active journey is not Couch -> 5K.")

    current_week = get_journey_current_week(journey)
    evidence = prepare_couch_to_5k_evidence(int(athlete_id), evidence)
    decision = decide_couch_to_5k_progress(
        journey.current_stage, evidence, current_week=current_week
    )
    payload = {
        "completed_as_planned": evidence.completed_as_planned,
        "perceived_difficulty": evidence.perceived_difficulty,
        "pain_or_concerning_symptoms": evidence.pain_or_concerning_symptoms,
        "sessions_completed_since_decision": evidence.sessions_completed_since_decision,
        "continuous_run_minutes": evidence.continuous_run_minutes,
        "completed_5k": evidence.completed_5k,
        "days_since_last_session": evidence.days_since_last_session,
        "activity_id": evidence.activity_id,
        "activity_date": evidence.activity_date,
        "activity_distance_km": evidence.activity_distance_km,
        "activity_moving_time_s": evidence.activity_moving_time_s,
        "week_before": decision.week_before,
        "week_after": decision.week_after,
    }

    preferences = dict(journey.preferences)
    preferences["current_week"] = decision.week_after or current_week

    conn = get_connection()
    cursor = conn.cursor()
    try:
        create_runner_journey_tables(cursor)
        if decision.graduate:
            cursor.execute(
                """UPDATE athlete_runner_journeys
                   SET current_stage=?, status='Complete',
                       completed_at=CURRENT_TIMESTAMP,
                       preferences_json=?, updated_at=CURRENT_TIMESTAMP
                   WHERE id=? AND athlete_id=?""",
                (
                    decision.stage_after, json.dumps(preferences, sort_keys=True),
                    journey.id, int(athlete_id),
                ),
            )
        else:
            cursor.execute(
                """UPDATE athlete_runner_journeys
                   SET current_stage=?, preferences_json=?, updated_at=CURRENT_TIMESTAMP
                   WHERE id=? AND athlete_id=?""",
                (
                    decision.stage_after, json.dumps(preferences, sort_keys=True),
                    journey.id, int(athlete_id),
                ),
            )
        cursor.execute(
            """INSERT INTO runner_journey_events (
                   journey_id, athlete_id, event_type, stage_before, stage_after,
                   decision, evidence_json, reason
               ) VALUES (?, ?, 'progress_review', ?, ?, ?, ?, ?)""",
            (
                journey.id, int(athlete_id), decision.stage_before,
                decision.stage_after, decision.decision,
                json.dumps(payload, sort_keys=True), decision.reason,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return decision
