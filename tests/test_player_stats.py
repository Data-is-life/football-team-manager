import copy
from dataclasses import replace
import unittest

from app.main import team_profile
from app.player_stats import COUNT_FIELDS, aggregate_player_stats
from app.playoffs import playoffs_through_round, postseason_snapshot
from app.simulation import roster_for, simulate_game, simulate_through_week
from app.league import generate_schedule
from app.stats import passer_rating


class PlayerSeasonStatsTests(unittest.TestCase):
    def test_initial_roster_includes_backups_and_untracked_positions(self):
        profile = team_profile("seattle")
        stats = profile["roster_stats"]
        self.assertEqual(stats["games"], 0)
        self.assertEqual(len(stats["players"]), 38)
        totals = {row["player_id"]: row for row in stats["players"]}
        for player in profile["roster"]:
            row = totals[player["id"]]
            self.assertEqual(row["position"], player["position"])
            if player["position"] == "QB":
                self.assertEqual(row["passing"]["attempts"], 0)
                self.assertIsNone(row["passing"]["passer_rating"])
            elif player["position"] in ("OL", "DL", "LB", "CB", "S"):
                self.assertEqual(set(row), {"player_id", "position"})
        self.assertIsNone(totals["seattle-k2"]["kicking"]["longest_field_goal"])

    def test_rates_use_combined_opportunities_and_longest_uses_max(self):
        players = list(roster_for("seattle").values())
        def fixture(att, cmp, pass_yards, carry, rush_yards, rec, rec_yards, fgm, fga, longest):
            return {
                "passing": [{"player_id": "seattle-qb1", "attempts": att,
                             "completions": cmp, "yards": pass_yards, "touchdowns": 0, "interceptions": 0}],
                "rushing": [{"player_id": "seattle-rb1", "attempts": carry,
                             "yards": rush_yards, "touchdowns": 1}],
                "receiving": [{"player_id": "seattle-rb1", "receptions": rec,
                               "yards": rec_yards, "touchdowns": 1}],
                "kicking": [{"player_id": "seattle-k1", "field_goals_made": fgm,
                             "field_goals_attempted": fga, "longest_field_goal": longest,
                             "extra_points_made": 2, "extra_points_attempted": 2, "kicking_points": fgm * 3 + 2}],
            }
        boxes = [fixture(1, 1, 10, 1, 10, 1, 20, 1, 1, 50),
                 fixture(9, 3, 10, 9, 9, 3, 10, 0, 3, None)]
        result = aggregate_player_stats(players, boxes)
        totals = {row["player_id"]: row for row in result["players"]}
        qb = totals["seattle-qb1"]["passing"]
        self.assertEqual(qb["completion_percentage"], 40)
        self.assertEqual(qb["yards_per_attempt"], 2)
        self.assertEqual(qb["passer_rating"], passer_rating(4, 10, 20, 0, 0))
        rb = totals["seattle-rb1"]
        self.assertEqual(rb["rushing"]["yards_per_carry"], 1.9)
        self.assertEqual(rb["receiving"]["yards_per_reception"], 7.5)
        self.assertEqual(rb["rushing"]["touchdowns"], 2)
        self.assertEqual(rb["receiving"]["touchdowns"], 2)
        kicker = totals["seattle-k1"]["kicking"]
        self.assertEqual(kicker["field_goal_percentage"], 25)
        self.assertEqual(kicker["longest_field_goal"], 50)
        self.assertEqual(kicker["kicking_points"], 7)
        self.assertEqual(kicker["extra_points_attempted"], 4)

    def test_player_ids_keep_identical_names_separate(self):
        roster = roster_for("seattle")
        players = [replace(roster["QB1"], name="Same Name"), replace(roster["QB2"], name="Same Name")]
        game = simulate_game("seattle", generate_schedule("seattle")[0], 1)
        own = next(game[side] for side in ("home", "away") if game[side]["team"]["id"] == "seattle")
        own = {"passing": own["passing"], "rushing": [], "receiving": [], "kicking": []}
        result = aggregate_player_stats(players, [own])
        self.assertGreater(result["players"][0]["passing"]["attempts"], 0)
        self.assertEqual(result["players"][1]["passing"]["attempts"], 0)

    def assert_matches_boxes(self, team_id, actual, boxes):
        self.assertEqual(actual["games"], len(boxes))
        totals = {row["player_id"]: row for row in actual["players"]}
        for player in roster_for(team_id).values():
            entry = totals[player.id]
            for category, fields in COUNT_FIELDS.items():
                if category not in entry:
                    continue
                for field in fields:
                    expected = sum(row[field] for box in boxes for row in box[category]
                                   if row["player_id"] == player.id)
                    self.assertEqual(entry[category][field], expected, (team_id, player.id, category, field))

    def test_regular_season_snapshots_include_only_completed_games(self):
        for team_id in ("seattle", "chicago"):
            schedule = generate_schedule(team_id)
            results = [simulate_game(team_id, game, 1) for game in schedule]
            boxes = [next(result[side] for side in ("home", "away")
                          if result[side]["team"]["id"] == team_id) for result in results]
            for week in (1, 4, 17):
                snapshot = simulate_through_week(team_id, 1, week)["roster_stats"]
                self.assert_matches_boxes(team_id, snapshot, boxes[:week])

    def test_playoff_snapshots_exclude_byes_and_stop_after_elimination(self):
        final = postseason_snapshot(1, 4)
        field = final["field"]
        cases = [field[0]["team"]["id"], final["champion"]["team"]["id"], "seattle"]
        from app.league import TEAMS
        cases.append(next(team.id for team in TEAMS if not any(row["team"]["id"] == team.id for row in field)))
        for team_id in set(cases):
            regular = simulate_through_week(team_id, 1, 17)["roster_stats"]
            original = copy.deepcopy(regular)
            for number in range(5):
                state = playoffs_through_round(team_id, 1, number)
                boxes = [game["result"][side] for round_ in state["rounds"] for game in round_["games"]
                         for side in ("home", "away") if game[side]["team"]["id"] == team_id]
                self.assert_matches_boxes(team_id, state["roster_stats"], boxes)
                if number == 1 and team_id == field[0]["team"]["id"]:
                    self.assertEqual(state["roster_stats"]["games"], 0)
            self.assertEqual(regular, original)
            self.assertEqual(simulate_through_week(team_id, 1, 17)["roster_stats"], original)

    def test_repeated_snapshots_do_not_double_count_or_mutate_games(self):
        game = simulate_game("seattle", generate_schedule("seattle")[0], 1)
        original = copy.deepcopy(game)
        own = next(game[side] for side in ("home", "away") if game[side]["team"]["id"] == "seattle")
        first = aggregate_player_stats(roster_for("seattle").values(), [own])
        second = aggregate_player_stats(roster_for("seattle").values(), [own])
        self.assertEqual(first, second)
        self.assertEqual(game, original)
