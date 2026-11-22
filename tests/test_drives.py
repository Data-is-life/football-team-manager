from dataclasses import replace
import random
import statistics
import unittest

from app.attributes import PlayerAttributes, generate_attributes
from app.drives import matchup, yardage
from app.league import generate_schedule
from app.lineups import lineup_context
from app.simulation import league_week_scores, simulate_game, roster_for


class DriveEngineTests(unittest.TestCase):
    def test_front_and_safeties_control_different_parts_of_rush_yardage(self):
        base = roster_for("seattle", 1234)

        def uniform(front, secondary):
            roster = {}
            for slot, player in base.items():
                grade = (front if player.position == "DL" else secondary
                         if player.position in ("CB", "S") else 75)
                attributes = PlayerAttributes(**{key: grade for key in vars(player.attributes)})
                roster[slot] = replace(player, rating=grade, attributes=attributes)
            return roster

        offense = uniform(75, 75)
        weak_front = matchup(offense, uniform(60, 60))
        strong_front = matchup(offense, uniform(90, 60))
        strong_both = matchup(offense, uniform(90, 90))
        strong_secondary = matchup(offense, uniform(60, 90))
        self.assertLess(strong_front.run, weak_front.run)
        self.assertAlmostEqual(strong_front.run, strong_both.run)
        self.assertLess(strong_both.run_breakaway, strong_front.run_breakaway)
        self.assertLess(strong_secondary.passing, weak_front.passing)
        self.assertAlmostEqual(strong_secondary.protection, weak_front.protection)
        self.assertLess(strong_front.protection, weak_front.protection)

        def gains(edge):
            return [yardage(random.Random(seed), 4, edge.run, edge.run_breakaway, False)
                    for seed in range(2000)]

        loose, bottleneck, contained = map(gains, (weak_front, strong_front, strong_both))
        self.assertLess(statistics.median(bottleneck), statistics.median(loose))
        self.assertGreater(sum(g >= 45 for g in bottleneck), sum(g >= 45 for g in contained))

    def test_aging_updates_skills_for_the_drive_engine(self):
        seed = 1234
        initial = lineup_context((), seed, 51)
        aged = lineup_context(initial, seed, 51, season=2)
        before = {p.id: p for p in dict(initial)["seattle"]}
        declining = [p for p in dict(aged)["seattle"] if p.rating < before[p.id].rating]
        self.assertTrue(declining)
        for player in declining:
            self.assertEqual(player.attributes,
                             generate_attributes(player.id, player.position, player.rating, seed))

    def test_scores_clock_and_box_totals_share_the_drive_result(self):
        seed = 1234
        context = lineup_context((), seed, 51, rebuild_team="seattle")
        for week in (16, 17):
            scores = {(home, away): (h, a) for home, away, h, a in
                      league_week_scores(1, week, seed, (), context)}
            for home, away in scores:
                game = generate_schedule(home, lineup_rules=51)[week-1]
                result = simulate_game(home, game, 1, run_seed=seed, roster_context=context)
                self.assertNotIn("drives", result)
                self.assertEqual(tuple(result[side]["score"] for side in ("home", "away")), scores[home, away])
                seconds = 0
                for side in ("home", "away"):
                    box = result[side]
                    stats = box["team_stats"]
                    kick = box["kicking"][0]
                    minute, second = map(int, stats["time_of_possession"].split(":"))
                    seconds += minute * 60 + second
                    self.assertEqual(sum(p["yards"] for p in box["rushing"]), stats["rushing_yards"])
                    self.assertEqual(sum(p["yards"] for p in box["receiving"]), stats["passing_yards"])
                    self.assertEqual(sum(p["touchdowns"] for p in box["receiving"]), box["passing"][0]["touchdowns"])
                    self.assertEqual(len(kick["field_goal_attempts"]), kick["field_goals_attempted"])
                    self.assertEqual(sum(a["made"] for a in kick["field_goal_attempts"]), kick["field_goals_made"])
                    self.assertEqual(box["score"], 6 * box["scoring"]["touchdowns"] + kick["kicking_points"])
                self.assertEqual(seconds, 3600)


if __name__ == "__main__":
    unittest.main()
