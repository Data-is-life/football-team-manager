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

    def test_profile_players_match_simulated_box_scores(self):
        team_id = "san-francisco"
        players = {player["name"] for player in team_profile(team_id)["roster"]}
        game = generate_schedule(team_id)[0]
        result = simulate_game(team_id, game, season=1)
        box = result["home"] if game.venue == "Home" else result["away"]
        for category in ("passing", "rushing", "receiving", "kicking"):
            self.assertTrue(all(row["player"] in players for row in box[category]))

    def test_standings_ratings_match_all_team_profiles(self):
        profiles = {team.id: team_profile(team.id)["ratings"] for team in TEAMS}
        for week, run_seed in ((1, 0), (17, 1234)):
            standings = standings_through_week(1, week, run_seed)
            rows = [row for group in standings["groups"] for row in group["teams"]]
            self.assertEqual({row["team"]["id"] for row in rows}, set(profiles))
            self.assertEqual(len(rows), 30)
            for row in rows + standings["playoff_race"]:
                with self.subTest(week=week, team=row["team"]["id"]):
                    self.assertEqual(row["ratings"], profiles[row["team"]["id"]])

    def test_unknown_team_returns_404(self):
        with self.assertRaises(HTTPException) as error:
            team_profile("not-a-team")
        self.assertEqual(error.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
