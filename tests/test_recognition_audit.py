"""Golden real-athlete checks for the read-only recognition audit."""

from __future__ import annotations

from dataclasses import replace
import json

import pytest

from core.database import (
    clear_activity_override,
    get_connection,
    save_activity_override,
)
from core.recognition_audit import (
    AUDIT_MODEL_VERSION,
    audit_activity,
    audit_activity_facts,
    build_recognition_audit,
)
from tests.test_classification_integration import _real_activity_facts
from ui.diagnostics import build_recognition_audit_html


JO_LATEST_INTERVALS = (
    "U0.400|2:27-U1.000|4:27-U0.165|2:00-U1.000|4:21-"
    "U0.163|2:00-U1.000|4:17-U0.165|2:00-U1.000|4:20-"
    "U0.174|2:00-U1.000|4:23-U0.177|2:00-U1.000|4:31-"
    "U0.149|2:00-U1.150|6:39"
)


def test_jo_real_five_by_one_k_is_flagged_without_changing_live_confidence():
    result = audit_activity(3, 5119)

    assert result.audit_status == "needs_review"
    assert result.issue_key == "missed_workout"
    assert result.review_priority == "high"
    assert result.proposed_session_type == "interval_workout"
    assert result.current_confidence < 0.70
    assert result.interval_evidence.work_count == 5
    assert result.interval_evidence.credible_recovery_count == 4
    assert result.interval_evidence.trustworthy_intervals is True


def test_jo_latest_six_by_one_k_is_identified_from_general_lap_rules():
    facts = replace(
        _real_activity_facts(5119),
        activity_id=990052,
        activity_date="2026-08-18",
        title="",
        distance_km=8.54,
        moving_time_s=2844.0,
        elapsed_time_s=2844.0,
        avg_hr=155.0,
        max_hr=180.0,
        raw_json_text=json.dumps({"splits": JO_LATEST_INTERVALS}),
    )

    result = audit_activity_facts(facts, override={})

    assert result.issue_key == "missed_workout"
    assert result.interval_evidence.work_count == 6
    assert result.interval_evidence.credible_recovery_count == 5
    assert result.interval_evidence.work_distance_km == 6.0


def test_paul_easy_run_with_strides_stays_out_of_workout_evidence():
    result = audit_activity(4, 10599)

    assert result.current_session_type == "easy_with_strides"
    assert result.proposed_session_type == "easy_with_strides"
    assert result.audit_status == "protected"
    assert result.issue_key == "protected_strides"
    assert result.needs_review is False


def test_paul_real_ten_k_remains_race_evidence_not_threshold():
    result = audit_activity(4, 9772)

    assert result.current_session_type == "race"
    assert result.proposed_session_type == "race"
    assert result.audit_status == "protected"
    assert result.issue_key == "protected_race"
    assert "threshold" in result.recommendation.lower()


def test_richard_real_trail_auto_laps_are_flagged_as_false_workout():
    result = audit_activity(1, 3737)

    assert result.current_session_type == "interval_workout"
    assert result.proposed_session_type == "long_run"
    assert result.issue_key == "false_workout_auto_laps"
    assert result.interval_evidence.repeated_auto_laps is True
    assert result.interval_evidence.credible_recovery_count == 0


def test_richard_genuine_ladder_stays_verified():
    result = audit_activity(1, 3177)

    assert result.current_session_type == "interval_workout"
    assert result.proposed_session_type == "interval_workout"
    assert result.audit_status == "verified"
    assert result.needs_review is False


def test_richard_latest_historical_long_run_is_protected():
    result = audit_activity(1, 9366)

    assert result.proposed_session_type == "long_run"
    assert result.audit_status == "protected"
    assert result.issue_key == "protected_long_run"


def test_reference_set_is_athlete_specific_and_balances_real_examples():
    report = build_recognition_audit(
        1,
        activity_ids=(3177, 3737, 9366, 5119, 9772),
    )

    assert report.athlete_name == "Richard Burke"
    assert report.total_running_activities == 3
    assert report.likely_false_workout_count == 1
    assert report.reviewed_count == 1
    assert report.review_queue[0].activity_id == 3737
    assert {entry.activity_id for entry in report.reference_cases} == {
        3177, 3737, 9366
    }
    assert report.model_version == AUDIT_MODEL_VERSION
    assert report.changes_live_classification is False


def test_manual_coach_correction_takes_priority_in_audit():
    try:
        save_activity_override(3, 5119, session_intent="workout")
        result = audit_activity(3, 5119)

        assert result.audit_status == "manual"
        assert result.manual_override is True
        assert result.needs_review is False
    finally:
        clear_activity_override(3, 5119)


def test_audit_does_not_change_saved_activity_evidence():
    connection = get_connection()
    before = connection.execute(
        "SELECT title, raw_json, avg_hr FROM activities WHERE id = 5119"
    ).fetchone()
    override_count = connection.execute(
        "SELECT COUNT(*) FROM athlete_activity_overrides"
    ).fetchone()[0]
    connection.close()

    report = build_recognition_audit(3, activity_ids=(5119,))

    connection = get_connection()
    after = connection.execute(
        "SELECT title, raw_json, avg_hr FROM activities WHERE id = 5119"
    ).fetchone()
    subsequent_override_count = connection.execute(
        "SELECT COUNT(*) FROM athlete_activity_overrides"
    ).fetchone()[0]
    connection.close()

    assert report.changes_live_classification is False
    assert before == after
    assert override_count == subsequent_override_count


def test_audit_page_clearly_labels_findings_as_a_read_only_preview():
    report = build_recognition_audit(3, activity_ids=(5119,))

    markup = build_recognition_audit_html(report)

    assert "HISTORICAL RECOGNITION AUDIT" in markup
    assert "READ-ONLY PREVIEW" in markup
    assert "Joanne Burke" in markup
    assert "LIKELY MISSED WORKOUTS" in markup
    assert "Nothing here changes your history" in markup


def test_audit_rejects_activities_owned_by_another_athlete():
    try:
        audit_activity(1, 5119)
    except ValueError as error:
        assert "does not belong" in str(error)
    else:
        raise AssertionError("Cross-athlete audit access should be rejected.")


def test_richard_confirmed_stopped_watch_intervals_are_not_demoted_to_easy():
    result = audit_activity(1, 3742)

    assert result.proposed_session_type == "interval_workout"
    assert result.issue_key == "missed_workout"
    assert result.interval_evidence.stopped_watch_work_count >= 5
    assert result.interval_evidence.trustworthy_intervals is True


@pytest.mark.parametrize(
    "activity_id, expected_distance",
    ((3559, 2.96), (3493, 3.21)),
)
def test_richard_long_repetitions_are_recovered_from_stopped_watch_boundaries(
    activity_id,
    expected_distance,
):
    result = audit_activity(1, activity_id)

    assert result.proposed_session_type == "interval_workout"
    assert result.issue_key == "missed_workout"
    assert result.interval_evidence.boundary_block_count == 3
    assert result.interval_evidence.boundary_block_distance_km == pytest.approx(
        expected_distance,
        abs=0.04,
    )


@pytest.mark.parametrize("activity_id", (3573, 3496))
def test_richard_confirmed_thirty_second_pickups_are_light_quality_only(activity_id):
    result = audit_activity(1, activity_id)

    assert result.proposed_session_type == "easy_with_pickups"
    assert result.proposed_label == "Easy run with pickups"
    assert result.audit_status == "protected"
    assert result.issue_key == "protected_pickups"
    assert result.interval_evidence.pickup_count >= 5
    assert result.interval_evidence.trustworthy_intervals is False


def test_jo_short_fast_efforts_with_long_easy_recoveries_are_a_real_session():
    result = audit_activity(3, 5559)

    assert result.proposed_session_type == "alternating_workout"
    assert result.proposed_label == "Alternating workout"
    assert result.issue_key == "missed_workout"
    assert result.interval_evidence.long_recovery_alternation_count == 4


def test_jo_equal_distance_on_off_session_is_not_ordinary_auto_laps():
    result = audit_activity(3, 5299)

    assert result.proposed_session_type == "alternating_workout"
    assert result.issue_key == "missed_workout"
    assert result.interval_evidence.equal_distance_alternation_count >= 3


@pytest.mark.parametrize("activity_id", (9876, 10443))
def test_paul_stopped_kilometre_auto_laps_are_not_workout_evidence(activity_id):
    result = audit_activity(4, activity_id)

    assert result.interval_evidence.stopped_watch_work_count == 0
    assert result.interval_evidence.trustworthy_intervals is False
    assert result.proposed_session_type in {"easy_run", "long_run"}


@pytest.mark.parametrize("activity_id", (5474, 5399, 5391, 5351, 5312))
def test_jo_confirmed_workouts_remain_recognised_across_multiple_real_patterns(
    activity_id,
):
    result = audit_activity(3, activity_id)

    assert result.proposed_session_type == "interval_workout"
    assert result.interval_evidence.trustworthy_intervals is True


@pytest.mark.parametrize(
    "athlete_id, activity_id, expected_type",
    (
        (1, 9360, "easy_run"),
        (1, 3737, "long_run"),
        (1, 3590, "long_run"),
        (3, 5453, "easy_run"),
        (3, 5447, "easy_run"),
        (3, 5403, "long_run"),
    ),
)
def test_confirmed_easy_and_long_controls_are_not_promoted_by_new_patterns(
    athlete_id,
    activity_id,
    expected_type,
):
    result = audit_activity(athlete_id, activity_id)

    assert result.proposed_session_type == expected_type
    assert result.issue_key == "false_workout_auto_laps"


def test_manual_pickup_override_is_supported_by_shared_classification():
    try:
        save_activity_override(1, 3573, session_intent="easy_with_pickups")
        result = audit_activity(1, 3573)

        assert result.audit_status == "manual"
        assert result.current_session_type == "easy_with_pickups"
        assert result.proposed_session_type == "easy_with_pickups"
    finally:
        clear_activity_override(1, 3573)


def test_audit_summary_counts_pickups_separately_from_prediction_workouts():
    report = build_recognition_audit(1, activity_ids=(3573, 3496, 3559))

    assert report.protected_pickups_count == 2
    assert report.likely_missed_workout_count == 1
    assert report.likely_false_workout_count == 0
