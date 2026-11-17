from unittest import TestCase
from dataclasses import replace
from fastapi import HTTPException
from app.main import CareerRequest,career_action
from app.career import replay_career
from app.lineups import lineup_context
from app.simple_offseason import expire_pool,stamp_pool
from app.development import initial_state,reveal_rookie,number
from app.draft import draft_class
from simple_offseason_fixtures import simple_fixture

class SimpleOffseasonTests(TestCase):
    @classmethod
    def setUpClass(cls):cls.f=simple_fixture()

    def call(self,action,**extra):
        return career_action('seattle',CareerRequest(action=action,**{**self.f['request'],**extra}))

    def test_order_signing_fixed_prices_and_forbidden_actions(self):
        with self.assertRaises(HTTPException):self.call('free_agency')
        with self.assertRaises(HTTPException):self.call('camp')
        with self.assertRaises(HTTPException):self.call('own_players',own_actions=[dict(kind='finish')])
        args=dict(own_actions=self.f['actions'])
        m=self.call('free_agency',**args)
        self.assertTrue(m['free_agency']['fixed_prices']);self.assertNotIn('wave',m['free_agency'])
        self.assertEqual(self.f['own']['profile']['roster'][0]['age'],m['profile']['roster'][0]['age'])
        for kind in ('pass','resign','drop'):
            with self.assertRaises(HTTPException):self.call('free_agency',**args,free_agency=[dict(kind=kind,player_id='' if kind=='pass' else self.f['actions'][0]['player_id'])])
        first=next(p for p in m['free_agency']['available'] if p['affordable'])
        after=self.call('free_agency',**args,free_agency=[dict(kind='sign',player_id=first['id'])])
        before={p['id']:p['annual_salary'] for p in m['free_agency']['available']}
        for p in after['free_agency']['available']:self.assertEqual(p['annual_salary'],before[p['id']])
        self.assertNotIn(first['id'],[p['id'] for p in after['free_agency']['available']])
        self.assertTrue(any(p['id']==first['id'] for p in after['profile']['roster']))
        self.assertEqual(m,self.call('free_agency',**args))
        # Unsigned rookies and declined veterans join the market, active contracts do not.
        source_ids={p['id'] for p in self.f['own']['profile']['roster'] if p.get('renewal_offer')}
        self.assertTrue(source_ids <= {p['id'] for p in m['free_agency']['available']})
        self.assertTrue(all(not p['id'].startswith('replacement-') for p in m['free_agency']['available']))

    def test_one_carryover_including_release_metadata(self):
        root=lineup_context((),1234,42,rebuild_team='seattle')
        p=draft_class(1,1234,42)[0]
        context=stamp_pool(replace(root,free_agents=(p,)),2)
        self.assertEqual(dict(context.free_agent_entries)[p.id],2)
        self.assertEqual(expire_pool(context,3).free_agents,(p,))
        self.assertEqual(expire_pool(context,4).free_agents,())
        self.assertEqual(expire_pool(context,4).free_agent_entries,())

    def test_balanced_rookie_thresholds_and_once_only_reveal(self):
        observed=set()
        for p in draft_class(1,1234,42):
            state=initial_state(p,1234,True)
            updated,out=reveal_rookie(p,state,1234,True,True,True)
            draw=number(1234,p.id,'rookie-reveal-v2')%100
            expected='boom' if draw<25 else 'bust' if draw<50 else 'normal'
            self.assertEqual(out.rookie_outcome,expected);observed.add(expected)
            self.assertEqual(reveal_rookie(updated,out,1234,True,True,True),(updated,out))
        self.assertEqual(observed,{'boom','bust','normal'})

    def test_finish_develops_once_and_replays_next_season(self):
        args=dict(own_actions=self.f['actions'],free_agency=[dict(kind='finish')])
        market=self.call('free_agency',**args)
        self.assertFalse(market['can_continue']);self.assertEqual(market['development_roster'],[])
        plan=market['payroll_floor_adjustment']
        args['pre_camp_actions']=[dict(kind='raise',player_id=plan['player_id'])] if plan else []
        args['trade_actions']=[dict(kind='finish')]
        done=self.call('trades',**args)
        self.assertTrue(done['can_continue']);self.assertTrue(done['development_roster'])
        veterans={p['id']:p for p in market['profile']['roster'] if not p['id'].startswith(('rookie-','replacement-'))}
        for p in done['profile']['roster']:
            if p['id'] in veterans:self.assertEqual(p['age'],veterans[p['id']]['age']+1)
        self.assertEqual(done,self.call('trades',**args))
        step=dict(season=1,lineup_rules=42,draft_rounds=6,manual_picks=self.f['request']['manual_picks'],**args)
        nextargs=dict(run_seed=1234,lineup_rules=42,rebuild_team='seattle',season=2,career=[step])
        profile=career_action('seattle',CareerRequest(action='profile',**nextargs))
        replay_career.cache_clear();self.assertEqual(profile,career_action('seattle',CareerRequest(action='profile',**nextargs)))
        self.assertEqual([(p['id'],p['age'],p['current_rating']) for p in profile['roster']],[(p['id'],p['age'],p['current_rating']) for p in done['profile']['roster']])
        with self.assertRaises(HTTPException):self.call('trades',own_actions=self.f['actions'])

    def test_unsigned_pool_expires_after_two_real_markets(self):
        from app.draft import build_draft
        from app.simple_offseason import run
        from app.player_contracts import contract_expired
        root=lineup_context((),1234,42,rebuild_team='seattle')
        old_pool=None
        for season in (1,2):
            draft,_=build_draft('seattle',season,1234,(),(),root,auto_pick=True,draft_rounds=6)
            choices=tuple(draft['manual_picks'])
            actions=[]
            _,prepared=run('seattle',season,1234,choices,(),root,6)
            for p in dict(prepared)['seattle']:
                if contract_expired(p,prepared.season):actions.append(('drop',p.id))
                elif p.rookie_offer:actions.append(('sign',p.id))
            actions.append(('finish',''))
            market,_=run('seattle',season,1234,choices,(),root,6,tuple(actions),(('finish',''),))
            plan=market['payroll_floor_adjustment'];review=(('raise',plan['player_id']),) if plan else ()
            _,root=run('seattle',season,1234,choices,(),root,6,tuple(actions),(('finish',''),),review,(('finish','','',''),))
            pool={p.id for p in root.free_agents}
            if old_pool is None:old_pool=pool
            else:old_pool&=pool
        self.assertTrue(old_pool,'Need a real unsigned carryover to test expiry')
        draft,_=build_draft('seattle',3,1234,(),(),root,auto_pick=True,draft_rounds=6)
        _,prepared=run('seattle',3,1234,tuple(draft['manual_picks']),(),root,6)
        self.assertFalse(old_pool & {p.id for p in prepared.free_agents})
