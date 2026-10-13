import copy
import random
import unittest
from unittest.mock import Mock

from app.simulation import resolve_overtime, simulate_league_week


def box(team_id, score=24):
    return {
        "team": {"id": team_id},
        "score": score,
        "scoring": {"touchdowns": 3, "field_goals": 1},
        "kicking": [{"field_goals_made": 1, "field_goals_attempted": 2}],
    }


class OvertimeTests(unittest.TestCase):
    def test_regulation_winner_is_unchanged(self):
        home, away = box("seattle", 24), box("san-francisco", 21)
        before = copy.deepcopy((home, away))
        rng = Mock()
        self.assertFalse(resolve_overtime(home, away, rng))
        self.assertEqual((home, away), before)
        rng.random.assert_not_called()

    def test_overtime_field_goal_updates_score_and_kicker(self):
        for draw, winner_index in ((0.0, 0), (0.99, 1)):
            with self.subTest(draw=draw):
                home, away = box("seattle"), box("san-francisco")
                rng = Mock()
                rng.random.side_effect = [0.5, draw]
                self.assertTrue(resolve_overtime(home, away, rng))
                winner, loser = (home, away) if winner_index == 0 else (away, home)
                self.assertEqual(winner["score"], 27)
                self.assertEqual(loser["score"], 24)
                self.assertEqual(winner["scoring"]["field_goals"], 2)
                self.assertEqual(winner["kicking"][0]["field_goals_made"], 2)
                self.assertEqual(winner["kicking"][0]["field_goals_attempted"], 3)
                self.assertEqual(winner["score"],
                                 winner["scoring"]["touchdowns"] * 7
                                 + winner["scoring"]["field_goals"] * 3)

    def test_overtime_can_still_end_tied(self):
        home, away = box("seattle"), box("san-francisco")
        before = copy.deepcopy((home, away))
        rng = Mock()
        rng.random.return_value = 0.01
        self.assertTrue(resolve_overtime(home, away, rng))
        self.assertEqual((home, away), before)

    def test_overtime_is_repeatable_with_same_seed(self):
        first = box("seattle"), box("san-francisco")
        second = copy.deepcopy(first)
        resolve_overtime(*first, random.Random(42))
        resolve_overtime(*second, random.Random(42))
        self.assertEqual(first, second)

    def test_ties_are_rare_across_ten_seasons(self):
        ties = games = overtime_games = 0
        for season in range(1, 11):
            for week in range(1, 18):
                for result in simulate_league_week(season, week):
                    games += 1
                    overtime_games += result["overtime"]
                    tied = result["home"]["score"] == result["away"]["score"]
                    ties += tied
                    if tied:
                        self.assertTrue(result["overtime"])
        self.assertGreater(overtime_games, 0)
        self.assertLess(ties / games, 0.02)


if __name__ == "__main__":
    unittest.main()
