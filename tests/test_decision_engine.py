import unittest

from core.capability import Capability
from core.coach_consensus import CoachConsensus
from core.decision_engine import build_decision
from core.performance_dna import PerformanceDNA


class DecisionEngineTests(unittest.TestCase):
    def _dna(self):
        return PerformanceDNA(
            athlete_id=1,
            overall_confidence=0.82,
            consensus_status="aligned",
            headline="Coaches aligned",
            summary="Test DNA",
            strongest_signal="Aerobic",
            limiting_signal="Threshold",
            verdicts=(),
            system_scores={
                "threshold": 67.0,
                "speed": 82.0,
                "endurance": 79.0,
                "aerobic": 88.0,
            },
            workout_archetype=None,
            workout_dna_confidence=0.70,
            athlete_dna_confidence=0.80,
            athlete_profile_label="Aerobic strength",
            system_confidence={
                "threshold": 0.78,
                "speed": 0.72,
                "endurance": 0.75,
                "aerobic": 0.85,
            },
            available_coach_count=4,
            total_coach_count=6,
        )

    def _consensus(self):
        return CoachConsensus(
            status="aligned",
            headline="Coaches agree",
            summary="Test consensus",
            confidence=0.81,
            lead_coach="Threshold Coach",
            supporting_coaches=("Workout Coach",),
            cautious_coaches=(),
            optimistic_coaches=(),
            strongest_system="aerobic",
            development_priority="threshold",
            positions=(),
            notes=(),
        )

    def _capability(self):
        return Capability(
            available=True,
            central_seconds=2350.0,
            low_seconds=2310.0,
            high_seconds=2390.0,
            confidence=0.80,
            target_seconds=2340.0,
            target_gap_seconds=10.0,
            target_probability=0.46,
            strongest_system="aerobic",
            limiting_system="threshold",
            headline="Goal within range",
            explanation="Test capability",
            evidence=(),
            limitations=(),
        )

    def test_identifies_strength_and_opportunity(self):
        decision = build_decision(
            performance_dna=self._dna(),
            coach_consensus=self._consensus(),
            capability=self._capability(),
            recognition_index={},
        )

        self.assertEqual(decision.strongest_system, "aerobic")
        self.assertEqual(decision.primary_opportunity, "threshold")
        self.assertEqual(
            decision.provisional_next_session,
            "Threshold Development",
        )

    def test_quality_session_waits_for_readiness(self):
        decision = build_decision(
            performance_dna=self._dna(),
            coach_consensus=self._consensus(),
            capability=self._capability(),
            recognition_index={},
        )

        self.assertFalse(decision.recommendation_ready)
        self.assertIn("Readiness", decision.recommendation_status)

    def test_positive_headline_leads_with_strength(self):
        decision = build_decision(
            performance_dna=self._dna(),
            coach_consensus=self._consensus(),
            capability=self._capability(),
            recognition_index={},
        )

        self.assertTrue(
            decision.headline.startswith("Aerobic is a current strength")
        )

    def test_signals_are_transparent(self):
        decision = build_decision(
            performance_dna=self._dna(),
            coach_consensus=self._consensus(),
            capability=self._capability(),
            recognition_index={},
        )

        signals = {
            signal.key: signal
            for signal in decision.coaching_signals
        }

        self.assertEqual(signals["aerobic"].direction, "strength")
        self.assertEqual(signals["threshold"].direction, "opportunity")
        self.assertEqual(signals["aerobic"].value, 88.0)
        self.assertEqual(signals["threshold"].value, 67.0)


if __name__ == "__main__":
    unittest.main()
