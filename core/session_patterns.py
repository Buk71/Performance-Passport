"""Shared, athlete-independent physical lap evidence for session recognition.

Both the live classifier and historical audit consume these same patterns.
No database values or activity classifications are modified by this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
from statistics import median
from typing import Any, Protocol

from core.splits import (
    Split,
    WorkoutRecognition,
    is_boundary_fragment,
    parse_splits,
    recognise_workout,
)


class PatternActivityFacts(Protocol):
    distance_km: float | None
    moving_time_s: float | None
    elapsed_time_s: float | None
    raw_json_text: str | None


@dataclass(frozen=True)
class IntervalEvidence:
    split_count: int
    work_count: int
    sustained_work_count: int
    work_distance_km: float
    average_work_distance_km: float | None
    average_work_pace_s_per_km: float | None
    recovery_count: int
    credible_recovery_count: int
    recovery_distance_ratio: float | None
    short_stride_count: int
    repeated_auto_laps: bool
    trustworthy_intervals: bool
    pickup_count: int
    boundary_block_count: int
    boundary_block_distance_km: float | None
    stopped_watch_work_count: int
    equal_distance_alternation_count: int
    long_recovery_alternation_count: int
    description: str


def _payload(raw_json_text: str | None) -> dict[str, Any]:
    try:
        value = json.loads(raw_json_text or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _pickup_pattern(
    splits: tuple[Split, ...],
    total_distance_km: float | None,
) -> int:
    """Separate repeated 20-60 second pickups from substantial easy running."""
    easy_laps = tuple(
        split for split in splits
        if split.distance_km >= 0.65
        and split.duration_s >= 120
        and split.pace_s_per_km is not None
    )
    if len(easy_laps) < 2:
        return 0
    easy_pace = float(median(split.pace_s_per_km for split in easy_laps))
    fast = tuple(
        split for split in splits
        if 0.075 <= split.distance_km <= 0.22
        and 18 <= split.duration_s <= 60
        and split.pace_s_per_km is not None
        and split.pace_s_per_km <= easy_pace * 0.88
    )
    if len(fast) < 5:
        return 0

    alternating_recoveries = 0
    for earlier, later in zip(fast, fast[1:]):
        between = tuple(
            split for split in splits
            if earlier.index < split.index < later.index
            and 0.06 <= split.distance_km <= 0.25
            and 15 <= split.duration_s <= 90
            and split.pace_s_per_km is not None
            and split.pace_s_per_km >= earlier.pace_s_per_km * 1.14
        )
        if between:
            alternating_recoveries += 1

    fast_distance = sum(split.distance_km for split in fast)
    easy_distance = sum(split.distance_km for split in easy_laps)
    activity_distance = total_distance_km or sum(split.distance_km for split in splits)
    if (
        alternating_recoveries < 3
        or fast_distance > 1.8
        or activity_distance <= 0
        or fast_distance / activity_distance > 0.25
        or easy_distance / activity_distance < 0.50
    ):
        return 0
    return len(fast)


def _boundary_delimited_blocks(
    splits: tuple[Split, ...],
    facts: PatternActivityFacts,
) -> tuple[int, float | None]:
    """Recover long repetitions when recovery happened with the watch stopped."""
    boundaries = tuple(split for split in splits if is_boundary_fragment(split))
    if len(boundaries) < 2 or not facts.elapsed_time_s or not facts.moving_time_s:
        return 0, None
    if facts.moving_time_s / facts.elapsed_time_s > 0.97:
        return 0, None

    groups: list[list[Split]] = [[]]
    for split in splits:
        if is_boundary_fragment(split):
            if groups[-1]:
                groups.append([])
        elif split.distance_km >= 0.08 and split.duration_s >= 15:
            groups[-1].append(split)

    substantial = tuple(
        group for group in groups
        if sum(split.distance_km for split in group) >= 1.8
        and sum(split.duration_s for split in group) >= 360
    )
    if len(substantial) < 3:
        return 0, None

    distances = tuple(sum(split.distance_km for split in group) for group in substantial)
    paces = tuple(
        sum(split.duration_s for split in group) / distance
        for group, distance in zip(substantial, distances)
    )
    representative_distance = float(median(distances))
    representative_pace = float(median(paces))
    similar = tuple(
        (distance, pace)
        for distance, pace in zip(distances, paces)
        if abs(distance - representative_distance) / representative_distance <= 0.14
        and abs(pace - representative_pace) / representative_pace <= 0.12
    )
    if len(similar) < 3:
        return 0, None
    return len(similar), round(float(median(item[0] for item in similar)), 2)


def _stopped_watch_repetitions(
    splits: tuple[Split, ...],
    recognition: WorkoutRecognition,
    facts: PatternActivityFacts,
) -> int:
    """Find repeated faster efforts when stopped recoveries have no lap."""
    if not facts.elapsed_time_s or not facts.moving_time_s:
        return 0
    moving_ratio = facts.moving_time_s / facts.elapsed_time_s
    stopped_seconds = facts.elapsed_time_s - facts.moving_time_s
    if moving_ratio > 0.91 or stopped_seconds < 150:
        return 0

    candidates = tuple(
        split for split in recognition.work_splits
        if 0.35 <= split.distance_km <= 1.35
        and split.duration_s >= 75
        and split.pace_s_per_km is not None
    )
    if len(candidates) < 4:
        return 0
    representative_distance = float(median(item.distance_km for item in candidates))
    family = tuple(
        item for item in candidates
        if abs(item.distance_km - representative_distance) / representative_distance <= 0.20
    )
    if len(family) < 4 or stopped_seconds < len(family) * 35:
        return 0

    # Uniform 1 km auto-laps and an occasionally stopped watch do not establish
    # a session. Genuine 1 km repetitions need distinct recoveries/boundaries.
    kilometre_auto_laps = sum(0.98 <= item.distance_km <= 1.02 for item in family)
    if kilometre_auto_laps / len(family) >= 0.80:
        return 0

    work_pace = float(median(item.pace_s_per_km for item in family))
    family_ids = {item.index for item in family}
    supporting_easy = tuple(
        item for item in splits
        if item.index not in family_ids
        and item.distance_km >= 0.5
        and item.duration_s >= 100
        and item.pace_s_per_km is not None
        and item.pace_s_per_km >= work_pace * 1.13
    )
    return len(family) if supporting_easy else 0


def _equal_distance_alternations(splits: tuple[Split, ...]) -> int:
    """Recognise sessions such as 800 m on / 800 m float recovery."""
    candidates = tuple(
        split for split in splits
        if 0.35 <= split.distance_km <= 1.25
        and split.duration_s >= 75
        and split.pace_s_per_km is not None
    )
    best = 0
    for pivot in candidates:
        family = tuple(
            split for split in candidates
            if abs(split.distance_km - pivot.distance_km) / pivot.distance_km <= 0.12
        )
        if len(family) < 6:
            continue
        even = tuple(split.pace_s_per_km for split in family[::2])
        odd = tuple(split.pace_s_per_km for split in family[1::2])
        if min(len(even), len(odd)) < 3:
            continue
        even_pace = float(median(even))
        odd_pace = float(median(odd))
        fast_pace, recovery_pace = sorted((even_pace, odd_pace))
        if recovery_pace < fast_pace * 1.085:
            continue
        fast_group = even if even_pace < odd_pace else odd
        recovery_group = odd if even_pace < odd_pace else even
        consistent_fast = sum(value <= fast_pace * 1.06 for value in fast_group)
        consistent_recovery = sum(value >= fast_pace * 1.075 for value in recovery_group)
        if consistent_fast >= 3 and consistent_recovery >= 3:
            best = max(best, min(consistent_fast, consistent_recovery))
    return best


def _long_recovery_alternations(splits: tuple[Split, ...]) -> int:
    """Recognise shorter hard efforts alternating with longer easy recoveries."""
    pairs = 0
    for fast, following in zip(splits, splits[1:]):
        if (
            0.25 <= fast.distance_km <= 0.70
            and fast.duration_s >= 55
            and fast.pace_s_per_km is not None
            and following.distance_km >= fast.distance_km * 1.35
            and following.duration_s >= 90
            and following.pace_s_per_km is not None
            and following.pace_s_per_km >= fast.pace_s_per_km * 1.15
        ):
            pairs += 1
    return pairs if pairs >= 3 else 0


@lru_cache(maxsize=12_288)
def analyse_session_patterns(facts: PatternActivityFacts) -> IntervalEvidence:
    """Return the common, cached physical lap evidence for a running activity."""
    payload = _payload(facts.raw_json_text)
    splits = parse_splits(payload.get("splits") or payload.get("splitsCustom"))
    recognition: WorkoutRecognition = recognise_workout(splits)
    work = tuple(
        split for split in recognition.work_splits
        if split.distance_km >= 0.16 and split.duration_s >= 35
    )
    sustained = tuple(
        split for split in work
        if split.distance_km >= 0.35 and split.duration_s >= 75
    )
    work_distance = sum(split.distance_km for split in work)
    average_distance = work_distance / len(work) if work else None
    average_pace = (
        sum(split.duration_s for split in work) / work_distance
        if work_distance > 0 else None
    )

    credible_recoveries = ()
    if average_distance and average_pace:
        credible_recoveries = tuple(
            split for split in recognition.recovery_splits
            if 18 <= split.duration_s <= 360
            and split.distance_km <= average_distance * 0.72
            and split.pace_s_per_km is not None
            and split.pace_s_per_km >= average_pace * 1.15
        )

    recovery_ratio = None
    if recognition.recovery_splits and average_distance:
        recovery_ratio = (
            median(split.distance_km for split in recognition.recovery_splits)
            / average_distance
        )

    substantial_family = tuple(
        split for split in splits
        if split.distance_km >= 0.7 and split.duration_s >= 120
    )
    auto_laps = False
    if len(substantial_family) >= 4:
        lap_distance = median(split.distance_km for split in substantial_family)
        similar = tuple(
            split for split in substantial_family
            if abs(split.distance_km - lap_distance) / lap_distance <= 0.12
        )
        auto_laps = (
            len(similar) >= max(4, int(len(substantial_family) * 0.75))
            and (
                not credible_recoveries
                or (recovery_ratio is not None and recovery_ratio >= 0.72)
            )
        )

    substantial_work = len(sustained) >= 3 and work_distance >= 1.6
    short_interval_work = len(work) >= 7 and work_distance >= 1.4
    required_recoveries = max(2, min(len(work) - 1, int(len(work) * 0.55)))
    trustworthy = (
        (substantial_work or short_interval_work)
        and len(credible_recoveries) >= required_recoveries
        and not auto_laps
    )

    short_strides = tuple(
        split for split in splits
        if 0.055 <= split.distance_km <= 0.22
        and 10 <= split.duration_s <= 65
    )
    pickup_count = _pickup_pattern(splits, facts.distance_km)
    block_count, block_distance = _boundary_delimited_blocks(splits, facts)
    stopped_count = _stopped_watch_repetitions(splits, recognition, facts)
    equal_alternations = _equal_distance_alternations(splits)
    long_alternations = _long_recovery_alternations(splits)

    trustworthy = (
        trustworthy
        or block_count >= 3
        or stopped_count >= 4
        or equal_alternations >= 3
        or long_alternations >= 3
    ) and pickup_count == 0

    return IntervalEvidence(
        split_count=len(splits),
        work_count=len(work),
        sustained_work_count=len(sustained),
        work_distance_km=round(work_distance, 3),
        average_work_distance_km=(
            round(average_distance, 3) if average_distance is not None else None
        ),
        average_work_pace_s_per_km=(
            round(average_pace, 1) if average_pace is not None else None
        ),
        recovery_count=len(recognition.recovery_splits),
        credible_recovery_count=len(credible_recoveries),
        recovery_distance_ratio=(
            round(recovery_ratio, 3) if recovery_ratio is not None else None
        ),
        short_stride_count=len(short_strides),
        repeated_auto_laps=auto_laps,
        trustworthy_intervals=trustworthy,
        pickup_count=pickup_count,
        boundary_block_count=block_count,
        boundary_block_distance_km=block_distance,
        stopped_watch_work_count=stopped_count,
        equal_distance_alternation_count=equal_alternations,
        long_recovery_alternation_count=long_alternations,
        description=recognition.description,
    )
