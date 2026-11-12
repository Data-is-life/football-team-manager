"""Venue splits and streaks follow the same chronological games as standings."""
from collections import Counter
from unittest import TestCase
from unittest.mock import patch

from app.lineups import lineup_context
from app.simulation import simulate_league_week
from app.standings import TeamStanding, standings_through_week


class StandingsDetailsTests(TestCase):
    def setUp(self):
        standings_through_week.cache_clear()

    def tearDown(self):
        standings_through_week.cache_clear()

    def test_empty_records_and_streak(self):
        team = TeamStanding('seattle')
        self.assertEqual((team.home_record, team.away_record, team.streak), ('0-0-0', '0-0-0', '—'))

    def test_exact_venue_splits_ties_and_streak_changes_at_each_cutoff(self):
        games = (
            ('seattle', 'san-francisco', 21, 10),
            ('san-francisco', 'seattle', 14, 7),
            ('seattle', 'san-francisco', 14, 14),
            ('san-francisco', 'seattle', 17, 17),
            ('seattle', 'san-francisco', 28, 0),
            ('seattle', 'san-francisco', 20, 10),
        )
        def scores(season, week, *args):
            return (games[week-1],) if season == 1 else (('san-francisco', 'seattle', 3, 0),)
        with patch('app.standings.league_week_scores', side_effect=scores):
            for week, streak in enumerate(('1W', '1L', '1T', '2T', '1W', '2W'), 1):
                data = standings_through_week(1, week)
                rows = {r['team']['id']: r for g in data['groups'] for r in g['teams']}
                self.assertEqual(rows['seattle']['streak'], streak)
                self.assertEqual(rows['seattle']['points_for'], rows['san-francisco']['points_against'])
                self.assertEqual(rows['seattle']['points_against'], rows['san-francisco']['points_for'])
            row = rows['seattle']
            self.assertEqual((row['wins'], row['losses'], row['ties']), (3, 1, 2))
            self.assertEqual((row['points_for'], row['points_against']), (107, 65))
            self.assertEqual((row['home_record'], row['away_record']), ('3-0-1', '0-1-1'))
            new = standings_through_week(2, 1)
            row = next(r for g in new['groups'] for r in g['teams'] if r['team']['id'] == 'seattle')
            self.assertEqual((row['streak'], row['home_record'], row['away_record']), ('1L', '0-0-0', '0-1-0'))

    def test_all_teams_match_full_games_and_replay_across_saved_rules(self):
        for season, rules, weeks in ((1, 1, 4), (1, 35, 17), (2, 35, 3)):
            with self.subTest(season=season, rules=rules):
                context = lineup_context((), 1234, rules, season=season,
                                         rebuild_team='seattle' if rules >= 4 else None)
                expected = {}
                for week in range(1, weeks+1):
                    for game in simulate_league_week(season, week, 1234, roster_context=context):
                        for venue, other in (('home', 'away'), ('away', 'home')):
                            team = game[venue]['team']['id']
                            points, against = game[venue]['score'], game[other]['score']
                            outcome = 'W' if points > against else 'L' if points < against else 'T'
                            entry = expected.setdefault(team, {'home': Counter(), 'away': Counter(), 'results': [], 'pf': 0, 'pa': 0})
                            entry[venue][outcome] += 1
                            entry['results'].append(outcome)
                            entry['pf'] += points
                            entry['pa'] += against
                data = standings_through_week(season, weeks, 1234, roster_context=context)
                for group in data['groups']:
                    for row in group['teams']:
                        entry = expected[row['team']['id']]
                        for venue in ('home', 'away'):
                            self.assertEqual(row[venue+'_record'], '-'.join(str(entry[venue][r]) for r in 'WLT'))
                        for key, outcome in (('wins', 'W'), ('losses', 'L'), ('ties', 'T')):
                            self.assertEqual(row[key], entry['home'][outcome]+entry['away'][outcome])
                        self.assertEqual((row['points_for'], row['points_against']), (entry['pf'], entry['pa']))
                        last = entry['results'][-1]
                        length = 0
                        for result in entry['results'][::-1]:
                            if result != last:
                                break
                            length += 1
                        self.assertEqual(row['streak'], f'{length}{last}')
                rows = {r['team']['id']: r for g in data['groups'] for r in g['teams']}
                for row in data['playoff_race']:
                    self.assertEqual(row['home_record'], rows[row['team']['id']]['home_record'])
                    self.assertEqual(row['streak'], rows[row['team']['id']]['streak'])
                standings_through_week.cache_clear()
                self.assertEqual(data, standings_through_week(season, weeks, 1234, roster_context=context))
