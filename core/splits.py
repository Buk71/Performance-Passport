"""
Runalyze split decoder and pattern-based Workout Coach recogniser.

The recogniser is designed around real lap-button use:

- work reps do not need to have identical distances;
- a session may contain more than one family of reps;
- very short fragments can be created by pressing lap, stopping the watch,
  restarting it and pressing lap again;
- stopped-watch recoveries may be missing or only partly represented;
- boundaries must never inflate the rep count.

Supported Runalyze split formats:

Legacy:
    U<distance_km>|<duration>

Current:
    I<distance_km>|<duration>||<metadata>

Examples:
    U1.000|4:02-U0.120|0:31-U0.998|4:01
    I1.000|4:02||0-I0.120|0:31||0-I0.998|4:01||0

Both formats are normalised into the same Split objects.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from statistics import mean, median, pstdev


TOKEN_PATTERN = re.compile(
    r"""
    ^\s*
    (?P<prefix>[A-Za-z]?)
    (?P<distance>\d+(?:\.\d+)?)
    \|
    (?P<time>\d+(?::\d{1,2}){1,2})
    (?P<suffix>(?:\|\|.*)?)?
    \s*$
    """,
    re.VERBOSE,
)

BOUNDARY_MAX_SECONDS = 10
BOUNDARY_MAX_DISTANCE_KM = 0.08


@dataclass(frozen=True)
class Split:
    index: int
    distance_km: float
    duration_s: int
    prefix: str = "U"

    @property
    def pace_s_per_km(self) -> float | None:
        if self.distance_km <= 0:
            return None
        return self.duration_s / self.distance_km

    @property
    def speed_kmh(self) -> float | None:
        if self.duration_s <= 0:
            return None
        return self.distance_km / (self.duration_s / 3600.0)


@dataclass(frozen=True)
class WorkoutBlock:
    kind: str
    splits: tuple[Split, ...]

    @property
    def distance_km(self) -> float:
        return sum(split.distance_km for split in self.splits)

    @property
    def duration_s(self) -> int:
        return sum(split.duration_s for split in self.splits)

    @property
    def pace_s_per_km(self) -> float | None:
        if self.distance_km <= 0:
            return None
        return self.duration_s / self.distance_km


@dataclass(frozen=True)
class WorkoutRecognition:
    workout_type: str
    confidence: float
    work_splits: tuple[Split, ...]
    recovery_splits: tuple[Split, ...]
    warmup_splits: tuple[Split, ...]
    cooldown_splits: tuple[Split, ...]
    description: str
    reasons: tuple[str, ...]
    limitations: tuple[str, ...]
    boundary_splits: tuple[Split, ...] = ()
    unknown_recovery_count: int = 0
    work_blocks: tuple[WorkoutBlock, ...] = ()

    @property
    def rep_count(self) -> int:
        return len(self.work_splits)

    @property
    def average_rep_distance_km(self) -> float | None:
        if not self.work_splits:
            return None
        return mean(split.distance_km for split in self.work_splits)

    @property
    def average_rep_pace_s_per_km(self) -> float | None:
        if not self.work_splits:
            return None

        total_distance = sum(split.distance_km for split in self.work_splits)
        total_time = sum(split.duration_s for split in self.work_splits)

        if total_distance <= 0:
            return None

        return total_time / total_distance

    @property
    def rep_pace_variation_percent(self) -> float | None:
        paces = [
            split.pace_s_per_km
            for split in self.work_splits
            if split.pace_s_per_km is not None
        ]

        if len(paces) < 2:
            return None

        average = mean(paces)
        if average <= 0:
            return None

        return pstdev(paces) / average * 100.0


def parse_duration(value: str) -> int:
    parts = [int(part) for part in value.strip().split(":")]

    if len(parts) == 2:
        minutes, seconds = parts
        if seconds >= 60:
            raise ValueError(f"Invalid duration: {value}")
        return minutes * 60 + seconds

    if len(parts) == 3:
        hours, minutes, seconds = parts
        if minutes >= 60 or seconds >= 60:
            raise ValueError(f"Invalid duration: {value}")
        return hours * 3600 + minutes * 60 + seconds

    raise ValueError(f"Unsupported duration: {value}")


def detect_split_format(raw_value: str | None) -> str:
    """Return the recognised split encoding family."""
    if raw_value is None:
        return "none"

    value = str(raw_value).strip()

    if not value:
        return "none"

    first_token = value.split("-", 1)[0].strip()

    if first_token.startswith("I"):
        return "runalyze_current_i"
    if first_token.startswith("U"):
        return "runalyze_legacy_u"

    return "unknown"


def parse_splits(raw_value: str | None) -> tuple[Split, ...]:
    if raw_value is None:
        return ()

    value = str(raw_value).strip()

    if not value or value.lower() in {"none", "null", "nan"}:
        return ()

    parsed = []

    for token in value.split("-"):
        match = TOKEN_PATTERN.match(token)

        if match is None:
            continue

        try:
            distance_km = float(match.group("distance"))
            duration_s = parse_duration(match.group("time"))
        except (TypeError, ValueError):
            continue

        if distance_km <= 0 or duration_s <= 0:
            continue

        parsed.append(
            Split(
                index=len(parsed) + 1,
                distance_km=distance_km,
                duration_s=duration_s,
                prefix=match.group("prefix") or "U",
            )
        )

    return tuple(parsed)


def is_boundary_fragment(split: Split) -> bool:
    """
    Tiny sub-10-second laps are usually lap/stop/start artefacts.

    They are kept for auditability but never counted as work or recovery reps.
    """
    if (
        split.duration_s < BOUNDARY_MAX_SECONDS
        and split.distance_km < BOUNDARY_MAX_DISTANCE_KM
    ):
        return True

    pace = split.pace_s_per_km
    if split.duration_s <= 5 and pace is not None:
        return True

    return False


def _valid_training_split(split: Split) -> bool:
    pace = split.pace_s_per_km
    if pace is None:
        return False

    return (
        split.duration_s >= 10
        and split.distance_km >= 0.06
        and 120 <= pace <= 900
    )


def _kmeans_two(values: list[float]) -> tuple[list[int], float, float] | None:
    """Small deterministic two-cluster k-means for pace separation."""
    if len(values) < 4:
        return None

    low = min(values)
    high = max(values)

    if high <= low:
        return None

    c1, c2 = low, high
    assignments = [0] * len(values)

    for _ in range(20):
        new_assignments = [
            0 if abs(value - c1) <= abs(value - c2) else 1
            for value in values
        ]

        group1 = [
            value for value, group in zip(values, new_assignments)
            if group == 0
        ]
        group2 = [
            value for value, group in zip(values, new_assignments)
            if group == 1
        ]

        if not group1 or not group2:
            return None

        new_c1 = mean(group1)
        new_c2 = mean(group2)

        if (
            new_assignments == assignments
            and abs(new_c1 - c1) < 0.01
            and abs(new_c2 - c2) < 0.01
        ):
            assignments = new_assignments
            c1, c2 = new_c1, new_c2
            break

        assignments = new_assignments
        c1, c2 = new_c1, new_c2

    if c1 > c2:
        assignments = [1 - group for group in assignments]
        c1, c2 = c2, c1

    return assignments, c1, c2


def _distance_families(
    splits: list[Split],
    tolerance_ratio: float = 0.18,
) -> list[list[Split]]:
    """
    Group work reps into approximate distance families.

    The tolerance is deliberately broad so time-based reps and manual-lap
    variation remain in the same family.
    """
    families: list[list[Split]] = []

    for split in sorted(splits, key=lambda item: item.distance_km):
        placed = False

        for family in families:
            centre = mean(item.distance_km for item in family)
            tolerance = max(centre * tolerance_ratio, 0.06)

            if abs(split.distance_km - centre) <= tolerance:
                family.append(split)
                placed = True
                break

        if not placed:
            families.append([split])

    return sorted(
        families,
        key=lambda family: min(item.index for item in family),
    )


def _format_distance(distance_km: float) -> str:
    if abs(distance_km - 1.609) <= 0.12:
        return "1 mile"
    if abs(distance_km - 3.218) <= 0.25:
        return "2 miles"
    if distance_km < 1:
        return f"{round(distance_km * 1000):.0f} m"
    return f"{distance_km:.2f} km"


def _format_duration(seconds: int) -> str:
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    remaining = seconds % 60

    if hours:
        return f"{hours}:{minutes:02d}:{remaining:02d}"
    return f"{minutes}:{remaining:02d}"


def _format_pace(seconds_per_km: float) -> str:
    minutes = int(seconds_per_km // 60)
    seconds = int(round(seconds_per_km % 60))

    if seconds == 60:
        minutes += 1
        seconds = 0

    return f"{minutes}:{seconds:02d}/km"


def _describe_families(work: list[Split]) -> str:
    families = _distance_families(work)
    parts = []

    for family in families:
        average_distance = mean(split.distance_km for split in family)
        parts.append(f"{len(family)} × {_format_distance(average_distance)}")

    return " + ".join(parts)


def _build_work_blocks(
    work: list[Split],
    all_meaningful: list[Split],
) -> tuple[WorkoutBlock, ...]:
    if not work:
        return ()

    work_indexes = {split.index for split in work}
    blocks: list[list[Split]] = []
    current: list[Split] = []
    previous_work_position: int | None = None

    meaningful_positions = {
        split.index: position
        for position, split in enumerate(all_meaningful)
    }

    for split in sorted(work, key=lambda item: item.index):
        position = meaningful_positions.get(split.index)

        if (
            previous_work_position is None
            or position is None
            or position - previous_work_position <= 2
        ):
            current.append(split)
        else:
            blocks.append(current)
            current = [split]

        previous_work_position = position

    if current:
        blocks.append(current)

    return tuple(
        WorkoutBlock(kind="work", splits=tuple(block))
        for block in blocks
    )


def recognise_workout(
    splits: tuple[Split, ...],
) -> WorkoutRecognition:
    if not splits:
        return WorkoutRecognition(
            workout_type="No split data",
            confidence=0.0,
            work_splits=(),
            recovery_splits=(),
            warmup_splits=(),
            cooldown_splits=(),
            description="No decodable split data was available.",
            reasons=(),
            limitations=("No split string was available.",),
        )

    boundaries = tuple(
        split for split in splits if is_boundary_fragment(split)
    )
    meaningful = [
        split
        for split in splits
        if not is_boundary_fragment(split)
        and _valid_training_split(split)
    ]

    if len(meaningful) < 2:
        return WorkoutRecognition(
            workout_type="Unclassified",
            confidence=0.30 if meaningful else 0.15,
            work_splits=(),
            recovery_splits=(),
            warmup_splits=tuple(meaningful),
            cooldown_splits=(),
            boundary_splits=boundaries,
            description=(
                f"{len(splits)} split(s) decoded, but too few meaningful "
                "segments remained after boundary filtering."
            ),
            reasons=(
                f"{len(boundaries)} probable lap/stop/start fragment(s) ignored.",
            ),
            limitations=(
                "The session structure cannot be recovered confidently.",
            ),
        )

    # A deliberately alternating fast/slow pattern is stronger evidence
    # than lap distance alone. In particular, 200 m reps are not recovery
    # connectors merely because the warm-up happens to be 400 m long.
    alternating_work: list[Split] = []
    alternating_recovery: list[Split] = []
    for family in _distance_families(meaningful, tolerance_ratio=0.10):
        if len(family) < 3 or median(item.distance_km for item in family) < 0.12:
            continue
        ordered_family = sorted(family, key=lambda item: item.index)
        linked_recoveries = []
        for previous, following in zip(ordered_family, ordered_family[1:]):
            between = [
                item for item in meaningful
                if previous.index < item.index < following.index
                and item.pace_s_per_km is not None
                and item.distance_km < following.distance_km * 0.86
                and item.pace_s_per_km >= following.pace_s_per_km * 1.20
            ]
            if between:
                linked_recoveries.append(between[-1])
        if len(linked_recoveries) < max(2, int((len(ordered_family) - 1) * 0.60)):
            continue
        if sum(item.distance_km for item in ordered_family) > sum(
            item.distance_km for item in alternating_work
        ):
            alternating_work = ordered_family
            alternating_recovery = linked_recoveries

    # Short connector laps can look deceptively fast because they occur
    # around lap/stop/start presses. When the session also contains several
    # substantial segments, treat these connectors as recovery candidates
    # before pace clustering.
    substantial = [
        split
        for split in meaningful
        if split.duration_s >= 90 and split.distance_km >= 0.25
    ]
    connector_recoveries = []

    if len(substantial) >= 2 and not alternating_work:
        connector_recoveries = [
            split
            for split in meaningful
            if split.duration_s < 90 and split.distance_km < 0.25
        ]

    clustering_pool = [
        split
        for split in meaningful
        if split not in connector_recoveries
    ]
    paces = [
        split.pace_s_per_km
        for split in clustering_pool
        if split.pace_s_per_km is not None
    ]
    clustering = _kmeans_two(paces)

    work: list[Split] = list(alternating_work)
    recovery: list[Split] = (
        list(alternating_recovery) if alternating_work else list(connector_recoveries)
    )
    pace_separation = 0.0

    if clustering is not None and not alternating_work:
        assignments, fast_centre, slow_centre = clustering
        pace_separation = (slow_centre - fast_centre) / slow_centre

        if pace_separation >= 0.12:
            for split, group in zip(clustering_pool, assignments):
                if group == 0:
                    work.append(split)
                else:
                    recovery.append(split)

    # Fallback for sessions with repeated distances but less obvious pace
    # separation, such as controlled threshold reps.
    if len(work) < 2:
        candidate_families = [
            family
            for family in _distance_families(
                clustering_pool,
                tolerance_ratio=0.10,
            )
            if len(family) >= 2
        ]

        if candidate_families:
            best_family = max(
                candidate_families,
                key=lambda family: (
                    len(family),
                    sum(split.distance_km for split in family),
                ),
            )
            family_pace = mean(
                split.pace_s_per_km
                for split in best_family
                if split.pace_s_per_km is not None
            )
            overall_pace = median(paces)

            if family_pace <= overall_pace * 1.06:
                work = list(best_family)
                work_indexes = {split.index for split in work}
                recovery = [
                    split
                    for split in meaningful
                    if split.index not in work_indexes
                    and min(work_indexes) < split.index < max(work_indexes)
                ]

    if len(work) < 2:
        longest = max(meaningful, key=lambda split: split.distance_km)

        if (
            longest.distance_km >= 3.0
            and longest.pace_s_per_km is not None
            and longest.pace_s_per_km <= 390
        ):
            return WorkoutRecognition(
                workout_type="Continuous sustained effort",
                confidence=0.64,
                work_splits=(longest,),
                recovery_splits=(),
                warmup_splits=tuple(
                    split for split in meaningful if split.index < longest.index
                ),
                cooldown_splits=tuple(
                    split for split in meaningful if split.index > longest.index
                ),
                boundary_splits=boundaries,
                description=(
                    f"One sustained {_format_distance(longest.distance_km)} "
                    f"effort in {_format_duration(longest.duration_s)}."
                ),
                reasons=(
                    "One long, continuous faster segment was identified.",
                    f"{len(boundaries)} boundary fragment(s) were ignored.",
                ),
                limitations=(
                    "A single segment cannot prove the intended workout type.",
                ),
            )

        return WorkoutRecognition(
            workout_type="Unclassified",
            confidence=0.35,
            work_splits=(),
            recovery_splits=(),
            warmup_splits=tuple(meaningful),
            cooldown_splits=(),
            boundary_splits=boundaries,
            description=(
                f"{len(splits)} split(s) decoded, but no convincing work "
                "pattern was found."
            ),
            reasons=(
                f"{len(boundaries)} probable lap/stop/start fragment(s) ignored.",
            ),
            limitations=(
                "The laps may be ordinary route splits or a session with "
                "recoveries omitted while the watch was stopped.",
            ),
        )

    work = sorted(work, key=lambda split: split.index)
    work_indexes = {split.index for split in work}
    first_work = min(work_indexes)
    last_work = max(work_indexes)

    # Only slower segments between work reps are recoveries. Slower segments
    # outside the work block are warm-up/cool-down.
    recovery = [
        split
        for split in recovery
        if first_work < split.index < last_work
    ]
    warmup = tuple(
        split
        for split in meaningful
        if split.index < first_work
    )
    cooldown = tuple(
        split
        for split in meaningful
        if split.index > last_work
    )

    # Boundary fragments between work reps indicate likely stopped-watch or
    # manual-lap transitions. They count as unknown recoveries, never reps.
    unknown_recovery_count = 0
    sorted_work = sorted(work, key=lambda split: split.index)

    for previous, following in zip(sorted_work, sorted_work[1:]):
        between_boundaries = [
            split
            for split in boundaries
            if previous.index < split.index < following.index
        ]
        between_recoveries = [
            split
            for split in recovery
            if previous.index < split.index < following.index
        ]

        if between_boundaries and not between_recoveries:
            unknown_recovery_count += 1

    average_pace = (
        sum(split.duration_s for split in work)
        / sum(split.distance_km for split in work)
    )
    variation = (
        pstdev(
            split.pace_s_per_km
            for split in work
            if split.pace_s_per_km is not None
        )
        / average_pace
        * 100.0
        if len(work) >= 2
        else 0.0
    )
    families = _distance_families(work)
    mixed = len(families) > 1
    blocks = _build_work_blocks(work, meaningful)

    average_distance = mean(split.distance_km for split in work)

    if mixed:
        workout_type = "Mixed interval session"
    elif 0.20 <= average_distance <= 0.55:
        workout_type = "Short intervals"
    elif 0.55 < average_distance <= 1.20:
        workout_type = "Long intervals"
    elif 1.20 < average_distance <= 1.95:
        workout_type = "Mile repetitions"
    elif 1.95 < average_distance <= 4.0:
        workout_type = "Long threshold repetitions"
    else:
        workout_type = "Structured workout"

    confidence = 0.46
    confidence += min(len(work), 8) / 8 * 0.18
    confidence += min(pace_separation / 0.30, 1.0) * 0.14
    confidence += 0.10 if recovery else 0.03
    confidence += 0.08 if variation <= 6 else 0.04 if variation <= 12 else 0
    confidence += 0.06 if boundaries else 0
    confidence -= min(unknown_recovery_count * 0.025, 0.10)
    confidence = max(0.35, min(confidence, 0.97))

    family_description = _describe_families(work)

    description = (
        f"{family_description} recognised at an average pace of "
        f"{_format_pace(average_pace)}."
    )

    reasons = [
        f"{len(work)} work segment(s) were identified by pace and sequence.",
        f"{len(recovery)} recorded recovery segment(s) were identified.",
        f"{len(boundaries)} probable lap/stop/start fragment(s) were ignored.",
        f"Rep pace variation is {variation:.1f}%.",
    ]

    if unknown_recovery_count:
        reasons.append(
            f"{unknown_recovery_count} recovery gap(s) may have occurred "
            "while the watch was stopped."
        )

    if mixed:
        reasons.append(
            "More than one work-distance family was recognised."
        )

    limitations = [
        "CSV splits do not include heart rate, cadence or power for each lap.",
        "Stopped-watch recovery duration cannot be reconstructed exactly.",
        "The parser identifies performed structure, not intended training zone.",
    ]

    return WorkoutRecognition(
        workout_type=workout_type,
        confidence=confidence,
        work_splits=tuple(work),
        recovery_splits=tuple(sorted(recovery, key=lambda split: split.index)),
        warmup_splits=warmup,
        cooldown_splits=cooldown,
        boundary_splits=boundaries,
        unknown_recovery_count=unknown_recovery_count,
        work_blocks=blocks,
        description=description,
        reasons=tuple(reasons),
        limitations=tuple(limitations),
    )


def splits_to_dicts(splits: tuple[Split, ...]) -> list[dict]:
    return [
        {
            "index": split.index,
            "distance_km": round(split.distance_km, 4),
            "duration_s": split.duration_s,
            "duration": _format_duration(split.duration_s),
            "pace_s_per_km": (
                round(split.pace_s_per_km, 2)
                if split.pace_s_per_km is not None
                else None
            ),
            "pace": (
                _format_pace(split.pace_s_per_km)
                if split.pace_s_per_km is not None
                else None
            ),
            "boundary_fragment": is_boundary_fragment(split),
        }
        for split in splits
    ]
