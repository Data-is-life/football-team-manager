import copy
import unittest

from app.league import TEAM_BY_ID, TEAMS, ScheduledGame, generate_schedule
from app.playoffs import playoffs_through_round, postseason_snapshot
from app.simulation import simulate_game, simulate_league_week, simulate_through_week
from app.standings import TeamStanding, _rank_teams, standings_through_week


class RunSeedTests(unittest.TestCase):
    def test_replaying_a_seed_is_stable_and_other_seeds_change_results(self):
        first = simulate_league_week(1, 1, 1234)
        self.assertEqual(first, simulate_league_week(1, 1, 1234))
        self.assertNotEqual(first, simulate_league_week(1, 1, 5678))
        self.assertEqual(simulate_league_week(1, 1), simulate_league_week(1, 1, 0))

    def test_the_same_game_agrees_from_either_team_perspective(self):
        game = generate_schedule("seattle")[0]
        team = TEAM_BY_ID["seattle"]
        reverse = ScheduledGame(game.week, team.id, team.city, team.group,
                                "Away" if game.venue == "Home" else "Home", game.reason)
        for seed in (0, 87, 4294967295):
            first = simulate_game("seattle", game, 1, run_seed=seed)
            other = simulate_game(game.opponent_id, reverse, 1, run_seed=seed)
            self.assertEqual(first["home"], other["home"])
            self.assertEqual(first["away"], other["away"])
            self.assertEqual(first["overtime"], other["overtime"])

    def test_league_scores_records_standings_and_player_totals_agree(self):
        seed = 91
        league = simulate_league_week(1, 3, seed)
        standings = standings_through_week(1, 3, seed)
        rows = {row["team"]["id"]: row for group in standings["groups"] for row in group["teams"]}
        for team in TEAMS:
            data = simulate_through_week(team.id, 1, 3, seed)
            match = next(game for game in league if team.id in (game["home"]["team"]["id"], game["away"]["team"]["id"]))
            self.assertEqual(data["run_seed"], seed)
            self.assertEqual(data["result"]["home"], match["home"])
            self.assertEqual(data["result"]["away"], match["away"])
            self.assertEqual(data["roster_stats"]["games"], 3)
            for key in ("wins", "losses", "ties"):
                self.assertEqual(data["record"][key], rows[team.id][key])
            previous = simulate_through_week(team.id, 1, 2, seed)
            self.assertEqual(data["game_results"][:2], previous["game_results"])
            expected = {(game["home"]["team"]["id"], game["away"]["team"]["id"]):
                        (game["home"]["score"], game["away"]["score"])
                        for game in league if game is not match}
            self.assertEqual({(game["home"]["id"], game["away"]["id"]):
                              (game["home_score"], game["away_score"])
                              for game in data["league_results"]}, expected)

    def test_final_seeds_and_postseason_belong_to_the_same_run(self):
        for seed in (33, 44):
            regular = simulate_through_week("seattle", 1, 17, seed)
            playoffs = playoffs_through_round("seattle", 1, 4, seed)
            self.assertEqual(playoffs["run_seed"], seed)
            self.assertEqual(playoffs["field"], regular["standings"]["playoff_race"])
            for round_ in playoffs["rounds"]:
                for game in round_["games"]:
                    self.assertNotEqual(game["result"]["home"]["score"], game["result"]["away"]["score"])

    def test_caches_do_not_mix_runs(self):
        first_standings = copy.deepcopy(standings_through_week(1, 17, 101))
        first_playoffs = copy.deepcopy(postseason_snapshot(1, 4, 101))
        standings_through_week(1, 17, 202)
        postseason_snapshot(1, 4, 202)
        self.assertEqual(standings_through_week(1, 17, 101), first_standings)
        self.assertEqual(postseason_snapshot(1, 4, 101), first_playoffs)
        standings_through_week.cache_clear()
        postseason_snapshot.cache_clear()
        self.assertEqual(standings_through_week(1, 17, 101), first_standings)
        self.assertEqual(postseason_snapshot(1, 4, 101), first_playoffs)

    def test_champion_varies_between_sample_runs(self):
        champions = {postseason_snapshot(1, 4, seed)["champion"]["team"]["id"] for seed in range(1, 9)}
        self.assertGreater(len(champions), 1)

    def test_final_tiebreak_draw_uses_the_run_seed(self):
        ids = [team.id for team in TEAMS[:5]]
        standings = {team_id: TeamStanding(team_id) for team_id in ids}
        orders = {tuple(_rank_teams(ids, standings, 1, seed)) for seed in range(1, 5)}
        self.assertGreater(len(orders), 1)
