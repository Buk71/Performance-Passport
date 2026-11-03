from core.runner_journey import JourneyProgressEvidence, prepare_couch_to_5k_evidence
from unittest.mock import patch


def test_activity_metadata_survives_evidence_preparation():
    evidence = JourneyProgressEvidence(
        completed_as_planned=True,
        perceived_difficulty="Comfortable",
        activity_id=123,
        activity_date="2026-09-05",
        activity_distance_km=3.4,
        activity_moving_time_s=1900,
    )
    with patch(
        "core.runner_journey.get_couch_to_5k_successes_since_decision",
        return_value=1,
    ):
        prepared = prepare_couch_to_5k_evidence(99, evidence)

    assert prepared.sessions_completed_since_decision == 2
    assert prepared.activity_id == 123
    assert prepared.activity_date == "2026-09-05"
    assert prepared.activity_distance_km == 3.4
    assert prepared.activity_moving_time_s == 1900
