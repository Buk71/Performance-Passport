"""Couch -> 5K session prescription engine."""

from __future__ import annotations
from dataclasses import dataclass
from core.session import BlockType, SessionPurpose, SessionType

@dataclass(frozen=True)
class BeginnerSessionBlock:
    block_type: BlockType
    label: str
    duration_s: int
    repeat_count: int = 1
    effort: str = ""
    coaching_cue: str = ""

@dataclass(frozen=True)
class BeginnerSessionPrescription:
    journey_type: str
    stage: str
    session_type: SessionType
    purpose: SessionPurpose
    title: str
    total_duration_s: int
    blocks: tuple[BeginnerSessionBlock, ...]
    success_criteria: tuple[str, ...]
    collect_after: tuple[str, ...]
    progression_note: str
    pace_guidance: str
    model_version: int = 1

PACE_GUIDANCE = (
    "Run slowly enough that completing the planned running is the objective. "
    "There is no pace target."
)

def _b(kind, label, minutes, repeats=1, effort="", cue=""):
    return BeginnerSessionBlock(
        block_type=kind, label=label,
        duration_s=int(round(minutes * 60)),
        repeat_count=repeats, effort=effort, coaching_cue=cue,
    )

def _make(stage, title, blocks, *, session_type=SessionType.STRUCTURED_WORKOUT,
          purpose=SessionPurpose.EASY, success=(), note=""):
    return BeginnerSessionPrescription(
        journey_type="couch_to_5k",
        stage=stage,
        session_type=session_type,
        purpose=purpose,
        title=title,
        total_duration_s=sum(x.duration_s * x.repeat_count for x in blocks),
        blocks=blocks,
        success_criteria=success,
        collect_after=(
            "Did you complete the session as planned?",
            "How difficult did the session feel?",
            "Did you have any pain or concerning physical symptoms?",
            "What was your longest continuous running block?",
        ),
        progression_note=note,
        pace_guidance=PACE_GUIDANCE,
    )

def build_couch_to_5k_session(stage: str) -> BeginnerSessionPrescription:
    warm = _b(BlockType.WARMUP, "Easy walk", 5, effort="Easy",
              cue="Walk comfortably and let your breathing settle.")
    cool = _b(BlockType.COOLDOWN, "Easy walk", 5, effort="Easy",
              cue="Finish relaxed rather than adding extra running.")

    if stage == "walking_foundation":
        blocks = (_b(BlockType.CONTINUOUS, "Comfortable walk", 25,
                     effort="Comfortable",
                     cue="Walk purposefully but sustainably."), cool)
        return _make(stage, "Walking foundation", blocks,
                     session_type=SessionType.WALK,
                     success=("Complete the walk comfortably.",
                              "Finish feeling you could have continued a little longer."),
                     note="Build comfortable time on feet before introducing running.")

    specs = {
        "run_walk_short": (1, 8, 1.5, 7, "Short run / walk"),
        "run_walk_build": (2, 7, 1.5, 6, "Build the running blocks"),
        "run_blocks_5": (5, 4, 2, 3, "Four 5-minute runs"),
        "run_blocks_8": (8, 3, 2, 2, "Three 8-minute runs"),
        "run_blocks_10": (10, 2, 2, 1, "Two 10-minute runs"),
    }
    if stage in specs:
        run_min, run_reps, walk_min, walk_reps, title = specs[stage]
        blocks = (
            warm,
            _b(BlockType.WORK, "Run", run_min, run_reps, "Very easy",
               "Stay relaxed enough to complete every running block."),
            _b(BlockType.RECOVERY, "Walk recovery", walk_min, walk_reps, "Easy",
               "Walk until your breathing is under control."),
            cool,
        )
        return _make(
            stage, title, blocks,
            success=("Complete all planned running blocks.",
                     "Keep the final running block controlled rather than racing it."),
            note="Two controlled completions support a one-stage progression."
        )

    continuous = {
        "continuous_15": 15,
        "continuous_20": 20,
        "continuous_25": 25,
        "continuous_30": 30,
    }
    if stage in continuous:
        minutes = continuous[stage]
        blocks = (
            warm,
            _b(BlockType.CONTINUOUS, "Continuous easy run", minutes, effort="Easy",
               cue="Start slower than feels necessary; duration, not speed, is the goal."),
            cool,
        )
        return _make(
            stage, f"{minutes}-minute continuous run", blocks,
            session_type=SessionType.CONTINUOUS_RUN,
            success=(f"Run continuously for {minutes} minutes.",
                     "Finish in control rather than all-out."),
            note="Continuous duration is now the progression measure; pace remains irrelevant."
        )

    if stage == "5k_ready":
        blocks = (
            warm,
            _b(BlockType.CONTINUOUS, "Easy 5K completion", 30,
               effort="Easy / controlled",
               cue="Complete 5K at whatever easy pace is needed; brief walking is acceptable."),
            cool,
        )
        return _make(
            stage, "5K completion / consolidation", blocks,
            session_type=SessionType.CONTINUOUS_RUN,
            success=("Complete 5K safely and under control.",
                     "Treat completion as the achievement; pace is not the goal."),
            note="Consolidate the new ability before the next running journey."
        )

    raise ValueError(f"Unsupported Couch -> 5K stage: {stage}")
