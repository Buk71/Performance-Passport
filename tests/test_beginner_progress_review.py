import json
from types import SimpleNamespace
from unittest.mock import patch

from core.runner_journey import (
    JourneyProgressEvidence,
    get_couch_to_5k_successes_since_decision,
    prepare_couch_to_5k_evidence,
    preview_couch_to_5k_progress,
)


def _journey(week=4, stage="run_blocks_5"):
    return SimpleNamespace(
        id=12,
        athlete_id=99,
        journey_type="couch_to_5k",
        current_stage=stage,
        preferences={"current_week": week},
    )


class _Conn:
    def __init__(self, rows):
        self.rows = rows
    def execute(self, *_args, **_kwargs):
        return self
    def fetchall(self):
        return self.rows
    def close(self):
        pass


def test_first_controlled_success_is_counted_as_one():
    evidence = JourneyProgressEvidence(
        completed_as_planned=True,
        perceived_difficulty="Comfortable",
    )
    with (
        patch("core.runner_journey.get_active_runner_journey", return_value=_journey()),
        patch("core.runner_journey.get_connection", return_value=_Conn([])),
    ):
        prepared = prepare_couch_to_5k_evidence(99, evidence)
    assert prepared.sessions_completed_since_decision == 1


def test_previous_controlled_hold_contributes_to_second_success():
    prior = json.dumps({
        "completed_as_planned": True,
        "perceived_difficulty": "Comfortable",
        "pain_or_concerning_symptoms": False,
        "sessions_completed_since_decision": 1,
        "week_before": 4,
        "week_after": 4,
    })
    rows = [("progress_review", "hold", prior)]
    with (
        patch("core.runner_journey.get_active_runner_journey", return_value=_journey()),
        patch("core.runner_journey.get_connection", return_value=_Conn(rows)),
    ):
        assert get_couch_to_5k_successes_since_decision(99) == 1
        prepared = prepare_couch_to_5k_evidence(
            99,
            JourneyProgressEvidence(
                completed_as_planned=True,
                perceived_difficulty="Moderate",
            ),
        )
    assert prepared.sessions_completed_since_decision == 2


def test_repeat_resets_success_evidence_window():
    prior = json.dumps({
        "completed_as_planned": False,
        "perceived_difficulty": "Hard",
        "pain_or_concerning_symptoms": False,
        "week_before": 4,
        "week_after": 4,
    })
    rows = [
        ("progress_review", "repeat", prior),
        ("progress_review", "hold", json.dumps({
            "completed_as_planned": True,
            "perceived_difficulty": "Comfortable",
            "week_before": 4,
            "week_after": 4,
        })),
    ]
    with (
        patch("core.runner_journey.get_active_runner_journey", return_value=_journey()),
        patch("core.runner_journey.get_connection", return_value=_Conn(rows)),
    ):
        assert get_couch_to_5k_successes_since_decision(99) == 0


def test_preview_recommends_progress_after_second_controlled_success():
    prior = json.dumps({
        "completed_as_planned": True,
        "perceived_difficulty": "Comfortable",
        "pain_or_concerning_symptoms": False,
        "week_before": 4,
        "week_after": 4,
    })
    with (
        patch("core.runner_journey.get_active_runner_journey", return_value=_journey()),
        patch("core.runner_journey.get_connection", return_value=_Conn([
            ("progress_review", "hold", prior),
        ])),
    ):
        decision, evidence = preview_couch_to_5k_progress(
            99,
            JourneyProgressEvidence(
                completed_as_planned=True,
                perceived_difficulty="Comfortable",
            ),
        )
    assert evidence.sessions_completed_since_decision == 2
    assert decision.decision == "progress"
    assert decision.week_after == 5


def test_preview_does_not_write_to_database():
    with (
        patch("core.runner_journey.get_active_runner_journey", return_value=_journey()),
        patch("core.runner_journey.get_connection", return_value=_Conn([])),
    ):
        decision, _ = preview_couch_to_5k_progress(
            99,
            JourneyProgressEvidence(
                completed_as_planned=False,
                perceived_difficulty="Moderate",
            ),
        )
    assert decision.decision == "repeat"
