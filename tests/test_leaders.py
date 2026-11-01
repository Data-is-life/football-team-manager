import json
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from fastapi import HTTPException
from app.leaders import METRICS, _season_totals, league_leaders
from app.league import TEAMS
from app.lineups import lineup_context
from app.main import CareerRequest, career_action
from app.simulation import ROSTER_RULES, simulate_through_week
from app.starter_choices import with_starters


class LeadersTests(TestCase):
    def test_totals_match_every_team_and_same_week_cutoff(self):
        for rules in (1, 7):
            context = lineup_context((), 1234, rules, 1, 1, 'seattle' if rules == 7 else None)
            totals = {row[0]: row[4] for row in _season_totals(1, 1, 1234, (), context)}
            for team in TEAMS:
                stats = simulate_through_week(team.id, 1, 1, 1234, (), context)['roster_stats']
                for player in stats['players']:
                    expected = tuple(player.get(category, {}).get(field, 0) for _, _, category, field in METRICS)
                    self.assertEqual(totals[player['player_id']], expected)
            payload = league_leaders('seattle', 1, 1, 1234, (), context)
            for category in payload['categories']:
                self.assertLessEqual(len(category['leaders']), 10)
                self.assertTrue(all(row['value'] > 0 for row in category['leaders']))
                self.assertEqual([r['value'] for r in category['leaders']], sorted((r['value'] for r in category['leaders']), reverse=True))

    def test_ties_are_shared_and_best_own_player_is_available_outside_top_ten(self):
        # Deterministic fixture covers ties at and beyond the display boundary.
        rows = tuple((f'other-{i:02}', f'Other {i}', 'QB', 'miami', (200-i,0,0,0,0)) for i in range(11))
        rows += (('own', 'Own', 'QB', 'seattle', (1,0,0,0,0)), ('own-zero', 'Zero', 'QB', 'seattle', (0,0,0,0,0)))
        with patch('app.leaders._season_totals', return_value=rows):
            result = league_leaders('seattle', 1, 1)
        passing = result['categories'][0]
        self.assertEqual(len(passing['leaders']), 10)
        self.assertEqual(passing['your_best']['rank'], 12)
        self.assertEqual(passing['your_best']['player_id'], 'own')
        self.assertIsNone(result['categories'][3]['your_best'])
        tied = tuple((str(i), 'Player', 'S', 'seattle' if i == 10 else 'miami', (0,0,0,1,0)) for i in range(12))
        with patch('app.leaders._season_totals', return_value=tied):
            result = league_leaders('seattle', 1, 1)['categories'][3]
        self.assertTrue(all(row['rank'] == 1 for row in result['leaders']))
        self.assertEqual(result['your_best']['rank'], 1)

    def test_manual_lineups_are_week_effective_and_cache_does_not_leak_mutation(self):
        base = lineup_context((), 1234, 7, 1, 1, 'seattle')
        players = dict(base)['seattle']
        selected = [p.id for p in players if p.depth <= ROSTER_RULES[p.position][1]]
        qb = next(p for p in players if p.position == 'QB' and p.depth == 2)
        starter = next(p for p in players if p.position == 'QB' and p.depth == 1)
        selected[selected.index(starter.id)] = qb.id
        context = with_starters(base, 'seattle', 1234, ((2, tuple(selected)),))
        self.assertEqual(league_leaders('seattle',1,1,1234,(),base), league_leaders('seattle',1,1,1234,(),context))
        data = league_leaders('seattle',1,2,1234,(),context)
        own = simulate_through_week('seattle',1,2,1234,(),context)['roster_stats']['players']
        expected = max(p.get('passing',{}).get('yards',0) for p in own)
        self.assertEqual(data['categories'][0]['your_best']['value'], expected)
        again = league_leaders('seattle',1,2,1234,(),context)
        data['categories'][0]['leaders'][0]['value'] = -100
        self.assertEqual(again,league_leaders('seattle',1,2,1234,(),context))
        with patch('app.leaders.simulate_league_week', side_effect=AssertionError('Cache miss')):
            self.assertEqual(again,league_leaders('seattle',1,2,1234,(),context))

    def test_career_api_uses_prior_rosters_and_current_draft_cuts_do_not_change_stats(self):
        # Actual mixed offseason history: the same reconstruction as career restores.
        fixture = json.loads((Path(__file__).resolve().parents[1] / 'benchmarks/year4.json').read_text())
        body = dict(action='leaders', season=fixture['season'], week=17, run_seed=fixture['runSeed'],
                    lineup_rules=fixture['lineupRules'], development_start=fixture['developmentStart'],
                    rebuild_team=fixture['rebuildTeam'], prior_standings=fixture['priorStandings'], career=fixture['career'])
        result = career_action(fixture['teamId'], CareerRequest(**body))
        self.assertEqual(result['week'],17)
        self.assertEqual(result['season'],4)
        self.assertEqual(result, career_action(fixture['teamId'], CareerRequest(**body, manual_picks=fixture['draftChoices'], dropped=fixture['dropped'])))
        for week in (0,18):
            with self.assertRaises(ValueError): league_leaders('seattle',1,week)
        with self.assertRaises(HTTPException): career_action('missing',CareerRequest(action='leaders'))
