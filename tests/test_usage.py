import random
import unittest
from unittest.mock import Mock

from app.league import generate_schedule
from app.simulation import (apply_usage, assign_possession, pass_share, possession_weights,
                            roster_for, simulate_game, simulate_league_week, total_plays)


class UsageTests(unittest.TestCase):
    def test_passing_increases_with_deficit_skill_and_experience(self):
        baseline = pass_share(80, 80, 0, 6)
        self.assertGreater(pass_share(80, 80, 14, 6), baseline)
        self.assertLess(pass_share(80, 80, -14, 6), baseline)
        self.assertGreater(pass_share(90, 70, 0, 6), baseline)
        self.assertLess(pass_share(70, 90, 0, 6), baseline)
        self.assertGreater(pass_share(80, 80, 0, 12), pass_share(80, 80, 0, 0))
        self.assertEqual(pass_share(99, 50, 100, 12), 0.75)
        self.assertEqual(pass_share(50, 99, -100, 0), 0.30)

    def test_play_volume_responds_to_score_and_skill(self):
        def fixed():
            rng = Mock()
            rng.gauss.side_effect = lambda center, spread: center
            return rng
        baseline = total_plays(44, 0, fixed())
        self.assertGreater(total_plays(70, 0, fixed()), baseline)
        self.assertGreater(total_plays(44, 15, fixed()), baseline)
        self.assertEqual(total_plays(200, 50, fixed()), 85)
        self.assertEqual(total_plays(0, -50, fixed()), 50)

    def test_rb_share_endpoints_preserve_team_totals(self):
        game = generate_schedule("seattle")[0]
        for share in (0.50, 0.90):
            result = simulate_game("seattle", game, 1)
            box, opponent = (result["home"], result["away"]) if game.venue == "Home" else (result["away"], result["home"])
            yards = box["team_stats"]["rushing_yards"]
            tds = sum(row["touchdowns"] for row in box["rushing"])
            rng = random.Random(42)
            rng.uniform = lambda low, high: share if (low, high) == (0.50, 0.90) else 1.0
            apply_usage(box, opponent, rng)
            rows = box["rushing"]
            carries = box["team_stats"]["rush_attempts"]
            self.assertEqual(sum(row["attempts"] for row in rows), carries)
            self.assertLessEqual(abs(rows[0]["attempts"] - carries * share), 1)
            self.assertEqual(sum(row["yards"] for row in rows), yards)
            self.assertEqual(sum(row["touchdowns"] for row in rows), tds)

    def test_game_statistics_reconcile_across_three_seasons(self):
        for season in range(1, 4):
            for week in range(1, 18):
                for result in simulate_league_week(season, week):
                    durations = []
                    for side in ("home", "away"):
                        box = result[side]
                        stats = box["team_stats"]
                        qb = box["passing"][0]
                        roster = roster_for(box["team"]["id"])
                        self.assertEqual(len(box["passing"]), 1)
                        self.assertEqual(qb["player"], roster["QB1"].name)
                        self.assertEqual(stats["total_plays"], qb["attempts"] + sum(row["attempts"] for row in box["rushing"]))
                        self.assertTrue(50 <= stats["total_plays"] <= 85)
                        self.assertEqual(len(box["rushing"]), 2)
                        self.assertEqual(sum(row["yards"] for row in box["rushing"]), stats["rushing_yards"])
                        self.assertEqual(sum(row["yards"] for row in box["receiving"]), stats["passing_yards"])
                        self.assertEqual(sum(row["receptions"] for row in box["receiving"]), qb["completions"])
                        self.assertEqual(sum(row["touchdowns"] for row in box["receiving"]), qb["touchdowns"])
                        self.assertEqual(len([row for row in box["receiving"] if row["position"] == "WR"]), 4)
                        self.assertEqual(len(box["receiving"]), 8)
                        for row in box["receiving"]:
                            self.assertLessEqual(row["touchdowns"], row["receptions"])
                            if row["receptions"] == 0:
                                self.assertEqual(row["yards"], 0)
                        self.assertEqual(qb["touchdowns"] + sum(row["touchdowns"] for row in box["rushing"]), box["scoring"]["touchdowns"])
                        minutes, seconds = map(int, stats["time_of_possession"].split(":"))
                        durations.append(minutes * 60 + seconds)
                    self.assertEqual(sum(durations), 3600)

    def test_possession_rewards_clock_consuming_plays(self):
        self.assertGreater(possession_weights(10, 0, 0), possession_weights(0, 10, 0))
        self.assertGreater(possession_weights(0, 10, 0), possession_weights(0, 0, 10))
        home = {"team_stats": {"rush_attempts": 40}, "passing": [{"attempts": 20, "completions": 15}]}
        away = {"team_stats": {"rush_attempts": 15}, "passing": [{"attempts": 45, "completions": 20}]}
        assign_possession(home, away)
        def seconds(box):
            minutes, seconds = map(int, box["team_stats"]["time_of_possession"].split(":"))
            return minutes * 60 + seconds
        self.assertGreater(seconds(home), seconds(away))
        self.assertEqual(seconds(home) + seconds(away), 3600)

    def test_experience_is_bounded_and_repeatable(self):
        first = roster_for("seattle")
        self.assertEqual(first, roster_for("seattle"))
        self.assertTrue(all(0 <= player.experience <= 12 for player in first.values()))


if __name__ == "__main__":
    unittest.main()
