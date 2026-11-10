"""Free agency prices, turn order, ownership, lifecycle and immutable API replay."""
from dataclasses import replace
from unittest import TestCase
from fastapi import HTTPException
from app.career import training_camp, cpu_cuts, offseason, replay_career
from app.draft import build_draft
from app.free_agency import asking_contract, free_agency, wave_percent, free_agency_order
from app.lineups import lineup_context
from app.main import CareerRequest, career_action
from app.player_contracts import minimum_salary, cap_ready, contract_expired, veteran_contract


class FreeAgencyTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = lineup_context((),1234,29,rebuild_team='seattle')
        board,_ = build_draft('seattle',1,1234,roster_context=cls.root,auto_pick=True,draft_rounds=6)
        cls.choices = tuple(board['manual_picks'])
        _,camp = training_camp('seattle',1,1234,cls.choices,(),cls.root,6)
        players = dict(camp)['seattle']
        keep = {p.id for p in cpu_cuts(players,35,31)}
        cls.dropped = tuple(p.id for p in players if p.id not in keep or contract_expired(p,2) or p.rookie_offer is not None)
        cls.actions = tuple(('drop',identity) for identity in cls.dropped)
        cls.board,cls.context = offseason('seattle',1,1234,cls.choices,cls.dropped,(),cls.root,6,cls.actions)
        cls.order = free_agency_order(1,1234,(),cls.root)
        cls.request = dict(season=1,run_seed=1234,lineup_rules=29,rebuild_team='seattle',draft_rounds=6,
            training_camp=True,manual_picks=list(cls.choices),dropped=list(cls.dropped),
            roster_actions=[dict(kind=k,player_id=i) for k,i in cls.actions])

    def market(self, actions=()):
        return free_agency('seattle',1,1234,self.context,self.order,actions)

    def test_prices_follow_original_demand_and_minimum(self):
        self.assertEqual([wave_percent(i) for i in range(1,7)],[120,110,105,100,95,90])
        p = max(self.context.free_agents,key=lambda p:p.rating)
        base = veteran_contract(p,2,29,dict(self.context.development)[p.id].potential)
        self.assertEqual(asking_contract(p,self.context,4).annual_salary,base.annual_salary)
        self.assertEqual(asking_contract(p,self.context,24).annual_salary,minimum_salary(2,29))
        for i in range(1,24):
            self.assertGreaterEqual(asking_contract(p,self.context,i).annual_salary,asking_contract(p,self.context,i+1).annual_salary)

    def test_user_first_signing_and_pass_preserve_unique_ownership(self):
        market,ctx = self.market()
        self.assertEqual(market['order'][0]['id'],'seattle')
        self.assertEqual(len(market['order']),30)
        self.assertTrue(set(self.dropped) <= {p.id for p in ctx.free_agents})
        affordable = next(p for p in market['available'] if p['affordable'])
        actions = (('sign',affordable['id']),)
        result,signed = self.market(actions)
        self.assertEqual(result['wave'],2)
        self.assertEqual(result['transactions'][0]['team']['id'],'seattle')
        p = next(p for p in dict(signed)['seattle'] if p.id==affordable['id'])
        self.assertEqual(p.contract.annual_salary,affordable['annual_salary'])
        self.assertEqual(replace(dict(signed.development)[p.id],rotation_share=0),replace(dict(ctx.development)[p.id],rotation_share=0))
        self.assertNotIn(p.id,{a.id for a in signed.free_agents})
        self.assertEqual((result,signed),self.market(actions))
        ids = [p.id for _,roster in signed for p in roster]+[p.id for p in signed.free_agents]
        self.assertEqual(len(ids),len(set(ids)))
        passed,_ = self.market((('pass',''),))
        self.assertEqual(passed['percent'],110)
        self.assertTrue(passed['transactions'])
        self.assertEqual(len(passed['available']),len(market['available'])-len(passed['transactions']))
        self.assertEqual([t['id'] for t in passed['order']],[t['id'] for t in market['order']])
        self.assertTrue(all(t['team']['id']!='seattle' for t in passed['transactions']))
        self.assertEqual(len({t['team']['id'] for t in passed['transactions']}),len(passed['transactions']))
        with self.assertRaises(ValueError): self.market(actions+(('sign',p.id),))

    def test_finish_replays_through_next_season_and_preserves_pool(self):
        market,context = self.market((('finish',''),))
        self.assertTrue(market['complete'])
        self.assertTrue(all(cap_ready(players,context,2,owner) for owner,players in context))
        self.assertTrue(set(self.context.dead_cap) <= set(context.dead_cap))
        with self.assertRaises(ValueError): self.market((('finish',''),('pass','')))
        step=(1,(),self.choices,self.dropped,29,(),6,self.actions,(('finish',''),))
        replayed=replay_career('seattle',1234,(step,),29,2,1,'seattle')
        from app.player_contracts import sign_retained_rookies
        self.assertEqual(dict(sign_retained_rookies(context,2))['seattle'],dict(replayed)['seattle'])
        self.assertEqual(context.free_agents,replayed.free_agents)
        with self.assertRaises(ValueError): replay_career('seattle',1234,(step[:8],),29,2,1,'seattle')

    def test_api_rejects_invalid_stage_targets_and_missing_completion(self):
        result=career_action('seattle',CareerRequest(action='free_agency',**self.request))
        self.assertEqual(result['wave'],1)
        for changes in ({'training_camp':False},{'free_agency':[dict(kind='sign',player_id='missing')]}, {'lineup_rules':28}):
            with self.assertRaises(HTTPException):
                career_action('seattle',CareerRequest(action='free_agency',**{**self.request,**changes}))

    def test_cap_roster_and_retirement_boundaries(self):
        from app.lineups import replace_lineup_rosters
        from app.retirement import retiring
        market,context=self.market()
        self.assertTrue(market['available'])
        # Unsigned retirees never return after their final season.
        old = context.free_agents[0]
        aged=replace(context,free_agents=(replace(old,age=99),))
        from app.development import advance_context
        aged=replace_lineup_rosters(aged,tuple(aged))
        next_year=advance_context(aged,1234,3,lineup_rules=29)
        self.assertNotIn(old.id,{p.id for p in next_year.free_agents})
        # A valid but unaffordable contract must be rejected server-side.
        rich=max(market['available'],key=lambda p:p['annual_salary'])
        if not rich['affordable']:
            with self.assertRaises(ValueError): self.market((('sign',rich['id']),))
        # A final pass at the minimum-price wave terminates deterministically.
        completed,_=self.market(tuple(('pass','') for _ in range(24)))
        self.assertTrue(completed['complete'])
        self.assertEqual(completed['wave'],24)

    def test_emergency_holds_are_only_guaranteed_when_retained(self):
        from app.retirement import fill_roster
        from app.lineups import replace_lineup_rosters
        from app.player_contracts import sign_retained_rookies, record_release
        fillers=fill_roster([], 'seattle',1,1234,context=self.context)
        self.assertTrue(all(p.contract is None and p.rookie_offer is not None for p in fillers))
        self.assertEqual(record_release(self.context,'seattle',fillers[0],2).dead_cap,self.context.dead_cap)
        rosters=dict(self.context);rosters['seattle']=fillers
        prepared=replace_lineup_rosters(self.context,tuple(rosters.items()))
        signed=sign_retained_rookies(prepared,2)
        self.assertTrue(all(p.contract is not None and p.rookie_offer is None for p in dict(signed)['seattle']))

    def test_second_offseason_replays_free_agents_and_development(self):
        first,_=self.market()
        target=next(p for p in first['available'] if p['affordable'])
        first_actions=(('sign',target['id']),('finish',''))
        step1=(1,(),self.choices,self.dropped,29,(),6,self.actions,first_actions)
        current=replay_career('seattle',1234,(step1,),29,2,1,'seattle')
        board,_=build_draft('seattle',2,1234,roster_context=current,auto_pick=True,draft_rounds=6)
        choices=tuple(board['manual_picks'])
        _,camp=training_camp('seattle',2,1234,choices,(),current,6)
        players=dict(camp)['seattle']
        keep={p.id for p in cpu_cuts(players,35,31)}
        dropped=tuple(p.id for p in players if p.id not in keep or p.rookie_offer is not None or contract_expired(p,3))
        actions=tuple(('drop',identity) for identity in dropped)
        _,prepared=offseason('seattle',2,1234,choices,dropped,(),current,6,actions)
        final,expected=free_agency('seattle',2,1234,prepared,
            free_agency_order(2,1234,(),current),(('finish',''),))
        step2=(2,(),choices,dropped,29,(),6,actions,(('finish',''),))
        replayed=replay_career('seattle',1234,(step1,step2),29,3,1,'seattle')
        # Season entry signs retained provisional rookies for every team.
        from app.player_contracts import sign_retained_rookies
        self.assertEqual(sign_retained_rookies(expected,3),replayed)
        identities=[p.id for _,players in replayed for p in players]+[p.id for p in replayed.free_agents]
        self.assertEqual(len(identities),len(set(identities)))
