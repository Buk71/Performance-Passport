"""
Recommended Next Run.

Single responsibility:
    Given what Performance Passport already knows, what is the most useful
    next running session family?

This engine deliberately does NOT invent a readiness score. Until a dedicated
Readiness/Fatigue engine exists, it distinguishes between:
- the highest-value DEVELOPMENT session;
- the earliest sensible timing;
- a safer alternative if the athlete does not feel recovered.

Inputs are existing coaching outputs:
- Coach's Journal / Recognition;
- Decision Engine focus;
- active Training Block and phase.

The result must remain positive, transparent and conservative.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime

from core.journal import JournalEntry, build_latest_journal_entry
from core.training_blocks import (
    TrainingBlock,
    get_active_training_block,
)


QUALITY_CATEGORIES = {
    "Threshold Development",
    "VO₂ Development",
    "Speed Development",
    "Race",
}

EASY_CATEGORIES = {
    "Recovery",
    "Easy",
    "Long Easy",
    "Steady Run",
}

QUALITY_FOCUS = {
    "Threshold Development",
    "VO₂ / Speed Development",
}

ENDURANCE_FOCUS = {
    "Long Easy / Endurance",
}


@dataclass(frozen=True)
class NextRunRecommendation:
    athlete_id: int
    session_family: str
    icon: str
    earliest_timing: str
    timing_detail: str

    headline: str
    why: tuple[str, ...]
    expected_benefit: str

    alternative: str
    alternative_reason: str

    confidence: float
    confidence_label: str
    readiness_required: bool

    block_name: str | None
    block_phase: str | None
    primary_focus: str | None

    latest_run_title: str | None
    latest_run_category: str | None

    next_key_session_family: str | None
    next_key_session_icon: str | None
    next_key_session_timing: str | None
    next_key_session_timing_detail: str | None
    next_key_session_readiness_required: bool

    model_version: int = 2


def _parse_date(value: str | None) -> datetime.date | None:
    if not value:
        return None

    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _days_since_latest(
    entry: JournalEntry,
    *,
    today: datetime.date,
) -> int | None:
    latest = _parse_date(entry.activity_date)

    if latest is None:
        return None

    return max((today - latest).days, 0)


def _timing_for_quality(
    entry: JournalEntry,
    *,
    today: datetime.date,
) -> tuple[str, str]:
    days_since = _days_since_latest(entry, today=today)
    latest_category = entry.category or ""

    if latest_category in QUALITY_CATEGORIES:
        if days_since == 0:
            return (
                "In 2 days",
                (
                    "Your latest run was already a quality session. "
                    "Bank at least one genuinely easy day before another hard effort."
                ),
            )

        if days_since == 1:
            return (
                "Tomorrow",
                (
                    "A quality session becomes sensible after another easy/recovery "
                    "day, provided you feel normally recovered."
                ),
            )

    if latest_category == "Long Easy":
        if days_since == 0:
            return (
                "Tomorrow or the day after",
                (
                    "The long run has already supplied a substantial endurance "
                    "stimulus. Let recovery decide whether one or two easy days is better."
                ),
            )

    if days_since == 0:
        return (
            "Tomorrow",
            (
                "Today's run was not a hard-quality session, so tomorrow is the "
                "earliest sensible window if recovery feels normal."
            ),
        )

    return (
        "Today, if recovered",
        (
            "Enough time has passed since the latest recorded run for the session "
            "to be considered, but readiness still needs a human check."
        ),
    )


def _timing_for_easy(
    entry: JournalEntry,
    *,
    today: datetime.date,
) -> tuple[str, str]:
    days_since = _days_since_latest(entry, today=today)

    if days_since == 0:
        return (
            "Tomorrow",
            "An easy run is a sensible next step after one night's recovery.",
        )

    return (
        "Today",
        "An easy aerobic session is appropriate if you feel normally recovered.",
    )


def _confidence(
    entry: JournalEntry,
    *,
    block: TrainingBlock | None,
    readiness_required: bool,
) -> tuple[float, str]:
    confidence = entry.evidence_confidence

    if block is not None:
        confidence += 0.07

    if readiness_required:
        confidence -= 0.12

    confidence = max(0.20, min(confidence, 0.93))

    if confidence >= 0.82:
        label = "High"
    elif confidence >= 0.66:
        label = "Good"
    elif confidence >= 0.50:
        label = "Developing"
    else:
        label = "Early evidence"

    return round(confidence, 4), label


def _key_session_from_focus(
    entry: JournalEntry,
    *,
    decision_focus: str,
    block_focus: str,
    phase: str,
    today: datetime.date,
) -> tuple[str | None, str | None, str | None, str | None, bool]:
    """
    Preserve strategic direction even when the immediate next run is easy.

    Example:
        Immediate next run: Easy Recovery
        Next key session: Threshold Development in 2 days
    """
    if phase in {"Recovery"}:
        return (
            None,
            None,
            "After the recovery phase",
            (
                "No quality session is being forced while the block is explicitly "
                "in recovery."
            ),
            False,
        )

    if phase in {"Taper"}:
        return (
            "Race-Pace / Sharpening",
            "🏁",
            "When fresh",
            (
                "Keep the next key stimulus short and specific; taper priorities "
                "are freshness and rhythm rather than fitness building."
            ),
            True,
        )

    if decision_focus in QUALITY_FOCUS:
        timing, detail = _timing_for_quality(
            entry,
            today=today,
        )
        return (
            decision_focus,
            "❤️" if "Threshold" in decision_focus else "⚡",
            timing,
            detail,
            True,
        )

    if decision_focus in ENDURANCE_FOCUS or block_focus == "Endurance":
        timing, detail = _timing_for_quality(
            entry,
            today=today,
        )
        return (
            "Long Easy / Endurance",
            "🧱",
            timing,
            detail,
            True,
        )

    return (
        None,
        None,
        None,
        None,
        False,
    )


def _recommend_from_context(
    entry: JournalEntry,
    block: TrainingBlock | None,
    *,
    today: datetime.date | None = None,
) -> NextRunRecommendation:
    today = today or datetime.date.today()

    phase = (
        (block.current_phase or "").strip()
        if block is not None
        else ""
    )
    block_focus = (
        (block.primary_focus or "").strip()
        if block is not None
        else ""
    )
    decision_focus = (entry.next_focus or "").strip()
    latest_category = entry.category or ""

    # Block phase can override development focus. This is "context before advice".
    if phase in {"Recovery"}:
        session_family = "Recovery Run"
        icon = "🔋"
        readiness_required = False
        earliest, timing_detail = _timing_for_easy(entry, today=today)
        headline = "Protect the recovery phase."
        expected_benefit = (
            "Absorb the work already completed and arrive fresher for the next block."
        )
        alternative = "Rest"
        alternative_reason = (
            "If your legs or general energy feel unusually flat, rest gives the "
            "same strategic benefit."
        )

    elif phase in {"Taper"}:
        session_family = "Easy Run + relaxed strides"
        icon = "🟢"
        readiness_required = False
        earliest, timing_detail = _timing_for_easy(entry, today=today)
        headline = "Stay sharp without adding fatigue."
        expected_benefit = (
            "Maintain rhythm and leg turnover while protecting freshness."
        )
        alternative = "Easy Run"
        alternative_reason = "Drop the strides if you feel any residual fatigue."

    elif decision_focus in QUALITY_FOCUS:
        # Avoid stacking quality sessions even when the Decision Engine says
        # that quality is the biggest development opportunity.
        if latest_category in QUALITY_CATEGORIES:
            session_family = "Easy Recovery Run"
            icon = "🟢"
            readiness_required = False
            earliest, timing_detail = _timing_for_easy(entry, today=today)
            headline = "Bank the quality — now absorb it."
            expected_benefit = (
                "Easy running protects the adaptation from your latest quality "
                "session and prepares you for the next one."
            )
            alternative = "Rest"
            alternative_reason = (
                "Rest is preferable if the latest quality session left unusual fatigue."
            )
        else:
            session_family = decision_focus
            icon = "❤️" if "Threshold" in decision_focus else "⚡"
            readiness_required = True
            earliest, timing_detail = _timing_for_quality(entry, today=today)
            headline = (
                f"{decision_focus} is the highest-value development session."
            )
            expected_benefit = (
                "Target the area the Decision Engine currently identifies as "
                "your clearest performance opportunity."
            )
            alternative = "Easy Run"
            alternative_reason = (
                "Choose easy running instead if recovery, soreness or general "
                "energy is not normal."
            )

    elif decision_focus in ENDURANCE_FOCUS or block_focus == "Endurance":
        if latest_category == "Long Easy":
            session_family = "Easy Recovery Run"
            icon = "🟢"
            readiness_required = False
            earliest, timing_detail = _timing_for_easy(entry, today=today)
            headline = "Let the long-run stimulus settle."
            expected_benefit = (
                "Recover aerobically while preserving the endurance adaptation."
            )
            alternative = "Rest"
            alternative_reason = "Rest is sensible if the long run was unusually demanding."
        else:
            session_family = "Long Easy / Endurance"
            icon = "🧱"
            readiness_required = True
            earliest, timing_detail = _timing_for_quality(entry, today=today)
            headline = "Endurance is the best next investment."
            expected_benefit = (
                "Build the durability your current Training Block is prioritising."
            )
            alternative = "Easy Run"
            alternative_reason = (
                "Keep the run shorter and easier if recovery is not fully normal."
            )

    else:
        session_family = "Easy Aerobic"
        icon = "😊"
        readiness_required = False
        earliest, timing_detail = _timing_for_easy(entry, today=today)
        headline = "Keep building the aerobic foundation."
        expected_benefit = (
            "Add useful aerobic work without forcing intensity when the coaching "
            "picture does not demand it."
        )
        alternative = "Recovery Run"
        alternative_reason = (
            "Shorten and soften the effort if your legs feel less fresh than usual."
        )

    why = [
        f"Today's win: {entry.todays_win}.",
        f"Current opportunity: {entry.next_opportunity}.",
    ]

    if block is not None:
        why.append(
            (
                f"Training Block: {block.name}"
                + (f" · {phase} phase" if phase else "")
                + (f" · {block_focus} focus" if block_focus else "")
                + "."
            )
        )

    if latest_category:
        why.append(
            f"Latest recognised session: {latest_category}."
        )

    (
        key_session_family,
        key_session_icon,
        key_session_timing,
        key_session_timing_detail,
        key_session_readiness_required,
    ) = _key_session_from_focus(
        entry,
        decision_focus=decision_focus,
        block_focus=block_focus,
        phase=phase,
        today=today,
    )

    confidence, confidence_label = _confidence(
        entry,
        block=block,
        readiness_required=readiness_required,
    )

    return NextRunRecommendation(
        athlete_id=entry.athlete_id,
        session_family=session_family,
        icon=icon,
        earliest_timing=earliest,
        timing_detail=timing_detail,
        headline=headline,
        why=tuple(why),
        expected_benefit=expected_benefit,
        alternative=alternative,
        alternative_reason=alternative_reason,
        confidence=confidence,
        confidence_label=confidence_label,
        readiness_required=readiness_required,
        block_name=block.name if block else None,
        block_phase=phase or None,
        primary_focus=(
            decision_focus
            or block_focus
            or None
        ),
        latest_run_title=entry.activity_title,
        latest_run_category=latest_category or None,
        next_key_session_family=key_session_family,
        next_key_session_icon=key_session_icon,
        next_key_session_timing=key_session_timing,
        next_key_session_timing_detail=key_session_timing_detail,
        next_key_session_readiness_required=key_session_readiness_required,
    )


def build_next_run_recommendation(
    athlete_id: int,
    *,
    today: datetime.date | None = None,
) -> NextRunRecommendation | None:
    entry = build_latest_journal_entry(athlete_id)

    if entry is None:
        return None

    block = get_active_training_block(athlete_id)

    return _recommend_from_context(
        entry,
        block,
        today=today,
    )
