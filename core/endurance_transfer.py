"""Evidence-led transfer of current speed into longer-distance capability.

The distance-specific coaches answer an important conservative question:
"what does the athlete's direct evidence at this distance support?"  That
answer can nevertheless lag current fitness when the best half or marathon is
older than the athlete's recent shorter-race performances.  This module lets a
small, transparent share of current shorter-distance capability transfer to a
half or marathon only when recent endurance evidence supports it.

The result remains a capability estimate.  The readiness label is deliberately
separate and never turns a ballpark outlook into a race-day guarantee.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import datetime
import math
from typing import Iterable

from core.activity_reliability import has_reliable_distance_and_pace
from core.database import get_athlete_sport_roles, get_connection


RIEGEL_EXPONENT = 1.06


@dataclass(frozen=True)
class EnduranceProfile:
    athlete_id: int
    reference_date: datetime.date | None
    reliable_run_count_84d: int
    weekly_km_42d: float
    weekly_km_56d: float
    longest_run_km_56d: float
    longest_run_km_84d: float
    half_long_run_count_56d: int
    marathon_long_run_count_84d: int
    half_completion_count_365d: int
    marathon_completion_count_730d: int


@dataclass(frozen=True)
class EnduranceAssessment:
    distance_key: str
    score: float
    confidence: float
    label: str
    summary: str


def _distance_km(value) -> float | None:
    try:
        distance = float(value)
    except (TypeError, ValueError):
        return None
    if distance <= 0:
        return None
    return distance / 1000.0 if distance > 250.0 else distance


def _date(value) -> datetime.date | None:
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def load_endurance_profile(athlete_id: int) -> EnduranceProfile:
    """Summarise reliable running volume, long runs and completion history."""
    running_ids = {
        str(sport_id)
        for sport_id, role in get_athlete_sport_roles(athlete_id).items()
        if role == "running"
    }
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT activity_date, distance_m, title, sport_id, route_name, raw_json
        FROM activities
        WHERE athlete_id = ?
        ORDER BY activity_date, id
        """,
        (athlete_id,),
    )
    rows = cursor.fetchall()
    connection.close()

    runs: list[tuple[datetime.date, float]] = []
    for activity_date, distance_m, title, sport_id, route_name, raw_json in rows:
        if str(sport_id or "") not in running_ids:
            continue
        run_date = _date(activity_date)
        distance_km = _distance_km(distance_m)
        if run_date is None or distance_km is None:
            continue
        if not has_reliable_distance_and_pace(
            title=title,
            sport_id=str(sport_id or ""),
            route_name=route_name,
            raw_json_text=raw_json,
        ):
            continue
        runs.append((run_date, distance_km))

    if not runs:
        return EnduranceProfile(
            athlete_id=athlete_id,
            reference_date=None,
            reliable_run_count_84d=0,
            weekly_km_42d=0.0,
            weekly_km_56d=0.0,
            longest_run_km_56d=0.0,
            longest_run_km_84d=0.0,
            half_long_run_count_56d=0,
            marathon_long_run_count_84d=0,
            half_completion_count_365d=0,
            marathon_completion_count_730d=0,
        )

    reference_date = max(run_date for run_date, _distance in runs)

    def recent(days: int) -> list[float]:
        return [
            distance
            for run_date, distance in runs
            if 0 <= (reference_date - run_date).days < days
        ]

    runs_42d = recent(42)
    runs_56d = recent(56)
    runs_84d = recent(84)
    runs_365d = recent(365)
    runs_730d = recent(730)

    return EnduranceProfile(
        athlete_id=athlete_id,
        reference_date=reference_date,
        reliable_run_count_84d=len(runs_84d),
        weekly_km_42d=sum(runs_42d) / 6.0,
        weekly_km_56d=sum(runs_56d) / 8.0,
        longest_run_km_56d=max(runs_56d, default=0.0),
        longest_run_km_84d=max(runs_84d, default=0.0),
        half_long_run_count_56d=sum(distance >= 16.0 for distance in runs_56d),
        # 23.5 km avoids treating normal GPS variation around 24 km as a
        # meaningful evidence boundary.
        marathon_long_run_count_84d=sum(
            distance >= 23.5 for distance in runs_84d
        ),
        half_completion_count_365d=sum(
            distance >= 18.9 for distance in runs_365d
        ),
        marathon_completion_count_730d=sum(
            distance >= 38.0 for distance in runs_730d
        ),
    )


def assess_endurance(
    profile: EnduranceProfile,
    distance_key: str,
) -> EnduranceAssessment | None:
    """Return a bounded, explainable endurance-support assessment."""
    if distance_key == "half_marathon":
        coverage = min(profile.longest_run_km_56d / 19.0, 1.0)
        volume = min(profile.weekly_km_42d / 45.0, 1.0)
        repetition = min(profile.half_long_run_count_56d / 3.0, 1.0)
        experience = min(profile.half_completion_count_365d / 2.0, 1.0)
        score = (
            0.35 * coverage
            + 0.25 * volume
            + 0.20 * repetition
            + 0.20 * experience
        )
        summary = (
            f"{profile.weekly_km_42d:.0f} km/week over 6 weeks; "
            f"longest run {profile.longest_run_km_56d:.1f} km; "
            f"{profile.half_long_run_count_56d} run(s) of at least 16 km; "
            f"{profile.half_completion_count_365d} run(s) of at least 18.9 km "
            "in 12 months"
        )
    elif distance_key == "marathon":
        coverage = min(profile.longest_run_km_84d / 32.0, 1.0)
        volume = min(profile.weekly_km_56d / 64.0, 1.0)
        repetition = min(profile.marathon_long_run_count_84d / 3.0, 1.0)
        experience = min(profile.marathon_completion_count_730d, 1.0)
        score = (
            0.30 * coverage
            + 0.25 * volume
            + 0.20 * repetition
            + 0.25 * experience
        )
        summary = (
            f"{profile.weekly_km_56d:.0f} km/week over 8 weeks; "
            f"longest run {profile.longest_run_km_84d:.1f} km; "
            f"{profile.marathon_long_run_count_84d} run(s) of about 24 km or more; "
            f"{profile.marathon_completion_count_730d} marathon completion(s) "
            "in 24 months"
        )
    else:
        return None

    score = min(max(score, 0.0), 1.0)
    if score >= 0.80:
        label = "Strong endurance"
    elif score >= 0.60:
        label = "Supported endurance"
    elif score >= 0.40:
        label = "Developing endurance"
    else:
        label = "Limited endurance"
    confidence = min(0.90, 0.50 + 0.40 * score)
    return EnduranceAssessment(
        distance_key=distance_key,
        score=score,
        confidence=confidence,
        label=label,
        summary=summary,
    )


def _equivalent_seconds(
    seconds: float,
    source_distance_km: float,
    target_distance_km: float,
) -> float:
    return seconds * math.pow(
        target_distance_km / source_distance_km,
        RIEGEL_EXPONENT,
    )


def calibrate_endurance_anchors(
    anchors: Iterable,
    profile: EnduranceProfile,
) -> tuple:
    """Reconcile longer-distance history with supported current fitness.

    ``anchors`` intentionally uses structural typing so the pure calibration
    remains independent of the presentation dataclass and easy to test.
    """
    calibrated = []
    available = {}

    for anchor in anchors:
        if (
            not anchor.available
            or anchor.central_seconds is None
            or anchor.central_seconds <= 0
        ):
            calibrated.append(anchor)
            continue

        assessment = assess_endurance(profile, anchor.key)
        if assessment is None:
            calibrated.append(anchor)
            available[anchor.key] = anchor
            continue

        shorter_candidates = []
        for shorter_key in ("10k", "half_marathon"):
            shorter = available.get(shorter_key)
            if shorter is None or shorter.distance_km >= anchor.distance_km:
                continue
            shorter_candidates.append(
                _equivalent_seconds(
                    float(shorter.central_seconds),
                    shorter.distance_km,
                    anchor.distance_km,
                )
            )

        raw_seconds = float(anchor.central_seconds)
        # The slower shorter-distance equivalence is the conservative transfer
        # anchor when more than one current-distance route is available.
        speed_equivalent = max(shorter_candidates, default=raw_seconds)
        transferable_gap = max(raw_seconds - speed_equivalent, 0.0)
        evidence_fraction = max(
            0.0,
            min((assessment.score - 0.35) / 0.65, 1.0),
        )
        maximum_transfer = 0.42 if anchor.key == "half_marathon" else 0.55
        transfer_fraction = evidence_fraction * maximum_transfer
        capability_seconds = raw_seconds - transferable_gap * transfer_fraction

        confidence = (
            0.75 * float(anchor.confidence)
            + 0.25 * assessment.confidence
            - (0.05 if anchor.key == "marathon" else 0.0)
        )
        confidence = min(max(confidence, 0.35), 0.90)
        changed = capability_seconds < raw_seconds - 0.5
        explanation = anchor.explanation
        if changed:
            explanation = (
                f"{explanation} Current shorter-distance fitness contributes "
                f"{transfer_fraction:.0%} of the gap to its standard equivalent "
                f"because the endurance record shows {assessment.summary}."
            )

        updated = replace(
            anchor,
            central_seconds=capability_seconds,
            confidence=confidence,
            source=(
                "distance_specific_coaches_plus_endurance_transfer"
                if changed else anchor.source
            ),
            explanation=explanation,
            raw_central_seconds=raw_seconds,
            speed_equivalent_seconds=speed_equivalent,
            readiness_score=assessment.score,
            readiness_label=assessment.label,
            endurance_summary=assessment.summary,
            transfer_fraction=transfer_fraction,
        )
        calibrated.append(updated)
        available[anchor.key] = updated

    return tuple(calibrated)
