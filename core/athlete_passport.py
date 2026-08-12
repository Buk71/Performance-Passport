"""Real athlete data for the compact Athlete Passport component.

This module is deliberately UI-free. It reuses the existing coaching engine
for easy-run classification and environmental pace adjustment, and uses the
same elapsed-time/GPS-tolerance rules as Hall of Fame for race PBs.

Road age standards are the 2020 USATF Masters Long Distance Running tables
maintained by Alan Jones (CC0):
https://github.com/AlanLyttonJones/Age-Grade-Tables
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime
import math
import statistics
from typing import Any

from core.activity_reliability import has_reliable_distance_and_pace
from core.coaching import (
    RunProfile,
    equivalent_performance,
    is_easy_baseline_candidate,
)
from core.database import (
    get_athlete_sport_roles,
    get_connection,
    get_effective_athlete_thresholds,
)


STANDARD_MIN_AGE = 5

MALE_5K_STANDARDS = (
    1272, 1168, 1086, 1020, 966, 922, 886, 856, 832, 813, 798, 787, 777, 771,
    771, 771, 771, 771, 771, 771, 771, 771, 771, 771, 771, 771, 772, 773,
    776, 779, 783, 789, 794, 800, 806, 812, 818, 824, 830, 837, 843, 849,
    856, 863, 870, 877, 884, 891, 898, 905, 913, 920, 928, 936, 944, 952,
    961, 969, 978, 986, 995, 1004, 1014, 1023, 1034, 1046, 1059, 1074,
    1089, 1106, 1125, 1145, 1167, 1190, 1216, 1245, 1276, 1309, 1346,
    1387, 1432, 1482, 1536, 1598, 1666, 1742, 1829, 1928, 2041, 2171,
    2324, 2505, 2721, 2986, 3316, 3739,
)

MALE_10K_STANDARDS = (
    2605, 2393, 2225, 2090, 1980, 1890, 1817, 1756, 1707, 1667, 1636,
    1613, 1597, 1587, 1584, 1584, 1584, 1584, 1584, 1584, 1584, 1584,
    1584, 1584, 1584, 1584, 1585, 1586, 1589, 1593, 1599, 1605, 1613,
    1622, 1632, 1644, 1657, 1670, 1683, 1697, 1710, 1724, 1739, 1753,
    1768, 1783, 1798, 1813, 1829, 1845, 1861, 1878, 1895, 1912, 1929,
    1947, 1965, 1983, 2002, 2021, 2041, 2061, 2081, 2102, 2123, 2145,
    2167, 2193, 2221, 2252, 2286, 2324, 2365, 2410, 2460, 2514, 2573,
    2638, 2710, 2789, 2876, 2972, 3080, 3199, 3333, 3484, 3655, 3849,
    4073, 4331, 4634, 4994, 5427, 5955, 6617, 7468,
)

MALE_HALF_STANDARDS = (
    5748, 5277, 4906, 4607, 4364, 4166, 4003, 3869, 3761, 3673, 3605,
    3553, 3510, 3483, 3481, 3481, 3481, 3481, 3481, 3481, 3481, 3481,
    3481, 3481, 3481, 3481, 3481, 3482, 3485, 3491, 3500, 3512, 3527,
    3545, 3566, 3590, 3617, 3647, 3677, 3708, 3739, 3770, 3802, 3835,
    3868, 3902, 3936, 3971, 4006, 4043, 4079, 4117, 4155, 4194, 4234,
    4274, 4315, 4357, 4400, 4444, 4489, 4534, 4580, 4628, 4676, 4726,
    4778, 4837, 4901, 4972, 5051, 5136, 5231, 5334, 5448, 5572, 5708,
    5858, 6024, 6206, 6408, 6632, 6882, 7161, 7475, 7830, 8231, 8694,
    9226, 9847, 10581, 11454, 12522, 13841, 15526, 17733,
)

FEMALE_5K_STANDARDS = (
    1224, 1177, 1134, 1097, 1064, 1035, 1008, 985, 964, 945, 929, 913,
    898, 888, 884, 884, 884, 884, 884, 884, 884, 884, 884, 884, 884,
    884, 884, 885, 886, 888, 890, 892, 896, 899, 903, 908, 913, 919,
    926, 933, 941, 949, 958, 968, 979, 989, 1000, 1011, 1023, 1034,
    1046, 1058, 1071, 1083, 1096, 1110, 1123, 1137, 1152, 1167, 1182,
    1197, 1213, 1230, 1246, 1264, 1282, 1300, 1319, 1338, 1358, 1379,
    1400, 1422, 1444, 1470, 1499, 1532, 1568, 1609, 1655, 1708, 1767,
    1833, 1908, 1995, 2094, 2209, 2343, 2501, 2689, 2917, 3198, 3552,
    4011, 4631,
)

FEMALE_10K_STANDARDS = (
    2470, 2482, 2378, 2288, 2209, 2140, 2080, 2027, 1980, 1940, 1905,
    1873, 1842, 1816, 1797, 1787, 1783, 1783, 1783, 1783, 1783, 1783,
    1783, 1783, 1785, 1787, 1789, 1793, 1797, 1803, 1809, 1816, 1824,
    1832, 1842, 1853, 1864, 1877, 1891, 1906, 1922, 1939, 1957, 1977,
    1999, 2021, 2044, 2068, 2092, 2116, 2142, 2168, 2194, 2221, 2249,
    2278, 2307, 2337, 2368, 2399, 2432, 2465, 2500, 2535, 2571, 2609,
    2647, 2687, 2728, 2770, 2814, 2860, 2912, 2969, 3033, 3104, 3182,
    3269, 3365, 3472, 3593, 3727, 3879, 4050, 4244, 4468, 4724, 5024,
    5375, 5795, 6303, 6927, 7715, 8736, 10113, 12072,
)

FEMALE_HALF_STANDARDS = (
    5361, 5779, 5496, 5253, 5042, 4858, 4698, 4558, 4435, 4327, 4233,
    4147, 4064, 3992, 3938, 3901, 3878, 3871, 3871, 3871, 3871, 3871,
    3871, 3871, 3871, 3872, 3875, 3880, 3887, 3897, 3909, 3922, 3938,
    3956, 3976, 3999, 4025, 4053, 4083, 4117, 4153, 4193, 4235, 4281,
    4330, 4381, 4434, 4487, 4542, 4598, 4655, 4714, 4775, 4837, 4901,
    4966, 5033, 5102, 5173, 5246, 5321, 5398, 5478, 5559, 5644, 5731,
    5820, 5913, 6008, 6107, 6209, 6314, 6428, 6554, 6696, 6854, 7029,
    7223, 7441, 7685, 7957, 8264, 8610, 9004, 9455, 9972, 10574, 11276,
    12112, 13113, 14337, 15871, 17830, 20438, 24043, 29370,
)

AGE_STANDARDS = {
    "male": {
        "5k": MALE_5K_STANDARDS,
        "10k": MALE_10K_STANDARDS,
        "half_marathon": MALE_HALF_STANDARDS,
    },
    "female": {
        "5k": FEMALE_5K_STANDARDS,
        "10k": FEMALE_10K_STANDARDS,
        "half_marathon": FEMALE_HALF_STANDARDS,
    },
}

EVENTS = (
    ("5k", "5K", 5000.0),
    ("10k", "10K", 10000.0),
    ("half_marathon", "HALF", 21097.5),
)


@dataclass(frozen=True)
class PassportPersonalBest:
    key: str
    label: str
    all_time_seconds: float | None
    last_12_months_seconds: float | None


@dataclass(frozen=True)
class AthletePassportData:
    athlete_id: int
    first_name: str
    last_name: str
    full_name: str
    initials: str
    age: int | None
    category: str
    sex: str | None
    age_grade_all_time: float | None
    age_grade_last_12_months: float | None
    personal_bests: tuple[PassportPersonalBest, ...]
    aerobic_trend_percent: float | None
    aerobic_chart_points: tuple[float, ...]
    aerobic_run_count: int


def _safe_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _as_date(value: Any) -> datetime.date | None:
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _age_on_date(
    date_of_birth: datetime.date | None,
    on_date: datetime.date,
) -> int | None:
    if date_of_birth is None:
        return None
    return on_date.year - date_of_birth.year - (
        (on_date.month, on_date.day)
        < (date_of_birth.month, date_of_birth.day)
    )


def _normalise_sex(value: str | None) -> str | None:
    text = str(value or "").strip().lower()
    if text in {"male", "m", "man"}:
        return "male"
    if text in {"female", "f", "woman"}:
        return "female"
    return None


def age_grade_percent(
    *,
    sex: str | None,
    age: int | None,
    event_key: str,
    elapsed_seconds: float | None,
) -> float | None:
    """Return the 2020 road age-performance percentage."""
    normalised_sex = _normalise_sex(sex)
    seconds = _safe_float(elapsed_seconds)

    if normalised_sex is None or age is None or seconds is None or seconds <= 0:
        return None

    table = AGE_STANDARDS.get(normalised_sex, {}).get(event_key)
    index = age - STANDARD_MIN_AGE
    if table is None or index < 0 or index >= len(table):
        return None

    return (table[index] / seconds) * 100.0


def _distance_km(stored_distance: Any) -> float | None:
    distance = _safe_float(stored_distance)
    if distance is None or distance <= 0:
        return None
    return distance / 1000.0 if distance > 250.0 else distance


def _trimmed_mean(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) >= 10:
        trim = max(int(len(ordered) * 0.10), 1)
        ordered = ordered[trim:-trim]
    return statistics.fmean(ordered) if ordered else None


def _month_start(value: datetime.date) -> datetime.date:
    return value.replace(day=1)


def _add_months(value: datetime.date, months: int) -> datetime.date:
    month_index = value.year * 12 + value.month - 1 + months
    return datetime.date(month_index // 12, month_index % 12 + 1, 1)


def _chart_points(month_values: list[float | None]) -> tuple[float, ...]:
    known = [value for value in month_values if value is not None]
    if not known:
        return (50.0,) * 12

    filled = list(month_values)
    for index, value in enumerate(filled):
        if value is not None:
            continue
        left = next((filled[i] for i in range(index - 1, -1, -1) if filled[i] is not None), None)
        right = next((filled[i] for i in range(index + 1, len(filled)) if filled[i] is not None), None)
        filled[index] = left if left is not None else right

    numeric = [float(value) for value in filled if value is not None]
    minimum = min(numeric)
    maximum = max(numeric)
    spread = maximum - minimum
    if spread <= 0:
        return (50.0,) * len(filled)

    return tuple(
        round(82.0 - ((float(value) - minimum) / spread) * 62.0, 2)
        for value in filled
        if value is not None
    )


def _aerobic_development(
    profiles: list[RunProfile],
    *,
    reference_date: datetime.date,
) -> tuple[float | None, tuple[float, ...], int]:
    cutoff = reference_date - datetime.timedelta(days=365)
    scored: list[tuple[datetime.date, float]] = []

    for run in profiles:
        run_date = _as_date(run.activity_date)
        if run_date is None or run_date < cutoff or run_date > reference_date:
            continue
        if not is_easy_baseline_candidate(run):
            continue
        if not run.distance_km or run.distance_km < 4.0 or not run.avg_hr:
            continue

        try:
            performance = equivalent_performance(run)
            equivalent_pace = _safe_float(
                performance.equivalent_pace_seconds_per_km
            )
        except Exception:
            equivalent_pace = None

        if equivalent_pace is None or equivalent_pace <= 0:
            continue

        efficiency = (1000.0 / equivalent_pace) / float(run.avg_hr)
        scored.append((run_date, efficiency))

    recent = [
        score for run_date, score in scored
        if 0 <= (reference_date - run_date).days <= 90
    ]
    opening = [
        score for run_date, score in scored
        if 275 <= (reference_date - run_date).days <= 365
    ]
    recent_mean = _trimmed_mean(recent)
    opening_mean = _trimmed_mean(opening)

    trend = None
    if (
        recent_mean is not None
        and opening_mean is not None
        and opening_mean > 0
        and len(recent) >= 4
        and len(opening) >= 4
    ):
        trend = ((recent_mean / opening_mean) - 1.0) * 100.0

    current_month = _month_start(reference_date)
    months = [_add_months(current_month, offset) for offset in range(-11, 1)]
    monthly_values: list[float | None] = []

    for month in months:
        next_month = _add_months(month, 1)
        values = [
            score for run_date, score in scored
            if month <= run_date < next_month
        ]
        monthly_values.append(_trimmed_mean(values))

    return trend, _chart_points(monthly_values), len(scored)


def _activity_profiles(athlete_id: int, rows) -> list[RunProfile]:
    thresholds = get_effective_athlete_thresholds(athlete_id)
    profiles = []

    for row in rows:
        distance = _distance_km(row[4])
        moving = _safe_float(row[5])
        if distance is None or moving is None or moving <= 0:
            continue

        profiles.append(
            RunProfile(
                athlete_id=athlete_id,
                activity_date=row[1],
                title=row[2],
                sport_id=row[3],
                distance_km=distance,
                moving_time_seconds=moving,
                avg_hr=_safe_float(row[7]),
                run_max_hr=_safe_float(row[8]),
                elevation_m=_safe_float(row[9]),
                temperature_c=_safe_float(row[10]),
                humidity=_safe_float(row[11]),
                lt1_hr=thresholds.get("lt1_hr"),
                lt2_hr=thresholds.get("lt2_hr"),
                athlete_max_hr=thresholds.get("athlete_max_hr"),
            )
        )

    return profiles


def build_athlete_passport(
    athlete_id: int,
    *,
    reference_date: datetime.date | None = None,
) -> AthletePassportData | None:
    reference_date = reference_date or datetime.date.today()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT first_name, last_name, date_of_birth, sex
        FROM athletes
        WHERE id = ?
        """,
        (athlete_id,),
    )
    athlete = cursor.fetchone()

    if athlete is None:
        conn.close()
        return None

    cursor.execute(
        """
        SELECT
            id,
            activity_date,
            title,
            sport_id,
            distance_m,
            moving_time_s,
            elapsed_time_s,
            avg_hr,
            max_hr,
            elevation_up_m,
            temperature_c,
            humidity
        FROM activities
        WHERE athlete_id = ?
        ORDER BY activity_datetime DESC
        """,
        (athlete_id,),
    )
    all_rows = cursor.fetchall()
    conn.close()

    running_ids = {
        str(sport_id)
        for sport_id, role in get_athlete_sport_roles(athlete_id).items()
        if role == "running"
    }
    rows = [
        row for row in all_rows
        if str(row[3] or "") in running_ids
        and has_reliable_distance_and_pace(
            title=row[2],
            sport_id=str(row[3] or ""),
        )
    ]

    first_name = str(athlete[0] or "Athlete").strip()
    last_name = str(athlete[1] or "").strip()
    full_name = f"{first_name} {last_name}".strip()
    initials = "".join(
        part[0].upper() for part in (first_name, last_name) if part
    )[:2] or "PP"
    date_of_birth = _as_date(athlete[2])
    sex = _normalise_sex(athlete[3])
    current_age = _age_on_date(date_of_birth, reference_date)
    category_prefix = "M" if sex == "male" else "W" if sex == "female" else "A"
    category = (
        f"{category_prefix}{current_age} · Runner"
        if current_age is not None
        else "Runner"
    )

    cutoff = reference_date - datetime.timedelta(days=365)
    pbs = []
    age_grades_all = []
    age_grades_recent = []

    for event_key, label, target_m in EVENTS:
        candidates = []
        recent_candidates = []
        tolerance = max(target_m * 0.025, 120.0)

        for row in rows:
            run_date = _as_date(row[1])
            distance = _distance_km(row[4])
            moving = _safe_float(row[5])
            elapsed = _safe_float(row[6])

            if (
                run_date is None
                or run_date > reference_date
                or distance is None
                or moving is None
                or moving <= 0
                or elapsed is None
                or elapsed <= 0
            ):
                continue
            pace = moving / distance
            if pace < 150 or pace > 720:
                continue
            if abs(distance * 1000.0 - target_m) > tolerance:
                continue

            candidates.append(elapsed)
            if cutoff <= run_date <= reference_date:
                recent_candidates.append(elapsed)

            age_at_run = _age_on_date(date_of_birth, run_date)
            grade = age_grade_percent(
                sex=sex,
                age=age_at_run,
                event_key=event_key,
                elapsed_seconds=elapsed,
            )
            if grade is not None:
                age_grades_all.append(grade)
                if cutoff <= run_date <= reference_date:
                    age_grades_recent.append(grade)

        pbs.append(
            PassportPersonalBest(
                key=event_key,
                label=label,
                all_time_seconds=min(candidates) if candidates else None,
                last_12_months_seconds=(
                    min(recent_candidates) if recent_candidates else None
                ),
            )
        )

    profiles = _activity_profiles(athlete_id, rows)
    aerobic_trend, chart_points, aerobic_count = _aerobic_development(
        profiles,
        reference_date=reference_date,
    )

    return AthletePassportData(
        athlete_id=athlete_id,
        first_name=first_name,
        last_name=last_name,
        full_name=full_name,
        initials=initials,
        age=current_age,
        category=category,
        sex=sex,
        age_grade_all_time=max(age_grades_all) if age_grades_all else None,
        age_grade_last_12_months=(
            max(age_grades_recent) if age_grades_recent else None
        ),
        personal_bests=tuple(pbs),
        aerobic_trend_percent=aerobic_trend,
        aerobic_chart_points=chart_points,
        aerobic_run_count=aerobic_count,
    )
