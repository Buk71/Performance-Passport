"""
Performance Passport Coaching Engine

Reusable deterministic coaching calculations.

No database logic.
No Streamlit logic.
No UI-specific calculations.
"""

from __future__ import annotations

import datetime
import math
from dataclasses import dataclass

from core.activity_reliability import has_reliable_distance_and_pace
from core.race_detection import score_athlete_relative_race_effort
from core.database import get_athlete_sport_roles


METRES_PER_MILE = 1609.344


@dataclass(frozen=True)
class RunProfile:
    title: str | None
    sport_id: str | int | None
    distance_km: float | None
    moving_time_seconds: float | None
    avg_hr: float | None = None
    run_max_hr: float | None = None
    activity_date: str | None = None
    elevation_m: float | None = None
    temperature_c: float | None = None
    humidity: float | None = None

    lt1_hr: float | None = None
    lt2_hr: float | None = None
    athlete_max_hr: float | None = None
    athlete_id: int | None = None


@dataclass(frozen=True)
class AthleteBaseline:
    run_type: str
    baseline_name: str
    run_count: int
    avg_distance_km: float
    avg_pace_seconds_per_km: float
    avg_hr: float
    avg_elevation_m: float


@dataclass(frozen=True)
class ActivityEvidence:
    classification: str
    easy_baseline_candidate: bool
    evidence: list[str]


@dataclass(frozen=True)
class TerrainAssessment:
    """
    Historical terrain assessment derived from total ascent and distance.

    This is deliberately separate from pace adjustment because total ascent
    alone is not sufficient to calculate a scientifically robust
    grade-adjusted pace.

    Effort distance follows the recognised km-effort convention:

        effort distance = distance in km + ascent in metres / 100
    """

    elevation_m: float | None
    climbing_density_m_per_km: float | None
    effort_distance_km: float | None
    terrain_rating: str
    method: str
    confidence: str


@dataclass(frozen=True)
class EnvironmentalAdjustment:
    """
    Environmental context and estimated pace penalties for a run.

    All penalties are stored in seconds per kilometre.

    Temperature and humidity currently contribute to equivalent pace.
    Elevation remains zero because historical total ascent is assessed
    separately through TerrainAssessment rather than being presented as a
    precise grade-adjusted pace.
    """

    temperature_penalty_seconds_per_km: float
    humidity_penalty_seconds_per_km: float
    elevation_penalty_seconds_per_km: float
    wind_penalty_seconds_per_km: float
    surface_penalty_seconds_per_km: float

    total_penalty_seconds_per_km: float

    temperature_c: float | None
    humidity: float | None
    dew_point_c: float | None

    heat_stress: str
    confidence: str


@dataclass(frozen=True)
class EquivalentPerformance:
    actual_pace_seconds_per_km: float
    equivalent_pace_seconds_per_km: float
    adjustment: EnvironmentalAdjustment
    terrain: TerrainAssessment

    @property
    def temperature_c(self) -> float | None:
        return self.adjustment.temperature_c

    @property
    def humidity(self) -> float | None:
        return self.adjustment.humidity

    @property
    def dew_point_c(self) -> float | None:
        return self.adjustment.dew_point_c

    @property
    def heat_stress(self) -> str:
        return self.adjustment.heat_stress

    @property
    def temperature_adjustment_seconds_per_km(self) -> float:
        return self.adjustment.temperature_penalty_seconds_per_km


@dataclass(frozen=True)
class BestEasyRun:
    run: RunProfile
    efficiency_score: float
    equivalent_performance: EquivalentPerformance
    coach_review: str


def metres_to_miles(metres: float) -> float:
    return metres / METRES_PER_MILE


def metres_to_km(metres: float) -> float:
    return metres / 1000


def seconds_to_pace(seconds_per_unit: float) -> str:
    minutes = int(seconds_per_unit // 60)
    seconds = int(round(seconds_per_unit % 60))

    if seconds == 60:
        minutes += 1
        seconds = 0

    return f"{minutes}:{seconds:02d}"


def pace_seconds_per_km(
    distance_km: float | None,
    moving_time_seconds: float | None,
) -> float | None:
    if not distance_km or not moving_time_seconds:
        return None

    if distance_km <= 0 or moving_time_seconds <= 0:
        return None

    return moving_time_seconds / distance_km


def pace_per_mile(
    distance_metres: float,
    moving_time_seconds: float,
) -> str:
    miles = metres_to_miles(distance_metres)

    if miles <= 0:
        return "-"

    return seconds_to_pace(moving_time_seconds / miles)


def pace_per_km(
    distance_metres: float,
    moving_time_seconds: float,
) -> str:
    km = metres_to_km(distance_metres)

    if km <= 0:
        return "-"

    return seconds_to_pace(moving_time_seconds / km)


def parse_activity_date(
    activity_date: str | None,
) -> datetime.date | None:
    if not activity_date:
        return None

    try:
        return datetime.date.fromisoformat(activity_date[:10])
    except ValueError:
        return None


def temperature_adjustment_seconds_per_km(
    temperature_c: float | None,
) -> float:
    """
    Return a conservative first-pass heat adjustment in seconds per kilometre.

    This deliberately uses a transparent generic model. It can later be
    replaced with an athlete-specific model learned from historical data.
    """

    if temperature_c is None:
        return 0.0

    if temperature_c >= 30:
        return 18.0

    if temperature_c >= 27:
        return 14.0

    if temperature_c >= 24:
        return 10.0

    if temperature_c >= 21:
        return 6.0

    if temperature_c >= 18:
        return 3.0

    return 0.0


def humidity_adjustment_seconds_per_km(
    temperature_c: float | None,
    dew_point_c: float | None,
) -> float:
    """
    Return a conservative first-pass humidity penalty.

    Dew point is used instead of relative humidity alone because it better
    represents the amount of moisture in the air.

    Humidity only adds a pace penalty when conditions are warm enough for
    moisture to meaningfully reduce evaporative cooling.

    This remains a transparent generic model. It can later be replaced by
    an athlete-specific model learned from historical performance.
    """

    if temperature_c is None or dew_point_c is None:
        return 0.0

    if temperature_c < 18:
        return 0.0

    if dew_point_c < 14:
        return 0.0

    if dew_point_c < 16:
        return 1.0

    if dew_point_c < 18:
        return 2.0

    if dew_point_c < 20:
        return 4.0

    return 6.0


def calculate_dew_point(
    temperature_c: float,
    humidity: float,
) -> float:
    """
    Approximate dew point using the Magnus formula.

    This is sufficiently accurate for coaching analysis.
    """

    a = 17.27
    b = 237.7

    alpha = (
        (a * temperature_c) / (b + temperature_c)
        + math.log(humidity / 100)
    )

    return (b * alpha) / (a - alpha)


def heat_stress_rating(
    dew_point_c: float,
) -> str:
    if dew_point_c < 10:
        return "🟢 Low"

    if dew_point_c < 16:
        return "🟡 Moderate"

    if dew_point_c < 19:
        return "🟠 High"

    return "🔴 Extreme"


def terrain_rating_from_climbing_density(
    climbing_density_m_per_km: float,
) -> str:
    """
    Convert metres climbed per kilometre into a simple terrain description.

    These labels describe route difficulty only. They do not imply a precise
    pace correction.
    """

    if climbing_density_m_per_km < 5:
        return "Flat"

    if climbing_density_m_per_km < 10:
        return "Gently rolling"

    if climbing_density_m_per_km < 20:
        return "Rolling"

    if climbing_density_m_per_km < 30:
        return "Hilly"

    return "Very hilly"


def assess_terrain(
    run: RunProfile,
) -> TerrainAssessment:
    """
    Assess historical terrain using total ascent and distance.

    This method works with historical CSV imports where point-by-point
    gradient data is unavailable.

    It intentionally does not modify equivalent pace.
    """

    distance_km = None

    if run.distance_km is not None:
        try:
            distance_km = float(run.distance_km)
        except (TypeError, ValueError):
            distance_km = None

    elevation_m = None

    if run.elevation_m is not None:
        try:
            elevation_m = max(float(run.elevation_m), 0.0)
        except (TypeError, ValueError):
            elevation_m = None

    if distance_km is None or distance_km <= 0:
        return TerrainAssessment(
            elevation_m=elevation_m,
            climbing_density_m_per_km=None,
            effort_distance_km=None,
            terrain_rating="Unknown",
            method="Unavailable",
            confidence="Low",
        )

    if elevation_m is None:
        return TerrainAssessment(
            elevation_m=None,
            climbing_density_m_per_km=None,
            effort_distance_km=None,
            terrain_rating="Unknown",
            method="Distance only",
            confidence="Low",
        )

    climbing_density = elevation_m / distance_km
    effort_distance = distance_km + (elevation_m / 100.0)

    return TerrainAssessment(
        elevation_m=elevation_m,
        climbing_density_m_per_km=climbing_density,
        effort_distance_km=effort_distance,
        terrain_rating=terrain_rating_from_climbing_density(
            climbing_density,
        ),
        method="Total ascent estimate",
        confidence="Medium",
    )


def environmental_adjustment(
    run: RunProfile,
) -> EnvironmentalAdjustment:
    """
    Build the environmental adjustment for a run.

    Temperature and humidity contribute separately to equivalent pace.

    Humidity is assessed through dew point rather than relative humidity
    alone because dew point better represents the amount of moisture in
    the air and its effect on evaporative cooling.

    Terrain is assessed separately and does not yet change equivalent pace.
    Wind and surface remain at zero until later sprints.
    """

    temperature_c = None

    if run.temperature_c is not None:
        try:
            temperature_c = float(run.temperature_c)
        except (TypeError, ValueError):
            temperature_c = None

    humidity = None

    if run.humidity is not None:
        try:
            humidity = float(run.humidity)
        except (TypeError, ValueError):
            humidity = None

    if humidity is not None and not 0 < humidity <= 100:
        humidity = None

    dew_point_c = None
    heat_stress = "Unknown"

    if temperature_c is not None and humidity is not None:
        dew_point_c = calculate_dew_point(
            temperature_c,
            humidity,
        )

        heat_stress = heat_stress_rating(
            dew_point_c,
        )

    temperature_penalty = (
        temperature_adjustment_seconds_per_km(
            temperature_c,
        )
    )

    humidity_penalty = (
        humidity_adjustment_seconds_per_km(
            temperature_c,
            dew_point_c,
        )
    )

    elevation_penalty = 0.0
    wind_penalty = 0.0
    surface_penalty = 0.0

    total_penalty = (
        temperature_penalty
        + humidity_penalty
        + elevation_penalty
        + wind_penalty
        + surface_penalty
    )

    if temperature_c is None:
        confidence = "Low"
    elif humidity is None:
        confidence = "Medium"
    else:
        confidence = "High"

    return EnvironmentalAdjustment(
        temperature_penalty_seconds_per_km=temperature_penalty,
        humidity_penalty_seconds_per_km=humidity_penalty,
        elevation_penalty_seconds_per_km=elevation_penalty,
        wind_penalty_seconds_per_km=wind_penalty,
        surface_penalty_seconds_per_km=surface_penalty,
        total_penalty_seconds_per_km=total_penalty,
        temperature_c=temperature_c,
        humidity=humidity,
        dew_point_c=dew_point_c,
        heat_stress=heat_stress,
        confidence=confidence,
    )


def equivalent_performance(
    run: RunProfile,
) -> EquivalentPerformance | None:
    """
    Estimate equivalent pace after accounting for environmental conditions.

    Historical terrain is assessed and returned with the result, but it does
    not yet modify equivalent pace because total ascent alone is insufficient
    for a precise grade-adjusted calculation.

    Pace remains numeric inside the coaching engine. The dashboard is
    responsible for formatting seconds per kilometre into pace text.
    """

    if (
        run.distance_km is None
        or run.moving_time_seconds is None
        or run.distance_km <= 0
        or run.moving_time_seconds <= 0
    ):
        return None

    actual_pace = (
        float(run.moving_time_seconds)
        / float(run.distance_km)
    )

    adjustment = environmental_adjustment(run)
    terrain = assess_terrain(run)

    equivalent_pace = max(
        actual_pace
        - adjustment.total_penalty_seconds_per_km,
        0.0,
    )

    return EquivalentPerformance(
        actual_pace_seconds_per_km=actual_pace,
        equivalent_pace_seconds_per_km=equivalent_pace,
        adjustment=adjustment,
        terrain=terrain,
    )


def assess_activity(
    run: RunProfile,
) -> ActivityEvidence:
    title = (run.title or "").lower()
    sport_id = str(run.sport_id or "")

    if run.athlete_id is not None:
        sport_roles = get_athlete_sport_roles(run.athlete_id)
        sport_role = sport_roles.get(sport_id)

        if sport_role != "running":
            return ActivityEvidence(
                classification="Other",
                easy_baseline_candidate=False,
                evidence=["Not a running activity"],
            )
    elif sport_id not in {"965611", "966023"}:
        # Backwards-compatible fallback for older callers that have not yet
        # supplied athlete_id. New code should always use athlete mappings.
        return ActivityEvidence(
            classification="Other",
            easy_baseline_candidate=False,
            evidence=["Not a recognised running activity"],
        )

    evidence = []

    race_keywords = [
        "race",
        "parkrun",
        "5k",
        "10k",
        "half",
        "marathon",
    ]

    session_keywords = [
        "session",
        "threshold",
        "tempo",
        "interval",
        "intervals",
        "rep",
        "reps",
        "400",
        "800",
        "1000",
        "1200",
        "1k",
        "fartlek",
        "hill",
    ]

    if any(keyword in title for keyword in race_keywords):
        evidence.append("Race keywords detected")

        return ActivityEvidence(
            classification="🏁 Race",
            easy_baseline_candidate=False,
            evidence=evidence,
        )

    relative_race = score_athlete_relative_race_effort(
        athlete_id=run.athlete_id,
        title=title,
        distance_km=run.distance_km,
        moving_time_s=run.moving_time_seconds,
    )

    if relative_race.is_race_quality:
        evidence.append(
            relative_race.reason
            or "Athlete-relative race-quality effort"
        )

        return ActivityEvidence(
            classification="🏁 Race",
            easy_baseline_candidate=False,
            evidence=evidence,
        )

    if run.distance_km and run.distance_km >= 16:
        evidence.append("Long run distance")

        return ActivityEvidence(
            classification="🔵 Long Run",
            easy_baseline_candidate=False,
            evidence=evidence,
        )

    if any(keyword in title for keyword in session_keywords):
        evidence.append("Session keywords detected")

    if (
        run.run_max_hr is not None
        and run.lt1_hr is not None
        and run.run_max_hr >= run.lt1_hr
    ):
        evidence.append("Maximum HR exceeded LT1")

    if (
        run.avg_hr is not None
        and run.lt1_hr is not None
        and run.avg_hr >= run.lt1_hr
    ):
        evidence.append("Average HR exceeded LT1")

    if evidence:
        return ActivityEvidence(
            classification="🔴 Session",
            easy_baseline_candidate=False,
            evidence=evidence,
        )

    return ActivityEvidence(
        classification="🟢 Run",
        easy_baseline_candidate=True,
        evidence=["Matches easy aerobic profile"],
    )


def classify_run(
    run: RunProfile,
) -> str | None:
    return assess_activity(run).classification


def is_easy_baseline_candidate(
    run: RunProfile,
) -> bool:
    if not has_reliable_distance_and_pace(
        title=run.title,
        sport_id=str(run.sport_id or ""),
    ):
        return False
    return assess_activity(run).easy_baseline_candidate


def build_baseline(
    runs: list[RunProfile],
    run_type: str,
    baseline_name: str | None = None,
    period_days: int | None = None,
    period: str | None = None,
) -> AthleteBaseline | None:
    name = baseline_name or period or "All Time"

    cutoff_date = None

    if period_days is not None:
        cutoff_date = (
            datetime.date.today()
            - datetime.timedelta(days=period_days)
        )

    matching_runs = []

    for run in runs:
        if not has_reliable_distance_and_pace(
            title=run.title,
            sport_id=str(run.sport_id or ""),
        ):
            continue

        if run_type == "🟢 Run":
            if not is_easy_baseline_candidate(run):
                continue
        elif classify_run(run) != run_type:
            continue

        if cutoff_date is not None:
            activity_date = parse_activity_date(
                run.activity_date,
            )

            if (
                activity_date is None
                or activity_date < cutoff_date
            ):
                continue

        pace = pace_seconds_per_km(
            run.distance_km,
            run.moving_time_seconds,
        )

        if pace is None or run.avg_hr is None:
            continue

        matching_runs.append(
            (run, pace)
        )

    if not matching_runs:
        return None

    run_count = len(matching_runs)

    avg_distance_km = (
        sum(
            run.distance_km or 0
            for run, _pace in matching_runs
        )
        / run_count
    )

    avg_pace_seconds_per_km = (
        sum(
            pace
            for _run, pace in matching_runs
        )
        / run_count
    )

    avg_hr = (
        sum(
            run.avg_hr or 0
            for run, _pace in matching_runs
        )
        / run_count
    )

    avg_elevation_m = (
        sum(
            run.elevation_m or 0
            for run, _pace in matching_runs
        )
        / run_count
    )

    return AthleteBaseline(
        run_type=run_type,
        baseline_name=name,
        run_count=run_count,
        avg_distance_km=avg_distance_km,
        avg_pace_seconds_per_km=(
            avg_pace_seconds_per_km
        ),
        avg_hr=avg_hr,
        avg_elevation_m=avg_elevation_m,
    )


def best_easy_run(
    runs: list[RunProfile],
    period_days: int = 90,
    minimum_distance_km: float = 5.0,
    include_strides: bool = False,
) -> BestEasyRun | None:
    """
    Find the strongest qualifying easy run using environmentally adjusted
    speed relative to average heart rate.
    """

    cutoff_date = (
        datetime.date.today()
        - datetime.timedelta(days=period_days)
    )

    candidates = []

    for run in runs:
        if not is_easy_baseline_candidate(run):
            continue

        activity_date = parse_activity_date(
            run.activity_date,
        )

        if (
            activity_date is None
            or activity_date < cutoff_date
        ):
            continue

        if (
            not run.distance_km
            or run.distance_km < minimum_distance_km
            or not run.moving_time_seconds
            or not run.avg_hr
        ):
            continue

        title = (run.title or "").lower()

        if not include_strides and (
            "stride" in title
            or "strides" in title
        ):
            continue

        performance = equivalent_performance(run)

        if performance is None:
            continue

        if (
            performance.equivalent_pace_seconds_per_km
            <= 0
        ):
            continue

        equivalent_speed_m_per_s = (
            1000
            / performance.equivalent_pace_seconds_per_km
        )

        efficiency_score = (
            equivalent_speed_m_per_s
            / run.avg_hr
        )

        candidates.append(
            (
                efficiency_score,
                run,
                performance,
            )
        )

    if not candidates:
        return None

    best_score, best_run, best_performance = max(
        candidates,
        key=lambda item: item[0],
    )

    if (
        best_performance
        .adjustment
        .total_penalty_seconds_per_km
        > 0
    ):
        coach_review = (
            "This is your strongest qualifying easy run in the selected "
            "period after adjusting pace for environmental conditions and "
            "comparing speed relative to heart rate."
        )
    else:
        coach_review = (
            "This is your strongest qualifying easy run in the selected "
            "period based on speed relative to heart rate."
        )

    return BestEasyRun(
        run=best_run,
        efficiency_score=best_score,
        equivalent_performance=best_performance,
        coach_review=coach_review,
    )


def aerobic_efficiency(
    avg_hr: float | None,
    pace_seconds_per_mile: float | None,
):
    return None
