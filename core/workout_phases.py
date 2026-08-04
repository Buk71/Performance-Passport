"""
Workout Phase Engine.

The engine produces one standard phase model from the best available source:

1. FIT-derived phases, when structured FIT phases have already been stored.
2. Runalyze CSV split reconstruction.
3. Activity-level fallback.

The first implementation focuses on making Runalyze CSV genuinely useful,
including mixed sessions such as:

    warm-up -> continuous threshold -> 10 x 400 m -> cool-down

It also leaves a clean FIT integration point without making Workout Coach
depend on any device-specific format.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from statistics import mean
from typing import Any

from core.splits import Split, is_boundary_fragment, parse_splits

# A split must be at least 12% faster than the athlete's easy pace to
# count as work. Easy-like splits remain available for warm-up,
# cool-down and recovery reconstruction.
WORK_PACE_RATIO = 0.88


@dataclass(frozen=True)
class WorkoutPhase:
    phase_type: str
    label: str
    source: str
    confidence: float
    distance_km: float
    duration_s: int
    pace_s_per_km: float | None
    rep_count: int = 1
    average_rep_distance_km: float | None = None
    recovery_duration_s: float | None = None
    split_indexes: tuple[int, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkoutPhaseResult:
    phases: tuple[WorkoutPhase, ...]
    source: str
    confidence: float
    summary: str
    reasons: tuple[str, ...]
    limitations: tuple[str, ...]


def _safe_json(raw_json_text: str | None) -> dict[str, Any]:
    if not raw_json_text:
        return {}

    try:
        value = json.loads(raw_json_text)
    except (TypeError, json.JSONDecodeError):
        return {}

    return value if isinstance(value, dict) else {}


def _phase_from_dict(value: dict[str, Any], source: str) -> WorkoutPhase | None:
    try:
        distance_km = float(value.get("distance_km") or 0.0)
        duration_s = int(round(float(value.get("duration_s") or 0.0)))
    except (TypeError, ValueError):
        return None

    pace = None
    if distance_km > 0 and duration_s > 0:
        pace = duration_s / distance_km

    return WorkoutPhase(
        phase_type=str(value.get("phase_type") or "unknown"),
        label=str(value.get("label") or "Workout phase"),
        source=source,
        confidence=float(value.get("confidence") or 0.95),
        distance_km=distance_km,
        duration_s=duration_s,
        pace_s_per_km=pace,
        rep_count=int(value.get("rep_count") or 1),
        average_rep_distance_km=(
            float(value["average_rep_distance_km"])
            if value.get("average_rep_distance_km") is not None
            else None
        ),
        recovery_duration_s=(
            float(value["recovery_duration_s"])
            if value.get("recovery_duration_s") is not None
            else None
        ),
        split_indexes=tuple(value.get("split_indexes") or ()),
        metadata=dict(value.get("metadata") or {}),
    )


def _stored_fit_phases(raw: dict[str, Any]) -> tuple[WorkoutPhase, ...]:
    """
    Read already-normalised FIT phases when the FIT importer supplies them.

    This intentionally does not parse FIT binary data here. The future FIT
    importer only needs to store `fit_workout_phases` in raw JSON and this
    engine will automatically prefer it.
    """
    values = raw.get("fit_workout_phases") or raw.get("workout_phases")

    if not isinstance(values, list):
        return ()

    phases = []

    for value in values:
        if not isinstance(value, dict):
            continue

        phase = _phase_from_dict(value, source="fit")

        if phase is not None:
            phases.append(phase)

    return tuple(phases)


def _distance_families(
    splits: list[Split],
    tolerance_ratio: float = 0.18,
) -> list[list[Split]]:
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


def _aggregate_phase(
    *,
    phase_type: str,
    label: str,
    source: str,
    confidence: float,
    splits: list[Split],
    rep_count: int | None = None,
    recovery_duration_s: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> WorkoutPhase:
    distance = sum(split.distance_km for split in splits)
    duration = sum(split.duration_s for split in splits)
    pace = duration / distance if distance > 0 else None
    count = rep_count if rep_count is not None else len(splits)

    return WorkoutPhase(
        phase_type=phase_type,
        label=label,
        source=source,
        confidence=confidence,
        distance_km=round(distance, 4),
        duration_s=int(duration),
        pace_s_per_km=pace,
        rep_count=max(count, 1),
        average_rep_distance_km=(
            round(distance / count, 4)
            if count and count > 0
            else None
        ),
        recovery_duration_s=recovery_duration_s,
        split_indexes=tuple(split.index for split in splits),
        metadata=metadata or {},
    )



def _find_alternating_float_pattern(
    meaningful: list[Split],
) -> dict | None:
    """
    Recognise continuous alternating work/float sessions.

    Example:
        6 x 800 m at HM pace with 800 m float recoveries

    Both the work and float laps can be faster than easy pace, so this pattern
    must be detected before the easy-pace work filter is applied.
    """
    candidates = [
        split
        for split in meaningful
        if 0.45 <= split.distance_km <= 1.15
        and split.duration_s >= 75
        and split.pace_s_per_km is not None
    ]

    if len(candidates) < 8:
        return None

    best = None

    # Search contiguous candidate windows. Programmed workouts may have a
    # warm-up or cool-down immediately outside the alternating sequence.
    for start in range(len(candidates)):
        for end in range(start + 8, len(candidates) + 1):
            window = candidates[start:end]

            indexes = [split.index for split in window]
            if any(
                following - previous > 2
                for previous, following in zip(indexes, indexes[1:])
            ):
                continue

            distances = [split.distance_km for split in window]
            average_distance = mean(distances)

            if average_distance <= 0:
                continue

            if any(
                abs(distance - average_distance) / average_distance > 0.28
                for distance in distances
            ):
                continue

            odd = window[0::2]
            even = window[1::2]

            if min(len(odd), len(even)) < 4:
                continue

            odd_pace = mean(split.pace_s_per_km for split in odd)
            even_pace = mean(split.pace_s_per_km for split in even)

            if odd_pace <= even_pace:
                work = odd
                floats = even
                work_pace = odd_pace
                float_pace = even_pace
            else:
                work = even
                floats = odd
                work_pace = even_pace
                float_pace = odd_pace

            pace_gap = (float_pace - work_pace) / work_pace

            # Floats should be meaningfully slower, but still running.
            if pace_gap < 0.07 or pace_gap > 0.45:
                continue

            balance = min(len(work), len(floats)) / max(
                len(work),
                len(floats),
            )
            score = (
                min(len(work), len(floats)) * 10
                + balance * 5
                - abs(average_distance - 0.8)
            )

            if best is None or score > best["score"]:
                best = {
                    "work": work,
                    "floats": floats,
                    "average_distance_km": average_distance,
                    "work_pace_s_per_km": work_pace,
                    "float_pace_s_per_km": float_pace,
                    "pace_gap": pace_gap,
                    "score": score,
                }

    return best

def _find_repeated_short_family(
    meaningful: list[Split],
) -> list[Split]:
    families = _distance_families(
        [
            split
            for split in meaningful
            if 0.20 <= split.distance_km <= 0.65
            and split.duration_s >= 30
        ],
        tolerance_ratio=0.20,
    )

    viable = [family for family in families if len(family) >= 3]

    if not viable:
        return []

    return max(
        viable,
        key=lambda family: (
            len(family),
            sum(split.distance_km for split in family),
        ),
    )


def _find_threshold_before_reps(
    meaningful: list[Split],
    first_rep_index: int,
) -> list[Split]:
    """
    Find a trailing sustained block before short reps.

    This merges adjacent manual laps when they are continuous and have nearly
    identical pace, which handles a 12-minute threshold block split into two
    lap-button segments.
    """
    before = [
        split
        for split in meaningful
        if split.index < first_rep_index
        and split.duration_s >= 90
        and split.distance_km >= 0.40
        and split.pace_s_per_km is not None
    ]

    if not before:
        return []

    selected = [before[-1]]

    for split in reversed(before[:-1]):
        current_pace = mean(
            item.pace_s_per_km
            for item in selected
            if item.pace_s_per_km is not None
        )
        split_pace = split.pace_s_per_km

        if split_pace is None:
            break

        pace_difference = abs(split_pace - current_pace) / current_pace
        adjacent = selected[0].index - split.index <= 2

        if adjacent and pace_difference <= 0.08:
            selected.insert(0, split)
        else:
            break

    total_duration = sum(split.duration_s for split in selected)

    if total_duration < 360:
        return []

    # Distinguish threshold from the warm-up immediately before it.
    preceding = [
        split
        for split in before
        if split.index < selected[0].index
    ]

    if preceding:
        threshold_pace = (
            sum(split.duration_s for split in selected)
            / sum(split.distance_km for split in selected)
        )
        preceding_pace = preceding[-1].pace_s_per_km

        if (
            preceding_pace is not None
            and threshold_pace >= preceding_pace * 0.93
        ):
            return []

    return selected


def _estimate_recovery_duration(
    reps: list[Split],
    meaningful: list[Split],
    boundaries: list[Split],
) -> float | None:
    recorded_recoveries = []

    for previous, following in zip(reps, reps[1:]):
        between = [
            split
            for split in meaningful
            if previous.index < split.index < following.index
            and split not in reps
        ]

        for split in between:
            if split.duration_s <= 180 and split.distance_km <= 0.40:
                recorded_recoveries.append(split.duration_s)

    if recorded_recoveries:
        return round(mean(recorded_recoveries), 1)

    boundary_gaps = 0

    for previous, following in zip(reps, reps[1:]):
        if any(
            previous.index < split.index < following.index
            for split in boundaries
        ):
            boundary_gaps += 1

    if boundary_gaps >= max(len(reps) - 2, 1):
        return None

    return None


def reconstruct_csv_phases(
    raw_splits: str | None,
    easy_pace_s_per_km: float | None = None,
) -> WorkoutPhaseResult:
    splits = list(parse_splits(raw_splits))

    if not splits:
        return WorkoutPhaseResult(
            phases=(),
            source="runalyze_csv",
            confidence=0.0,
            summary="No decodable Runalyze split data.",
            reasons=(),
            limitations=("No split data was available.",),
        )

    boundaries = [
        split for split in splits if is_boundary_fragment(split)
    ]
    meaningful = [
        split for split in splits if not is_boundary_fragment(split)
    ]

    easy_cutoff = (
        easy_pace_s_per_km * WORK_PACE_RATIO
        if easy_pace_s_per_km is not None
        and easy_pace_s_per_km > 0
        else None
    )

    if easy_cutoff is not None:
        work_candidates = [
            split
            for split in meaningful
            if split.pace_s_per_km is not None
            and split.pace_s_per_km < easy_cutoff
        ]
        easy_like = [
            split
            for split in meaningful
            if split not in work_candidates
        ]
    else:
        work_candidates = meaningful
        easy_like = []

    float_pattern = _find_alternating_float_pattern(meaningful)
    short_reps = _find_repeated_short_family(work_candidates)
    phases: list[WorkoutPhase] = []
    reasons = []
    limitations = []

    if float_pattern:
        work_splits = list(float_pattern["work"])
        float_splits = list(float_pattern["floats"])
        first_pattern_index = min(
            split.index for split in work_splits + float_splits
        )
        last_pattern_index = max(
            split.index for split in work_splits + float_splits
        )

        warmup_candidates = [
            split
            for split in meaningful
            if split.index < first_pattern_index
        ]
        cooldown_candidates = [
            split
            for split in meaningful
            if split.index > last_pattern_index
        ]

        if warmup_candidates:
            phases.append(
                _aggregate_phase(
                    phase_type="warmup",
                    label="Warm-up",
                    source="runalyze_csv",
                    confidence=0.78,
                    splits=warmup_candidates,
                    rep_count=1,
                )
            )

        average_float_duration = mean(
            split.duration_s for split in float_splits
        )

        phases.append(
            _aggregate_phase(
                phase_type="threshold",
                label="Alternating threshold work reps",
                source="runalyze_csv",
                confidence=0.94,
                splits=work_splits,
                rep_count=len(work_splits),
                recovery_duration_s=average_float_duration,
                metadata={
                    "workout_archetype": "threshold_with_float",
                    "float_rep_count": len(float_splits),
                    "average_float_distance_km": round(
                        mean(split.distance_km for split in float_splits),
                        3,
                    ),
                    "average_float_pace_s_per_km": round(
                        float_pattern["float_pace_s_per_km"],
                        1,
                    ),
                    "pace_gap_percent": round(
                        float_pattern["pace_gap"] * 100,
                        1,
                    ),
                },
            )
        )

        phases.append(
            _aggregate_phase(
                phase_type="recovery",
                label="Active float recoveries",
                source="runalyze_csv",
                confidence=0.94,
                splits=float_splits,
                rep_count=len(float_splits),
                metadata={
                    "recovery_style": "float",
                    "workout_archetype": "threshold_with_float",
                },
            )
        )

        if cooldown_candidates:
            phases.append(
                _aggregate_phase(
                    phase_type="cooldown",
                    label="Cool-down",
                    source="runalyze_csv",
                    confidence=0.70,
                    splits=cooldown_candidates,
                    rep_count=1,
                )
            )

        distance_m = round(
            float_pattern["average_distance_km"] * 1000 / 25
        ) * 25
        summary = (
            f"{len(work_splits)} x {distance_m} m threshold "
            f"with {len(float_splits)} x {distance_m} m float"
        )

        reasons.extend(
            [
                "Recognised an alternating equal-distance work/float pattern.",
                f"Work laps were {float_pattern['pace_gap'] * 100:.0f}% "
                "faster than float laps.",
                "Float laps were retained as active recovery rather than "
                "misclassified as additional work reps.",
            ]
        )

        return WorkoutPhaseResult(
            phases=tuple(phases),
            source="runalyze_csv",
            confidence=0.94,
            summary=summary,
            reasons=tuple(reasons),
            limitations=(
                "CSV reconstruction infers work versus float from the "
                "alternating pace pattern; FIT workout steps will take "
                "priority when available.",
            ),
        )

    if short_reps:
        first_rep = min(split.index for split in short_reps)
        last_rep = max(split.index for split in short_reps)

        threshold_splits = _find_threshold_before_reps(
            work_candidates,
            first_rep,
        )

        warmup_candidates = [
            split
            for split in meaningful
            if split.index < first_rep
            and split not in threshold_splits
            and (
                easy_cutoff is None
                or split in easy_like
            )
        ]

        if threshold_splits:
            first_threshold = min(
                split.index for split in threshold_splits
            )
            warmup_candidates = [
                split
                for split in meaningful
                if split.index < first_threshold
                and (
                    easy_cutoff is None
                    or split in easy_like
                )
            ]

        if warmup_candidates:
            phases.append(
                _aggregate_phase(
                    phase_type="warmup",
                    label="Warm-up",
                    source="runalyze_csv",
                    confidence=0.80,
                    splits=warmup_candidates,
                    rep_count=1,
                )
            )

        if threshold_splits:
            phases.append(
                _aggregate_phase(
                    phase_type="threshold",
                    label="Continuous threshold block",
                    source="runalyze_csv",
                    confidence=0.92,
                    splits=threshold_splits,
                    rep_count=1,
                    metadata={
                        "merged_manual_laps": len(threshold_splits),
                    },
                )
            )
            reasons.append(
                f"Merged {len(threshold_splits)} adjacent sustained lap(s) "
                "into one continuous threshold block."
            )

        recovery_duration = _estimate_recovery_duration(
            short_reps,
            meaningful,
            boundaries,
        )

        phases.append(
            _aggregate_phase(
                phase_type="short_intervals",
                label="Short interval repetitions",
                source="runalyze_csv",
                confidence=0.94,
                splits=short_reps,
                rep_count=len(short_reps),
                recovery_duration_s=recovery_duration,
                metadata={
                    "boundary_fragment_count": len(
                        [
                            split
                            for split in boundaries
                            if first_rep < split.index < last_rep
                        ]
                    ),
                    "recovery_recording": (
                        "recorded"
                        if recovery_duration is not None
                        else "stopped_watch_or_missing"
                    ),
                },
            )
        )
        reasons.append(
            f"Recognised {len(short_reps)} repeated short work reps."
        )

        cooldown_candidates = [
            split
            for split in meaningful
            if split.index > last_rep
            and split not in short_reps
            and (
                easy_cutoff is None
                or split in easy_like
            )
        ]

        if cooldown_candidates:
            phases.append(
                _aggregate_phase(
                    phase_type="cooldown",
                    label="Cool-down",
                    source="runalyze_csv",
                    confidence=0.70,
                    splits=cooldown_candidates,
                    rep_count=1,
                )
            )

        confidence = 0.92 if threshold_splits else 0.84

        if easy_cutoff is not None:
            reasons.append(
                "Excluded splits at or slower than "
                f"{easy_cutoff:.0f} sec/km from work-pace calculations "
                f"(12% faster than easy pace of "
                f"{easy_pace_s_per_km:.0f} sec/km)."
            )

        if recovery_duration is None:
            limitations.append(
                "Recovery duration was not fully recorded, probably because "
                "the watch was stopped between reps."
            )

        summary_parts = []

        for phase in phases:
            if phase.phase_type == "threshold":
                summary_parts.append(
                    f"{round(phase.duration_s / 60):.0f} min threshold"
                )
            elif phase.phase_type == "short_intervals":
                distance_m = round(
                    (phase.average_rep_distance_km or 0) * 1000
                )
                summary_parts.append(
                    f"{phase.rep_count} x {distance_m} m"
                )

        summary = " + ".join(summary_parts) or "Structured workout"

        return WorkoutPhaseResult(
            phases=tuple(phases),
            source="runalyze_csv",
            confidence=confidence,
            summary=summary,
            reasons=tuple(reasons),
            limitations=tuple(limitations),
        )

    # Fallback: detect one long sustained quality block.
    sustained = [
        split
        for split in work_candidates
        if split.duration_s >= 480
        and split.distance_km >= 1.20
        and split.pace_s_per_km is not None
    ]

    if sustained:
        selected = min(
            sustained,
            key=lambda split: split.pace_s_per_km,
        )
        phase = _aggregate_phase(
            phase_type="threshold",
            label="Sustained quality block",
            source="runalyze_csv",
            confidence=0.68,
            splits=[selected],
            rep_count=1,
        )
        return WorkoutPhaseResult(
            phases=(phase,),
            source="runalyze_csv",
            confidence=0.68,
            summary="One sustained quality block",
            reasons=("One long faster split was identified.",),
            limitations=(
                "CSV data could not prove the complete intended workout.",
            ),
        )

    return WorkoutPhaseResult(
        phases=(),
        source="runalyze_csv",
        confidence=0.30,
        summary="No reliable workout phases reconstructed.",
        reasons=(),
        limitations=(
            "The split sequence did not contain a clear sustained or repeated "
            "work pattern.",
        ),
    )


def reconstruct_workout_phases(
    raw_json_text: str | None,
    easy_pace_s_per_km: float | None = None,
) -> WorkoutPhaseResult:
    raw = _safe_json(raw_json_text)
    fit_phases = _stored_fit_phases(raw)

    if fit_phases:
        return WorkoutPhaseResult(
            phases=fit_phases,
            source="fit",
            confidence=min(
                mean(phase.confidence for phase in fit_phases),
                0.99,
            ),
            summary="FIT-derived structured workout",
            reasons=(
                "FIT-derived phases were available and took priority over CSV.",
            ),
            limitations=(),
        )

    raw_splits = raw.get("splits") or raw.get("splitsCustom")
    return reconstruct_csv_phases(
        raw_splits,
        easy_pace_s_per_km=easy_pace_s_per_km,
    )


def phases_to_dicts(
    result: WorkoutPhaseResult,
) -> list[dict[str, Any]]:
    return [
        {
            "phase_type": phase.phase_type,
            "label": phase.label,
            "source": phase.source,
            "confidence": phase.confidence,
            "distance_km": phase.distance_km,
            "duration_s": phase.duration_s,
            "pace_s_per_km": phase.pace_s_per_km,
            "rep_count": phase.rep_count,
            "average_rep_distance_km":
                phase.average_rep_distance_km,
            "recovery_duration_s": phase.recovery_duration_s,
            "split_indexes": list(phase.split_indexes),
            "metadata": phase.metadata,
        }
        for phase in result.phases
    ]
