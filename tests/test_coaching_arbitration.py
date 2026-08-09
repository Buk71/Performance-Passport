import datetime
import unittest
from unittest.mock import patch

from core.coaching_arbitration import build_coaching_arbitration
from core.next_run import NextRunRecommendation


def make_existing(
    key_family="Threshold Development",
    phase="Build",
    athlete_id=1,
):
    return NextRunRecommendation(
        athlete_id=athlete_id,
        session_family="Easy Recovery Run",
        icon="🟢",
        earliest_timing="Today",
        timing_detail="Easy first",
        headline="Recover",
        why=(),
        expected_benefit="Recover",
        alternative="Rest",
        alternative_reason="If tired",
        confidence=0.80,
        confidence_label="Good",
        readiness_required=True,
        block_name="10K",
        block_phase=phase,
        primary_focus=key_family,
        latest_run_title="Run",
        latest_run_category="Easy",
        next_key_session_family=key_family,
        next_key_session_icon="❤️",
        next_key_session_timing="Wednesday",
        next_key_session_timing_detail="Quality",
        next_key_session_readiness_required=True,
    )


class Day:
    def __init__(self, name, family, prescription):
        self.day_name = name
        self.session_family = family
        self.prescription = prescription


class Week:
    def __init__(self, days):
        self.days = tuple(days)


class Plan:
    available = True
    weeks = (
        Week([
            Day("Wednesday","vo2","8 × 500m"),
            Day("Saturday","threshold","3 × 10 min threshold"),
        ]),
    )


class Proposal:
    key_family = "vo2"
    key_prescription = "8 × 500m"
    key_day = "Wednesday"
    progression_headline = "Progress slightly"
    release_gate_ready = True
    adaptive_confidence = 0.80


class ArbitrationTests(unittest.TestCase):
    @patch(
        "core.coaching_arbitration.build_adaptive_coach_proposal",
        return_value=Proposal(),
    )
    @patch(
        "core.coaching_arbitration.build_adaptive_weekly_plan",
        return_value=Plan(),
    )
    def test_sequence_wins_when_weakness_is_preserved(self, plan, proposal):
        result = build_coaching_arbitration(
            1,
            today=datetime.date(2026,8,9),
            existing_recommendation=make_existing(),
        )
        self.assertEqual(result.selected_family, "vo2")
        self.assertTrue(result.complementary_session_preserved)
        self.assertTrue(result.disagreement_resolved)

    @patch(
        "core.coaching_arbitration.build_adaptive_coach_proposal",
        return_value=Proposal(),
    )
    @patch("core.coaching_arbitration.build_adaptive_weekly_plan")
    def test_missing_weakness_blocks_takeover(self, plan, proposal):
        plan.return_value = type("Plan", (), {
            "available": True,
            "weeks": (
                Week([
                    Day("Wednesday","vo2","8 × 500m"),
                    Day("Saturday","vo2","6 × 800m"),
                ]),
            ),
        })()
        result = build_coaching_arbitration(
            1,
            existing_recommendation=make_existing(),
        )
        self.assertEqual(result.selected_family, "threshold")
        self.assertFalse(result.ready_for_live)

    @patch(
        "core.coaching_arbitration.build_adaptive_coach_proposal",
        return_value=Proposal(),
    )
    @patch(
        "core.coaching_arbitration.build_adaptive_weekly_plan",
        return_value=Plan(),
    )
    def test_recovery_phase_overrides_quality(self, plan, proposal):
        result = build_coaching_arbitration(
            1,
            existing_recommendation=make_existing(phase="Recovery"),
        )
        self.assertEqual(result.selected_family, "recovery")


if __name__ == "__main__":
    unittest.main()
