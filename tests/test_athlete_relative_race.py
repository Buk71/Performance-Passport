import unittest

from core.race_detection import score_athlete_relative_race_effort


class AthleteRelativeRaceTests(unittest.TestCase):
    def test_training_title_prevents_promotion(self):
        result = score_athlete_relative_race_effort(
            athlete_id=3,
            title="Recovery 5k",
            distance_km=5.0,
            moving_time_s=1450,
            elapsed_time_s=1450,
        )
        self.assertFalse(result.is_race_quality)


if __name__ == "__main__":
    unittest.main()
