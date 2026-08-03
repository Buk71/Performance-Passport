"""
Runalyze split-string decoder and workout recogniser.

Observed Runalyze format:
    U1.609|8:16-U0.153|1:00-U1.609|7:58

Each segment is:
    U<distance_km>|<duration>

Examples:
    U1.609|8:16  -> 1.609 km in 8:16
    U0.400|1:32  -> 400 m in 1:32

The leading "U" is preserved as the source marker but is not required for
parsing. Distances are treated as kilometres because 1.609 consistently
represents one mile in the exported data.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from statistics import mean, pstdev


TOKEN_PATTERN = re.compile(
    r"""
    ^\s*
    (?P<prefix>[A-Za-z]?)
    (?P<distance>\d+(?:\.\d+)?)
    \|
    (?P<time>\d+(?::\d{1,2}){1,2})
    \s*$
    """,
    re.VERBOSE,
)


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
    """Convert M:SS or H:MM:SS to seconds."""
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


def parse_splits(raw_value: str | None) -> tuple[Split, ...]:
    """
    Decode a Runalyze splits string.

    Invalid tokens are skipped rather than breaking the whole activity.
    """
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


def _is_plausible_work_split(split: Split) -> bool:
    pace = split.pace_s_per_km

    if pace is None:
        return False

    # Broad running-work range: 2:30/km to 6:30/km.
    return 150 <= pace <= 390 and 0.20 <= split.distance_km <= 5.0


def _distance_cluster(splits: list[Split]) -> list[Split]:
    """
    Return the strongest repeated-distance cluster.

    A tolerance of 8% allows GPS/lap rounding while separating work and
    recovery segments.
    """
    if not splits:
        return []

    best = []

    for seed in splits:
        tolerance = max(seed.distance_km * 0.08, 0.025)
        cluster = [
            split
            for split in splits
            if abs(split.distance_km - seed.distance_km) <= tolerance
        ]

        if len(cluster) > len(best):
            best = cluster
        elif len(cluster) == len(best) and cluster:
            if sum(s.distance_km for s in cluster) > sum(
                s.distance_km for s in best
            ):
                best = cluster

    return best


def _format_distance(distance_km: float) -> str:
    if abs(distance_km - 1.609) <= 0.08:
        return "1 mile"
    if abs(distance_km - 3.218) <= 0.15:
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


def recognise_workout(
    splits: tuple[Split, ...],
) -> WorkoutRecognition:
    """
    Recognise the most likely workout structure from manual/recorded laps.

    Version 1 focuses on repeated-distance sessions. It deliberately returns
    "Unclassified" when the split pattern is ambiguous.
    """
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

    plausible = [split for split in splits if _is_plausible_work_split(split)]
    cluster = _distance_cluster(plausible)

    if len(cluster) < 2:
        longest = max(splits, key=lambda split: split.distance_km)

        if (
            longest.distance_km >= 3.0
            and longest.pace_s_per_km is not None
            and longest.pace_s_per_km <= 360
        ):
            other = [split for split in splits if split != longest]
            return WorkoutRecognition(
                workout_type="Continuous sustained effort",
                confidence=0.62,
                work_splits=(longest,),
                recovery_splits=(),
                warmup_splits=tuple(
                    split for split in other if split.index < longest.index
                ),
                cooldown_splits=tuple(
                    split for split in other if split.index > longest.index
                ),
                description=(
                    f"One sustained {_format_distance(longest.distance_km)} "
                    f"effort in {_format_duration(longest.duration_s)}."
                ),
                reasons=(
                    "One long, continuous, faster split was identified.",
                ),
                limitations=(
                    "A single split cannot prove the intended workout type.",
                ),
            )

        return WorkoutRecognition(
            workout_type="Unclassified",
            confidence=0.25,
            work_splits=(),
            recovery_splits=(),
            warmup_splits=(),
            cooldown_splits=(),
            description=(
                f"{len(splits)} split(s) decoded, but no repeated work "
                "pattern was strong enough to classify."
            ),
            reasons=("Split data was successfully decoded.",),
            limitations=(
                "The laps may represent route splits rather than workout reps.",
            ),
        )

    # When work and recoveries use similar lap distances (for example
    # alternating 400 m fast / 400 m float), split the distance cluster by
    # pace and keep the faster group as the work reps.
    cluster_paces = [
        split.pace_s_per_km
        for split in cluster
        if split.pace_s_per_km is not None
    ]

    if len(cluster_paces) >= 4:
        median_pace = sorted(cluster_paces)[len(cluster_paces) // 2]
        fast_group = [
            split
            for split in cluster
            if split.pace_s_per_km is not None
            and split.pace_s_per_km <= median_pace * 0.92
        ]
        slow_group = [
            split
            for split in cluster
            if split not in fast_group
        ]

        if len(fast_group) >= 2 and len(slow_group) >= 1:
            cluster = fast_group

    cluster_indexes = {split.index for split in cluster}
    first_work = min(cluster_indexes)
    last_work = max(cluster_indexes)

    between = [
        split
        for split in splits
        if first_work <= split.index <= last_work
        and split.index not in cluster_indexes
    ]

    work_average_pace = mean(
        split.pace_s_per_km
        for split in cluster
        if split.pace_s_per_km is not None
    )

    recoveries = [
        split
        for split in between
        if split.distance_km < mean(s.distance_km for s in cluster) * 0.65
        or (
            split.pace_s_per_km is not None
            and split.pace_s_per_km > work_average_pace * 1.18
        )
    ]

    warmup = tuple(split for split in splits if split.index < first_work)
    cooldown = tuple(split for split in splits if split.index > last_work)

    average_distance = mean(split.distance_km for split in cluster)
    average_pace = (
        sum(split.duration_s for split in cluster)
        / sum(split.distance_km for split in cluster)
    )
    variation = (
        pstdev(split.pace_s_per_km for split in cluster)
        / average_pace
        * 100.0
        if len(cluster) >= 2
        else 0.0
    )

    confidence = 0.45
    confidence += min(len(cluster), 8) / 8 * 0.25
    confidence += 0.15 if len(recoveries) >= len(cluster) - 1 else 0.05
    confidence += 0.15 if variation <= 5 else 0.08 if variation <= 10 else 0
    confidence = min(confidence, 0.98)

    if 0.30 <= average_distance <= 0.50:
        workout_type = "Short intervals"
    elif 0.70 <= average_distance <= 1.20:
        workout_type = "Long intervals"
    elif 1.35 <= average_distance <= 1.85:
        workout_type = "Mile repetitions"
    elif 2.5 <= average_distance <= 3.8:
        workout_type = "Long threshold repetitions"
    else:
        workout_type = "Repeated-distance workout"

    description = (
        f"{len(cluster)} × {_format_distance(average_distance)} recognised "
        f"at an average pace of {_format_pace(average_pace)}."
    )

    reasons = [
        f"{len(cluster)} work splits have closely matched distances.",
        f"{len(recoveries)} likely recovery split(s) were identified.",
        f"Rep pace variation is {variation:.1f}%.",
    ]

    limitations = [
        "The decoder identifies lap structure, not the athlete's intended zone.",
        "Heart rate per split is not present in the CSV split string.",
        "FIT lap records will later add split heart rate, cadence and power.",
    ]

    return WorkoutRecognition(
        workout_type=workout_type,
        confidence=confidence,
        work_splits=tuple(sorted(cluster, key=lambda split: split.index)),
        recovery_splits=tuple(recoveries),
        warmup_splits=warmup,
        cooldown_splits=cooldown,
        description=description,
        reasons=tuple(reasons),
        limitations=tuple(limitations),
    )


def _format_pace(seconds_per_km: float) -> str:
    minutes = int(seconds_per_km // 60)
    seconds = int(round(seconds_per_km % 60))

    if seconds == 60:
        minutes += 1
        seconds = 0

    return f"{minutes}:{seconds:02d}/km"


def splits_to_dicts(splits: tuple[Split, ...]) -> list[dict]:
    """Return JSON-friendly split rows for UI/debug use."""
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
        }
        for split in splits
    ]
