import unittest

from app.league import GROUPS, TEAMS, generate_league_schedule, generate_schedule, rotating_group
from app.simulation import roster_for, simulate_game, simulate_league_week, simulate_through_week
from app.standings import standings_through_week


class ScheduleTests(unittest.TestCase):
    def test_every_team_gets_seventeen_games(self) -> None:
        for team in TEAMS:
            self.assertEqual(len(generate_schedule(team.id)), 17, team.city)

    def test_every_week_has_fifteen_games_and_every_team(self) -> None:
        schedule = generate_league_schedule(season=1)
        self.assertEqual(len(schedule), 255)
        for week in range(1, 18):
            games = [game for game in schedule if game.week == week]
            participants = [team_id for game in games for team_id in (game.away_id, game.home_id)]
            self.assertEqual(len(games), 15)
            self.assertEqual(set(participants), {team.id for team in TEAMS})

    def test_home_games_are_balanced(self) -> None:
        schedule = generate_league_schedule(season=1)
        for team in TEAMS:
            home_games = sum(game.home_id == team.id for game in schedule)
            self.assertIn(home_games, (8, 9))

    def test_schedule_uses_required_formula(self) -> None:
        games = generate_schedule("san-francisco")
        reasons = [game.reason for game in games]
        self.assertEqual(reasons.count("Group rematch"), 8)
        self.assertEqual(reasons.count("Same-place matchup"), 5)
        self.assertEqual(reasons.count("Rotating group"), 4)

    def test_group_opponents_are_played_home_and_away(self) -> None:
        games = generate_schedule("san-francisco")
        group_games = [game for game in games if game.reason == "Group rematch"]
        opponents = {game.opponent_id for game in group_games}
        self.assertEqual(len(opponents), 4)
        for opponent in opponents:
            venues = {game.venue for game in group_games if game.opponent_id == opponent}
            self.assertEqual(venues, {"Home", "Away"})

    def test_rotation_covers_every_other_group_in_five_seasons(self) -> None:
        for group in GROUPS:
            opponents = {rotating_group(group, season) for season in range(1, 6)}
            self.assertEqual(opponents, set(GROUPS) - {group})

    def test_simulation_is_deterministic(self) -> None:
        game = generate_schedule("san-francisco")[0]
        self.assertEqual(
            simulate_game("san-francisco", game, season=1),
            simulate_game("san-francisco", game, season=1),
        )

    def test_simulation_returns_consistent_box_score(self) -> None:
        game = generate_schedule("san-francisco")[0]
        result = simulate_game("san-francisco", game, season=1)
        for side in ("home", "away"):
            box = result[side]
            self.assertEqual(box["score"], box["scoring"]["touchdowns"] * 7 + box["scoring"]["field_goals"] * 3)
            self.assertEqual(sum(row["yards"] for row in box["receiving"]), box["team_stats"]["passing_yards"])
            self.assertEqual(sum(row["receptions"] for row in box["receiving"]), box["passing"][0]["completions"])
        possession_seconds = []
        for side in ("home", "away"):
            minutes, seconds = result[side]["team_stats"]["time_of_possession"].split(":")
            possession_seconds.append(int(minutes) * 60 + int(seconds))
        self.assertEqual(sum(possession_seconds), 60 * 60)

    def test_week_progress_updates_record(self) -> None:
        season = simulate_through_week("san-francisco", season=1, week=4)
        record = season["record"]
        self.assertEqual(record["wins"] + record["losses"] + record["ties"], 4)
        self.assertEqual(season["next_week"], 5)

    def test_week_contains_fourteen_other_league_results(self) -> None:
        season = simulate_through_week("san-francisco", season=1, week=1)
        self.assertEqual(len(season["league_results"]), 14)
        league_week = simulate_league_week(season=1, week=1)
        self.assertEqual(len(league_week), 15)
        selected = next(
            result for result in league_week
            if "san-francisco" in (result["home"]["team"]["id"], result["away"]["team"]["id"])
        )
        self.assertEqual(selected["home"]["score"], season["result"]["home"]["score"])
        self.assertEqual(selected["away"]["score"], season["result"]["away"]["score"])

    def test_roster_names_are_unique_within_team(self) -> None:
        roster = roster_for("san-francisco")
        self.assertEqual(len({player.name for player in roster.values()}), len(roster))

    def test_standings_include_six_complete_groups(self) -> None:
        data = standings_through_week(season=1, week=5)
        self.assertEqual(len(data["groups"]), 6)
        self.assertTrue(all(len(group["teams"]) == 5 for group in data["groups"]))
        rows = [row for group in data["groups"] for row in group["teams"]]
        self.assertEqual(len({row["team"]["id"] for row in rows}), 30)
        self.assertTrue(all(row["wins"] + row["losses"] + row["ties"] == 5 for row in rows))

    def test_playoff_race_has_six_winners_and_eight_wildcards(self) -> None:
        race = standings_through_week(season=1, week=7)["playoff_race"]
        self.assertEqual(len(race), 14)
        self.assertEqual(sum(row["qualification"] == "Group winner" for row in race), 6)
        self.assertEqual(sum(row["qualification"] == "Wildcard" for row in race), 8)
        self.assertEqual([row["seed"] for row in race if row["bye"]], [1, 2])

    def test_league_records_balance(self) -> None:
        rows = [
            row
            for group in standings_through_week(season=1, week=4)["groups"]
            for row in group["teams"]
        ]
        self.assertEqual(sum(row["wins"] for row in rows), sum(row["losses"] for row in rows))
        self.assertEqual(sum(row["wins"] + row["losses"] + row["ties"] for row in rows), 120)


if __name__ == "__main__":
    unittest.main()
