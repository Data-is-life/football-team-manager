"""Rules 31: pre-development contracts, oversized markets and hard financial gates."""
from dataclasses import replace
from unittest import TestCase
from fastapi import HTTPException
from app.main import CareerRequest,career_action
from app.lineups import lineup_context,replace_lineup_rosters
from app.career import replay_career
from app.preseason import prepare,run,financial_ready,raise_plan,raise_to_floor,release_player,floor_payroll
from app.free_agency import free_agency,free_agency_order
from app.player_contracts import payroll_floor,salary_cap,sign_retained_rookies,contract_terms,record_release
from app.simulation import roster_rules


class PreCampTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=lineup_context((),1234,31,rebuild_team='seattle')
        cls.base=dict(run_seed=1234,lineup_rules=31,rebuild_team='seattle',draft_rounds=6)
        cls.draft=career_action('seattle',CareerRequest(action='draft',auto_draft=True,**cls.base))
        cls.choices=tuple(cls.draft['manual_picks'])

    def call(self,action='free_agency',**extra):
        return career_action('seattle',CareerRequest(action=action,manual_picks=list(self.choices),**self.base,**extra))

    def complete_market(self):
        result=self.call(); actions=[]
        # Resolve old contracts before development, and free provisional holds
        # while preserving the user's freedom to sign above the roster limit.
        for p in result['profile']['roster']:
            if p.get('renewal_offer') or p.get('contract_offer'):
                actions.append(dict(kind='drop',player_id=p['id']))
        return actions+[dict(kind='finish')]

    def test_market_precedes_development_and_allows_oversized_signings(self):
        opened=self.call()
        self.assertFalse(opened['training_camp'])
        originals={p.id:p for _,ps in self.root for p in ps}
        for p in opened['profile']['roster']:
            if p['id'] in originals:
                self.assertEqual((p['current_rating'],p['age']),(originals[p['id']].rating,originals[p['id']].age))
            if p['id'].startswith('rookie-'):
                self.assertNotIn('rookie_outcome',p)
        release=max((p for p in opened['profile']['roster'] if p.get('contract_offer')),key=lambda p:p['contract_offer']['annual_salary'])
        actions=[dict(kind='drop',player_id=release['id'])]
        available=self.call(free_agency=actions)
        target=next(p for p in available['free_agency']['available'] if p['affordable'])
        signed=self.call(free_agency=actions+[dict(kind='sign',player_id=target['id'])])
        self.assertGreater(len(signed['profile']['roster']),38)
        p=next(p for p in signed['profile']['roster'] if p['id']==target['id'])
        self.assertEqual(p['contract']['annual_salary'],target['annual_salary'])
        with self.assertRaises(HTTPException): self.call('camp')
        with self.assertRaises(HTTPException): self.call('camp',free_agency=[dict(kind='finish')])

    def test_initial_review_camp_final_cuts_and_saved_replay(self):
        actions=self.complete_market()
        review=self.call(free_agency=actions)
        self.assertTrue(review['free_agency']['complete'])
        self.assertFalse(review['training_camp'])
        pre=[]
        if review['payroll_floor_adjustment']:
            pre=[dict(kind='raise',player_id=review['payroll_floor_adjustment']['player_id'])]
        camp=self.call('camp',free_agency=actions,pre_camp_actions=pre)
        self.assertTrue(camp['training_camp']);self.assertTrue(camp['can_continue'])
        self.assertEqual(camp,self.call('camp',free_agency=actions,pre_camp_actions=pre))
        before={p['id']:p for p in review['profile']['roster']}
        for p in camp['profile']['roster']:
            if p['id'] in before and not p['id'].startswith('rookie-'):
                self.assertEqual(p['age'],before[p['id']]['age']+1)
        # The API itself rejects an otherwise legal roster below the floor.
        expensive=next(p for p in review['profile']['roster'] if p['position']=='QB' and p['contract']['annual_salary']>10_000_000)
        with self.assertRaises(HTTPException) as blocked:
            self.call('camp',free_agency=actions,pre_camp_actions=[dict(kind='drop',player_id=expensive['id'])])
        self.assertEqual(blocked.exception.status_code,422)
        self.assertIn('payroll minimum',str(blocked.exception.detail))
        # A position-minimum release may use a weak replacement after camp.
        kicker=next(p for p in camp['profile']['roster'] if p['position']=='K')
        final=self.call('cuts',training_camp=True,free_agency=actions,pre_camp_actions=pre,
                        camp_actions=[dict(kind='drop',player_id=kicker['id'])])
        self.assertTrue(final['can_continue'])
        camp=final
        # Replay includes every phase, and no second development pass occurs.
        step=(1,(),self.choices,(),31,(),6,(),tuple((a['kind'],a.get('player_id','')) for a in actions),tuple((a['kind'],a['player_id']) for a in pre),(('drop',kicker['id']),))
        replayed=replay_career('seattle',1234,(step,),31,2,1,'seattle')
        self.assertTrue(all(financial_ready(ps,replayed,o) for o,ps in replayed))
        by_id={p.id:p for p in dict(replayed)['seattle']}
        for p in camp['profile']['roster']:
            self.assertEqual((p['current_rating'],p['age']),(by_id[p['id']].rating,by_id[p['id']].age))
        with self.assertRaises(HTTPException): self.call('cuts',camp_actions=[dict(kind='drop',player_id='missing')])

    def test_exact_sixty_percent_floor_and_signed_only_accounting(self):
        self.assertEqual(payroll_floor(3,31),salary_cap(3,31)*60//100)
        self.assertEqual(payroll_floor(2,30),168_000_000)
        _,context=prepare('seattle',1,1234,self.choices,(),self.root,6)
        rosters=dict(context)
        players=[replace(p,contract=replace(contract_terms(p),annual_salary=1_050_000,signed_season=2,years=2),rookie_offer=None) for p in rosters['seattle']]
        rosters['seattle']=tuple(players)
        low=replace_lineup_rosters(context,tuple(rosters.items()))
        self.assertFalse(financial_ready(players,low,'seattle'))
        plan=raise_plan(players,low,'seattle');self.assertTrue(plan['allowed'])
        ready=raise_to_floor(low,'seattle',plan['player_id'])
        self.assertEqual(floor_payroll(dict(ready)['seattle'],ready),payroll_floor(2,31))
        small=next(p for p in dict(ready)['seattle'] if p.id!=plan['player_id'])
        with self.assertRaises(ValueError): release_player(ready,'seattle',small.id,final=True)
        charged=record_release(low,'seattle',players[0],2)
        self.assertEqual(floor_payroll(players,charged),floor_payroll(players,low))

    def test_guaranteed_over_cap_blocks_free_agents(self):
        _,context=prepare('seattle',1,1234,self.choices,(),self.root,6)
        rosters=dict(context)
        rosters['seattle']=tuple(replace(p,contract=replace(contract_terms(p),annual_salary=10_000_000,signed_season=2,years=2),rookie_offer=None) for p in rosters['seattle'])
        over=replace_lineup_rosters(context,tuple(rosters.items()))
        order=free_agency_order(1,1234,(),self.root)
        data,_=free_agency('seattle',1,1234,over,order)
        self.assertTrue(data['available']);self.assertFalse(any(p['affordable'] for p in data['available']))
        with self.assertRaises(ValueError):free_agency('seattle',1,1234,over,order,(('sign',data['available'][0]['id']),))

    def test_renewal_uses_pre_camp_ability_and_old_drafts_remain_old(self):
        # Force one actual expiring veteran in an immutable fixture.
        rosters=dict(self.root);player=next(p for p in rosters['seattle'] if p.contract)
        rosters['seattle']=tuple(replace(p,contract=replace(p.contract,years=1)) if p.id==player.id else p for p in rosters['seattle'])
        root=replace_lineup_rosters(self.root,tuple(rosters.items()))
        data,ctx=run('seattle',1,1234,self.choices,(),root,6)
        with self.assertRaises(ValueError):run('seattle',1,1234,self.choices,(),root,6,(('finish',''),))
        # Release provisional draft holds to leave room for the renewal.
        actions=tuple(('drop',p.id) for p in dict(ctx)['seattle'] if p.rookie_offer)
        data,ctx=run('seattle',1,1234,self.choices,(),root,6,actions+(('resign',player.id),))
        signed=next(p for p in dict(ctx)['seattle'] if p.id==player.id)
        self.assertEqual(signed.rating,player.rating)
        self.assertEqual(signed.age,player.age)
        self.assertEqual(signed.contract.signed_season,2)

    def test_legacy_starter_plan_metadata_is_supported(self):
        from app.starter_choices import with_starters
        starters=tuple(p.id for p in dict(self.root)['seattle'] if p.depth<=roster_rules(self.root)[p.position][1])
        planned=with_starters(self.root,'seattle',1234,((1,starters),))
        data,_=run('seattle',1,1234,self.choices,(),planned,6)
        self.assertFalse(data['training_camp'])

    def test_two_offseasons_and_all_cpu_financial_limits(self):
        root=self.root;steps=[]
        from app.draft import build_draft
        for season in (1,2):
            board,_=build_draft('seattle',season,1234,roster_context=root,auto_pick=True,draft_rounds=6)
            choices=tuple(board['manual_picks'])
            opened,ctx=run('seattle',season,1234,choices,(),root,6)
            actions=tuple(('drop',p.id) for p in dict(ctx)['seattle'] if p.contract and p.contract.signed_season+p.contract.years-1<season+1)
            actions=actions+(('finish',''),)
            reviewed,ctx=run('seattle',season,1234,choices,(),root,6,actions)
            pre=tuple(('drop',p.id) for p in dict(ctx)['seattle'] if p.rookie_offer)
            reviewed,ctx=run('seattle',season,1234,choices,(),root,6,actions,pre)
            plan=reviewed['payroll_floor_adjustment']
            if plan: pre=pre+(('raise',plan['player_id']),)
            camp,ctx=run('seattle',season,1234,choices,(),root,6,actions,pre,True)
            self.assertTrue(camp['can_continue'])
            self.assertTrue(all(financial_ready(ps,ctx,o) for o,ps in ctx))
            steps.append((season,(),choices,(),31,(),6,(),actions,pre,()))
            replayed=replay_career('seattle',1234,tuple(steps),31,season+1,1,'seattle')
            self.assertEqual(ctx,replayed)
            root=replayed
