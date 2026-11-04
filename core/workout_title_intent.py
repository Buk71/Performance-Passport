
"""
Workout Title Intent v0.21.1.

Activity titles can contain the intended session more reliably than CSV split
inference. This module parses explicit session titles and reconciles them with
the actual Runalyze splits.

Example:
    2 x 800, 1 mile, 2 x 800, 1 mile, 2 x 800, off 60

becomes:
    2 × 800m + 1 × 1 mile + 2 × 800m + 1 × 1 mile + 2 × 800m
    recovery: 60 sec

The title supplies intent. Actual splits still supply performed pace/time.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
from statistics import mean, median
from typing import Any

from core.splits import is_boundary_fragment, parse_splits


@dataclass(frozen=True)
class IntentBlock:
    reps: int
    distance_km: float | None
    duration_s: float | None
    label: str
    recovery_s: float | None = None


@dataclass(frozen=True)
class WorkoutTitleIntent:
    blocks: tuple[IntentBlock, ...]
    recovery_s: float | None
    confidence: float
    summary: str
    structure_shape: str | None = None
    distance_sequence_km: tuple[float, ...] = ()

    @property
    def total_reps(self) -> int:
        return sum(block.reps for block in self.blocks)


def _normalise(title: str) -> str:
    value = (title or "").lower()
    value = value.replace("×", "x")
    value = value.replace("–", "-")
    value = value.replace("—", "-")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _distance_km(value: float, unit: str | None) -> float | None:
    unit = (unit or "").strip().lower()

    if unit in {"mile", "miles", "mi"}:
        return value * 1.609344
    if unit in {"km", "k"}:
        return value
    if unit in {"m", "metre", "metres", "meter", "meters"}:
        return value / 1000.0

    # Titles commonly say "8 x 500" or "2 x 800".
    if value >= 100:
        return value / 1000.0

    return None


def _block_label(reps: int, distance_km: float | None, duration_s: float | None) -> str:
    if distance_km is not None:
        if abs(distance_km - 1.609344) <= 0.06:
            return f"{reps} × 1 mile"
        if distance_km >= 1.0:
            return f"{reps} × {distance_km:.2f} km"
        return f"{reps} × {int(round(distance_km * 1000 / 25) * 25)}m"

    if duration_s is not None:
        minutes = duration_s / 60.0
        if abs(minutes - round(minutes)) < 0.05:
            return f"{reps} × {int(round(minutes))} min"
        return f"{reps} × {duration_s:.0f} sec"

    return f"{reps} reps"



def _sequence_shape(distances_km: list[float]) -> str | None:
    """Recognise ordered ladder/pyramid shapes before distance-family grouping."""
    if len(distances_km) < 4:
        return None

    # Ignore tiny rounding noise while preserving genuine changes in rep length.
    tolerance = 0.08

    def rising(a: float, b: float) -> bool:
        return b > a + tolerance

    def falling(a: float, b: float) -> bool:
        return b < a - tolerance

    if all(rising(a, b) for a, b in zip(distances_km, distances_km[1:])):
        return "ascending_ladder"

    if all(falling(a, b) for a, b in zip(distances_km, distances_km[1:])):
        return "descending_ladder"

    peak = max(range(len(distances_km)), key=distances_km.__getitem__)
    if peak == 0 or peak == len(distances_km) - 1:
        return None

    left = distances_km[: peak + 1]
    right = distances_km[peak:]

    if not all(rising(a, b) for a, b in zip(left, left[1:])):
        return None
    if not all(falling(a, b) for a, b in zip(right, right[1:])):
        return None

    # A pyramid should broadly mirror around its peak. This keeps unrelated
    # mixed-distance titles from being over-labelled.
    left_without_peak = left[:-1]
    right_without_peak = right[1:]
    mirrored_pairs = min(len(left_without_peak), len(right_without_peak))
    if mirrored_pairs < 2:
        return None

    matches = 0
    for a, b in zip(
        reversed(left_without_peak[-mirrored_pairs:]),
        right_without_peak[:mirrored_pairs],
    ):
        if abs(a - b) <= max(a * 0.15, 0.08):
            matches += 1

    if matches / mirrored_pairs < 0.75:
        return None

    return "pyramid"


def _extract_ordered_distance_sequence(body: str) -> tuple[list[IntentBlock], str | None]:
    """Parse titles such as '400 800 1200 1600 2000 1600 1200 800 400 off 60'."""
    # Recovery numbers must never become work distances.
    work_text = re.split(r"\boff\b|\brecovery\b|\brecoveries\b", body, maxsplit=1)[0]

    values = []
    for match in re.finditer(
        r"(?<![\dx])\b(?P<value>\d{3,4}(?:\.\d+)?)\s*(?P<unit>m|metres?|meters?|km|k)?\b",
        work_text,
    ):
        value = float(match.group("value"))
        unit = match.group("unit")
        distance = _distance_km(value, unit or ("m" if value >= 100 else None))
        if distance is None:
            continue
        if 0.20 <= distance <= 5.0:
            values.append(distance)

    shape = _sequence_shape(values)
    if shape is None:
        return [], None

    blocks = [
        IntentBlock(
            reps=1,
            distance_km=distance,
            duration_s=None,
            label=_block_label(1, distance, None),
        )
        for distance in values
    ]
    return blocks, shape


def _sequence_summary(
    distances_km: tuple[float, ...],
    shape: str | None,
    recovery_s: float | None,
) -> str | None:
    if not distances_km or shape is None:
        return None

    values_m = [int(round(distance * 1000 / 25) * 25) for distance in distances_km]
    prefix = {
        "pyramid": "Pyramid",
        "ascending_ladder": "Ascending ladder",
        "descending_ladder": "Descending ladder",
    }.get(shape, "Mixed intervals")

    summary = f"{prefix}: " + " → ".join(str(value) for value in values_m) + "m"
    if recovery_s is not None:
        summary += f" · {int(round(recovery_s))} sec recovery"
    return summary


def parse_workout_title(title: str) -> WorkoutTitleIntent | None:
    text = _normalise(title)

    if not text:
        return None

    # Strong negative intent: these are whole continuous sessions, not rep
    # workouts, unless the title also explicitly contains workout structure.
    structured_tokens = (" x ", "reps", "interval", "session", "threshold", "tempo", "fartlek")
    continuous_tokens = ("long run", "slr", "recovery", "easy run", "easy ", "steady run")

    has_structure_hint = any(token in text for token in structured_tokens)

    if any(token in text for token in continuous_tokens) and not has_structure_hint:
        return None

    body = text
    if ":" in text:
        prefix, suffix = text.split(":", 1)
        # Most titles use the text before a colon as a label (for example,
        # "Blizzard session:").  Some real activity titles put genuine work
        # structure there instead (for example, "6 x 100m strides:").  Keep
        # the full title whenever the prefix already contains a rep pattern.
        prefix_has_structure = bool(
            re.search(r"\b\d+\s*x\s*\d+", prefix)
        )
        body = text if prefix_has_structure else suffix

    # Recovery: "off 60", "off 60 sec", "60s recovery", "off 200m".
    recovery_s = None
    recovery_match = re.search(
        r"\boff\s+(\d+(?:\.\d+)?)\s*(s|sec|secs|second|seconds|min|mins|minute|minutes)?\b",
        body,
    )
    if recovery_match:
        value = float(recovery_match.group(1))
        unit = (recovery_match.group(2) or "").lower()
        if unit.startswith("min"):
            recovery_s = value * 60.0
        else:
            # Unitless "off 60" is overwhelmingly seconds in session titles.
            recovery_s = value

    if recovery_s is None:
        recovery_match = re.search(
            r"\b(\d+(?:\.\d+)?)\s*(s|sec|secs|second|seconds|min|mins|minute|minutes)\s+(?:recovery|recoveries)\b",
            body,
        )
        if recovery_match:
            value = float(recovery_match.group(1))
            unit = recovery_match.group(2).lower()
            recovery_s = value * 60.0 if unit.startswith("min") else value

    # Split on punctuation and linking words while keeping sequence order.
    parts = [
        part.strip(" .-")
        for part in re.split(r"\s*(?:,|\+|;|\band\b|\bthen\b)\s*", body)
        if part.strip(" .-")
    ]

    blocks: list[IntentBlock] = []

    repeated_distance = re.compile(
        r"(?P<reps>\d+)\s*x\s*(?P<value>\d+(?:\.\d+)?)\s*"
        r"(?P<unit>mile|miles|mi|km|k|m|metre|metres|meter|meters)?\b"
    )
    repeated_time = re.compile(
        r"(?P<reps>\d+)\s*x\s*(?P<value>\d+(?:\.\d+)?)\s*"
        r"(?P<unit>min|mins|minute|minutes|sec|secs|second|seconds)\b"
    )
    single_distance = re.compile(
        r"^(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>mile|miles|mi|km|k)\b"
    )

    for part in parts:
        block_recovery = None
        local_recovery = re.search(
            r"\boff\s+(\d+(?:\.\d+)?)\s*"
            r"(s|sec|secs|second|seconds|min|mins|minute|minutes)?\b",
            part,
        )
        if local_recovery:
            recovery_value = float(local_recovery.group(1))
            recovery_unit = (local_recovery.group(2) or "").lower()
            block_recovery = (
                recovery_value * 60.0
                if recovery_unit.startswith("min")
                else recovery_value
            )

        time_match = repeated_time.search(part)
        if time_match:
            reps = int(time_match.group("reps"))
            value = float(time_match.group("value"))
            unit = time_match.group("unit").lower()
            duration_s = value * 60.0 if unit.startswith("min") else value
            blocks.append(
                IntentBlock(
                    reps=reps,
                    distance_km=None,
                    duration_s=duration_s,
                    label=_block_label(reps, None, duration_s),
                    recovery_s=block_recovery,
                )
            )
            continue

        distance_match = repeated_distance.search(part)
        if distance_match:
            reps = int(distance_match.group("reps"))
            value = float(distance_match.group("value"))
            distance = _distance_km(value, distance_match.group("unit"))
            if distance is not None and 0 < reps <= 40:
                blocks.append(
                    IntentBlock(
                        reps=reps,
                        distance_km=distance,
                        duration_s=None,
                        label=_block_label(reps, distance, None),
                        recovery_s=block_recovery,
                    )
                )
            continue

        single_match = single_distance.search(part)
        if single_match:
            distance = _distance_km(
                float(single_match.group("value")),
                single_match.group("unit"),
            )
            if distance is not None:
                blocks.append(
                    IntentBlock(
                        reps=1,
                        distance_km=distance,
                        duration_s=None,
                        label=_block_label(1, distance, None),
                        recovery_s=block_recovery,
                    )
                )

    structure_shape = None

    if not blocks:
        sequence_blocks, structure_shape = _extract_ordered_distance_sequence(body)
        if sequence_blocks:
            blocks.extend(sequence_blocks)

    if not blocks:
        return None

    total_reps = sum(block.reps for block in blocks)

    # One isolated distance mention is too weak to be workout intent.
    if total_reps < 2 and not has_structure_hint:
        return None

    confidence = 0.84
    if total_reps >= 4:
        confidence += 0.05
    if recovery_s is not None:
        confidence += 0.04
    if "session" in text or "interval" in text or "reps" in text:
        confidence += 0.03

    confidence = min(confidence, 0.97)

    distance_sequence_km = tuple(
        block.distance_km
        for block in blocks
        for _ in range(block.reps)
        if block.distance_km is not None
    )

    summary = _sequence_summary(
        distance_sequence_km,
        structure_shape,
        recovery_s,
    )
    if summary is None:
        summary = " + ".join(block.label for block in blocks)
        if recovery_s is not None:
            summary += f" · {int(round(recovery_s))} sec recovery"

    return WorkoutTitleIntent(
        blocks=tuple(blocks),
        recovery_s=recovery_s,
        confidence=confidence,
        summary=summary,
        structure_shape=structure_shape,
        distance_sequence_km=distance_sequence_km,
    )


def _phase_type(
    distance_km: float | None,
    duration_s: float | None,
    recovery_s: float | None = None,
) -> tuple[str, str]:
    if distance_km is not None:
        if distance_km >= 1.20:
            # Fast 1,200 m repetitions with substantial recoveries are long
            # intervals, not the sustainable threshold pace an athlete could
            # hold continuously. Longer mile blocks, or genuinely short
            # recoveries, retain their established threshold interpretation.
            if distance_km < 1.45 and recovery_s is not None and recovery_s > 60:
                return "long_intervals", "Long intervals"
            return "threshold", "Long threshold repetitions"
        if distance_km >= 0.65:
            return "long_intervals", "Long intervals"
        if distance_km >= 0.20:
            return "short_intervals", "Short intervals"

    if duration_s is not None:
        if duration_s >= 480:
            return "threshold", "Threshold repetitions"
        if duration_s >= 120:
            return "long_intervals", "Long intervals"
        return "short_intervals", "Short intervals"

    return "unknown", "Workout block"


def _match_expected_distances(intent: WorkoutTitleIntent, raw_splits: str | None):
    splits = [
        split
        for split in parse_splits(raw_splits)
        if not is_boundary_fragment(split)
    ]

    expected: list[tuple[int, IntentBlock]] = []
    for block_index, block in enumerate(intent.blocks):
        if block.distance_km is None:
            continue
        for _ in range(block.reps):
            expected.append((block_index, block))

    if not expected or not splits:
        return {}, 0.0

    matches: dict[int, list] = {}
    cursor = 0
    matched = 0

    for block_index, block in expected:
        target = float(block.distance_km)
        found = None

        # Warm-up strides and drills can legitimately precede the first
        # titled work block. Search the remaining sequence in order rather
        # than silently missing a genuine workout after four such splits.
        for split_index in range(cursor, len(splits)):
            split = splits[split_index]
            tolerance = max(target * 0.14, 0.08)
            if abs(split.distance_km - target) <= tolerance:
                found = (split_index, split)
                break

        if found is None:
            continue

        split_index, split = found
        matches.setdefault(block_index, []).append(split)
        cursor = split_index + 1
        matched += 1

    return matches, matched / len(expected)


def build_title_intent_evidence(
    title: str,
    raw_json_text: str | None,
) -> dict[str, Any] | None:
    intent = parse_workout_title(title)

    if intent is None:
        return None

    try:
        raw = json.loads(raw_json_text or "{}")
    except Exception:
        raw = {}

    raw_splits = raw.get("splits") or raw.get("splitsCustom")
    matches, match_ratio = _match_expected_distances(intent, raw_splits)

    phases = []
    components = []

    for index, block in enumerate(intent.blocks):
        block_recovery = (
            block.recovery_s
            if block.recovery_s is not None
            else intent.recovery_s
        )
        phase_type, label = _phase_type(
            block.distance_km,
            block.duration_s,
            block_recovery,
        )
        matched_splits = matches.get(index, [])

        if matched_splits:
            distance = sum(split.distance_km for split in matched_splits)
            duration = sum(split.duration_s for split in matched_splits)
            rep_count = len(matched_splits)
            avg_distance = distance / rep_count if rep_count else block.distance_km
            pace = duration / distance if distance > 0 else None
            split_indexes = [split.index for split in matched_splits]
        else:
            distance = (block.distance_km or 0.0) * block.reps
            duration = int(round((block.duration_s or 0.0) * block.reps))
            rep_count = block.reps
            avg_distance = block.distance_km
            pace = None
            split_indexes = []

        phase = {
            "phase_type": phase_type,
            "label": block.label,
            "source": "activity_title+runalyze_splits",
            "confidence": min(intent.confidence, 0.97),
            "distance_km": round(distance, 4),
            "duration_s": int(duration),
            "pace_s_per_km": pace,
            "rep_count": rep_count,
            "average_rep_distance_km": avg_distance,
            "recovery_duration_s": block_recovery,
            "split_indexes": split_indexes,
            "metadata": {
                "title_intent": True,
                "expected_reps": block.reps,
            },
        }
        phases.append(phase)

        if phase_type in {"threshold", "long_intervals", "short_intervals"}:
            components.append(
                {
                    "component_type": phase_type,
                    "label": label,
                    "rep_count": rep_count,
                    "average_rep_distance_km": avg_distance,
                    "total_work_distance_km": round(distance, 4),
                    "average_pace_s_per_km": pace,
                    "recovery_duration_s": block_recovery,
                    "source": "activity_title+runalyze_splits",
                    "confidence": min(intent.confidence, 0.97),
                }
            )

    if intent.structure_shape in {"pyramid", "ascending_ladder", "descending_ladder"}:
        # Preserve each ordered phase above for audit/display, but roll the
        # performed work into physiological families for prediction. This lets
        # total quality volume contribute without pretending a pyramid is
        # merely "2 x 400".
        grouped: dict[str, list[dict[str, Any]]] = {}
        for phase in phases:
            if (
                phase["phase_type"] in {"threshold", "long_intervals", "short_intervals"}
                and phase.get("pace_s_per_km") is not None
                and phase.get("distance_km", 0) > 0
            ):
                grouped.setdefault(phase["phase_type"], []).append(phase)

        rolled_components = []
        labels = {
            "threshold": "Long aerobic / threshold reps",
            "long_intervals": "Long intervals",
            "short_intervals": "Short intervals",
        }
        for phase_type, group in grouped.items():
            distance = sum(float(item["distance_km"]) for item in group)
            duration = sum(float(item["duration_s"]) for item in group)
            reps = sum(int(item.get("rep_count") or 1) for item in group)
            rolled_components.append(
                {
                    "component_type": phase_type,
                    "label": labels[phase_type],
                    "rep_count": reps,
                    "average_rep_distance_km": round(distance / reps, 4),
                    "total_work_distance_km": round(distance, 4),
                    "average_pace_s_per_km": round(duration / distance, 1),
                    "recovery_duration_s": intent.recovery_s,
                    "source": "activity_title+ordered_splits",
                    "confidence": min(intent.confidence, 0.97),
                }
            )
        if rolled_components:
            components = rolled_components

    confidence = intent.confidence

    if match_ratio >= 0.95:
        confidence = min(confidence + 0.02, 0.98)
    elif match_ratio < 0.60:
        confidence = max(confidence - 0.15, 0.60)

    return {
        "intent": intent,
        "display_description": intent.summary,
        "components": components,
        "metadata": {
            "source": "activity_title+runalyze_splits",
            "confidence": round(confidence, 4),
            "summary": intent.summary,
            "reasons": [
                "Explicit workout structure was found in the activity title.",
                f"{match_ratio:.0%} of title-derived distance reps matched Runalyze splits.",
                "The title supplies intended structure; splits supply performed pace and duration.",
            ],
            "limitations": (
                []
                if match_ratio >= 0.80
                else ["Some title-derived reps could not be matched to exported splits."]
            ),
            "phases": phases,
            "title_intent": True,
            "match_ratio": round(match_ratio, 4),
            "recovery_s": intent.recovery_s,
            "structure_shape": intent.structure_shape,
            "distance_sequence_m": [
                int(round(distance * 1000 / 25) * 25)
                for distance in intent.distance_sequence_km
            ],
            "total_reps": intent.total_reps,
            "total_work_distance_km": round(
                sum(intent.distance_sequence_km),
                4,
            ),
        },
    }


def _safe_fit_splits(raw_json_text: str | None) -> list[dict[str, Any]]:
    """Return ordered Garmin/FIT lap evidence from one stored activity payload."""
    try:
        raw = json.loads(raw_json_text or "{}")
    except Exception:
        return []

    values = raw.get("fit_splits")
    if not isinstance(values, list):
        return []

    result = []
    for value in values:
        if not isinstance(value, dict):
            continue
        try:
            distance_km = float(value.get("distance_km") or 0.0)
            duration_s = float(value.get("duration_s") or 0.0)
            elapsed_s = float(value.get("elapsed_time_s") or duration_s or 0.0)
        except (TypeError, ValueError):
            continue
        result.append({
            "index": int(value.get("index") or len(result) + 1),
            "distance_km": distance_km,
            "duration_s": duration_s,
            "elapsed_time_s": elapsed_s,
            "lap_trigger": str(value.get("lap_trigger") or ""),
        })
    return result


def _is_stopped_recovery_lap(lap: dict[str, Any]) -> bool:
    """Identify tiny lap-button fragments whose elapsed time is mostly stopped recovery."""
    distance_km = float(lap.get("distance_km") or 0.0)
    duration_s = float(lap.get("duration_s") or 0.0)
    elapsed_s = float(lap.get("elapsed_time_s") or duration_s or 0.0)
    stopped_s = max(elapsed_s - duration_s, 0.0)
    return (
        distance_km <= 0.035
        and elapsed_s >= 35.0
        and stopped_s >= 25.0
        and stopped_s >= elapsed_s * 0.55
    )


def _quantise_rep_distance(distance_km: float) -> float:
    """Snap GPS/FIT rep distance to a plausible nominal 100 m boundary."""
    if not 0.20 <= distance_km <= 3.20:
        return distance_km
    nominal = round(distance_km * 10.0) / 10.0
    tolerance = max(0.045, nominal * 0.055)
    return nominal if abs(distance_km - nominal) <= tolerance else distance_km


def _fit_work_groups(raw_json_text: str | None) -> list[dict[str, Any]]:
    """
    Build substantial work blocks separated by stopped-recovery lap fragments.

    Garmin can auto-lap inside a manually controlled rep. Summing every
    contiguous substantial segment until the next stopped-recovery boundary
    naturally repairs cases such as 1609 m + 379 m = one intended 2000 m rep.
    """
    laps = _safe_fit_splits(raw_json_text)
    if not laps:
        return []

    groups: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    pending_recovery_s: float | None = None

    def flush() -> None:
        nonlocal current
        substantial = [
            lap for lap in current
            if float(lap.get("distance_km") or 0.0) >= 0.20
        ]
        if substantial:
            distance = sum(float(lap["distance_km"]) for lap in substantial)
            duration = sum(float(lap["duration_s"]) for lap in substantial)
            groups.append({
                "distance_km": distance,
                "duration_s": duration,
                "pace_s_per_km": duration / distance if distance > 0 else None,
                "split_indexes": [int(lap["index"]) for lap in substantial],
                "segment_count": len(substantial),
                "recovery_before_s": pending_recovery_s,
            })
        current = []

    for lap in laps:
        if _is_stopped_recovery_lap(lap):
            flush()
            pending_recovery_s = float(lap.get("elapsed_time_s") or 0.0)
            continue
        current.append(lap)
    flush()

    return groups


def infer_fit_workout_structure(raw_json_text: str | None) -> WorkoutTitleIntent | None:
    """
    Infer a ladder/pyramid from ordered FIT laps without using the activity title.

    This is deliberately conservative: a candidate needs at least four
    substantial work blocks, a recognised ordered shape, and stopped-recovery
    evidence between most neighbouring work blocks. Ordinary auto-lapped
    continuous runs therefore do not qualify.
    """
    groups = _fit_work_groups(raw_json_text)
    if len(groups) < 4:
        return None

    best = None
    # Search contiguous windows so warm-up/cool-down blocks cannot poison an
    # otherwise convincing structured sequence.
    for start in range(len(groups)):
        for end in range(start + 4, len(groups) + 1):
            window = groups[start:end]
            distances = [
                _quantise_rep_distance(float(item["distance_km"]))
                for item in window
            ]
            shape = _sequence_shape(distances)
            if shape is None:
                continue

            recoveries = [
                float(item["recovery_before_s"])
                for item in window[1:]
                if item.get("recovery_before_s") is not None
            ]
            expected = max(len(window) - 1, 1)
            coverage = len(recoveries) / expected
            if coverage < 0.70:
                continue

            mirror_bonus = 2.0 if shape == "pyramid" else 1.0
            score = len(window) * 10.0 + coverage * 5.0 + mirror_bonus
            if best is None or score > best["score"]:
                best = {
                    "window": window,
                    "distances": distances,
                    "shape": shape,
                    "recoveries": recoveries,
                    "coverage": coverage,
                    "score": score,
                }

    if best is None:
        return None

    distances = best["distances"]
    recovery_s = median(best["recoveries"]) if best["recoveries"] else None
    blocks = tuple(
        IntentBlock(
            reps=1,
            distance_km=distance,
            duration_s=None,
            label=_block_label(1, distance, None),
            recovery_s=recovery_s,
        )
        for distance in distances
    )
    confidence = min(0.90 + min(len(distances), 9) * 0.006 + best["coverage"] * 0.03, 0.98)
    sequence = tuple(distances)
    summary = _sequence_summary(sequence, best["shape"], recovery_s)

    return WorkoutTitleIntent(
        blocks=blocks,
        recovery_s=recovery_s,
        confidence=confidence,
        summary=summary or "Structured workout from ordered FIT laps",
        structure_shape=best["shape"],
        distance_sequence_km=sequence,
    )


def build_fit_structure_evidence(raw_json_text: str | None) -> dict[str, Any] | None:
    """Build provider-ready evidence from title-free ordered FIT structure."""
    intent = infer_fit_workout_structure(raw_json_text)
    if intent is None:
        return None

    groups = _fit_work_groups(raw_json_text)
    target = list(intent.distance_sequence_km)
    selected = None
    for start in range(len(groups)):
        window = groups[start:start + len(target)]
        if len(window) != len(target):
            continue
        quantised = [_quantise_rep_distance(float(item["distance_km"])) for item in window]
        if all(abs(a - b) <= max(b * 0.08, 0.06) for a, b in zip(quantised, target)):
            selected = window
            break
    if selected is None:
        return None

    phases = []
    grouped: dict[str, list[dict[str, Any]]] = {}
    for distance, group in zip(target, selected):
        phase_type, label = _phase_type(distance, None, intent.recovery_s)
        actual_distance = float(group["distance_km"])
        duration = float(group["duration_s"])
        pace = duration / actual_distance if actual_distance > 0 else None
        phase = {
            "phase_type": phase_type,
            "label": _block_label(1, distance, None),
            "source": "garmin_fit_ordered_laps",
            "confidence": intent.confidence,
            "distance_km": round(actual_distance, 4),
            "duration_s": int(round(duration)),
            "pace_s_per_km": pace,
            "rep_count": 1,
            "average_rep_distance_km": distance,
            "recovery_duration_s": intent.recovery_s,
            "split_indexes": list(group["split_indexes"]),
            "metadata": {
                "fit_ordered_structure": True,
                "segment_count": int(group["segment_count"]),
                "nominal_distance_km": distance,
            },
        }
        phases.append(phase)
        if phase_type in {"threshold", "long_intervals", "short_intervals"} and pace is not None:
            grouped.setdefault(phase_type, []).append(phase)

    labels = {
        "threshold": "Long aerobic / threshold reps",
        "long_intervals": "Long intervals",
        "short_intervals": "Short intervals",
    }
    components = []
    for phase_type, values in grouped.items():
        distance = sum(float(item["distance_km"]) for item in values)
        duration = sum(float(item["duration_s"]) for item in values)
        reps = len(values)
        components.append({
            "component_type": phase_type,
            "label": labels[phase_type],
            "rep_count": reps,
            "average_rep_distance_km": round(distance / reps, 4),
            "total_work_distance_km": round(distance, 4),
            "average_pace_s_per_km": round(duration / distance, 1),
            "recovery_duration_s": intent.recovery_s,
            "source": "garmin_fit_ordered_laps",
            "confidence": intent.confidence,
        })

    return {
        "intent": intent,
        "display_description": intent.summary,
        "components": components,
        "metadata": {
            "source": "garmin_fit_ordered_laps",
            "confidence": round(intent.confidence, 4),
            "summary": intent.summary,
            "reasons": [
                "Ordered FIT laps form a recognised ladder/pyramid shape.",
                "Stopped-recovery lap fragments separate most neighbouring work reps.",
                "Contiguous auto-lap segments are merged until the next recovery boundary.",
            ],
            "limitations": [],
            "phases": phases,
            "title_intent": False,
            "fit_ordered_structure": True,
            "match_ratio": 1.0,
            "recovery_s": intent.recovery_s,
            "structure_shape": intent.structure_shape,
            "distance_sequence_m": [int(round(distance * 1000)) for distance in intent.distance_sequence_km],
            "total_reps": intent.total_reps,
            "total_work_distance_km": round(sum(float(item["distance_km"]) for item in selected), 4),
            "nominal_work_distance_km": round(sum(intent.distance_sequence_km), 4),
        },
    }


def build_workout_structure_evidence(
    title: str,
    raw_json_text: str | None,
) -> dict[str, Any] | None:
    """Prefer explicit title intent, then fall back to conservative FIT structure."""
    title_evidence = build_title_intent_evidence(title, raw_json_text)
    if title_evidence is not None:
        return title_evidence
    return build_fit_structure_evidence(raw_json_text)
