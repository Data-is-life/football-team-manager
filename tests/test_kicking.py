import copy
import random
import unittest
from unittest.mock import Mock

from app.kicking import add_kicking_stats
from app.playoffs import postseason_snapshot
from app.simulation import simulate_league_week


def box(made, attempted, extra_points=0):
    return {"kicking": [{"field_goals_made": made, "field_goals_attempted": attempted,
                         "extra_points_made": extra_points}]}


class KickingTests(unittest.TestCase):
    def test_no_attempts_with_extra_points(self):
        result = box(0, 0, 3)
        add_kicking_stats(result, random.Random(1))
        row = result["kicking"][0]
        self.assertIsNone(row["longest_field_goal"])
        self.assertIsNone(row["field_goal_percentage"])
        self.assertEqual(row["field_goal_attempts"], [])
        self.assertEqual(row["extra_points_attempted"], 3)
        self.assertEqual(row["kicking_points"], 3)

    def test_all_misses_have_zero_percentage_but_no_longest(self):
        result = box(0, 2)
        add_kicking_stats(result, random.Random(1))
        row = result["kicking"][0]
        self.assertEqual(row["field_goal_percentage"], 0)
        self.assertIsNone(row["longest_field_goal"])
        self.assertFalse(any(kick["made"] for kick in row["field_goal_attempts"]))

    def test_longer_miss_is_excluded(self):
        result = box(1, 2, 2)
        rng = Mock()
        rng.triangular.side_effect = (20, 62)
        add_kicking_stats(result, rng)
        row = result["kicking"][0]
        self.assertEqual(row["longest_field_goal"], 20)
        self.assertEqual(row["field_goal_percentage"], 50)
        self.assertEqual(row["kicking_points"], 5)

    def test_overtime_winner_can_set_longest(self):
        result = box(2, 2, 1)
        rng = Mock()
        rng.triangular.side_effect = (20, 55)
        add_kicking_stats(result, rng, overtime_winner=True)
        row = result["kicking"][0]
        self.assertEqual(row["longest_field_goal"], 55)
        self.assertEqual(row["field_goal_percentage"], 100)
        self.assertEqual(row["kicking_points"], 7)
        self.assertEqual(row["field_goal_attempts"][-1],
                         {"distance_yards": 55, "made": True, "overtime": True})

    def test_overtime_can_be_the_only_field_goal(self):
        result = box(1, 1)
        add_kicking_stats(result, random.Random(1), overtime_winner=True)
        row = result["kicking"][0]
        self.assertEqual(len(row["field_goal_attempts"]), 1)
        self.assertTrue(row["field_goal_attempts"][0]["overtime"])
        self.assertEqual(row["kicking_points"], 3)

    def test_details_are_repeatable_and_preserve_counts(self):
        original = box(2, 3, 4)
        first, second = copy.deepcopy(original), copy.deepcopy(original)
        add_kicking_stats(first, random.Random(19))
        add_kicking_stats(second, random.Random(19))
        self.assertEqual(first, second)
        for key, value in original["kicking"][0].items():
            self.assertEqual(first["kicking"][0][key], value)

    def assert_game(self, game):
        for side, other in (("home", "away"), ("away", "home")):
            result = game[side]
            row = result["kicking"][0]
            attempts = row["field_goal_attempts"]
            made = [kick for kick in attempts if kick["made"]]
            self.assertEqual(len(attempts), row["field_goals_attempted"])
            self.assertEqual(len(made), row["field_goals_made"])
            self.assertEqual(row["longest_field_goal"],
                             max((kick["distance_yards"] for kick in made), default=None))
            expected_pct = len(made) / len(attempts) * 100 if attempts else None
            self.assertEqual(row["field_goal_percentage"], expected_pct)
            self.assertEqual(row["extra_points_attempted"], result["scoring"]["touchdowns"])
            self.assertEqual(row["kicking_points"], 3 * len(made) + row["extra_points_made"])
            self.assertEqual(result["score"], 6 * result["scoring"]["touchdowns"] + row["kicking_points"])
            overtime_winner = game["overtime"] and result["score"] > game[other]["score"]
            self.assertEqual(sum(kick["overtime"] for kick in attempts), int(overtime_winner))
            for kick in attempts:
                self.assertIsInstance(kick["distance_yards"], int)
                self.assertGreaterEqual(kick["distance_yards"], 18)
                self.assertLessEqual(kick["distance_yards"], 55 if kick["overtime"] else 62)
                if kick["overtime"]:
                    self.assertTrue(kick["made"])

    def test_regular_season_including_overtime(self):
        overtime_wins = 0
        for week in range(1, 18):
            for game in simulate_league_week(1, week):
                self.assert_game(game)
                overtime_wins += bool(game["overtime"] and game["home"]["score"] != game["away"]["score"])
        self.assertGreater(overtime_wins, 0)

    def test_every_playoff_round(self):
        for round_ in postseason_snapshot(1, 4)["rounds"]:
            for game in round_["games"]:
                self.assert_game(game["result"])
