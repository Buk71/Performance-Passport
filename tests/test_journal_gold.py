import unittest

from core.journal import _journal_title


class FakeRecognition:
    celebration = "Top 5% Easy"
    rank = 5
    total = 100
    top_percent = 5
    environment_factors = ("24°C heat", "16°C dew point")
    category_key = "easy"


class JournalGoldTests(unittest.TestCase):
    def test_hot_top_run_gets_memorable_title(self):
        title = _journal_title(
            FakeRecognition(),
            decision_direction="Positive",
            block=None,
        )
        self.assertEqual(title, "Winning in the heat.")


if __name__ == "__main__":
    unittest.main()
