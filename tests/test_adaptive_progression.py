import datetime
import unittest
from unittest.mock import patch

from core.adaptive_progression import evaluate_progression


class AdaptiveProgressionTests(unittest.TestCase):
    @patch("core.adaptive_progression._trusted_recent_workouts")
    def test_strong_execution_progresses(self, rows):
        rows.return_value=[
            {"activity_id":1,"date":"2026-08-08","signature":"short_intervals_8x500m",
             "components":{"vo2"},"execution":93.0,"title":"8 x 500"},
            {"activity_id":2,"date":"2026-08-01","signature":"short_intervals_10x400m",
             "components":{"vo2"},"execution":88.0,"title":"10 x 400"},
        ]
        result=evaluate_progression(1,"vo2",as_of=datetime.date(2026,8,9))
        self.assertEqual(result.action,"progress")
        self.assertGreater(result.load_multiplier,1.0)

    @patch("core.adaptive_progression._trusted_recent_workouts")
    def test_middling_execution_repeats(self, rows):
        rows.return_value=[
            {"activity_id":1,"date":"2026-08-08","signature":"threshold_3x10min",
             "components":{"threshold"},"execution":76.0,"title":"Threshold"},
        ]
        result=evaluate_progression(1,"threshold",as_of=datetime.date(2026,8,9))
        self.assertEqual(result.action,"repeat")

    @patch("core.adaptive_progression._trusted_recent_workouts")
    def test_low_execution_reduces(self, rows):
        rows.return_value=[
            {"activity_id":1,"date":"2026-08-08","signature":"threshold_3x10min",
             "components":{"threshold"},"execution":66.0,"title":"Threshold"},
        ]
        result=evaluate_progression(1,"threshold",as_of=datetime.date(2026,8,9))
        self.assertEqual(result.action,"reduce")

    @patch("core.adaptive_progression._trusted_recent_workouts")
    def test_different_stimulus_does_not_drive_progression(self, rows):
        rows.return_value=[
            {"activity_id":1,"date":"2026-08-08","signature":"threshold_3x10min",
             "components":{"threshold"},"execution":95.0,"title":"Threshold"},
        ]
        result=evaluate_progression(1,"vo2",as_of=datetime.date(2026,8,9))
        self.assertEqual(result.action,"hold")


if __name__=="__main__":
    unittest.main()
