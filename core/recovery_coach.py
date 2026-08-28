"""Evidence-backed Recovery Coach composition.

Recovery Coach keeps four kinds of information deliberately separate:

* athlete-reported sleep, fatigue, soreness and motivation;
* source-labelled nightly HRV, resting heart rate and sleep trends;
* completed training evidence and demonstrated durability;
* recovery space in the athlete-approved Training Block.

It does not infer illness, injury or a physiological readiness score. Saving a
check-in or importing health evidence never changes the approved training plan.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime
import statistics
from typing import Any

from core.database import (
    create_athlete_health_daily_table,
    create_recovery_checkins_table,
    get_connection,
)
from core.operational_block import OperationalWeek, build_operational_block_week
from core.progress import ProgressSummary, build_progress_summary


MODEL_VERSION = 2
DEMANDING_FAMILIES = {"threshold", "quality", "race", "long"}
RECOVERY_FAMILIES = {"rest", "easy", "recovery"}


@dataclass(frozen=True)
class RecoveryCheckIn:
    athlete_id: int
    checkin_date: str
    sleep_quality: int
    fatigue: int
    soreness: int
    motivation: int
    notes: str | None
    updated_at: str | None = None


@dataclass(frozen=True)
class RecoveryLoadSignal:
    current_miles: float
    baseline_miles: float | None
    change_percent: float | None
    active_days: int
    easy_miles: float
    long_miles: float
    quality_miles: float
    easy_share_percent: float | None
    status: str
    explanation: str
    evidence_weeks: int


@dataclass(frozen=True)
class RecoveryDay:
    day: str
    date: str
    family: str
    session_type: str
    status: str
    is_today: bool
    is_recovery_support: bool
    is_demanding: bool


@dataclass(frozen=True)
class RecoveryScheduleSignal:
    available: bool
    block_name: str
    week_label: str
    status: str
    recovery_support_days: int
    demanding_days: int
    completed_demanding_days: int
    next_demand: str
    next_demand_timing: str
    protected_days_before_next_demand: int
    days: tuple[RecoveryDay, ...]
    explanation: str


@dataclass(frozen=True)
class RecoveryDurabilitySignal:
    available: bool
    status: str
    recent_decoupling_percent: float | None
    change_percent: float | None
    sample_size: int
    confidence: str
    explanation: str


@dataclass(frozen=True)
class RecoveryHealthSignal:
    available: bool
    latest_date: str | None
    source: str
    hrv_metric_code: str | None
    hrv_recent: float | None
    hrv_baseline: float | None
    hrv_change_percent: float | None
    hrv_status: str
    hrv_recent_count: int
    hrv_baseline_count: int
    resting_hr_recent: float | None
    resting_hr_baseline: float | None
    resting_hr_change: float | None
    resting_hr_status: str
    sleep_recent_minutes: float | None
    sleep_baseline_minutes: float | None
    sleep_change_minutes: float | None
    sleep_quality_recent: float | None
    sleep_status: str
    confidence: str
    explanation: str


@dataclass(frozen=True)
class RecoveryMobilityRoutine:
    title: str
    duration: str
    purpose: str
    exercises: tuple[str, ...]
    caution: str


@dataclass(frozen=True)
class RecoveryCoachDetail:
    athlete_id: int
    athlete_name: str
    reference_date: str
    headline: str
    direction: str
    checkin_status: str
    checkin: RecoveryCheckIn | None
    load: RecoveryLoadSignal
    schedule: RecoveryScheduleSignal
    durability: RecoveryDurabilitySignal
    health: RecoveryHealthSignal
    mobility_routines: tuple[RecoveryMobilityRoutine, ...]
    evidence_confidence: str
    strengths: tuple[str, ...]
    cautions: tuple[str, ...]
    priorities: tuple[str, ...]
    limitations: tuple[str, ...]
    model_version: int = MODEL_VERSION


def _date(value: Any) -> datetime.date | None:
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _validate_scale(label: str, value: int) -> int:
    number = int(value)
    if not 1 <= number <= 5:
        raise ValueError(f"{label} must be between 1 and 5.")
    return number


def get_recovery_checkin(
    athlete_id: int,
    checkin_date: datetime.date | str,
) -> RecoveryCheckIn | None:
    day = _date(checkin_date)
    if day is None:
        raise ValueError("Provide a valid check-in date.")
    connection = get_connection()
    cursor = connection.cursor()
    create_recovery_checkins_table(cursor)
    row = cursor.execute(
        """
        SELECT athlete_id, checkin_date, sleep_quality, fatigue, soreness,
               motivation, notes, updated_at
        FROM athlete_recovery_checkins
        WHERE athlete_id = ? AND checkin_date = ?
        """,
        (int(athlete_id), day.isoformat()),
    ).fetchone()
    connection.close()
    if row is None:
        return None
    return RecoveryCheckIn(
        athlete_id=int(row[0]),
        checkin_date=str(row[1]),
        sleep_quality=int(row[2]),
        fatigue=int(row[3]),
        soreness=int(row[4]),
        motivation=int(row[5]),
        notes=str(row[6]).strip() if row[6] else None,
        updated_at=str(row[7]) if row[7] else None,
    )


def save_recovery_checkin(
    athlete_id: int,
    checkin_date: datetime.date | str,
    *,
    sleep_quality: int,
    fatigue: int,
    soreness: int,
    motivation: int,
    notes: str | None = None,
) -> RecoveryCheckIn:
    """Save one explicit daily report without changing a training plan."""
    day = _date(checkin_date)
    if day is None:
        raise ValueError("Provide a valid check-in date.")
    values = (
        _validate_scale("Sleep quality", sleep_quality),
        _validate_scale("Fatigue", fatigue),
        _validate_scale("Soreness", soreness),
        _validate_scale("Motivation", motivation),
    )
    clean_notes = str(notes or "").strip() or None
    connection = get_connection()
    cursor = connection.cursor()
    create_recovery_checkins_table(cursor)
    owner = cursor.execute(
        "SELECT id FROM athletes WHERE id = ?", (int(athlete_id),)
    ).fetchone()
    if owner is None:
        connection.close()
        raise ValueError("Athlete not found.")
    cursor.execute(
        """
        INSERT INTO athlete_recovery_checkins (
            athlete_id, checkin_date, sleep_quality, fatigue, soreness,
            motivation, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(athlete_id, checkin_date) DO UPDATE SET
            sleep_quality = excluded.sleep_quality,
            fatigue = excluded.fatigue,
            soreness = excluded.soreness,
            motivation = excluded.motivation,
            notes = excluded.notes,
            updated_at = CURRENT_TIMESTAMP
        """,
        (int(athlete_id), day.isoformat(), *values, clean_notes),
    )
    connection.commit()
    connection.close()
    saved = get_recovery_checkin(athlete_id, day)
    if saved is None:  # pragma: no cover - defensive database boundary
        raise RuntimeError("The recovery check-in could not be reloaded.")
    return saved


def _empty_load() -> RecoveryLoadSignal:
    return RecoveryLoadSignal(
        current_miles=0.0,
        baseline_miles=None,
        change_percent=None,
        active_days=0,
        easy_miles=0.0,
        long_miles=0.0,
        quality_miles=0.0,
        easy_share_percent=None,
        status="Training evidence building",
        explanation="More reliable running activity is needed to compare rolling load.",
        evidence_weeks=0,
    )


def _load_signal(progress: ProgressSummary | None) -> RecoveryLoadSignal:
    if progress is None or not progress.rhythm.points:
        return _empty_load()
    points = tuple(progress.rhythm.points)
    current = points[-1]
    prior = tuple(point for point in points[-5:-1] if point.reliable_miles > 0)
    baseline = (
        statistics.fmean(point.reliable_miles for point in prior)
        if prior else None
    )
    change = (
        (current.reliable_miles / baseline - 1.0) * 100.0
        if baseline and baseline > 0 else None
    )
    total = current.reliable_miles
    easy_share = current.easy_miles / total * 100.0 if total > 0 else None
    if change is None:
        status = "Baseline building"
    elif change >= 20.0:
        status = "Load rose sharply"
    elif change >= 10.0:
        status = "Load is building"
    elif change <= -25.0:
        status = "Reduced load"
    else:
        status = "Load broadly stable"
    comparison = (
        f"{change:+.0f}% versus the previous four-week rolling average"
        if change is not None else "a comparable rolling baseline is still building"
    )
    return RecoveryLoadSignal(
        current_miles=round(current.reliable_miles, 1),
        baseline_miles=round(baseline, 1) if baseline is not None else None,
        change_percent=round(change, 1) if change is not None else None,
        active_days=int(current.active_days),
        easy_miles=round(current.easy_miles, 1),
        long_miles=round(current.long_miles, 1),
        quality_miles=round(current.quality_miles, 1),
        easy_share_percent=round(easy_share, 1) if easy_share is not None else None,
        status=status,
        explanation=(
            f"The latest rolling seven days contain {current.reliable_miles:.1f} "
            f"reliable miles across {current.active_days} running days; {comparison}."
        ),
        evidence_weeks=sum(point.reliable_miles > 0 for point in points),
    )


def _timing(day: datetime.date | None, today: datetime.date) -> str:
    if day is None:
        return "Not scheduled"
    delta = (day - today).days
    if delta == 0:
        return "Today"
    if delta == 1:
        return "Tomorrow"
    if 1 < delta <= 6:
        return day.strftime("%A")
    return day.strftime("%-d %b")


def _schedule_signal(
    week: OperationalWeek | None,
    today: datetime.date,
) -> RecoveryScheduleSignal:
    if week is None:
        return RecoveryScheduleSignal(
            available=False,
            block_name="No approved block",
            week_label="Current week",
            status="Schedule context unavailable",
            recovery_support_days=0,
            demanding_days=0,
            completed_demanding_days=0,
            next_demand="No demanding session identified",
            next_demand_timing="Not scheduled",
            protected_days_before_next_demand=0,
            days=(),
            explanation=(
                "Recovery Coach can still describe completed load, but an approved "
                "Training Block is needed to judge planned recovery spacing."
            ),
        )
    days = tuple(
        RecoveryDay(
            day=day.day,
            date=day.date,
            family=day.planned_family,
            session_type=day.planned_type,
            status=day.status,
            is_today=day.date == today.isoformat(),
            is_recovery_support=day.planned_family in RECOVERY_FAMILIES,
            is_demanding=day.planned_family in DEMANDING_FAMILIES,
        )
        for day in week.days
    )
    future_demands = [
        day for day in days
        if day.is_demanding and (_date(day.date) or today) >= today
        and day.status not in {"Complete", "Different", "Extra"}
    ]
    next_day = future_demands[0] if future_demands else None
    next_date = _date(next_day.date) if next_day else None
    protected = sum(
        day.is_recovery_support
        and today <= (_date(day.date) or today)
        and (next_date is None or (_date(day.date) or today) < next_date)
        for day in days
    )
    demanding = [day for day in days if day.is_demanding]
    completed = [
        day for day in demanding
        if day.status in {"Complete", "Different", "Extra"}
    ]
    if week.status == "Review suggested":
        status = "Recovery review suggested"
    elif next_day is not None and protected >= 1:
        status = "Recovery space protected"
    elif next_day is not None:
        status = "Demand is close"
    else:
        status = "No further demand this week"
    next_name = next_day.session_type if next_day else "No further demanding session"
    next_timing = _timing(next_date, today)
    return RecoveryScheduleSignal(
        available=True,
        block_name=week.block_name,
        week_label=f"Week {week.week_number} of {week.total_weeks}",
        status=status,
        recovery_support_days=sum(day.is_recovery_support for day in days),
        demanding_days=len(demanding),
        completed_demanding_days=len(completed),
        next_demand=next_name,
        next_demand_timing=next_timing,
        protected_days_before_next_demand=int(protected),
        days=days,
        explanation=(
            f"The saved week contains {sum(day.is_recovery_support for day in days)} "
            f"easy/rest support days and {len(demanding)} demanding commitments. "
            f"Next demand: {next_name} {next_timing.lower()}."
        ),
    )


def _durability_signal(
    progress: ProgressSummary | None,
) -> RecoveryDurabilitySignal:
    if progress is None or not progress.durability.available:
        return RecoveryDurabilitySignal(
            available=False,
            status="Durability evidence building",
            recent_decoupling_percent=None,
            change_percent=None,
            sample_size=0,
            confidence="Limited",
            explanation=(
                "More continuous Long Easy runs are needed before Recovery Coach "
                "can assess late-run stability."
            ),
        )
    value = progress.durability
    return RecoveryDurabilitySignal(
        available=True,
        status=value.status,
        recent_decoupling_percent=value.recent_decoupling_percent,
        change_percent=value.change_percent,
        sample_size=value.total_sample_size,
        confidence=value.confidence,
        explanation=value.summary,
    )


def _empty_health() -> RecoveryHealthSignal:
    return RecoveryHealthSignal(
        available=False,
        latest_date=None,
        source="No health feed",
        hrv_metric_code=None,
        hrv_recent=None,
        hrv_baseline=None,
        hrv_change_percent=None,
        hrv_status="HRV baseline unavailable",
        hrv_recent_count=0,
        hrv_baseline_count=0,
        resting_hr_recent=None,
        resting_hr_baseline=None,
        resting_hr_change=None,
        resting_hr_status="Resting-HR baseline unavailable",
        sleep_recent_minutes=None,
        sleep_baseline_minutes=None,
        sleep_change_minutes=None,
        sleep_quality_recent=None,
        sleep_status="Sleep baseline unavailable",
        confidence="Unavailable",
        explanation=(
            "Import a Runalyze combined health CSV to compare HRV, resting heart "
            "rate and sleep with the athlete’s own recent history."
        ),
    )


def _mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def _percent_change(current: float | None, baseline: float | None) -> float | None:
    if current is None or baseline is None or baseline == 0:
        return None
    return (current / baseline - 1.0) * 100.0


def _hrv_status(change: float | None, recent: int, baseline: int) -> str:
    if recent < 4 or baseline < 14 or change is None:
        return "HRV baseline building"
    if change <= -10.0:
        return "Below recent HRV baseline"
    if change >= 10.0:
        return "Above recent HRV baseline"
    return "Within recent HRV range"


def _resting_status(change: float | None, recent: int, baseline: int) -> str:
    if recent < 4 or baseline < 14 or change is None:
        return "Resting-HR baseline building"
    if change >= 3.0:
        return "Resting HR is above baseline"
    if change <= -3.0:
        return "Resting HR is below baseline"
    return "Resting HR is broadly stable"


def _sleep_status(change: float | None, recent: int, baseline: int) -> str:
    if recent < 4 or baseline < 14 or change is None:
        return "Sleep baseline building"
    if change <= -30.0:
        return "Sleep duration is below baseline"
    if change >= 30.0:
        return "Sleep duration is above baseline"
    return "Sleep duration is broadly stable"


def build_recovery_health_signal(
    athlete_id: int,
    *,
    today: datetime.date,
) -> RecoveryHealthSignal:
    """Compare seven recent days with the preceding 28-day personal baseline."""
    connection = get_connection()
    cursor = connection.cursor()
    create_athlete_health_daily_table(cursor)
    rows = cursor.execute(
        """
        SELECT health_date, source, hrv_value, hrv_metric_code,
               hrv_measurement_type, hrv_source_code, resting_hr,
               sleep_duration_min, sleep_quality_100
        FROM athlete_health_daily
        WHERE athlete_id = ?
          AND date(health_date) BETWEEN date(?, '-60 days') AND date(?)
        ORDER BY health_date,
                 CASE source
                     WHEN 'garmin_connect_health' THEN 0
                     ELSE 1
                 END
        """,
        (int(athlete_id), today.isoformat(), today.isoformat()),
    ).fetchall()
    connection.close()
    if not rows:
        return _empty_health()

    # More than one connector can provide the same calendar day. Prefer the
    # direct Garmin row, then fill any missing values from another source so
    # one night is never counted twice in the personal baseline.
    merged_days = {}
    for row in rows:
        key = str(row[0])
        if key not in merged_days:
            merged_days[key] = list(row)
            continue
        current = merged_days[key]
        for index in range(2, len(current)):
            if current[index] is None and row[index] is not None:
                current[index] = row[index]
    merged_rows = [tuple(row) for row in merged_days.values()]
    dated = [(_date(row[0]), row) for row in merged_rows]
    dated = [(day, row) for day, row in dated if day is not None]
    if not dated:
        return _empty_health()
    latest = max(day for day, _ in dated)
    recent_start = today - datetime.timedelta(days=6)
    baseline_start = today - datetime.timedelta(days=34)
    baseline_end = today - datetime.timedelta(days=7)

    latest_hrv = next(
        (row for _, row in reversed(dated) if row[2] is not None),
        None,
    )
    hrv_signature = (
        (latest_hrv[3], latest_hrv[4], latest_hrv[5])
        if latest_hrv is not None else None
    )

    def values(index: int, start: datetime.date, end: datetime.date, *, hrv=False):
        result = []
        for day, row in dated:
            if not start <= day <= end or row[index] is None:
                continue
            if hrv and hrv_signature is not None and (row[3], row[4], row[5]) != hrv_signature:
                continue
            result.append(float(row[index]))
        return result

    recent_hrv = values(2, recent_start, today, hrv=True)
    baseline_hrv = values(2, baseline_start, baseline_end, hrv=True)
    recent_resting = values(6, recent_start, today)
    baseline_resting = values(6, baseline_start, baseline_end)
    recent_sleep = values(7, recent_start, today)
    baseline_sleep = values(7, baseline_start, baseline_end)
    recent_quality = values(8, recent_start, today)

    hrv_current = _mean(recent_hrv)
    hrv_baseline = _mean(baseline_hrv)
    hrv_change = _percent_change(hrv_current, hrv_baseline)
    resting_current = _mean(recent_resting)
    resting_baseline = _mean(baseline_resting)
    resting_change = (
        resting_current - resting_baseline
        if resting_current is not None and resting_baseline is not None
        else None
    )
    sleep_current = _mean(recent_sleep)
    sleep_baseline = _mean(baseline_sleep)
    sleep_change = (
        sleep_current - sleep_baseline
        if sleep_current is not None and sleep_baseline is not None
        else None
    )
    ready = sum(
        (
            len(recent_hrv) >= 4 and len(baseline_hrv) >= 14,
            len(recent_resting) >= 4 and len(baseline_resting) >= 14,
            len(recent_sleep) >= 4 and len(baseline_sleep) >= 14,
        )
    )
    stale_days = (today - latest).days
    if ready >= 2 and stale_days <= 2:
        confidence = "Strong"
    elif ready >= 1 and stale_days <= 7:
        confidence = "Moderate"
    else:
        confidence = "Limited"
    source = str(merged_rows[-1][1] or "health data").replace("_", " ").title()
    freshness = "current" if stale_days <= 1 else f"last updated {stale_days} days ago"
    return RecoveryHealthSignal(
        available=True,
        latest_date=latest.isoformat(),
        source=source,
        hrv_metric_code=str(hrv_signature[0]) if hrv_signature and hrv_signature[0] is not None else None,
        hrv_recent=round(hrv_current, 1) if hrv_current is not None else None,
        hrv_baseline=round(hrv_baseline, 1) if hrv_baseline is not None else None,
        hrv_change_percent=round(hrv_change, 1) if hrv_change is not None else None,
        hrv_status=_hrv_status(hrv_change, len(recent_hrv), len(baseline_hrv)),
        hrv_recent_count=len(recent_hrv),
        hrv_baseline_count=len(baseline_hrv),
        resting_hr_recent=round(resting_current, 1) if resting_current is not None else None,
        resting_hr_baseline=round(resting_baseline, 1) if resting_baseline is not None else None,
        resting_hr_change=round(resting_change, 1) if resting_change is not None else None,
        resting_hr_status=_resting_status(resting_change, len(recent_resting), len(baseline_resting)),
        sleep_recent_minutes=round(sleep_current, 1) if sleep_current is not None else None,
        sleep_baseline_minutes=round(sleep_baseline, 1) if sleep_baseline is not None else None,
        sleep_change_minutes=round(sleep_change, 1) if sleep_change is not None else None,
        sleep_quality_recent=round(_mean(recent_quality), 1) if recent_quality else None,
        sleep_status=_sleep_status(sleep_change, len(recent_sleep), len(baseline_sleep)),
        confidence=confidence,
        explanation=(
            "Seven recent calendar days are compared with the preceding 28-day "
            f"personal baseline. The connected health evidence is {freshness}."
        ),
    )


def _mobility_routines(
    checkin: RecoveryCheckIn | None,
) -> tuple[RecoveryMobilityRoutine, ...]:
    focal_caution = bool(checkin and checkin.soreness >= 4)
    first = RecoveryMobilityRoutine(
        title="Pain-free reset" if focal_caution else "Post-run reset",
        duration="5–6 min",
        purpose=(
            "Keep movement gentle while soreness is elevated."
            if focal_caution else "Relax calves, hips and upper back after an easy run."
        ),
        exercises=(
            "Slow breathing · 60 seconds",
            "Ankle circles · 5 each direction",
            "Gentle cat–cow · 6 repetitions",
            "Supported hip shifts · 5 each side",
        ) if focal_caution else (
            "Wall calf stretch · 30 seconds each side",
            "Half-kneeling hip-flexor stretch · 30 seconds each side",
            "Figure-four glute stretch · 30 seconds each side",
            "Open-book rotation · 5 each side",
        ),
        caution="Use only a comfortable range; stop if pain is sharp, focal or worsening.",
    )
    return (
        first,
        RecoveryMobilityRoutine(
            title="Lower-leg mobility",
            duration="5 min",
            purpose="Maintain comfortable ankle and calf movement without adding load.",
            exercises=(
                "Knee-to-wall ankle rocks · 8 each side",
                "Straight-knee calf stretch · 30 seconds each side",
                "Bent-knee soleus stretch · 30 seconds each side",
                "Easy double-leg calf raises · 8 controlled repetitions",
            ),
            caution="Skip calf raises or stretching if either reproduces pain.",
        ),
        RecoveryMobilityRoutine(
            title="Rest-day yoga flow",
            duration="8 min",
            purpose="A short, calm sequence for general mobility rather than fitness.",
            exercises=(
                "Child’s pose with side reach · 30 seconds each side",
                "Cat–cow · 6 slow repetitions",
                "Low lunge · 30 seconds each side",
                "Downward-dog pedal · 45 seconds",
                "Supine twist · 30 seconds each side",
            ),
            caution="Keep every position easy; this is not treatment for an injury.",
        ),
    )


def _checkin_state(checkin: RecoveryCheckIn | None) -> tuple[str, tuple[str, ...]]:
    if checkin is None:
        return "Not reported today", ()
    concerns = []
    if checkin.sleep_quality <= 2:
        concerns.append("Sleep quality is reported as low")
    if checkin.fatigue >= 4:
        concerns.append("Fatigue is reported as high")
    if checkin.soreness >= 4:
        concerns.append("Soreness is reported as high")
    if checkin.motivation <= 2:
        concerns.append("Motivation is reported as low")
    if len(concerns) >= 2 or checkin.soreness == 5:
        return "Several recovery flags reported", tuple(concerns)
    if concerns:
        return "One recovery flag reported", tuple(concerns)
    return "No concern reported", ()


def compose_recovery_coach(
    *,
    athlete_id: int,
    athlete_name: str,
    progress: ProgressSummary | None,
    week: OperationalWeek | None,
    checkin: RecoveryCheckIn | None,
    today: datetime.date,
    health: RecoveryHealthSignal | None = None,
) -> RecoveryCoachDetail:
    """Compose subjective, wearable, completed-load and schedule evidence."""
    load = _load_signal(progress)
    schedule = _schedule_signal(week, today)
    durability = _durability_signal(progress)
    health = health or _empty_health()
    checkin_status, reported_concerns = _checkin_state(checkin)

    cautions = list(reported_concerns)
    health_concerns = []
    if health.hrv_status == "Below recent HRV baseline":
        health_concerns.append(
            f"Seven-day HRV is {abs(health.hrv_change_percent or 0):.0f}% below the preceding personal baseline"
        )
    if health.resting_hr_status == "Resting HR is above baseline":
        health_concerns.append(
            f"Seven-day resting HR is {health.resting_hr_change or 0:+.1f} bpm versus the preceding personal baseline"
        )
    if health.sleep_status == "Sleep duration is below baseline":
        health_concerns.append(
            f"Seven-day sleep duration is {abs(health.sleep_change_minutes or 0):.0f} minutes below the preceding personal baseline"
        )
    cautions.extend(health_concerns)
    if load.change_percent is not None and load.change_percent >= 20:
        cautions.append("Rolling seven-day mileage rose sharply versus recent weeks")
    if schedule.status == "Recovery review suggested":
        cautions.append("The approved week already contains a recovery review signal")

    strengths = []
    if schedule.available and schedule.recovery_support_days >= 3:
        strengths.append(
            f"The approved week includes {schedule.recovery_support_days} easy or rest support days"
        )
    if load.easy_share_percent is not None and load.easy_share_percent >= 50:
        strengths.append(
            f"{load.easy_share_percent:.0f}% of reliable mileage in the latest seven days is easy running"
        )
    if durability.available and durability.status in {"Strong", "Controlled", "Improving"}:
        strengths.append(
            f"Long-run durability is currently described as {durability.status.lower()}"
        )
    stable_health = health.available and not health_concerns and health.confidence in {"Strong", "Moderate"}
    if stable_health:
        strengths.append(
            "Connected health trends—HRV, resting HR and sleep—are broadly consistent with current personal baselines"
        )
    if not strengths:
        strengths.append("Recovery evidence is being kept separate from unsupported physiology")

    priorities = []
    if checkin is None:
        priorities.append("Complete today’s short check-in before interpreting how recovered you feel")
    elif reported_concerns:
        priorities.append("Respect the reported recovery flags before adding intensity or extra mileage")
    else:
        priorities.append("Keep the planned easy work genuinely easy; no extra proof is needed today")
    if health_concerns and not reported_concerns:
        priorities.append(
            "Compare the wearable trend with how you actually feel before deciding whether to reduce load"
        )
    elif health.available and health.confidence == "Strong":
        priorities.append(
            "Use the health trend as supporting context, not permission to add unplanned intensity"
        )
    if schedule.next_demand_timing != "Not scheduled":
        priorities.append(
            f"Arrive fresh for {schedule.next_demand} {schedule.next_demand_timing.lower()}"
        )
    if load.change_percent is not None and load.change_percent >= 10:
        priorities.append("Let the current load settle before adding unplanned volume")
    elif load.change_percent is not None and load.change_percent <= -25:
        priorities.append("Resume the useful sequence without trying to repay missed mileage")
    else:
        priorities.append("Maintain the current training rhythm rather than forcing additional load")

    if len(reported_concerns) >= 2 or (checkin and checkin.soreness == 5):
        headline = "Today calls for a recovery adjustment."
        direction = (
            "Several athlete-reported signals are unfavourable. Keep today easy or rest, "
            "and do not force a demanding session; persistent or focal pain needs proper assessment."
        )
    elif reported_concerns or health_concerns or cautions:
        headline = "Protect recovery before adding more load."
        direction = (
            "There is at least one reason for caution. Preserve the purpose of the week, "
            "but keep easy running easy and move a demanding session if the concern persists."
        )
    elif checkin is None:
        headline = "Training balance looks controlled; how you feel is still unreported."
        direction = (
            "Completed training and the saved week provide useful context, but Recovery Coach "
            "will not guess sleep, fatigue, soreness or motivation."
        )
    else:
        headline = "The current week is giving adaptation room."
        direction = (
            "No athlete-reported concern is recorded today and the training evidence does not "
            "currently call for an automatic reduction. Continue to follow the planned spacing."
        )

    evidence_count = load.evidence_weeks
    confidence = (
        "Strong"
        if (
            evidence_count >= 10
            and schedule.available
            and health.confidence in {"Strong", "Unavailable"}
        )
        else "Moderate"
        if evidence_count >= 6 or health.confidence in {"Strong", "Moderate"}
        else "Limited"
    )
    return RecoveryCoachDetail(
        athlete_id=int(athlete_id),
        athlete_name=str(athlete_name or "Athlete"),
        reference_date=today.isoformat(),
        headline=headline,
        direction=direction,
        checkin_status=checkin_status,
        checkin=checkin,
        load=load,
        schedule=schedule,
        durability=durability,
        health=health,
        mobility_routines=_mobility_routines(checkin),
        evidence_confidence=confidence,
        strengths=tuple(strengths),
        cautions=tuple(cautions),
        priorities=tuple(priorities),
        limitations=(
            (
                "HRV, resting-HR and sleep trends are compared only with the athlete’s own recent source-consistent baseline."
                if health.available
                else "No connected HRV, sleep-duration or wearable recovery feed is used."
            ),
            "The daily check-in is athlete-reported context, not a medical assessment.",
            "Recovery Coach advises; it never silently changes the approved Training Block.",
            "There is no hidden or physiological readiness score.",
        ),
    )


def build_recovery_coach_detail(
    athlete_id: int,
    *,
    today: datetime.date | None = None,
) -> RecoveryCoachDetail | None:
    today = today or datetime.date.today()
    progress = build_progress_summary(athlete_id, reference_date=today)
    if progress is None:
        connection = get_connection()
        row = connection.execute(
            "SELECT first_name, last_name FROM athletes WHERE id = ?",
            (int(athlete_id),),
        ).fetchone()
        connection.close()
        if row is None:
            return None
        athlete_name = f"{row[0] or ''} {row[1] or ''}".strip() or "Athlete"
    else:
        athlete_name = progress.athlete_name
    return compose_recovery_coach(
        athlete_id=athlete_id,
        athlete_name=athlete_name,
        progress=progress,
        week=build_operational_block_week(athlete_id, today=today),
        checkin=get_recovery_checkin(athlete_id, today),
        today=today,
        health=build_recovery_health_signal(athlete_id, today=today),
    )
