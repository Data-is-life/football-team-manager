from contextlib import ExitStack
import unittest
from unittest.mock import patch

from app.simulation import league_week_scores, simulate_league_week, _league_week_matchups
from app.standings import standings_through_week


class ScoreCacheTests(unittest.TestCase):
    def setUp(self):
        league_week_scores.cache_clear()
        standings_through_week.cache_clear()

    def tearDown(self):
        league_week_scores.cache_clear()
        standings_through_week.cache_clear()

    def test_reuses_scores_but_separates_season_week_and_run(self):
        with patch('app.simulation._league_week_matchups', wraps=_league_week_matchups) as simulate:
            for context in ((1, 1, 0), (1, 2, 0), (1, 1, 1234), (2, 1, 0)):
                first = league_week_scores(*context)
                self.assertEqual(first, league_week_scores(*context))
                expected = tuple((g['home']['team']['id'], g['away']['team']['id'],
                                  g['home']['score'], g['away']['score'])
                                 for g in simulate_league_week(*context))
                self.assertEqual(first, expected)
            self.assertEqual(simulate.call_count, 8)  # Four score misses plus four full-game references.

    def test_cached_scores_cannot_be_modified_by_callers(self):
        scores = league_week_scores(1, 1, 11)
        with self.assertRaises(TypeError):
            scores[0][2] = 999
        with self.assertRaises(TypeError):
            scores[0] = ()

    def test_advancing_standings_only_simulates_new_weeks(self):
        with patch('app.simulation._league_week_matchups', wraps=_league_week_matchups) as simulate:
            standings_through_week(1, 1, 11)
            standings_through_week(1, 2, 11)
            expected = standings_through_week(1, 3, 11)
            self.assertEqual(simulate.call_count, 3)
            league_week_scores.cache_clear()
            standings_through_week.cache_clear()
            self.assertEqual(expected, standings_through_week(1, 3, 11))

    def test_scores_match_full_games_across_rules_and_seeded_contexts(self):
        from app.lineups import lineup_context
        for seed in (0, 1234):
            for rules in range(1, 7):
                context = lineup_context((), seed, rules, rebuild_team='seattle' if rules >= 4 else None)
                for week in (1, 9, 17):
                    with self.subTest(seed=seed, rules=rules, week=week):
                        expected = tuple((g['home']['team']['id'], g['away']['team']['id'],
                                          g['home']['score'], g['away']['score'])
                                         for g in simulate_league_week(1, week, seed, roster_context=context))
                        self.assertEqual(league_week_scores(1, week, seed, roster_context=context), expected)

    def test_standings_score_path_skips_independent_statistical_streams(self):
        from app.lineups import lineup_context
        context = lineup_context((), 5678, 6, rebuild_team='seattle')
        expected = tuple((g['home']['team']['id'], g['away']['team']['id'], g['home']['score'], g['away']['score'])
                         for g in simulate_league_week(1, 17, 5678, roster_context=context))
        with ExitStack() as patches:
            for name in ('app.simulation.apply_usage', 'app.simulation.assign_possession',
                         'app.simulation.add_efficiency_stats', 'app.simulation.add_kicking_stats',
                         'app.rotation.add_participation', 'app.simulation.add_defense_and_blocking'):
                patches.enter_context(patch(name, side_effect=AssertionError('Stats must not run for standings')))
            self.assertEqual(league_week_scores(1, 17, 5678, roster_context=context), expected)


if __name__ == '__main__':
    unittest.main()
