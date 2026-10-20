from dataclasses import FrozenInstanceError, asdict, replace
import unittest
from unittest.mock import patch

from app.attributes import generate_attributes
from app.league import TEAMS, generate_schedule
from app.main import team_profile
from app.simulation import _roster_players, roster_for, simulate_game


SPECIALTIES = {
    "QB": {"accuracy", "arm_strength", "clutch"},
    "WR": {"catching", "strength"}, "TE": {"catching", "strength"},
    "RB": {"strength", "agility"}, "OL": {"strength", "blocking"},
    "DL": {"strength", "tackling"}, "LB": {"strength", "tackling"},
    "CB": {"strength", "agility"}, "S": {"strength", "agility"},
    "K": {"kick_accuracy", "kick_power"},
}


class PlayerAttributeTests(unittest.TestCase):
    def test_all_teams_have_exact_position_attributes_with_bounded_values(self):
        for team in TEAMS:
            profile = team_profile(team.id)
            rules = {rule["position"]: rule for rule in profile["roster_rules"]}
            for player in profile["roster"]:
                expected = {"iq", "speed", "durability"} | SPECIALTIES[player["position"]]
                self.assertEqual(set(player["attributes"]), expected)
                self.assertEqual({item["key"] for item in rules[player["position"]]["attributes"]}, expected)
                for value in player["attributes"].values():
                    self.assertIs(type(value), int)
                    self.assertGreaterEqual(value, 1)
                    self.assertLessEqual(value, 99)
            qb_rule = rules["QB"]["attributes"]
            self.assertEqual(next(item["label"] for item in qb_rule if item["key"] == "clutch"), "Clutch Factor")

    def test_attributes_reproduce_after_clearing_the_roster_cache(self):
        original = team_profile("seattle")
        _roster_players.cache_clear()
        self.assertEqual(team_profile("seattle"), original)

    def test_nested_attributes_are_immutable_and_api_data_is_independent(self):
        player = roster_for("seattle")["QB1"]
        with self.assertRaises(FrozenInstanceError):
            player.attributes.clutch = 99
        profile = team_profile("seattle")
        expected = profile["roster"][0]["attributes"]["iq"]
        profile["roster"][0]["attributes"]["iq"] = -1
        profile["roster_rules"][0]["attributes"][0]["label"] = "Changed"
        fresh = team_profile("seattle")
        self.assertEqual(fresh["roster"][0]["attributes"]["iq"], expected)
        self.assertEqual(fresh["roster_rules"][0]["attributes"][0]["label"], "Football IQ")

    def test_players_with_equal_overall_can_have_different_attribute_profiles(self):
        by_rating = {}
        for team in TEAMS:
            for player in roster_for(team.id).values():
                key = (player.position, player.rating)
                by_rating.setdefault(key, set()).add(tuple(asdict(player.attributes).values()))
        self.assertTrue(any(len(profiles) > 1 for profiles in by_rating.values()))

    def test_generated_attributes_are_clamped_and_repeatable(self):
        for position in SPECIALTIES:
            for rating in (1, 50, 99):
                attributes = generate_attributes("test-player", position, rating)
                self.assertEqual(attributes, generate_attributes("test-player", position, rating))
                for value in asdict(attributes).values():
                    if value is not None:
                        self.assertGreaterEqual(value, 1)
                        self.assertLessEqual(value, 99)

    def test_attributes_including_clutch_do_not_change_current_gameplay(self):
        game = generate_schedule("seattle")[0]
        expected = simulate_game("seattle", game, 1)
        original_roster_for = roster_for
        alternate = {slot: replace(player, attributes=generate_attributes(player.id, player.position, 1))
                     for slot, player in roster_for("seattle").items()}
        with patch("app.simulation.roster_for", side_effect=lambda team_id:
                   alternate if team_id == "seattle" else original_roster_for(team_id)):
            self.assertEqual(simulate_game("seattle", game, 1), expected)
