import unittest

from core.session_designer import _format_recovery


class RecoveryFormattingTests(unittest.TestCase):
    def test_short_recovery_rounds_to_15_seconds(self):
        self.assertEqual(_format_recovery(54), "60 sec")
        self.assertEqual(_format_recovery(47), "45 sec")
        self.assertEqual(_format_recovery(73), "75 sec")

    def test_longer_recovery_uses_clean_minutes(self):
        self.assertEqual(_format_recovery(120), "2 min")
        self.assertEqual(_format_recovery(148), "2:30")


if __name__ == "__main__":
    unittest.main()
