from dataclasses import replace
import random
import unittest

from app.attributes import PlayerAttributes
from app.development import advance_context
from app.drives import matchup
from app.league import generate_schedule
from app.lineups import lineup_context
from app.simulation import league_week_scores, roster_for, simulate_game
from app.snaps import (Possession, calibrated_matchup, completion, play_call,
                       red_zone_compression, rush, simulate)


class SnapEngineTests(unittest.TestCase):
    def test_calibration_requires_new_career(self):
        context = lineup_context((), 1234, 52)
        with self.assertRaisesRegex(ValueError, "Calibrated simulation requires a new career"):
            advance_context(context, 1234, 2, lineup_rules=53)

    def test_red_zone_requires_new_career(self):
        context = lineup_context((), 1234, 53)
        with self.assertRaisesRegex(ValueError, "Red-zone simulation requires a new career"):
            advance_context(context, 1234, 2, lineup_rules=54)

    def test_red_zone_compresses_field_without_changing_midfield_matchups(self):
        self.assertEqual([red_zone_compression(s) for s in (50, 79, 80, 85, 90, 95, 100)],
                         [0, 0, 0, .25, .5, .75, 1])
        roster = roster_for("seattle", 1234)
        edge = calibrated_matchup(roster, roster)
        for seed in range(50):
            self.assertEqual(rush(random.Random(seed), edge),
                             rush(random.Random(seed), edge, compression=red_zone_compression(80)))
            self.assertEqual(completion(random.Random(seed), edge, 10, calibrated=True),
                             completion(random.Random(seed), edge, 10, calibrated=True,
                                        compression=red_zone_compression(80)))
        self.assertLess(sum(rush(random.Random(i), edge, compression=.9) for i in range(200)),
                        sum(rush(random.Random(i), edge) for i in range(200)))
        self.assertLess(sum(completion(random.Random(i), edge, 10, calibrated=True,
                                       compression=.5) for i in range(200)),
                        sum(completion(random.Random(i), edge, 10, calibrated=True) for i in range(200)))

    def test_default_coach_passes_more_often_near_goal_line(self):
        roster = roster_for("seattle", 1234)
        edge = calibrated_matchup(roster, roster)
        for spot in (50, 80, 95):
            state = Possession(0, spot, 1, 5)
            old = sum(play_call(state, edge, 0, 800, 0, random.Random(i),
                                calibrated=True) == "pass" for i in range(200))
            new = sum(play_call(state, edge, 0, 800, 0, random.Random(i),
                                calibrated=True, red_zone=True) == "pass" for i in range(200))
            if spot <= 80:
                self.assertEqual(old, new)
            else:
                self.assertGreater(new, old)

    def test_calibration_scales_roster_edges_but_preserves_home_and_kicking(self):
        offense = roster_for("seattle", 1234)
        defense = roster_for("boston", 1234)
        for home_edge in (0, 1.6):
            original = matchup(offense, defense, home_edge)
            adjusted = calibrated_matchup(offense, defense, home_edge)
            for name in ("run", "passing", "protection"):
                self.assertAlmostEqual(getattr(adjusted, name),
                                       .60 * (getattr(original, name) - home_edge) + home_edge)
            for name in ("run_breakaway", "pass_breakaway"):
                self.assertAlmostEqual(getattr(adjusted, name), .60 * getattr(original, name))
            for name in ("ball_security", "kick_accuracy", "kick_power"):
                self.assertEqual(getattr(adjusted, name), getattr(original, name))

    def test_down_distance_goal_to_go_and_change_of_possession(self):
        state = Possession(0, spot=86)
        state.advance(7)
        self.assertEqual((state.spot, state.down, state.to_go), (93, 2, 3))
        state.advance(-5)
        self.assertEqual((state.spot, state.down, state.to_go), (88, 3, 8))
        state.advance(8)
        self.assertEqual((state.spot, state.down, state.to_go), (96, 1, 4))
        state.restart(4)
        self.assertEqual((state.offense, state.spot, state.down, state.to_go), (1, 4, 1, 10))

    def test_default_coach_punts_kicks_or_tries_to_convert(self):
        roster = roster_for("seattle", 1234)
        edge = matchup(roster, roster)
        rng = random.Random(1)
        self.assertEqual(play_call(Possession(0, 25, 4, 6), edge, 0, 800, 0, rng), "punt")
        self.assertEqual(play_call(Possession(0, 79, 4, 6), edge, 0, 800, 0, rng), "kick")
        self.assertIn(play_call(Possession(0, 79, 4, 6), edge, 1, 40, -4, rng), ("run", "pass"))
        self.assertEqual(play_call(Possession(0, 79, 2, 6), edge, 1, 8, -2, rng), "kick")

    def test_same_offense_changes_play_selection_across_matchups(self):
        base = roster_for("seattle", 1234)

        def roster(front, secondary):
            return {slot: replace(p, rating=rating, attributes=PlayerAttributes(
                **{field: rating for field in vars(p.attributes)}))
                for slot, p in base.items()
                for rating in [front if p.position in ("DL", "LB") else
                               secondary if p.position in ("CB", "S") else 75]}

        offense = roster(75, 75)
        strong_front, strong_secondary = roster(90, 60), roster(60, 90)
        for rules in (52, 53, 54):
            self.check_matchups(offense, strong_front, strong_secondary, rules)

    def check_matchups(self, offense, strong_front, strong_secondary, rules):
        front_games = [simulate(random.Random(i), offense, strong_front, neutral_site=True, rules=rules)[0][0]
                       for i in range(150)]
        secondary_games = [simulate(random.Random(i), offense, strong_secondary, neutral_site=True, rules=rules)[0][0]
                           for i in range(150)]
        self.assertGreater(sum(s.attempts for s in front_games), sum(s.attempts for s in secondary_games))
        self.assertLess(sum(s.rushing_yards for s in front_games), sum(s.rushing_yards for s in secondary_games))
        self.assertGreater(sum(s.passing_yards for s in front_games), sum(s.passing_yards for s in secondary_games))

    def test_score_only_parity_and_credit_conservation(self):
        for rules in (52, 53, 54):
            with self.subTest(rules=rules):
                self.check_score_only_parity(rules)

    def check_score_only_parity(self, rules):
        seed = 6789
        context = lineup_context((), seed, rules, rebuild_team="seattle")
        for week in (16, 17):
            for home, away, home_score, away_score in league_week_scores(1, week, seed, (), context):
                game = generate_schedule(home, lineup_rules=rules)[week - 1]
                result = simulate_game(home, game, 1, run_seed=seed, roster_context=context)
                self.assertNotIn("plays", result)
                self.assertEqual(tuple(result[side]["score"] for side in ("home", "away")), (home_score, away_score))
                seconds = 0
                for side, opponent in (("home", "away"), ("away", "home")):
                    box = result[side]
                    self.assertNotIn("_snap_credits", box)
                    qb, = box["passing"]
                    kicker, = box["kicking"]
                    stats = box["team_stats"]
                    self.assertEqual(stats["rush_attempts"], sum(p["attempts"] for p in box["rushing"]))
                    self.assertEqual(stats["rushing_yards"], sum(p["yards"] for p in box["rushing"]))
                    self.assertEqual(qb["yards"], sum(p["yards"] for p in box["receiving"]))
                    self.assertEqual(qb["attempts"], sum(p["targets"] for p in box["receiving"]))
                    self.assertEqual(qb["completions"], sum(p["receptions"] for p in box["receiving"]))
                    self.assertEqual(qb["touchdowns"], sum(p["touchdowns"] for p in box["receiving"]))
                    self.assertEqual(box["score"], 6 * box["scoring"]["touchdowns"]
                                     + kicker["kicking_points"] + 2 * box["scoring"].get("safeties", 0))
                    self.assertEqual(sum(p["sacks"] for p in box["defense"]), result[opponent]["team_stats"]["sacks_allowed"])
                    self.assertEqual(sum(p["interceptions"] for p in box["defense"]),
                                     result[opponent]["passing"][0]["interceptions"])
                    self.assertTrue(all(p["snaps"] >= p["tackles"] + p["interceptions"] for p in box["defense"]))
                    minute, second = map(int, stats["time_of_possession"].split(":"))
                    seconds += minute * 60 + second
                self.assertEqual(seconds, 3600)
