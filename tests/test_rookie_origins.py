"""Rookie signing origins survive market decisions, releases and career replay."""
from dataclasses import replace
from unittest import TestCase

from app.career import replay_career
from app.draft import draft_class
from app.lineups import lineup_context
from app.main import CareerRequest, career_action
from app.preseason import prepare, release_player
from app.simple_offseason import _own_phase, _market_phase
from simple_offseason_fixtures import simple_fixture


def label_fixture():
    fixture = simple_fixture(46)
    actions = [dict(kind='drop',player_id=p['id']) for p in fixture['own']['profile']['roster']
               if p.get('renewal_offer') or p.get('contract_offer')]
    actions.append(dict(kind='finish',player_id=''))
    request = dict(**fixture['request'],own_actions=actions)
    market = career_action('seattle',CareerRequest(action='free_agency',**request))
    root = lineup_context((),1234,46,rebuild_team='seattle')
    _, context, _ = _own_phase('seattle',1,1234,tuple(request['manual_picks']),(),root,6,
                               tuple((a['kind'],a['player_id']) for a in actions))
    origins = {p.id:p.rookie_origin for p in context.free_agents}
    targets = {origin:next(p['id'] for p in market['free_agency']['available']
                          if p['affordable'] and origins.get(p['id'])==origin)
               for origin in ('undrafted','released')}
    checkpoint = {**fixture['checkpoint'],'ownActions':actions,'freeAgency':[]}
    return dict(request=request,checkpoint=checkpoint,targets=targets)


class RookieOriginTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = label_fixture()

    def test_pool_distinguishes_undrafted_and_cpu_and_managed_releases(self):
        root = lineup_context((),1234,46,rebuild_team='seattle')
        choices = tuple(self.fixture['request']['manual_picks'])
        _, context = prepare('seattle',1,1234,choices,(),root,6)
        board = career_action('seattle',CareerRequest(action='draft',**{
            k:v for k,v in self.fixture['request'].items() if k!='own_actions'}))
        picked = {p['player']['id'] for p in board['picks']}
        pool = {p.id:p for p in context.free_agents}
        undrafted = {p.id for p in draft_class(1,1234,46)}-picked
        self.assertEqual(len(undrafted),20)
        self.assertTrue(all(pool[i].rookie_origin=='undrafted' for i in undrafted))
        cpu_cuts = picked & set(pool)
        self.assertTrue(cpu_cuts)
        self.assertTrue(all(pool[i].rookie_origin=='released' for i in cpu_cuts))
        own = next(p for p in dict(context)['seattle'] if p.id in choices)
        released = release_player(context,'seattle',own.id)
        self.assertEqual(next(p for p in released.free_agents if p.id==own.id).rookie_origin,'released')

    def test_signing_and_career_replay_preserve_both_origins(self):
        for origin, identity in self.fixture['targets'].items():
            args = dict(**self.fixture['request'],free_agency=[dict(kind='sign',player_id=identity)])
            signed = career_action('seattle',CareerRequest(action='free_agency',**args))
            player = next(p for p in signed['profile']['roster'] if p['id']==identity)
            self.assertEqual(player['rookie_origin'],origin)
            self.assertEqual(player['contract']['category'],'free_agent')
            _own_phase.cache_clear(); _market_phase.cache_clear(); prepare.cache_clear()
            self.assertEqual(signed,career_action('seattle',CareerRequest(action='free_agency',**args)))
            args['free_agency'].append(dict(kind='finish'))
            market = career_action('seattle',CareerRequest(action='free_agency',**args))
            plan = market['payroll_floor_adjustment']
            args['pre_camp_actions'] = [dict(kind='raise',player_id=plan['player_id'])] if plan else []
            args['trade_actions'] = [dict(kind='finish')]
            done = career_action('seattle',CareerRequest(action='trades',**args))
            self.assertTrue(done['can_continue'])
            self.assertEqual(next(p for p in done['profile']['roster'] if p['id']==identity)['rookie_origin'],origin)
            step = dict(season=1,**{k:v for k,v in args.items() if k not in ('run_seed','rebuild_team')})
            next_args = dict(run_seed=1234,lineup_rules=46,rebuild_team='seattle',season=2,career=[step])
            replay_career.cache_clear()
            restored = career_action('seattle',CareerRequest(action='profile',**next_args))
            self.assertEqual(next(p for p in restored['roster'] if p['id']==identity)['rookie_origin'],origin)

    def test_releasing_a_signed_udfa_changes_its_origin(self):
        root = lineup_context((),1234,46,rebuild_team='seattle')
        choices = tuple(self.fixture['request']['manual_picks'])
        _, context = prepare('seattle',1,1234,choices,(),root,6)
        udfa = next(p for p in context.free_agents if p.rookie_origin=='undrafted')
        # Use an existing legal roster slot to isolate the release path.
        rosters = dict(context)
        existing = next(p for p in rosters['seattle'] if p.position==udfa.position)
        rosters['seattle'] = tuple(replace(udfa,contract=existing.contract,rookie_offer=existing.rookie_offer)
                                   if p.id==existing.id else p for p in rosters['seattle'])
        from app.lineups import replace_lineup_rosters
        context = replace_lineup_rosters(context,tuple(rosters.items()))
        released = release_player(context,'seattle',udfa.id)
        self.assertEqual(next(p for p in released.free_agents if p.id==udfa.id).rookie_origin,'released')


if __name__=='__main__':
    import json
    print(json.dumps(label_fixture()))
