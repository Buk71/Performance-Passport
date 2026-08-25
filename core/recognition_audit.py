"""Read-only, athlete-independent audit of historical session recognition.

The audit does not mutate activities or replace ``classify_session``.  It
compares the live classifier against the same independently cached physical
lap evidence, exposes remaining disagreement, and explains ambiguous history.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import datetime as dt
from typing import Any

from core.database import get_activity_overrides, get_athlete_sport_roles, get_connection
from core.session import SessionPurpose, SessionType
from core.session_patterns import IntervalEvidence, analyse_session_patterns
from core.session_intelligence import (
    ActivityFacts,
    RELIABLE_SESSION_CONFIDENCE,
    classify_session,
)
from core.workout_title_intent import parse_workout_title


AUDIT_MODEL_VERSION = "recognition-audit-v3"

SESSION_LABELS = {
    "easy_run": "Easy run",
    "easy_with_strides": "Easy run with strides",
    "easy_with_pickups": "Easy run with pickups",
    "standalone_strides": "Standalone strides",
    "long_run": "Long run",
    "interval_workout": "Interval workout",
    "threshold_workout": "Threshold workout",
    "alternating_workout": "Alternating workout",
    "fartlek_workout": "Fartlek workout",
    "hill_workout": "Hill workout",
    "race": "Race",
    "cross_training": "Cross-training",
    "unknown": "Needs identification",
}

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2, "none": 3}


@dataclass(frozen=True)
class RecognitionAuditEntry:
    activity_id: int
    athlete_id: int
    activity_date: str
    title: str
    distance_km: float | None
    recorded_avg_hr: float | None
    heart_rate_status: str
    current_session_type: str
    current_label: str
    current_confidence: float
    proposed_session_type: str
    proposed_label: str
    audit_status: str
    review_priority: str
    issue_key: str | None
    recommendation: str
    evidence: tuple[str, ...]
    interval_evidence: IntervalEvidence
    manual_override: bool

    @property
    def needs_review(self) -> bool:
        return self.audit_status == "needs_review"


@dataclass(frozen=True)
class RecognitionAuditReport:
    athlete_id: int
    athlete_name: str
    total_running_activities: int
    reviewed_count: int
    protected_count: int
    verified_count: int
    manually_confirmed_count: int
    likely_missed_workout_count: int
    likely_false_workout_count: int
    protected_strides_count: int
    protected_pickups_count: int
    confirmed_race_count: int
    unreliable_heart_rate_count: int
    entries: tuple[RecognitionAuditEntry, ...]
    review_queue: tuple[RecognitionAuditEntry, ...]
    reference_cases: tuple[RecognitionAuditEntry, ...]
    model_version: str = AUDIT_MODEL_VERSION
    changes_live_classification: bool = False


def _distance_km(value: Any) -> float | None:
    try:
        distance = float(value)
    except (TypeError, ValueError):
        return None
    if distance <= 0:
        return None
    return distance / 1_000.0 if distance > 250 else distance


def _interval_evidence(facts: ActivityFacts) -> IntervalEvidence:
    return analyse_session_patterns(facts)


def _looks_long(facts: ActivityFacts) -> bool:
    title = (facts.title or "").lower()
    return (
        "long run" in title
        or title.startswith("slr")
        or (facts.distance_km is not None and facts.distance_km >= 14.0)
    )


def _workout_kind(facts: ActivityFacts, purpose: SessionPurpose) -> str:
    title = (facts.title or "").lower()
    if purpose == SessionPurpose.THRESHOLD or any(
        token in title for token in ("threshold", "tempo", "cruise")
    ):
        return "threshold_workout"
    if purpose == SessionPurpose.FARTLEK or "fartlek" in title:
        return "fartlek_workout"
    if purpose == SessionPurpose.HILLS or "hill rep" in title:
        return "hill_workout"
    return "interval_workout"


def _session_kind(facts: ActivityFacts, session: Any) -> str:
    intent = session.metadata.get("activity_intent")
    if intent in {
        "easy_with_strides", "easy_with_pickups", "standalone_strides",
        "alternating_workout",
    }:
        return str(intent)
    if session.session_type == SessionType.RACE:
        return "race"
    if session.session_type == SessionType.STRUCTURED_WORKOUT:
        return _workout_kind(facts, session.purpose)
    if session.session_type == SessionType.CONTINUOUS_RUN:
        return "long_run" if _looks_long(facts) else "easy_run"
    if session.session_type == SessionType.CROSS_TRAINING:
        return "cross_training"
    return "unknown"


def _heart_rate_status(facts: ActivityFacts, override: dict[str, Any]) -> str:
    if override.get("heart_rate_reliable") is False:
        return "manually_excluded"
    if override.get("corrected_avg_hr") is not None:
        return "manually_corrected"
    if facts.avg_hr is None:
        return "unavailable"
    if facts.avg_hr < 55 or (
        facts.max_hr is not None and facts.avg_hr > facts.max_hr + 2
    ) or (
        facts.athlete_max_hr is not None
        and facts.avg_hr > facts.athlete_max_hr + 5
    ):
        return "implausible"
    return "recorded"


def audit_activity_facts(
    facts: ActivityFacts,
    *,
    override: dict[str, Any] | None = None,
) -> RecognitionAuditEntry:
    """Compare live recognition with independently verified lap evidence."""
    correction = override
    if correction is None:
        correction = get_activity_overrides(facts.athlete_id).get(
            facts.activity_id, {}
        )
    session = classify_session(facts)
    structure = _interval_evidence(facts)
    current_kind = _session_kind(facts, session)
    proposed_kind = current_kind
    status = "verified"
    priority = "none"
    issue = None
    reasons: list[str] = []
    recommendation = "Existing classification agrees with the available evidence."
    manual = bool(correction.get("session_intent"))
    heart_rate_status = _heart_rate_status(facts, correction)

    if manual:
        status = "manual"
        reasons.append("An athlete or coach has explicitly confirmed this activity.")
        recommendation = "Keep the existing manual classification."
    elif current_kind in {"easy_with_strides", "standalone_strides"}:
        status = "protected"
        issue = "protected_strides"
        stride_count = session.metadata.get("stride_details", {}).get(
            "stride_count", structure.short_stride_count
        )
        reasons.append(f"{stride_count} short strides do not establish a sustained workout.")
        recommendation = "Keep strides separate from Workout Coach evidence."
    elif current_kind == "easy_with_pickups" or structure.pickup_count >= 5:
        proposed_kind = "easy_with_pickups"
        status = "protected"
        issue = "protected_pickups"
        reasons.append(
            f"{structure.pickup_count} short fast pickups are embedded within "
            "a substantially longer easy run."
        )
        recommendation = (
            "Record the light speed stimulus without treating short pickups "
            "as a full race-prediction workout."
        )
    elif current_kind == "race":
        status = "protected"
        issue = "protected_race"
        reasons.append("Race evidence takes priority over ordinary kilometre or mile laps.")
        recommendation = "Use this activity as race evidence, not as a threshold workout."
    elif structure.trustworthy_intervals:
        if (
            structure.equal_distance_alternation_count >= 3
            or structure.long_recovery_alternation_count >= 3
        ):
            proposed_kind = "alternating_workout"
        else:
            proposed_kind = _workout_kind(facts, session.purpose)

        if structure.boundary_block_count >= 3:
            reasons.append(
                f"{structure.boundary_block_count} sustained blocks of about "
                f"{structure.boundary_block_distance_km:g} km are separated "
                "by stopped-watch lap markers."
            )
        elif structure.equal_distance_alternation_count >= 3:
            reasons.append(
                f"{structure.equal_distance_alternation_count} faster efforts "
                "alternate with slower recoveries of the same distance."
            )
        elif structure.long_recovery_alternation_count >= 3:
            reasons.append(
                f"{structure.long_recovery_alternation_count} faster efforts "
                "alternate with longer, slower recovery segments."
            )
        elif structure.stopped_watch_work_count >= 4:
            reasons.append(
                f"{structure.stopped_watch_work_count} consistent faster repetitions "
                "and elapsed-time gaps indicate stopped-watch recoveries."
            )
        else:
            reasons.append(
                f"{structure.work_count} meaningful work repetitions and "
                f"{structure.credible_recovery_count} slower recoveries were recorded."
            )
        if (
            session.session_type != SessionType.STRUCTURED_WORKOUT
            or session.confidence < RELIABLE_SESSION_CONFIDENCE
        ):
            status = "needs_review"
            priority = "high"
            issue = "missed_workout"
            recommendation = (
                "Strong interval structure is present, but the live classifier "
                "does not yet treat it as reliable coaching evidence."
            )
        else:
            recommendation = "Retain this verified interval workout."
    elif (
        session.session_type == SessionType.STRUCTURED_WORKOUT
        and structure.repeated_auto_laps
        and session.confidence < RELIABLE_SESSION_CONFIDENCE
        and parse_workout_title(facts.title or "") is None
    ):
        proposed_kind = "long_run" if _looks_long(facts) else "easy_run"
        status = "needs_review"
        priority = "high"
        issue = "false_workout_auto_laps"
        reasons.append(
            "The supposed recoveries are ordinary laps of similar distance "
            "rather than shorter, slower recovery segments."
        )
        recommendation = "Protect this continuous run from accidental workout promotion."
    elif (
        session.session_type == SessionType.STRUCTURED_WORKOUT
        and session.confidence < RELIABLE_SESSION_CONFIDENCE
    ):
        status = "needs_review"
        priority = "medium"
        issue = "ambiguous_workout"
        reasons.append(
            "The workout score is inconclusive and the available laps do not "
            "independently verify the complete work/recovery pattern."
        )
        recommendation = "Review the title and original laps before using this as evidence."
    elif structure.repeated_auto_laps and current_kind == "long_run":
        status = "protected"
        issue = "protected_long_run"
        reasons.append("Similar kilometre or mile laps are continuous-running auto-laps.")
        recommendation = "Keep this activity in long-run and durability comparisons."
    else:
        if parse_workout_title(facts.title or "") is not None:
            reasons.append("The activity title describes a deliberate workout structure.")
        elif structure.split_count:
            reasons.append(f"{structure.split_count} recorded laps support the existing view.")
        else:
            reasons.append("No decodable laps were available; the live classification remains unchanged.")

    if heart_rate_status == "implausible":
        reasons.append("The recorded heart rate conflicts with basic physiological limits.")
        if status != "manual":
            status = "needs_review"
            priority = "high"
            issue = issue or "unreliable_heart_rate"
            recommendation += " Check the heart-rate reading before using it."
    elif heart_rate_status == "manually_excluded":
        reasons.append("A manual correction already excludes unreliable heart-rate data.")

    return RecognitionAuditEntry(
        activity_id=facts.activity_id,
        athlete_id=facts.athlete_id,
        activity_date=str(facts.activity_date or "")[:10],
        title=facts.title or "Untitled activity",
        distance_km=facts.distance_km,
        recorded_avg_hr=facts.avg_hr,
        heart_rate_status=heart_rate_status,
        current_session_type=current_kind,
        current_label=SESSION_LABELS.get(current_kind, current_kind),
        current_confidence=round(session.confidence, 3),
        proposed_session_type=proposed_kind,
        proposed_label=SESSION_LABELS.get(proposed_kind, proposed_kind),
        audit_status=status,
        review_priority=priority,
        issue_key=issue,
        recommendation=recommendation,
        evidence=tuple(reasons),
        interval_evidence=structure,
        manual_override=manual,
    )


def _facts_from_row(row: Any) -> ActivityFacts:
    return ActivityFacts(
        activity_id=int(row["id"]),
        athlete_id=int(row["athlete_id"]),
        activity_date=row["activity_date"],
        title=row["title"] or "",
        sport_id=str(row["sport_id"]) if row["sport_id"] is not None else None,
        distance_km=_distance_km(row["distance_m"]),
        moving_time_s=row["moving_time_s"],
        elapsed_time_s=row["elapsed_time_s"],
        avg_hr=row["avg_hr"],
        max_hr=row["max_hr"],
        elevation_up_m=row["elevation_up_m"],
        temperature_c=row["temperature_c"],
        humidity=row["humidity"],
        wind_speed=row["wind_speed"],
        route_name=row["route_name"],
        raw_json_text=row["raw_json"],
        athlete_lt1_hr=row["athlete_lt1_hr"],
        athlete_lt2_hr=row["athlete_lt2_hr"],
        athlete_max_hr=row["athlete_max_hr"],
    )


def _reference_group(entry: RecognitionAuditEntry) -> str:
    if entry.issue_key:
        return entry.issue_key
    return entry.proposed_session_type


def select_reference_cases(
    entries: tuple[RecognitionAuditEntry, ...],
    *,
    limit: int = 24,
) -> tuple[RecognitionAuditEntry, ...]:
    """Choose a balanced, recent, real-session review set without hardcoded IDs."""
    groups: dict[str, list[RecognitionAuditEntry]] = defaultdict(list)
    for entry in entries:
        groups[_reference_group(entry)].append(entry)
    ordered_groups = sorted(
        groups,
        key=lambda group: (
            min(PRIORITY_ORDER[item.review_priority] for item in groups[group]),
            group,
        ),
    )
    selected = []
    while ordered_groups and len(selected) < limit:
        next_groups = []
        for group in ordered_groups:
            if groups[group]:
                selected.append(groups[group].pop(0))
            if groups[group]:
                next_groups.append(group)
            if len(selected) >= limit:
                break
        ordered_groups = next_groups
    return tuple(selected)


def build_recognition_audit(
    athlete_id: int,
    *,
    activity_ids: tuple[int, ...] | None = None,
    recent_days: int | None = None,
    reference_date: str | None = None,
) -> RecognitionAuditReport:
    """Read an athlete's running history without changing data or predictions."""
    import sqlite3

    connection = get_connection()
    connection.row_factory = sqlite3.Row
    athlete = connection.execute(
        "SELECT id, first_name, last_name FROM athletes WHERE id = ?",
        (int(athlete_id),),
    ).fetchone()
    if athlete is None:
        connection.close()
        raise ValueError(f"Athlete {athlete_id} does not exist.")

    where = ["a.athlete_id = ?"]
    parameters: list[Any] = [int(athlete_id)]
    if activity_ids is not None:
        if not activity_ids:
            where.append("1 = 0")
        else:
            where.append("a.id IN (" + ", ".join("?" for _ in activity_ids) + ")")
            parameters.extend(int(item) for item in activity_ids)
    if recent_days is not None:
        if recent_days <= 0:
            connection.close()
            raise ValueError("recent_days must be a positive integer.")
        anchor = (
            dt.date.fromisoformat(str(reference_date)[:10])
            if reference_date else dt.date.today()
        )
        earliest = anchor - dt.timedelta(days=recent_days)
        where.append("date(a.activity_date) BETWEEN date(?) AND date(?)")
        parameters.extend((earliest.isoformat(), anchor.isoformat()))

    query = """
        SELECT a.*, at.lt1_hr AS athlete_lt1_hr,
               at.lt2_hr AS athlete_lt2_hr, at.max_hr AS athlete_max_hr
        FROM activities a
        JOIN athletes at ON at.id = a.athlete_id
        WHERE """ + " AND ".join(where) + """
        ORDER BY a.activity_datetime DESC, a.id DESC
    """
    rows = connection.execute(query, parameters).fetchall()
    connection.close()

    sport_roles = get_athlete_sport_roles(int(athlete_id))
    corrections = get_activity_overrides(int(athlete_id))
    entries = tuple(
        audit_activity_facts(
            _facts_from_row(row),
            override=corrections.get(int(row["id"]), {}),
        )
        for row in rows
        if sport_roles.get(str(row["sport_id"])) == "running"
    )
    queue = tuple(
        sorted(
            (entry for entry in entries if entry.needs_review),
            key=lambda entry: (
                PRIORITY_ORDER[entry.review_priority],
                -int(entry.activity_date.replace("-", "") or 0),
                -entry.activity_id,
            ),
        )
    )
    statuses = Counter(entry.audit_status for entry in entries)
    issues = Counter(entry.issue_key for entry in entries)
    return RecognitionAuditReport(
        athlete_id=int(athlete_id),
        athlete_name=f"{athlete['first_name'] or ''} {athlete['last_name'] or ''}".strip(),
        total_running_activities=len(entries),
        reviewed_count=statuses["needs_review"],
        protected_count=statuses["protected"],
        verified_count=statuses["verified"],
        manually_confirmed_count=statuses["manual"],
        likely_missed_workout_count=issues["missed_workout"],
        likely_false_workout_count=issues["false_workout_auto_laps"],
        protected_strides_count=issues["protected_strides"],
        protected_pickups_count=issues["protected_pickups"],
        confirmed_race_count=sum(
            entry.proposed_session_type == "race" for entry in entries
        ),
        unreliable_heart_rate_count=sum(
            entry.heart_rate_status in {"implausible", "manually_excluded"}
            for entry in entries
        ),
        entries=entries,
        review_queue=queue,
        reference_cases=select_reference_cases(entries),
    )


def audit_activity(athlete_id: int, activity_id: int) -> RecognitionAuditEntry:
    report = build_recognition_audit(
        athlete_id,
        activity_ids=(int(activity_id),),
    )
    if not report.entries:
        raise ValueError(
            f"Running activity {activity_id} does not belong to athlete {athlete_id}."
        )
    return report.entries[0]
