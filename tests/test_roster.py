from collections import Counter
from dataclasses import replace
import unittest

from app.league import TEAMS, generate_schedule
from app.main import team_profile
from app.simulation import roster_for, simulate_game, validate_roster


COUNTS = {"QB": 2, "WR": 4, "TE": 2, "RB": 2, "OL": 8, "K": 2, "DL": 6, "LB": 5, "CB": 4, "S": 3}
MINIMUMS = {"QB": 1, "WR": 2, "TE": 1, "RB": 1, "OL": 5, "K": 1, "DL": 4, "LB": 3, "CB": 2, "S": 2}


class ExpandedRosterTests(unittest.TestCase):
    def test_every_team_has_the_requested_distribution(self):
        for team in TEAMS:
            with self.subTest(team=team.id):
                profile = team_profile(team.id)
                players = profile["roster"]
                self.assertEqual(len(players), 38)
                self.assertEqual(Counter(player["position"] for player in players), COUNTS)
                self.assertEqual(len({player["name"] for player in players}), 38)
                self.assertEqual(len({player["id"] for player in players}), 38)
                for position, count in COUNTS.items():
                    group = [player for player in players if player["position"] == position]
                    self.assertEqual([player["depth"] for player in group], list(range(1, count + 1)))
                self.assertEqual({row["position"]: row["minimum"] for row in profile["roster_rules"]}, MINIMUMS)
                self.assertEqual({row["position"]: row["count"] for row in profile["roster_rules"]}, COUNTS)
                self.assertEqual(profile, team_profile(team.id))

    def test_offense_and_defense_have_equal_depth(self):
        for team in TEAMS:
            counts = Counter(player.position for player in roster_for(team.id).values())
            self.assertEqual(sum(counts[position] for position in ("QB", "WR", "TE", "RB", "OL")), 18)
            self.assertEqual(sum(counts[position] for position in ("DL", "LB", "CB", "S")), 18)
            self.assertEqual(counts["K"], 2)

    def test_full_roster_and_minimum_roster_are_valid(self):
        full = list(roster_for("seattle").values())
        validate_roster(full)
        minimum = [player for player in full if player.depth <= MINIMUMS[player.position]]
        self.assertEqual(len(minimum), 22)
        validate_roster(minimum)

    def test_falling_below_any_position_minimum_is_rejected(self):
        full = list(roster_for("seattle").values())
        for position, minimum in MINIMUMS.items():
            players = [player for player in full
                       if player.position != position or player.depth < minimum]
            with self.subTest(position=position), self.assertRaisesRegex(ValueError, f"{position} needs at least {minimum}"):
                validate_roster(players)

    def test_unknown_positions_and_duplicate_ids_are_rejected(self):
        full = list(roster_for("seattle").values())
        with self.assertRaisesRegex(ValueError, "Unknown roster position"):
            validate_roster([replace(full[0], position="UNKNOWN"), *full[1:]])
        with self.assertRaisesRegex(ValueError, "duplicate player IDs"):
            validate_roster([*full, full[0]])

    def test_returned_mapping_cannot_change_another_call(self):
        roster = roster_for("seattle")
        original = roster.copy()
        roster.pop("QB1")
        self.assertEqual(roster_for("seattle"), original)

    def test_box_scores_use_the_default_depth_players(self):
        for team in TEAMS:
            with self.subTest(team=team.id):
                roster = roster_for(team.id)
                game = generate_schedule(team.id)[0]
                result = simulate_game(team.id, game, season=1)
                box = result["home"] if game.venue == "Home" else result["away"]
                self.assertEqual(box["passing"][0]["player"], roster["QB1"].name)
                self.assertEqual(box["rushing"][0]["player"], roster["RB1"].name)
                self.assertEqual(box["kicking"][0]["player"], roster["K1"].name)
                self.assertEqual([row["player"] for row in box["receiving"]],
                                 [roster[slot].name for slot in ("WR1", "WR2", "TE1", "RB1")])


if __name__ == "__main__":
    unittest.main()
