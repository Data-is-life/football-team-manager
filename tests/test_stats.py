import unittest

from app.playoffs import postseason_snapshot
from app.simulation import simulate_league_week
from app.stats import add_efficiency_stats, passer_rating, per_opportunity


class EfficiencyTests(unittest.TestCase):
    def test_published_manning_2004_example(self):
        self.assertAlmostEqual(passer_rating(336, 497, 4557, 49, 10), 121.1, places=1)

    def test_component_caps_and_floor(self):
        self.assertAlmostEqual(passer_rating(20, 20, 400, 5, 0), 158.33333333333334)
        self.assertEqual(passer_rating(0, 20, 0, 0, 10), 0)
        # A negative yardage component cannot cancel the no-interception component.
        self.assertAlmostEqual(passer_rating(0, 20, 0, 0, 0), 39.58333333333333)

    def test_zero_opportunities_are_unavailable(self):
        box = {"passing": [{"attempts": 0, "completions": 0, "yards": 0,
                            "touchdowns": 0, "interceptions": 0}],
               "rushing": [{"attempts": 0, "yards": 0}],
               "receiving": [{"receptions": 0, "yards": 0}]}
        add_efficiency_stats(box)
        for key in ("passer_rating", "completion_percentage", "yards_per_attempt"):
            self.assertIsNone(box["passing"][0][key])
        self.assertIsNone(box["rushing"][0]["yards_per_carry"])
        self.assertIsNone(box["receiving"][0]["yards_per_reception"])

    def test_zero_yards_and_full_precision(self):
        self.assertEqual(per_opportunity(0, 3), 0)
        self.assertEqual(per_opportunity(10, 3), 10 / 3)

    def assert_box(self, box):
        for row in box["passing"]:
            self.assertEqual(row["completion_percentage"], row["completions"] / row["attempts"] * 100)
            self.assertEqual(row["yards_per_attempt"], row["yards"] / row["attempts"])
            self.assertEqual(row["passer_rating"], passer_rating(row["completions"], row["attempts"],
                             row["yards"], row["touchdowns"], row["interceptions"]))
            self.assertGreaterEqual(row["passer_rating"], 0)
            self.assertLessEqual(row["passer_rating"], 158.33333333333334)
        for row in box["rushing"]:
            self.assertEqual(row["yards_per_carry"], per_opportunity(row["yards"], row["attempts"]))
        for row in box["receiving"]:
            self.assertEqual(row["yards_per_reception"], per_opportunity(row["yards"], row["receptions"]))

    def test_regular_season_all_teams(self):
        for week in range(1, 18):
            for game in simulate_league_week(1, week):
                for side in ("home", "away"):
                    self.assert_box(game[side])

    def test_all_playoff_rounds(self):
        for round_ in postseason_snapshot(1, 4)["rounds"]:
            for game in round_["games"]:
                for side in ("home", "away"):
                    self.assert_box(game["result"][side])
