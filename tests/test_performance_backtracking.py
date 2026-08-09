import unittest
from core.performance_backtracking import _bucket, _family_components

class PerformanceBacktrackingTests(unittest.TestCase):
    def test_standard_distance_bucket(self):
        self.assertEqual(_bucket(5.01),5.0)
        self.assertEqual(_bucket(10.04),10.0)
        self.assertIsNone(_bucket(7.0))

    def test_mixed_quality_counts_both_stimuli(self):
        import json
        phases=json.dumps([
            {"phase_type":"threshold"},
            {"phase_type":"short_intervals"},
        ])
        self.assertEqual(
            _family_components(phases),
            {"threshold","short_intervals"},
        )

if __name__=="__main__":
    unittest.main()
