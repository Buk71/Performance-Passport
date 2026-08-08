import datetime
import unittest

from core.training_blocks import TrainingBlock, block_progress


class TrainingBlockTests(unittest.TestCase):
    def _block(self):
        return TrainingBlock(
            id=1,
            athlete_id=1,
            name="Test 10K Block",
            block_type="10K",
            purpose="Threshold development",
            start_date="2026-08-01",
            end_date="2026-10-23",
            status="Active",
            primary_focus="Threshold",
            current_phase="Build",
            notes=None,
            created_at=None,
            updated_at=None,
        )

    def test_active_week_is_calculated(self):
        result = block_progress(
            self._block(),
            today=datetime.date(2026, 8, 8),
        )
        self.assertEqual(result.week_number, 2)
        self.assertEqual(result.total_weeks, 12)

    def test_upcoming_block_reports_week_zero(self):
        result = block_progress(
            self._block(),
            today=datetime.date(2026, 7, 20),
        )
        self.assertEqual(result.week_number, 0)
        self.assertEqual(result.date_status, "Upcoming")

    def test_completed_dates_cap_progress(self):
        result = block_progress(
            self._block(),
            today=datetime.date(2026, 11, 1),
        )
        self.assertEqual(result.progress_fraction, 1.0)
        self.assertEqual(result.days_remaining, 0)


if __name__ == "__main__":
    unittest.main()
