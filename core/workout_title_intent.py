
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
from statistics import mean
from typing import Any

from core.splits import is_boundary_fragment, parse_splits


@dataclass(frozen=True)
class IntentBlock:
    reps: int
    distance_km: float | None
    duration_s: float | None
    label: str


@dataclass(frozen=True)
class WorkoutTitleIntent:
    blocks: tuple[IntentBlock, ...]
    recovery_s: float | None
    confidence: float
    summary: str

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

    # Remove recovery phrase before block parsing.
    body = re.sub(
        r"\boff\s+\d+(?:\.\d+)?\s*(?:s|sec|secs|second|seconds|min|mins|minute|minutes)?\b",
        "",
        body,
    )

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
                    )
                )

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

    summary = " + ".join(block.label for block in blocks)
    if recovery_s is not None:
        summary += f" · {int(round(recovery_s))} sec recovery"

    return WorkoutTitleIntent(
        blocks=tuple(blocks),
        recovery_s=recovery_s,
        confidence=confidence,
        summary=summary,
    )


def _phase_type(distance_km: float | None, duration_s: float | None) -> tuple[str, str]:
    if distance_km is not None:
        if distance_km >= 1.20:
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

        for split_index in range(cursor, min(cursor + 4, len(splits))):
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
        phase_type, label = _phase_type(block.distance_km, block.duration_s)
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
            "recovery_duration_s": intent.recovery_s,
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
                    "recovery_duration_s": intent.recovery_s,
                    "source": "activity_title+runalyze_splits",
                    "confidence": min(intent.confidence, 0.97),
                }
            )

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
        },
    }
