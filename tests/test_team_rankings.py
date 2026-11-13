"""Exact overall ratings and rankings from each current roster phase."""
from unittest import TestCase
from unittest.mock import patch

from app.draft import build_draft
from app.league import TEAMS
from app.lineups import lineup_context, replace_lineup_rosters
from app.main import CareerRequest, DraftRequest, career_action, rookie_draft
from app.preseason import run
from app.simulation import TeamRatings, team_ratings, ranked_players
from app.team_rankings import league_team_rankings


class TeamRankingsTests(TestCase):
    def assert_rankings(self, profile, context, seed=1234):
        rows = profile['rankings']
        self.assertEqual(len(rows), 30)
        self.assertEqual(len({row['team']['id'] for row in rows}), 30)
        self.assertEqual([row['rank'] for row in rows], list(range(1, 31)))
        self.assertEqual(rows, sorted(rows, key=lambda row: (-row['ratings']['overall'], row['team']['city'], row['team']['id'])))
        for row in rows:
            ratings = team_ratings(row['team']['id'], seed, context)
            self.assertEqual(row['ratings'], dict(offense=ratings.offense, defense=ratings.defense, overall=ratings.overall))
        own = next(row for row in rows if row['team']['id'] == profile['team']['id'])
        self.assertEqual((own['ratings']['offense'], own['ratings']['defense']),
                         (profile['ratings']['offense'], profile['ratings']['defense']))

    def test_exact_half_points_and_alphabetical_ties(self):
        self.assertEqual(TeamRatings(75, 76).overall, 75.5)
        self.assertEqual(TeamRatings(99, 1).overall, 50)
        with patch('app.team_rankings.team_ratings', return_value=TeamRatings(75, 76)):
            rows = league_team_rankings()
        self.assertEqual([row['team']['city'] for row in rows], sorted(t.city for t in TEAMS))
        self.assertTrue(all(row['ratings']['overall'] == 75.5 for row in rows))

    def test_profiles_include_all_teams_before_any_game_for_old_and_new_careers(self):
        for rules in (1, 4, 35):
            args = dict(run_seed=1234, lineup_rules=rules)
            if rules >= 4: args['rebuild_team'] = 'seattle'
            profile = career_action('seattle', CareerRequest(action='profile', **args))
            context = lineup_context((), 1234, rules, rebuild_team=args.get('rebuild_team'))
            self.assert_rankings(profile, context)
            self.assertEqual(profile, career_action('seattle', CareerRequest(action='profile', **args)))

    def test_both_draft_apis_include_cpu_picks_and_scout_the_same_rosters(self):
        args = dict(run_seed=1234, lineup_rules=35, rebuild_team='seattle', draft_rounds=6)
        root = lineup_context((), 1234, 35, rebuild_team='seattle')
        for choices in ((), None):
            request = dict(auto_draft=choices is None, manual_picks=list(choices or ()), **args)
            data = career_action('seattle', CareerRequest(action='draft', **request))
            _, rosters = build_draft('seattle', 1, 1234, tuple(data['manual_picks']), (), root,
                                     return_league=True, draft_rounds=6)
            context = replace_lineup_rosters(root, tuple((o, ranked_players(ps)) for o, ps in rosters.items()))
            self.assert_rankings(data['profile'], context)
            standalone = rookie_draft('seattle', DraftRequest(**request))
            self.assertEqual(standalone['profile']['rankings'], data['profile']['rankings'])
            cpu = next(p['team']['id'] for p in data['picks'] if p['team']['id'] != 'seattle') if data['picks'] else 'miami'
            viewed = career_action('seattle', CareerRequest(action='draft', view_team=cpu,
                manual_picks=data['manual_picks'], **args))
            self.assertEqual(viewed['profile']['team']['id'], cpu)
            self.assertEqual({p['id'] for p in viewed['profile']['roster']}, {p.id for p in dict(context)[cpu]})
            self.assert_rankings(viewed['profile'], context)

    def test_market_roster_changes_camp_and_saved_rollover_have_current_rankings(self):
        args = dict(run_seed=1234, lineup_rules=35, rebuild_team='seattle', draft_rounds=6)
        root = lineup_context((), 1234, 35, rebuild_team='seattle')
        draft = career_action('seattle', CareerRequest(action='draft', auto_draft=True, **args))
        req = dict(manual_picks=draft['manual_picks'], **args)
        opened = career_action('seattle', CareerRequest(action='free_agency', **req))
        target = next(p for p in opened['free_agency']['available'] if p['affordable'])
        actions = [dict(kind='sign', player_id=target['id'])]
        signed = career_action('seattle', CareerRequest(action='free_agency', free_agency=actions, **req))
        _, context = run('seattle', 1, 1234, tuple(draft['manual_picks']), (), root, 6, (('sign', target['id']),))
        self.assert_rankings(signed['profile'], context)
        for player in signed['profile']['roster']:
            if player.get('renewal_offer') or player.get('contract_offer'):
                actions.append(dict(kind='drop', player_id=player['id']))
        actions.append(dict(kind='finish'))
        review = career_action('seattle', CareerRequest(action='free_agency', free_agency=actions, **req))
        pre = [dict(kind='raise', player_id=review['payroll_floor_adjustment']['player_id'])] if review['payroll_floor_adjustment'] else []
        camp = career_action('seattle', CareerRequest(action='camp', free_agency=actions, pre_camp_actions=pre, **req))
        self.assertTrue(camp['can_continue'])
        _, context = run('seattle', 1, 1234, tuple(draft['manual_picks']), (), root, 6,
            tuple((a['kind'], a.get('player_id', '')) for a in actions), tuple((a['kind'], a['player_id']) for a in pre), True)
        self.assert_rankings(camp['profile'], context)
        step = dict(season=1, lineup_rules=35, draft_rounds=6, manual_picks=draft['manual_picks'],
                    free_agency=actions, pre_camp_actions=pre, camp_actions=[])
        next_req = dict(action='profile', season=2, career=[step], **args)
        profile = career_action('seattle', CareerRequest(**next_req))
        self.assertEqual(profile, career_action('seattle', CareerRequest(**next_req)))
        self.assert_rankings(profile, context)
