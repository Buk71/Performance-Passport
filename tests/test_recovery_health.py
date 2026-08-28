import datetime

import core.database as database
from core.recovery_coach import (
    RecoveryCheckIn,
    RecoveryHealthSignal,
    build_recovery_health_signal,
    compose_recovery_coach,
)
from core.runalyze_health import RunalyzeHealthRecord, import_runalyze_health_records
from tests.test_recovery_coach import _progress, _week


TODAY = datetime.date(2026, 8, 27)


def _database(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "health-signal.db")
    connection = database.get_connection()
    cursor = connection.cursor()
    database.create_base_tables(cursor)
    database.create_athlete_health_daily_table(cursor)
    cursor.execute("INSERT INTO athletes (id, first_name, last_name) VALUES (1, 'Richard', 'Burke')")
    connection.commit()
    connection.close()


def _health(*, hrv_status="Within recent HRV range", rhr_status="Resting HR is broadly stable"):
    return RecoveryHealthSignal(
        available=True,
        latest_date=TODAY.isoformat(),
        source="Runalyze Health Csv",
        hrv_metric_code="2",
        hrv_recent=58.0,
        hrv_baseline=58.5,
        hrv_change_percent=-0.9 if hrv_status == "Within recent HRV range" else -15.0,
        hrv_status=hrv_status,
        hrv_recent_count=7,
        hrv_baseline_count=28,
        resting_hr_recent=51.0,
        resting_hr_baseline=50.0,
        resting_hr_change=1.0 if rhr_status == "Resting HR is broadly stable" else 4.0,
        resting_hr_status=rhr_status,
        sleep_recent_minutes=495.0,
        sleep_baseline_minutes=500.0,
        sleep_change_minutes=-5.0,
        sleep_quality_recent=81.0,
        sleep_status="Sleep duration is broadly stable",
        confidence="Strong",
        explanation="Seven recent days versus the preceding 28-day baseline.",
    )


def test_health_signal_uses_seven_days_against_the_preceding_28(tmp_path, monkeypatch):
    _database(tmp_path, monkeypatch)
    records = []
    for offset in range(35):
        day = TODAY - datetime.timedelta(days=34 - offset)
        recent = day >= TODAY - datetime.timedelta(days=6)
        records.append(
            RunalyzeHealthRecord(
                health_date=day.isoformat(),
                file_kind="combined_health",
                hrv_value=60 if recent else 50,
                hrv_metric_code="2",
                hrv_measurement_type="2",
                hrv_source_code="3",
                resting_hr=50 if recent else 52,
                sleep_duration_min=500 if recent else 480,
            )
        )
    import_runalyze_health_records(records, athlete_id=1)
    signal = build_recovery_health_signal(1, today=TODAY)

    assert signal.hrv_recent == 60
    assert signal.hrv_baseline == 50
    assert signal.hrv_change_percent == 20
    assert signal.hrv_recent_count == 7
    assert signal.hrv_baseline_count == 28
    assert signal.confidence == "Strong"


def test_low_hrv_and_elevated_resting_hr_are_transparent_cautions_not_a_score():
    detail = compose_recovery_coach(
        athlete_id=1,
        athlete_name="Richard Burke",
        progress=_progress(),
        week=_week(),
        checkin=None,
        today=TODAY,
        health=_health(
            hrv_status="Below recent HRV baseline",
            rhr_status="Resting HR is above baseline",
        ),
    )

    assert any("HRV" in caution for caution in detail.cautions)
    assert any("resting HR" in caution for caution in detail.cautions)
    assert "Protect recovery" in detail.headline
    assert any("never silently changes" in item for item in detail.limitations)


def test_stable_connected_health_is_supporting_context_not_permission_for_extra_load():
    detail = compose_recovery_coach(
        athlete_id=1,
        athlete_name="Richard Burke",
        progress=_progress(),
        week=_week(),
        checkin=None,
        today=TODAY,
        health=_health(),
    )

    assert any("health trends" in strength.lower() for strength in detail.strengths)
    assert any("not permission" in priority.lower() for priority in detail.priorities)
    assert any("no hidden" in item.lower() for item in detail.limitations)


def test_elevated_soreness_replaces_stretching_with_a_pain_free_reset():
    checkin = RecoveryCheckIn(
        athlete_id=1,
        checkin_date=TODAY.isoformat(),
        sleep_quality=3,
        fatigue=3,
        soreness=4,
        motivation=4,
        notes="Focal calf soreness",
    )
    detail = compose_recovery_coach(
        athlete_id=1,
        athlete_name="Richard Burke",
        progress=_progress(),
        week=_week(),
        checkin=checkin,
        today=TODAY,
    )

    assert detail.mobility_routines[0].title == "Pain-free reset"
    assert all("stretch" not in move.lower() for move in detail.mobility_routines[0].exercises)
    assert "sharp, focal or worsening" in detail.mobility_routines[0].caution

