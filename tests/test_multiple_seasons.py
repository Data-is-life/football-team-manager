import json
import unittest

from fastapi import HTTPException

from app.league import TEAMS, TEAM_BY_ID, default_standings, generate_league_schedule, generate_schedule
from app.main import parse_prior_standings, team_schedule, simulate_week, playoff_round
from app.simulation import league_week_scores, simulate_league_week, simulate_through_week
from app.standings import standings_through_week
from app.playoffs import postseason_snapshot


class MultipleSeasonTests(unittest.TestCase):
    def test_previous_season_ranks_drive_all_next_season_views(self):
        seed = 1234
        final = standings_through_week(1, 17, seed)
        ranks = {row['team']['id']: row['rank'] for group in final['groups'] for row in group['teams']}
        context = parse_prior_standings(json.dumps(ranks))
        schedule = generate_league_schedule(2, ranks)
        self.assertEqual(len(schedule), 255)
        for team in TEAMS:
            games = generate_schedule(team.id, 2, ranks)
            self.assertEqual(len(games), 17)
            # Exactly five cross-group same-place games, ranked using season 1 results.
            same_place = [g for g in games if g.reason == 'Same-place matchup']
            self.assertEqual(len(same_place), 5)
            self.assertTrue(all(ranks[g.opponent_id] == ranks[team.id] for g in same_place))
            self.assertEqual(team_schedule(team.id, 2, json.dumps(ranks))['games'],
                             team_schedule(team.id, 2, json.dumps(dict(reversed(list(ranks.items())))))['games'])
        data = simulate_week('seattle', 17, 2, seed, json.dumps(ranks))
        self.assertEqual([g['opponent_id'] for g in data['game_results']],
                         [g.opponent_id for g in generate_schedule('seattle', 2, ranks)])
        row = next(row for group in data['standings']['groups'] for row in group['teams'] if row['team']['id'] == 'seattle')
        self.assertEqual(data['record'], {key: row[key] for key in ('wins', 'losses', 'ties')})
        self.assertEqual(data['roster_stats']['games'], 17)
        postseason = playoff_round('seattle', 4, 2, seed, json.dumps(ranks))
        self.assertEqual(postseason['field'], data['standings']['playoff_race'])
        # Week results and cached score inputs use the same context as schedule/standings/playoffs.
        full_week = simulate_league_week(2, 17, seed, prior_standings=context)
        self.assertEqual(league_week_scores(2, 17, seed, context), tuple(
            (g['home']['team']['id'], g['away']['team']['id'], g['home']['score'], g['away']['score']) for g in full_week))
        own = next(g for g in full_week if 'seattle' in (g['home']['team']['id'], g['away']['team']['id']))
        self.assertEqual(data['result']['home'], own['home'])
        self.assertEqual(data['result']['away'], own['away'])
        self.assertEqual(data, simulate_through_week('seattle', 2, 17, seed, context))

    def test_schedule_context_is_validated_and_canonicalized(self):
        ranks = default_standings()
        self.assertEqual(parse_prior_standings(None), ())
        self.assertEqual(parse_prior_standings(json.dumps(ranks)), tuple(sorted(ranks.items())))
        for invalid in ('{', '[]', 'null', '{}', json.dumps({**ranks, 'seattle': True}),
                        json.dumps({**ranks, 'seattle': 2}), json.dumps({**ranks, 'seattle': 1.0})):
            with self.subTest(invalid=invalid):
                with self.assertRaises(HTTPException) as error:
                    parse_prior_standings(invalid)
                self.assertEqual(error.exception.status_code, 422)

    def test_caches_do_not_mix_different_prior_standings(self):
        ranks = default_standings()
        a = tuple(sorted(ranks.items()))
        ranks['seattle'], ranks['las-vegas'] = ranks['las-vegas'], ranks['seattle']
        b = tuple(sorted(ranks.items()))
        for cached, args in ((league_week_scores, (2, 1, 1234)),
                             (standings_through_week, (2, 17, 1234)),
                             (postseason_snapshot, (2, 0, 1234))):
            cached.cache_clear()
            first = cached(*args, a)
            other = cached(*args, b)
            self.assertNotEqual(first, other)
            self.assertEqual(first, cached(*args, a))
            self.assertEqual(cached.cache_info().misses, 2)
            self.assertEqual(cached.cache_info().hits, 1)


if __name__ == '__main__':
    unittest.main()
