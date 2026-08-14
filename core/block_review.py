"""Deliberate, auditable review of athlete-approved Training Blocks.

The saved design remains the factual plan. Review actions are append-only
events and accepted recommendations are applied as a transparent read-time
overlay. A later Defer or Reject event therefore removes the overlay without
rewriting or losing the original commitment.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
import datetime
import hashlib
import json
from typing import Any

from core.database import create_block_review_actions_table, get_connection


REVIEW_DECISIONS = ("Accept", "Defer", "Reject")
RECOVERY_REVIEW_TYPE = "protect_adjacent_hard_day"


@dataclass(frozen=True)
class SessionCommitment:
    session_type: str
    detail: str
    family: str
    is_hard: bool


@dataclass(frozen=True)
class BlockReviewAction:
    id: int
    athlete_id: int
    training_block_id: int
    review_key: str
    review_type: str
    week_number: int
    target_date: str
    decision: str
    original: SessionCommitment
    proposed: SessionCommitment
    evidence: str
    reason: str | None
    created_at: str | None


@dataclass(frozen=True)
class BlockReviewProposal:
    athlete_id: int
    training_block_id: int
    review_key: str
    review_type: str
    week_number: int
    target_date: str
    title: str
    evidence: str
    original: SessionCommitment
    proposed: SessionCommitment
    latest_decision: str | None = None
    latest_reason: str | None = None
    latest_created_at: str | None = None

    @property
    def is_accepted(self) -> bool:
        return self.latest_decision == "Accept"


def _date(value: Any) -> datetime.date | None:
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _commitment_to_dict(commitment: SessionCommitment) -> dict[str, Any]:
    return {
        "session_type": commitment.session_type,
        "detail": commitment.detail,
        "family": commitment.family,
        "is_hard": commitment.is_hard,
    }


def _commitment_from_dict(value: dict[str, Any]) -> SessionCommitment:
    return SessionCommitment(
        session_type=str(value.get("session_type") or "Unspecified"),
        detail=str(value.get("detail") or ""),
        family=str(value.get("family") or "easy"),
        is_hard=bool(value.get("is_hard")),
    )


def build_review_key(
    *,
    training_block_id: int,
    week_number: int,
    target_date: str,
    review_type: str,
    original_session_type: str,
    original_detail: str,
) -> str:
    identity = (
        f"{training_block_id}|{week_number}|{target_date}|{review_type}|"
        f"{original_session_type}|{original_detail}"
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    return f"block-review-{digest}"


def _action_from_row(row) -> BlockReviewAction:
    return BlockReviewAction(
        id=int(row[0]),
        athlete_id=int(row[1]),
        training_block_id=int(row[2]),
        review_key=str(row[3]),
        review_type=str(row[4]),
        week_number=int(row[5]),
        target_date=str(row[6]),
        decision=str(row[7]),
        original=_commitment_from_dict(json.loads(row[8])),
        proposed=_commitment_from_dict(json.loads(row[9])),
        evidence=str(row[10]),
        reason=row[11],
        created_at=row[12],
    )


def list_block_review_actions(
    athlete_id: int,
    training_block_id: int,
    *,
    review_key: str | None = None,
) -> tuple[BlockReviewAction, ...]:
    connection = get_connection()
    cursor = connection.cursor()
    create_block_review_actions_table(cursor)
    if review_key is None:
        cursor.execute(
            """
            SELECT id, athlete_id, training_block_id, review_key, review_type,
                   week_number, target_date, decision, original_json,
                   proposed_json, evidence, reason, created_at
            FROM block_review_actions
            WHERE athlete_id = ? AND training_block_id = ?
            ORDER BY id
            """,
            (athlete_id, training_block_id),
        )
    else:
        cursor.execute(
            """
            SELECT id, athlete_id, training_block_id, review_key, review_type,
                   week_number, target_date, decision, original_json,
                   proposed_json, evidence, reason, created_at
            FROM block_review_actions
            WHERE athlete_id = ? AND training_block_id = ? AND review_key = ?
            ORDER BY id
            """,
            (athlete_id, training_block_id, review_key),
        )
    rows = cursor.fetchall()
    connection.close()
    return tuple(_action_from_row(row) for row in rows)


def latest_block_review_action(
    athlete_id: int,
    training_block_id: int,
    review_key: str,
) -> BlockReviewAction | None:
    actions = list_block_review_actions(
        athlete_id,
        training_block_id,
        review_key=review_key,
    )
    return actions[-1] if actions else None


def build_recovery_review(
    *,
    athlete_id: int,
    training_block_id: int,
    week_number: int,
    target_date: str | None,
    planned_type: str,
    planned_detail: str,
    planned_family: str,
    reason: str,
) -> BlockReviewProposal | None:
    """Build the first v0.32 review type from existing operational evidence."""
    if _date(target_date) is None:
        return None
    review_key = build_review_key(
        training_block_id=training_block_id,
        week_number=week_number,
        target_date=str(target_date),
        review_type=RECOVERY_REVIEW_TYPE,
        original_session_type=planned_type,
        original_detail=planned_detail,
    )
    latest = latest_block_review_action(
        athlete_id,
        training_block_id,
        review_key,
    )
    proposal = BlockReviewProposal(
        athlete_id=athlete_id,
        training_block_id=training_block_id,
        review_key=review_key,
        review_type=RECOVERY_REVIEW_TYPE,
        week_number=week_number,
        target_date=str(target_date),
        title="Protect recovery before the next hard commitment",
        evidence=reason,
        original=SessionCommitment(
            session_type=planned_type,
            detail=planned_detail,
            family=planned_family,
            is_hard=True,
        ),
        proposed=SessionCommitment(
            session_type="Recovery / easy running",
            detail=(
                "Replace this one hard commitment with recovery or genuinely "
                "easy running. The original session remains in the approved plan."
            ),
            family="recovery",
            is_hard=False,
        ),
    )
    if latest is None:
        return proposal
    return replace(
        proposal,
        latest_decision=latest.decision,
        latest_reason=latest.reason,
        latest_created_at=latest.created_at,
    )


def save_block_review_action(
    proposal: BlockReviewProposal,
    *,
    decision: str,
    reason: str | None = None,
) -> int:
    if decision not in REVIEW_DECISIONS:
        raise ValueError(f"Unsupported Block Review decision: {decision}")
    clean_reason = str(reason or "").strip() or None
    connection = get_connection()
    cursor = connection.cursor()
    create_block_review_actions_table(cursor)
    cursor.execute(
        """
        INSERT INTO block_review_actions (
            athlete_id, training_block_id, review_key, review_type,
            week_number, target_date, decision, original_json,
            proposed_json, evidence, reason
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            proposal.athlete_id,
            proposal.training_block_id,
            proposal.review_key,
            proposal.review_type,
            proposal.week_number,
            proposal.target_date,
            decision,
            json.dumps(_commitment_to_dict(proposal.original), sort_keys=True),
            json.dumps(_commitment_to_dict(proposal.proposed), sort_keys=True),
            proposal.evidence,
            clean_reason,
        ),
    )
    action_id = int(cursor.lastrowid)
    connection.commit()
    connection.close()
    return action_id


def _latest_actions_by_review(
    athlete_id: int,
    training_block_id: int,
) -> dict[str, BlockReviewAction]:
    latest: dict[str, BlockReviewAction] = {}
    for action in list_block_review_actions(athlete_id, training_block_id):
        latest[action.review_key] = action
    return latest


def apply_accepted_block_reviews(
    plan: dict[str, Any],
    *,
    athlete_id: int,
    training_block_id: int,
) -> dict[str, Any]:
    """Return the effective plan while preserving the supplied factual plan."""
    effective = deepcopy(plan)
    accepted = tuple(
        action
        for action in _latest_actions_by_review(
            athlete_id,
            training_block_id,
        ).values()
        if action.decision == "Accept"
    )
    if not accepted:
        return effective
    for action in accepted:
        target = _date(action.target_date)
        if target is None:
            continue
        for week in effective.get("weeks") or ():
            start = _date(week.get("start_date"))
            if start is None:
                continue
            day_index = (target - start).days
            days = week.get("days") or ()
            if day_index < 0 or day_index >= len(days):
                continue
            day = days[day_index]
            day["session_type"] = action.proposed.session_type
            day["detail"] = action.proposed.detail
            day["is_hard"] = action.proposed.is_hard
            day["block_review_key"] = action.review_key
            day["approved_plan_session_type"] = action.original.session_type
            day["approved_plan_detail"] = action.original.detail
            break
    return effective
