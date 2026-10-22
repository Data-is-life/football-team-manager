import unittest
from unittest.mock import patch

from app.simulation import league_week_scores, simulate_league_week
from app.standings import standings_through_week


class ScoreCacheTests(unittest.TestCase):
    def setUp(self):
        league_week_scores.cache_clear()
        standings_through_week.cache_clear()

    def tearDown(self):
        league_week_scores.cache_clear()
        standings_through_week.cache_clear()

    def test_reuses_scores_but_separates_season_week_and_run(self):
        with patch('app.simulation.simulate_league_week', wraps=simulate_league_week) as simulate:
            for context in ((1, 1, 0), (1, 2, 0), (1, 1, 1234), (2, 1, 0)):
                first = league_week_scores(*context)
                self.assertEqual(first, league_week_scores(*context))
                expected = tuple((g['home']['team']['id'], g['away']['team']['id'],
                                  g['home']['score'], g['away']['score'])
                                 for g in simulate_league_week(*context))
                self.assertEqual(first, expected)
            self.assertEqual(simulate.call_count, 4)

    def test_cached_scores_cannot_be_modified_by_callers(self):
        scores = league_week_scores(1, 1, 11)
        with self.assertRaises(TypeError):
            scores[0][2] = 999
        with self.assertRaises(TypeError):
            scores[0] = ()

    def test_advancing_standings_only_simulates_new_weeks(self):
        with patch('app.simulation.simulate_league_week', wraps=simulate_league_week) as simulate:
            standings_through_week(1, 1, 11)
            standings_through_week(1, 2, 11)
            expected = standings_through_week(1, 3, 11)
            self.assertEqual(simulate.call_count, 3)
            league_week_scores.cache_clear()
            standings_through_week.cache_clear()
            self.assertEqual(expected, standings_through_week(1, 3, 11))


if __name__ == '__main__':
    unittest.main()
