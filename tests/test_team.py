import unittest

from fastapi import HTTPException

from app.league import TEAMS, generate_schedule
from app.main import team_profile
from app.simulation import ROSTER_RULES, roster_for, simulate_game, team_ratings
from app.standings import standings_through_week


class TeamProfileTests(unittest.TestCase):
    def test_profiles_cover_each_teams_actual_roster_and_ratings(self):
        for team in TEAMS:
            with self.subTest(team=team.id):
                profile = team_profile(team.id)
                self.assertEqual(profile["team"]["id"], team.id)
                self.assertEqual(profile["team"]["city"], team.city)
                self.assertEqual(profile["team"]["group"], team.group)
                self.assertEqual(profile["ratings"]["offense"], team_ratings(team.id).offense)
                self.assertEqual(profile["ratings"]["defense"], team_ratings(team.id).defense)
                self.assertEqual([rule["position"] for rule in profile["roster_rules"]], list(ROSTER_RULES))
                self.assertEqual(
                    [player["name"] for player in profile["roster"]],
                    [player.name for player in roster_for(team.id).values()],
                )
                self.assertEqual(len({player["id"] for player in profile["roster"]}), 38)
                for player in profile["roster"]:
                    self.assertIsInstance(player["rating"], int)
                    self.assertGreaterEqual(player["rating"], 50)
                    self.assertLessEqual(player["rating"], 99)
                self.assertEqual(profile, team_profile(team.id))

    def test_player_ages_are_stable_and_consistent_with_experience(self):
        ages = set()
        for team in TEAMS:
            profile = team_profile(team.id)
            repeated = team_profile(team.id)
            for player, again in zip(profile["roster"], repeated["roster"]):
                with self.subTest(player=player["id"]):
                    self.assertIsInstance(player["age"], int)
                    self.assertGreaterEqual(player["age"], 21)
                    self.assertLessEqual(player["age"], 36)
                    self.assertIn(player["age"] - player["experience"], range(21, 25))
                    self.assertEqual(player["age"], again["age"])
                    self.assertEqual(player["age"], roster_for(team.id)[f'{player["position"]}{player["depth"]}'].age)
                    ages.add(player["age"])
        self.assertGreater(len(ages), 1)

    def test_profile_players_match_simulated_box_scores(self):
        team_id = "san-francisco"
        players = {player["name"] for player in team_profile(team_id)["roster"]}
        game = generate_schedule(team_id)[0]
        result = simulate_game(team_id, game, season=1)
        box = result["home"] if game.venue == "Home" else result["away"]
        for category in ("passing", "rushing", "receiving", "kicking"):
            self.assertTrue(all(row["player"] in players for row in box[category]))

    def test_standings_ratings_match_all_team_profiles_for_each_run_and_season(self):
        for seed in (0, 1234, 5678):
            profiles = {team.id: team_profile(team.id, seed)["ratings"] for team in TEAMS}
            first_final = standings_through_week(1, 17, seed)
            ranks = tuple(sorted((row["team"]["id"], row["rank"])
                                 for group in first_final["groups"] for row in group["teams"]))
            for season, week, prior in ((1, 1, ()), (1, 17, ()), (2, 1, ranks)):
                standings = standings_through_week(season, week, seed, prior)
                rows = [row for group in standings["groups"] for row in group["teams"]]
                self.assertEqual({row["team"]["id"] for row in rows}, set(profiles))
                self.assertEqual(len(rows), 30)
                for row in rows + standings["playoff_race"]:
                    with self.subTest(season=season, week=week, seed=seed, team=row["team"]["id"]):
                        self.assertEqual(row["ratings"], profiles[row["team"]["id"]])

    def test_unknown_team_returns_404(self):
        with self.assertRaises(HTTPException) as error:
            team_profile("not-a-team")
        self.assertEqual(error.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
