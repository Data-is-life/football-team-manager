import unittest

from app.league import TEAMS, generate_schedule
from app.simulation import simulate_game, simulate_through_week


class ResultHistoryTests(unittest.TestCase):
    def test_history_scores_match_home_and_away_games_for_every_team(self):
        for team in TEAMS:
            with self.subTest(team=team.id):
                schedule = generate_schedule(team.id)
                data = simulate_through_week(team.id, 1, 17)
                self.assertEqual([row["week"] for row in data["game_results"]], list(range(1, 18)))
                for game, row in zip(schedule, data["game_results"]):
                    result = simulate_game(team.id, game, 1)
                    own = "home" if game.venue == "Home" else "away"
                    opponent = "away" if own == "home" else "home"
                    self.assertEqual(row["team_score"], result[own]["score"])
                    self.assertEqual(row["opponent_score"], result[opponent]["score"])
                    self.assertEqual(row["opponent_id"], game.opponent_id)
                    self.assertEqual(row["venue"], game.venue)
                    self.assertEqual(row["overtime"], result["overtime"])
                    expected = "W" if row["team_score"] > row["opponent_score"] else "L" if row["team_score"] < row["opponent_score"] else "T"
                    self.assertEqual(row["outcome"], expected)
                for outcome, label in (("W", "wins"), ("L", "losses"), ("T", "ties")):
                    self.assertEqual(sum(row["outcome"] == outcome for row in data["game_results"]), data["record"][label])

    def test_history_contains_only_completed_games_and_retains_prior_scores(self):
        first = simulate_through_week("seattle", 1, 1)
        later = simulate_through_week("seattle", 1, 5)
        self.assertEqual(len(first["game_results"]), 1)
        self.assertEqual(len(later["game_results"]), 5)
        self.assertEqual(first["game_results"], later["game_results"][:1])

    def test_latest_history_score_matches_current_result(self):
        data = simulate_through_week("san-francisco", 1, 4)
        row = data["game_results"][-1]
        result = data["result"]
        own = "home" if result["home"]["team"]["id"] == data["team"]["id"] else "away"
        self.assertEqual(row["team_score"], result[own]["score"])
        self.assertEqual(row["outcome"], result["outcome"])


if __name__ == "__main__":
    unittest.main()
