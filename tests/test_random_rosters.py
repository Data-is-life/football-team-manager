from dataclasses import asdict
import unittest

from app.attributes import attribute_keys
from app.league import TEAMS, generate_schedule
from app.main import team_profile
from app.playoffs import postseason_snapshot
from app.simulation import _roster_players, roster_for, simulate_game, team_ratings, validate_roster


class RandomRosterTests(unittest.TestCase):
    def test_all_teams_get_new_valid_rosters_and_repeat_within_a_run(self):
        strength_changes = 0
        for team in TEAMS:
            first = team_profile(team.id, 1234)
            second = team_profile(team.id, 5678)
            self.assertEqual(first, team_profile(team.id, 1234))
            self.assertEqual(first['run_seed'], 1234)
            self.assertEqual(first['ratings'], asdict(team_ratings(team.id, 1234)))
            strength_changes += first['ratings'] != second['ratings']
            for field in ('name', 'rating', 'experience', 'age', 'attributes'):
                self.assertNotEqual([p[field] for p in first['roster']],
                                    [p[field] for p in second['roster']])
            for seed, profile in ((1234, first), (5678, second)):
                players = roster_for(team.id, seed)
                validate_roster(list(players.values()))
                self.assertEqual(len(players), 38)
                self.assertEqual(len({p.name for p in players.values()}), 38)
                for player in profile['roster']:
                    self.assertIn(player['age'] - player['experience'], range(21, 25))
                    self.assertIn(player['experience'], range(13))
                    self.assertGreaterEqual(player['rating'], 50)
                    self.assertLessEqual(player['rating'], 99)
                    self.assertEqual(set(player['attributes']), set(attribute_keys(player['position'])))
                    self.assertTrue(all(1 <= value <= 99 for value in player['attributes'].values()))
        self.assertGreater(strength_changes, 0)

    def test_cache_eviction_and_api_edits_cannot_change_a_run(self):
        expected = team_profile('seattle', 1234)
        altered = team_profile('seattle', 1234)
        altered['roster'][0]['name'] = 'Edited'
        altered['roster'][0]['attributes']['iq'] = 1
        roster_for('seattle', 1234).clear()
        for seed in range(130):
            roster_for('seattle', seed)
        self.assertEqual(expected, team_profile('seattle', 1234))
        _roster_players.cache_clear()
        self.assertEqual(expected, team_profile('seattle', 1234))

    def check_box(self, box, seed):
        players = {player.id: player for player in roster_for(box['team']['id'], seed).values()}
        for category in ('passing', 'rushing', 'receiving', 'kicking'):
            for row in box[category]:
                self.assertEqual(row['player'], players[row['player_id']].name)

    def test_regular_and_postseason_boxes_use_the_same_rosters_as_profiles(self):
        for seed in (1234, 5678):
            game = simulate_game('seattle', generate_schedule('seattle')[0], 1, run_seed=seed)
            self.check_box(game['home'], seed)
            self.check_box(game['away'], seed)
            postseason = postseason_snapshot(1, 4, seed)
            for round_ in postseason['rounds']:
                for matchup in round_['games']:
                    self.check_box(matchup['result']['home'], seed)
                    self.check_box(matchup['result']['away'], seed)


if __name__ == '__main__':
    unittest.main()
