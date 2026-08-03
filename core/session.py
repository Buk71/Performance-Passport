from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SessionType(str, Enum):
    WALK = "walk"
    RACE = "race"
    CONTINUOUS_RUN = "continuous_run"
    STRUCTURED_WORKOUT = "structured_workout"
    CROSS_TRAINING = "cross_training"
    UNKNOWN = "unknown"


class SessionPurpose(str, Enum):
    EASY = "easy"
    RECOVERY = "recovery"
    STEADY = "steady"
    LONG = "long"
    PROGRESSION = "progression"
    CONTINUOUS_TEMPO = "continuous_tempo"
    THRESHOLD = "threshold"
    VO2 = "vo2"
    HILLS = "hills"
    FARTLEK = "fartlek"
    RACE = "race"
    GENERAL = "general"
    UNKNOWN = "unknown"


class BlockType(str, Enum):
    WARMUP = "warmup"
    WORK = "work"
    RECOVERY = "recovery"
    COOLDOWN = "cooldown"
    CONTINUOUS = "continuous"
    BOUNDARY = "boundary"
    UNKNOWN = "unknown"


class CoachRoute(str, Enum):
    WORKOUT = "workout"
    RACE = "race"
    THRESHOLD = "threshold"
    EASY = "easy"
    LONG_RUN = "long_run"
    ENVIRONMENT = "environment"
    RECOVERY = "recovery"
    PROGRESS = "progress"
    GOAL = "goal"


@dataclass(frozen=True)
class SessionBlock:
    block_type: BlockType
    start_index: int | None = None
    end_index: int | None = None
    distance_km: float | None = None
    duration_s: float | None = None
    pace_s_per_km: float | None = None
    avg_hr: float | None = None
    max_hr: float | None = None
    confidence: float = 0.0
    source: str = "activity_summary"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SessionEvidence:
    key: str
    description: str
    strength: float
    supports: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Session:
    activity_id: int
    athlete_id: int
    activity_date: str | None
    title: str
    sport_id: str | None
    session_type: SessionType
    purpose: SessionPurpose
    confidence: float
    distance_km: float | None = None
    moving_time_s: float | None = None
    elapsed_time_s: float | None = None
    avg_hr: float | None = None
    max_hr: float | None = None
    elevation_up_m: float | None = None
    temperature_c: float | None = None
    humidity: float | None = None
    wind_speed: float | None = None
    route_name: str | None = None
    blocks: tuple[SessionBlock, ...] = ()
    evidence: tuple[SessionEvidence, ...] = ()
    suitable_coaches: tuple[CoachRoute, ...] = ()
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def moving_ratio(self) -> float | None:
        if not self.moving_time_s or not self.elapsed_time_s:
            return None
        return max(0.0, min(self.moving_time_s / self.elapsed_time_s, 1.0))
