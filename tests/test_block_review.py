import datetime
import sqlite3
from types import SimpleNamespace

import pytest

from core.block_review import (
    apply_accepted_block_reviews,
    build_recovery_review,
    build_review_key,
    latest_block_review_action,
    list_block_review_actions,
    save_block_review_action,
)
from core.database import create_block_review_actions_table
from core.operational_block import (
    OperationalActivity,
    _load_operational_activities,
    build_operational_block_week,
    compose_operational_week,
)


def _database(path):
    connection = sqlite3.connect(path)
    create_block_review_actions_table(connection.cursor())
    connection.commit()
    connection.close()


def _proposal():
    return build_recovery_review(
        athlete_id=1,
        training_block_id=9,
        week_number=2,
        target_date="2026-08-18",
        planned_type="Threshold",
        planned_detail="6 mi total",
        planned_family="threshold",
        reason="A demanding run was completed within one day.",
    )


def _plan():
    return {
        "weeks": [{
            "week_number": 2,
            "start_date": "2026-08-17",
            "end_date": "2026-08-23",
            "target_miles": 30.0,
            "phase": "Build",
            "emphasis": "Threshold rhythm",
            "days": [
                {"day": "Monday", "session_type": "Rest", "detail": "Rest", "is_hard": False},
                {"day": "Tuesday", "session_type": "Threshold", "detail": "6 mi total", "is_hard": True},
                {"day": "Wednesday", "session_type": "Recovery", "detail": "4 mi easy", "is_hard": False},
                {"day": "Thursday", "session_type": "Easy", "detail": "5 mi easy", "is_hard": False},
                {"day": "Friday", "session_type": "Rest", "detail": "Rest", "is_hard": False},
                {"day": "Saturday", "session_type": "Easy", "detail": "5 mi easy", "is_hard": False},
                {"day": "Sunday", "session_type": "Long run", "detail": "10 mi", "is_hard": False},
            ],
        }]
    }


def _unexpected_quality():
    return OperationalActivity(
        activity_id=41,
        activity_date="2026-08-17",
        title="Unexpected hard session",
        family="quality",
        family_label="Structured workout",
        distance_miles=5.0,
        moving_time_s=2400.0,
        confidence=0.9,
        distance_reliable=True,
    )


def test_review_key_is_deterministic_and_scoped_to_commitment():
    first = build_review_key(
        training_block_id=9,
        week_number=2,
        target_date="2026-08-18",
        review_type="protect_adjacent_hard_day",
        original_session_type="Threshold",
        original_detail="6 mi total",
    )
    second = build_review_key(
        training_block_id=9,
        week_number=2,
        target_date="2026-08-18",
        review_type="protect_adjacent_hard_day",
        original_session_type="Threshold",
        original_detail="6 mi total",
    )
    different = build_review_key(
        training_block_id=9,
        week_number=2,
        target_date="2026-08-19",
        review_type="protect_adjacent_hard_day",
        original_session_type="Threshold",
        original_detail="6 mi total",
    )
    changed_commitment = build_review_key(
        training_block_id=9,
        week_number=2,
        target_date="2026-08-18",
        review_type="protect_adjacent_hard_day",
        original_session_type="VO₂ session",
        original_detail="8 × 500m",
    )

    assert first == second
    assert first != different
    assert first != changed_commitment


def test_actions_are_append_only_and_latest_decision_wins(monkeypatch, tmp_path):
    path = tmp_path / "reviews.db"
    _database(path)
    monkeypatch.setattr(
        "core.block_review.get_connection",
        lambda: sqlite3.connect(path),
    )
    proposal = _proposal()
    save_block_review_action(proposal, decision="Defer", reason="Review tomorrow")
    save_block_review_action(proposal, decision="Accept", reason="Still tired")

    actions = list_block_review_actions(1, 9, review_key=proposal.review_key)
    latest = latest_block_review_action(1, 9, proposal.review_key)

    assert [action.decision for action in actions] == ["Defer", "Accept"]
    assert latest.decision == "Accept"
    assert latest.reason == "Still tired"
    assert list_block_review_actions(2, 9) == ()


def test_accepted_review_overlays_copy_and_preserves_approved_plan(monkeypatch, tmp_path):
    path = tmp_path / "reviews.db"
    _database(path)
    monkeypatch.setattr(
        "core.block_review.get_connection",
        lambda: sqlite3.connect(path),
    )
    approved = _plan()
    proposal = _proposal()
    save_block_review_action(proposal, decision="Accept", reason="Protect recovery")

    effective = apply_accepted_block_reviews(
        approved,
        athlete_id=1,
        training_block_id=9,
    )

    assert approved["weeks"][0]["days"][1]["session_type"] == "Threshold"
    assert effective["weeks"][0]["days"][1]["session_type"] == "Recovery / easy running"
    assert effective["weeks"][0]["days"][1]["approved_plan_session_type"] == "Threshold"


def test_later_reject_removes_previously_accepted_overlay(monkeypatch, tmp_path):
    path = tmp_path / "reviews.db"
    _database(path)
    monkeypatch.setattr(
        "core.block_review.get_connection",
        lambda: sqlite3.connect(path),
    )
    proposal = _proposal()
    save_block_review_action(proposal, decision="Accept")
    save_block_review_action(proposal, decision="Reject", reason="Recovered normally")

    effective = apply_accepted_block_reviews(
        _plan(),
        athlete_id=1,
        training_block_id=9,
    )

    assert effective["weeks"][0]["days"][1]["session_type"] == "Threshold"


def test_unsupported_decision_is_rejected_before_database_write():
    proposal = SimpleNamespace()
    with pytest.raises(ValueError, match="Unsupported Block Review decision"):
        save_block_review_action(proposal, decision="Maybe")


def test_operational_disruption_creates_review_without_changing_plan(monkeypatch, tmp_path):
    path = tmp_path / "reviews.db"
    _database(path)
    monkeypatch.setattr(
        "core.block_review.get_connection",
        lambda: sqlite3.connect(path),
    )
    saved = SimpleNamespace(plan=_plan())
    monkeypatch.setattr(
        "core.operational_block.get_active_training_block",
        lambda athlete_id: SimpleNamespace(id=9, name="Test block"),
    )
    monkeypatch.setattr(
        "core.operational_block.get_training_block_design",
        lambda block_id, athlete_id: saved,
    )
    monkeypatch.setattr(
        "core.operational_block._load_operational_activities",
        lambda athlete_id, start, end: (_unexpected_quality(),),
    )

    week = build_operational_block_week(1, today=datetime.date(2026, 8, 17))

    assert week.review is not None
    assert week.review.latest_decision is None
    assert week.next_run.adapted is True
    assert week.next_run.planned_type == "Threshold"
    assert saved.plan["weeks"][0]["days"][1]["session_type"] == "Threshold"


def test_accepted_review_becomes_effective_for_operational_consumers(monkeypatch, tmp_path):
    path = tmp_path / "reviews.db"
    _database(path)
    monkeypatch.setattr(
        "core.block_review.get_connection",
        lambda: sqlite3.connect(path),
    )
    saved = SimpleNamespace(plan=_plan())
    monkeypatch.setattr(
        "core.operational_block.get_active_training_block",
        lambda athlete_id: SimpleNamespace(id=9, name="Test block"),
    )
    monkeypatch.setattr(
        "core.operational_block.get_training_block_design",
        lambda block_id, athlete_id: saved,
    )
    monkeypatch.setattr(
        "core.operational_block._load_operational_activities",
        lambda athlete_id, start, end: (_unexpected_quality(),),
    )
    original = build_operational_block_week(1, today=datetime.date(2026, 8, 17))
    save_block_review_action(original.review, decision="Accept", reason="Protect Tuesday")

    effective = build_operational_block_week(1, today=datetime.date(2026, 8, 17))

    assert effective.review.latest_decision == "Accept"
    assert effective.next_run.session_type == "Recovery / easy running"
    assert effective.next_run.adapted is False
    assert "accepted Block Review" in effective.source
    assert saved.plan["weeks"][0]["days"][1]["session_type"] == "Threshold"


def test_real_jo_block_has_no_review_before_its_first_week():
    week = build_operational_block_week(3, today=datetime.date(2026, 8, 14))

    assert week is not None
    assert week.state == "Upcoming"
    assert week.review is None


def test_real_richard_quality_session_triggers_adjacent_hard_day_protection():
    real_activities = _load_operational_activities(
        1,
        datetime.date(2026, 8, 5),
        datetime.date(2026, 8, 5),
    )
    blizard = next(
        activity
        for activity in real_activities
        if "Blizard session" in activity.title
    )
    plan = {
        "weeks": [{
            "week_number": 1,
            "start_date": "2026-08-03",
            "end_date": "2026-08-09",
            "target_miles": 30.0,
            "phase": "Build",
            "emphasis": "Quality rhythm",
            "days": [
                {"day": "Monday", "session_type": "Rest", "detail": "Rest", "is_hard": False},
                {"day": "Tuesday", "session_type": "Easy", "detail": "5 mi easy", "is_hard": False},
                {"day": "Wednesday", "session_type": "Rest", "detail": "Rest", "is_hard": False},
                {"day": "Thursday", "session_type": "Threshold", "detail": "6 mi total", "is_hard": True},
                {"day": "Friday", "session_type": "Recovery", "detail": "4 mi easy", "is_hard": False},
                {"day": "Saturday", "session_type": "Easy", "detail": "5 mi easy", "is_hard": False},
                {"day": "Sunday", "session_type": "Long run", "detail": "10 mi", "is_hard": False},
            ],
        }]
    }

    week = compose_operational_week(
        athlete_id=1,
        training_block_id=9,
        block_name="Real-evidence review fixture",
        plan=plan,
        activities=(blizard,),
        today=datetime.date(2026, 8, 5),
    )

    assert blizard.family == "quality"
    assert week.next_run.day == "Thursday"
    assert week.next_run.planned_type == "Threshold"
    assert week.next_run.adapted is True
