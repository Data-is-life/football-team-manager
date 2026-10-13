import copy
import random
import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException

from app.league import TEAMS, ScheduledGame
from app.main import playoff_round
from app.playoffs import pair_survivors, playoffs_through_round, postseason_snapshot
from app.simulation import _team_box, resolve_overtime, simulate_game
from app.standings import standings_through_week


class PlayoffTests(unittest.TestCase):
    def test_qualification_and_initial_pairings(self):
        snapshot = postseason_snapshot(1, 0)
        self.assertEqual(snapshot["field"], standings_through_week(1, 17)["playoff_race"])
        field = snapshot["field"]
        self.assertEqual(len({row["team"]["id"] for row in field}), 14)
        self.assertEqual(sum(row["qualification"] == "Group winner" for row in field), 6)
        self.assertEqual([row["seed"] for row in snapshot["upcoming"]["byes"]], [1, 2])
        self.assertEqual(
            [(game["home"]["seed"], game["away"]["seed"]) for game in snapshot["upcoming"]["games"]],
            [(3, 14), (4, 13), (5, 12), (6, 11), (7, 10), (8, 9)],
        )

    def test_reseeding_after_upsets_uses_original_seeds(self):
        survivors = [{"seed": seed} for seed in (12, 2, 9, 1, 14, 4, 10, 6)]
        self.assertEqual(
            [(home["seed"], away["seed"]) for home, away in pair_survivors(survivors)],
            [(1, 14), (2, 12), (4, 10), (6, 9)],
        )

    def test_complete_brackets_have_one_champion_and_no_repeat_losers(self):
        for season in range(1, 11):
            with self.subTest(season=season):
                snapshot = postseason_snapshot(season, 4)
                self.assertEqual([len(row["games"]) for row in snapshot["rounds"]], [6, 4, 2, 1])
                self.assertEqual(len(snapshot["survivors"]), 1)
                self.assertEqual(snapshot["champion"], snapshot["survivors"][0])
                self.assertIsNone(snapshot["upcoming"])
                alive = {row["team"]["id"] for row in snapshot["field"]}
                for round_ in snapshot["rounds"]:
                    participants = []
                    winners = {row["team"]["id"] for row in round_["byes"]}
                    for game in round_["games"]:
                        home_id, away_id = game["home"]["team"]["id"], game["away"]["team"]["id"]
                        participants.extend((home_id, away_id))
                        self.assertIn(home_id, alive)
                        self.assertIn(away_id, alive)
                        self.assertLess(game["home"]["seed"], game["away"]["seed"])
                        self.assertEqual(game["neutral_site"], round_["number"] == 4)
                        result = game["result"]
                        self.assertNotEqual(result["home"]["score"], result["away"]["score"])
                        winner_id = result["home"]["team"]["id"] if result["home"]["score"] > result["away"]["score"] else result["away"]["team"]["id"]
                        self.assertEqual(game["winner"]["team"]["id"], winner_id)
                        winners.add(winner_id)
                        for side in ("home", "away"):
                            box = result[side]
                            self.assertEqual(box["score"], box["scoring"]["touchdowns"] * 7 + box["scoring"]["field_goals"] * 3)
                    self.assertEqual(len(participants), len(set(participants)))
                    expected = pair_survivors([row for row in snapshot["field"] if row["team"]["id"] in alive and row not in round_["byes"]])
                    self.assertEqual([(game["home"]["seed"], game["away"]["seed"]) for game in round_["games"]],
                                     [(home["seed"], away["seed"]) for home, away in expected])
                    alive = winners
                self.assertEqual(alive, {snapshot["champion"]["team"]["id"]})

    def test_neutral_final_passes_no_home_advantage_to_both_teams(self):
        game = ScheduledGame(week=21, opponent_id="seattle", opponent="Seattle",
                             opponent_group="Pacific", venue="Home", reason="Championship")
        with patch("app.simulation._team_box", wraps=_team_box) as boxes:
            simulate_game("san-francisco", game, 1, allow_ties=False, neutral_site=True)
            self.assertEqual([call.args[2] for call in boxes.call_args_list], [None, None])

    def test_playoff_overtime_cannot_choose_the_regular_season_tie_path(self):
        def box(team_id):
            return {"team": {"id": team_id}, "score": 24,
                    "scoring": {"touchdowns": 3, "field_goals": 1},
                    "kicking": [{"field_goals_made": 1, "field_goals_attempted": 1}]}
        home, away = box("seattle"), box("san-francisco")
        rng = Mock()
        rng.random.return_value = 0.01
        self.assertTrue(resolve_overtime(home, away, rng, allow_ties=False, neutral_site=True))
        self.assertNotEqual(home["score"], away["score"])

    def test_champion_is_identical_for_every_selected_team(self):
        snapshot = postseason_snapshot(1, 4)
        for team in TEAMS:
            response = playoffs_through_round(team.id, 1, 4)
            self.assertEqual(response["champion"], snapshot["champion"])
            self.assertEqual(response["qualified"], any(row["team"]["id"] == team.id for row in snapshot["field"]))
            self.assertEqual(response["eliminated"], response["qualified"] and team.id != snapshot["champion"]["team"]["id"])
            self.assertTrue(response["postseason_complete"])
            self.assertIsNone(response["next_round"])

    def test_round_prefix_is_repeatable_and_does_not_mutate_standings(self):
        standings_before = copy.deepcopy(standings_through_week(1, 17))
        first = copy.deepcopy(postseason_snapshot(1, 2))
        postseason_snapshot.cache_clear()
        second = postseason_snapshot(1, 2)
        self.assertEqual(first, second)
        self.assertEqual(first["rounds"], postseason_snapshot(1, 4)["rounds"][:2])
        self.assertEqual(standings_through_week(1, 17), standings_before)

    def test_invalid_team_and_rounds_are_rejected(self):
        for team, round_number, expected in (("unknown", 0, 404), ("seattle", -1, 400), ("seattle", 5, 400)):
            with self.subTest(team=team, round=round_number), self.assertRaises(HTTPException) as error:
                playoff_round(team, round_number, season=1)
            self.assertEqual(error.exception.status_code, expected)


if __name__ == "__main__":
    unittest.main()
