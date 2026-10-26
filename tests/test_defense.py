import copy
import random
import unittest
from unittest.mock import patch

from app.defense import DEFENSIVE_UNIT, _allocate, add_defense_and_blocking
from app.simulation import roster_for, simulate_game, simulate_league_week
from app.league import generate_schedule


class DefenseStatsTests(unittest.TestCase):
    def test_counts_agree_with_opponent_and_participation(self):
        for seed in (0, 1234):
            for week in (1, 9, 17):
                for game in simulate_league_week(1, week, seed):
                    for side, other in (('home', 'away'), ('away', 'home')):
                        box, opponent = game[side], game[other]
                        with self.subTest(seed=seed, week=week, team=box['team']['id']):
                            defense = box['defense']
                            self.assertEqual(len(defense), 18)
                            roster = {p.id: p for p in roster_for(box['team']['id'], seed).values()}
                            total_snaps = opponent['team_stats']['total_plays'] + opponent['team_stats']['sacks_allowed']
                            for row in defense + box['blocking']:
                                self.assertEqual(row['player'], roster[row['player_id']].name)
                            for position, count in DEFENSIVE_UNIT.items():
                                self.assertEqual(sum(row['snaps'] for row in defense if row['position'] == position), count * total_snaps)
                            for row in defense:
                                self.assertLessEqual(row['snaps'], total_snaps)
                                self.assertGreaterEqual(row['tackles'], row['sacks'])
                                self.assertLessEqual(row['tackles'] + row['interceptions'], row['snaps'])
                                self.assertTrue(all(isinstance(row[key], int) and row[key] >= 0
                                    for key in ('snaps', 'tackles', 'sacks', 'interceptions')))
                            self.assertEqual(sum(row['sacks'] for row in defense), opponent['team_stats']['sacks_allowed'])
                            self.assertEqual(sum(row['interceptions'] for row in defense), sum(row['interceptions'] for row in opponent['passing']))
                            tackles = opponent['team_stats']['rush_attempts'] - sum(row['touchdowns'] for row in opponent['rushing'])
                            tackles += sum(row['completions'] - row['touchdowns'] for row in opponent['passing'])
                            tackles += opponent['team_stats']['sacks_allowed']
                            self.assertEqual(sum(row['tackles'] for row in defense), tackles)
                            self.assertEqual(sum(row['sacks_allowed'] for row in box['blocking']), box['team_stats']['sacks_allowed'])
                            self.assertEqual(sum(row['sacks_allowed'] for row in box['blocking']), sum(row['sacks'] for row in opponent['defense']))
                            self.assertEqual(len(box['blocking']), 8)
                            for row in box['blocking']:
                                starter = roster[row['player_id']].depth <= 5
                                self.assertEqual(row['pass_block_snaps'], (box['team_stats']['pass_attempts'] + box['team_stats']['sacks_allowed']) if starter else 0)
                                self.assertEqual(row['run_block_snaps'], box['team_stats']['rush_attempts'] if starter else 0)
                                if not starter:
                                    self.assertEqual(row['sacks_allowed'], 0)

    def test_allocator_preserves_totals_without_exceeding_capacity(self):
        rng = random.Random(5)
        for _ in range(200):
            capacities = [rng.randrange(10) for _ in range(8)]
            total = rng.randrange(sum(capacities) + 1)
            result = _allocate(total, [rng.uniform(.1, 5) for _ in capacities], capacities)
            self.assertEqual(sum(result), total)
            self.assertTrue(all(0 <= value <= cap for value, cap in zip(result, capacities)))
        with self.assertRaises(ValueError):
            _allocate(2, [1], [1])

    def test_no_plays_produce_zero_line_and_defensive_counts(self):
        game = simulate_game('seattle', generate_schedule('seattle')[0], 1)
        box = copy.deepcopy(game['home'])
        for key in ('pass_attempts', 'rush_attempts', 'total_plays', 'sacks_allowed'):
            box['team_stats'][key] = 0
        for row in box['passing']:
            row.update(completions=0, touchdowns=0, interceptions=0)
        for row in box['rushing']:
            row['touchdowns'] = 0
        add_defense_and_blocking(box, box, roster_for(box['team']['id']), random.Random(1))
        for row in box['defense']:
            self.assertTrue(all(row[key] == 0 for key in ('snaps', 'tackles', 'sacks', 'interceptions')))
        for row in box['blocking']:
            self.assertTrue(all(row[key] == 0 for key in ('pass_block_snaps', 'run_block_snaps', 'sacks_allowed')))

    def test_new_detail_preserves_existing_scores_and_offensive_production(self):
        for seed in (0, 1234):
            for game in generate_schedule('seattle')[:3]:
                with patch('app.simulation.add_defense_and_blocking'):
                    baseline = simulate_game('seattle', game, 1, run_seed=seed)
                actual = simulate_game('seattle', game, 1, run_seed=seed)
                for side in ('home', 'away'):
                    actual[side].pop('defense')
                    actual[side].pop('blocking')
                self.assertEqual(actual, baseline)

    def test_score_only_path_matches_full_boxes_without_extra_detail(self):
        detailed = simulate_league_week(1, 2, 1234)
        scores = simulate_league_week(1, 2, 1234, include_defense_and_blocking=False)
        for game in detailed:
            for side in ('home', 'away'):
                game[side].pop('defense')
                game[side].pop('blocking')
        self.assertEqual(scores, detailed)


if __name__ == '__main__':
    unittest.main()
