from dataclasses import replace
from unittest import TestCase
from app.lineups import lineup_context,replace_lineup_rosters
from app.development import initial_state
from app.player_contracts import PlayerContract,cap_payroll,veteran_contract,contract_potential
from app.trades import evaluate,replay,eligibility,swap_context
from app.main import CareerRequest,career_action
from app.career import replay_career
from app.preseason import run,financial_ready
from app.draft import build_draft
from fastapi import HTTPException

class TradeTests(TestCase):
    @classmethod
    def setUpClass(cls):
        root=lineup_context((),1234,41,rebuild_team='seattle')
        rosters=[]
        for owner,ps in root:
            players=tuple(replace(p,rating=70,age=26,rookie_offer=None,
                contract=PlayerContract(18_000_000 if p.position=='K' else 3_000_000,1,5,'veteran')) for p in ps)
            rosters.append((owner,players))
        root=replace_lineup_rosters(root,tuple(rosters))
        cls.context=replace(root,development=tuple((p.id,replace(initial_state(p,1234,True),potential=p.rating)) for _,ps in root for p in ps))

    def player(self,owner,pos,depth=1):
        return next(p for p in dict(self.context)[owner] if p.position==pos and p.depth==depth)

    def test_acceptance_and_whole_contract_transfer_are_deterministic(self):
        offered=self.player('seattle','WR');target=self.player('miami','WR')
        improved=replace(offered,rating=75)
        root=replace_lineup_rosters(self.context,tuple((o,tuple(improved if p.id==offered.id else p for p in ps)) for o,ps in self.context))
        before=root
        decision=evaluate(root,'seattle','miami',offered.id,target.id)
        self.assertTrue(decision['accepted'],decision)
        self.assertEqual(decision,evaluate(root,'seattle','miami',offered.id,target.id))
        actions=(('swap','miami',offered.id,target.id),('finish','','',''))
        board,after=replay(root,'seattle',actions)
        self.assertTrue(board['complete']);self.assertEqual(before,root)
        self.assertEqual(next(p for p in dict(after)['miami'] if p.id==offered.id).contract,offered.contract)
        self.assertEqual(next(p for p in dict(after)['seattle'] if p.id==target.id).contract,target.contract)
        self.assertEqual(root.dead_cap,after.dead_cap)
        for owner in ('seattle','miami'):
            self.assertEqual(cap_payroll(dict(after)[owner],after,owner=owner),cap_payroll(dict(root)[owner],root,owner=owner))
        self.assertEqual((board,after),replay(root,'seattle',actions))
        with self.assertRaisesRegex(ValueError,'finished'):replay(root,'seattle',actions+(('finish','','',''),))

    def test_eligibility_lopsided_offers_and_cpu_backup_minimums(self):
        p=self.player('seattle','WR')
        self.assertIn('draft year',eligibility(replace(p,id='rookie-1234-1-1'),self.context))
        self.assertIsNone(eligibility(replace(p,id='rookie-1234-1-1'),replace(self.context,season=2)))
        self.assertIn('free agency',eligibility(replace(p,contract=replace(p.contract,category='free_agent')),self.context))
        self.assertIsNone(eligibility(replace(p,contract=replace(p.contract,category='free_agent',signed_season=0)),self.context))
        same=evaluate(self.context,'seattle','miami',p.id,self.player('miami','WR').id)
        self.assertFalse(same['accepted']);self.assertTrue(any('justify' in r for r in same['reasons']))
        bad=evaluate(self.context,'seattle','miami',self.player('seattle','K').id,self.player('miami','QB').id)
        self.assertFalse(bad['accepted']);self.assertTrue(any('QB' in r or 'value' in r for r in bad['reasons']))
        q=self.player('miami','QB');poor=replace(q,rating=40)
        root=replace_lineup_rosters(self.context,tuple((o,tuple(poor if p.id==q.id else x for x in ps)) for o,ps in self.context))
        rejected=evaluate(root,'seattle','miami',poor.id,p.id)
        self.assertFalse(rejected['accepted']) # incorrect ownership
        with self.assertRaises(ValueError):replay(self.context,'seattle',(('swap','miami',self.player('seattle','K').id,q.id),))

    def test_salary_and_floor_checks_on_both_sides(self):
        outgoing=self.player('seattle','WR');target=self.player('miami','WR')
        rich=replace(target,contract=replace(target.contract,annual_salary=100_000_000))
        root=replace_lineup_rosters(self.context,tuple((o,tuple(rich if p.id==target.id else p for p in ps)) for o,ps in self.context))
        decision=evaluate(root,'seattle','miami',outgoing.id,target.id)
        self.assertFalse(decision['accepted']);self.assertTrue(any('salary cap' in r for r in decision['reasons']))
        floor=evaluate(self.context,'seattle','miami',self.player('seattle','K').id,target.id)
        self.assertFalse(floor['accepted']);self.assertTrue(any('below the required minimum' in r for r in floor['reasons']))
        qb=self.player('seattle','QB')
        poor=replace_lineup_rosters(self.context,tuple((o,tuple(replace(p,rating=40) if p.id==qb.id or (o=='miami' and p.position=='QB' and p.depth>1) else p for p in ps)) for o,ps in self.context))
        loss=evaluate(poor,'seattle','miami',qb.id,self.player('miami','QB').id)
        self.assertIn('Losing too much at quarterback.',loss['reasons'])

    def test_full_api_window_finish_replay_and_legacy_guards(self):
        args=dict(run_seed=1234,lineup_rules=41,rebuild_team='seattle',draft_rounds=6)
        d=career_action('seattle',CareerRequest(action='draft',auto_draft=True,**args));choices=d['manual_picks']
        request=dict(args,manual_picks=choices)
        with self.assertRaises(HTTPException):career_action('seattle',CareerRequest(action='trades',**request))
        market=career_action('seattle',CareerRequest(action='free_agency',**request))
        actions=[{'kind':'drop','player_id':p['id']} for p in market['profile']['roster'] if p.get('renewal_offer') or p.get('contract_offer')]+[{'kind':'finish','player_id':''}]
        review=career_action('seattle',CareerRequest(action='free_agency',free_agency=actions,**request))
        plan=review['payroll_floor_adjustment'];pre=[{'kind':'raise','player_id':plan['player_id']}] if plan else []
        request.update(free_agency=actions,pre_camp_actions=pre,training_camp=True)
        camp=career_action('seattle',CareerRequest(action='camp',**request));self.assertFalse(camp['can_continue'])
        self.assertEqual(len(camp['trading']['teams']),29)
        for p in camp['trading']['own_players']:
            self.assertFalse(p['id'].startswith('rookie-1234-2-'))
        finish=[{'kind':'finish','other_team':'','give_id':'','receive_id':''}]
        done=career_action('seattle',CareerRequest(action='trades',trade_actions=finish,**request));self.assertTrue(done['can_continue'])
        step=dict(season=1,lineup_rules=41,manual_picks=choices,draft_rounds=6,dropped=[],free_agency=actions,pre_camp_actions=pre,trade_actions=finish)
        next_args=dict(args,season=2,career=[step])
        profile=career_action('seattle',CareerRequest(action='profile',**next_args))
        replay_career.cache_clear();self.assertEqual(profile,career_action('seattle',CareerRequest(action='profile',**next_args)))
        step['trade_actions']=[]
        with self.assertRaises(HTTPException):career_action('seattle',CareerRequest(action='profile',**dict(args,season=2,career=[step])))
        with self.assertRaises(HTTPException):career_action('seattle',CareerRequest(action='trades',lineup_rules=40))

    def test_accepted_api_trade_survives_finish_and_next_season_replay(self):
        from trade_fixtures import trading_fixture
        f=trading_fixture();request=f['request'];proposal=f['proposal']
        preview=career_action('seattle',CareerRequest(action='trades',trade_proposal=proposal,**request))
        self.assertTrue(preview['trade_preview']['accepted'])
        self.assertEqual(f['camp']['profile'],preview['profile'])
        signed=career_action('seattle',CareerRequest(action='trades',trade_actions=[proposal],**request))
        own=next(p for p in signed['profile']['roster'] if p['id']==proposal['receive_id'])
        other=next(t for t in f['camp']['trading']['teams'] if t['id']==proposal['other_team'])
        incoming=next(p for p in other['players'] if p['id']==proposal['receive_id'])
        self.assertEqual((own['contract']['annual_salary'],own['contract']['years_remaining']),(incoming['salary'],incoming['years']))
        self.assertNotIn(proposal['give_id'],[p['id'] for p in signed['profile']['roster']])
        self.assertEqual(signed,career_action('seattle',CareerRequest(action='trades',trade_actions=[proposal],**request)))
        finish=dict(kind='finish',other_team='',give_id='',receive_id='')
        step=dict(season=1,lineup_rules=41,manual_picks=request['manual_picks'],draft_rounds=6,dropped=[],free_agency=request['free_agency'],pre_camp_actions=request['pre_camp_actions'],trade_actions=[proposal,finish])
        args=dict(run_seed=1234,lineup_rules=41,rebuild_team='seattle',season=2,career=[step])
        p=career_action('seattle',CareerRequest(action='profile',**args))
        self.assertIn(proposal['receive_id'],[x['id'] for x in p['roster']])
        cpu=career_action('seattle',CareerRequest(action='profile',view_team=proposal['other_team'],**args))
        self.assertIn(proposal['give_id'],[x['id'] for x in cpu['roster']])
        replay_career.cache_clear();self.assertEqual(p,career_action('seattle',CareerRequest(action='profile',**args)))

    def test_approximately_equal_value_can_pass_for_positional_fit(self):
        offered=self.player('seattle','RB');target=self.player('miami','WR',4)
        changes={offered.id:75,target.id:75}
        changes.update({p.id:60 for p in dict(self.context)['miami'] if p.position=='RB'})
        root=replace_lineup_rosters(self.context,tuple((o,tuple(replace(p,rating=changes.get(p.id,p.rating)) for p in ps)) for o,ps in self.context))
        # Match age and normal salary so equal talent really has equal contract value.
        rosters=[]
        for owner,players in root:
            updated=[]
            for p in players:
                if p.id in (offered.id,target.id):
                    p=replace(p,age=21)
                    normal=veteran_contract(p,root.season,root.lineup_rules,contract_potential(p,root),run_seed=root.run_seed,context=root)
                    p=replace(p,contract=replace(p.contract,annual_salary=normal.annual_salary))
                updated.append(p)
            rosters.append((owner,tuple(updated)))
        root=replace_lineup_rosters(root,tuple(rosters))
        result=evaluate(root,'seattle','miami',offered.id,target.id)
        self.assertAlmostEqual(result['cpu_incoming_value'],result['cpu_outgoing_value'])
        self.assertTrue(result['accepted'],result)
        self.assertGreater(result['cpu_overall_change'],.05)
