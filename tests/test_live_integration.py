import unittest
from core.live_integration import _adjust_for_gate, _families_agree

class LiveIntegrationTests(unittest.TestCase):
    def test_reduce_removes_one_rep(self):
        adjusted,_ = _adjust_for_gate("8 × 500m controlled intervals","reduce")
        self.assertEqual(adjusted,"7 × 500m controlled intervals")

    def test_repeat_keeps_workout(self):
        adjusted,_ = _adjust_for_gate("3 × 10 min threshold","repeat")
        self.assertEqual(adjusted,"3 × 10 min threshold")

    def test_conflicting_family_is_flagged(self):
        agree,text = _families_agree("threshold","endurance")
        self.assertFalse(agree)
        self.assertIn("Different",text)

    def test_compatible_fast_families_agree(self):
        agree,_ = _families_agree("race_pace","vo2")
        self.assertTrue(agree)

if __name__=="__main__":
    unittest.main()
