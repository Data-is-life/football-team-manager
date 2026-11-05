from collections import Counter
from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch
from fastapi import HTTPException
from app.career import cpu_cuts, offseason, replay_career, training_camp
from app.draft import build_draft
from app.lineups import lineup_context, replace_lineup_rosters
from app.main import CareerRequest, career_action
from app.player_contracts import (PlayerContract, veteran_contract, contract_expired, contract_payload,
    pending_renewals, renew_player, payroll, cap_ready)
from app.simulation import ROSTER_RULES, validate_roster


class ReSigningTests(TestCase):
    @classmethod
    def setUpClass(cls):
        root=lineup_context((),1234,20,rebuild_team='seattle')
        board,_=build_draft('seattle',1,1234,roster_context=root,auto_pick=True,draft_rounds=6)
        _,camp=training_camp('seattle',1,1234,tuple(board['manual_picks']),(),root,6)
        players=dict(camp)['seattle'];keep={p.id for p in cpu_cuts(players,38,35)}
        cuts=tuple(p.id for p in players if p.id not in keep)
        actions=tuple(('drop',identity) for identity in cuts)
        cls.step=(1,(),tuple(board['manual_picks']),cuts,20,(),6,actions)
        cls.current=replay_career('seattle',1234,(cls.step,),20,2,1,'seattle')
        cls.past=dict(season=1,lineup_rules=20,draft_rounds=6,manual_picks=list(board['manual_picks']),dropped=list(cuts),roster_actions=[dict(kind=k,player_id=i) for k,i in actions])
        board,_=build_draft('seattle',2,1234,roster_context=cls.current,auto_pick=True,draft_rounds=6)
        cls.choices=tuple(board['manual_picks'])
        _,cls.camp=training_camp('seattle',2,1234,cls.choices,(),cls.current,6)
        cls.request=dict(season=2,run_seed=1234,lineup_rules=20,rebuild_team='seattle',draft_rounds=6,manual_picks=list(cls.choices),career=[cls.past],training_camp=True)

    def call(self,actions=(),action='camp'):
        return career_action('seattle',CareerRequest(action=action,roster_actions=[dict(kind=k,player_id=i) for k,i in actions],dropped=[i for k,i in actions if k=='drop'],**self.request))

    def test_price_and_term_use_current_position_rating_age_and_minimum(self):
        p=next(iter(dict(self.current)['seattle']))
        for rating,age,years,category in [(95,35,5,'franchise'),(60,35,2,'low_rated'),(80,30,4,'veteran'),(80,25,3,'young')]:
            deal=veteran_contract(replace(p,rating=rating,age=age),3,20)
            self.assertEqual((deal.years,deal.category,deal.signed_season),(years,category,3))
            self.assertGreaterEqual(deal.annual_salary,1_100_000)
        self.assertEqual(veteran_contract(replace(p,position='QB',rating=75),3,20).annual_salary,8_000_000)
        self.assertEqual(veteran_contract(replace(p,position='K',rating=1),3,20).annual_salary,1_100_000)
        self.assertEqual(veteran_contract(replace(p,id='rookie-1234-2-1',position='WR',rating=75),3,20).annual_salary,4_500_000)

    def test_expiry_label_and_offer_only_after_deal_ends(self):
        data=self.call();expired=[p for p in data['profile']['roster'] if p.get('renewal_offer')]
        self.assertTrue(expired)
        self.assertEqual(data['contracts_pending'],len(expired));self.assertFalse(data['can_continue'])
        pay=data['profile']['payroll'];self.assertGreater(pay['expired_holds'],0)
        self.assertEqual(pay['total'],pay['committed']+pay['rookie_holds']+pay['expired_holds'])
        self.assertEqual(pay['below_floor'],max(0,pay['floor']-pay['committed']))
        for p in expired:
            self.assertEqual(p['contract']['status'],'expired')
            self.assertEqual(p['renewal_offer']['starts_season'],3)
            self.assertEqual(p['renewal_offer']['annual_change'],p['renewal_offer']['annual_salary']-p['contract']['annual_salary'])
        deal=PlayerContract(1_000_000,1,2,'low_rated')
        self.assertEqual(contract_payload(deal,2,20)['status'],'active')
        self.assertEqual(contract_payload(deal,3,20)['status'],'expired')
        self.assertEqual(contract_payload(deal,3,19)['status'],'renewal_due')

    def test_acceptance_updates_only_contract_and_is_replayable(self):
        before=self.call();p=next(p for p in before['profile']['roster'] if p.get('renewal_offer'))
        actions=(('resign',p['id']),)
        after=self.call(actions,'resign');new=next(v for v in after['profile']['roster'] if v['id']==p['id'])
        self.assertEqual(new['contract']['annual_salary'],p['renewal_offer']['annual_salary'])
        self.assertEqual((new['contract']['signed_season'],new['contract']['years_remaining']),(3,p['renewal_offer']['years']))
        self.assertNotIn('renewal_offer',new)
        for key in ('rating','current_rating','potential_rating','age','attributes','rating_change'):self.assertEqual(new[key],p[key])
        self.assertEqual(after['profile']['payroll']['total']-before['profile']['payroll']['total'],p['renewal_offer']['annual_change'])
        self.assertEqual(after['contracts_pending'],before['contracts_pending']-1)
        training_camp.cache_clear();replay_career.cache_clear()
        self.assertEqual(after,self.call(actions,'resign'))

    def test_invalid_phase_player_duplicate_and_action_history_are_rejected(self):
        data=self.call();expired=next(p['id'] for p in data['profile']['roster'] if p.get('renewal_offer'))
        active=next(p['id'] for p in data['profile']['roster'] if p.get('contract',{}).get('status')=='active')
        rookie=next(p['id'] for p in data['profile']['roster'] if p.get('contract_offer'))
        for identity in ('unknown','miami-qb1',active,rookie):
            with self.assertRaises(HTTPException):self.call((('resign',identity),),'resign')
        with self.assertRaises(HTTPException):self.call((('resign',expired),('resign',expired)),'resign')
        with self.assertRaises(HTTPException):
            career_action('seattle',CareerRequest(action='resign',**{**self.request,'training_camp':False},roster_actions=[dict(kind='resign',player_id=expired)]))
        with self.assertRaises(HTTPException):
            career_action('seattle',CareerRequest(action='cuts',**self.request,dropped=[expired]))

    def finish(self):
        data=self.call();actions=[]
        while len(data['profile']['roster'])>35:
            counts={r['position']:(r['count'],r['minimum']) for r in data['profile']['roster_rules']}
            p=min((p for p in data['profile']['roster'] if counts[p['position']][0]>counts[p['position']][1]),key=lambda p:p['rating'])
            actions.append(('drop',p['id']));data=self.call(tuple(actions))
        for p in tuple(data['profile']['roster']):
            if p.get('renewal_offer'):
                actions.append(('resign',p['id']));data=self.call(tuple(actions),'resign')
        return tuple(actions),data

    def test_finalization_requires_resolution_and_preserves_full_renewed_terms(self):
        # An unresolved but otherwise legal roster cannot enter the next season.
        players=dict(self.camp)['seattle'];keep={p.id for p in cpu_cuts(players,38,35)}
        cuts=tuple(p.id for p in players if p.id not in keep);actions=tuple(('drop',i) for i in cuts)
        with self.assertRaisesRegex(ValueError,'expired contracts'):
            replay_career('seattle',1234,(self.step,(2,(),self.choices,cuts,20,(),6,actions)),20,3,1,'seattle')
        actions,data=self.finish();self.assertTrue(data['can_continue']);self.assertEqual(data['contracts_pending'],0)
        self.assertTrue(any(k=='resign' for k,i in actions))
        step=(2,(),self.choices,tuple(i for k,i in actions if k=='drop'),20,(),6,actions)
        final=replay_career('seattle',1234,(self.step,step),20,3,1,'seattle')
        byid={p.id:p for p in dict(final)['seattle']}
        for p in data['profile']['roster']:
            if p.get('contract'):
                self.assertEqual(byid[p['id']].contract.annual_salary,p['contract']['annual_salary'])
                self.assertEqual(byid[p['id']].contract.years,p['contract']['years'])
        self.assertEqual(final,replay_career('seattle',1234,(self.step,step),20,3,1,'seattle'))
        for _,players in final:
            validate_roster(players,minimum_total=35,maximum_total=38)
            self.assertTrue(cap_ready(players,final));self.assertEqual(pending_renewals(players,final),0)

    def test_ordered_drop_then_renew_replays_cap_sensitive_replacements(self):
        players=list(dict(self.current)['seattle'])[:]
        players=cpu_cuts(players,35,35)
        qb=next(p for p in players if p.position=='QB');other=next(p for p in players if p.id!=qb.id)
        players=[replace(p,contract=PlayerContract(100_000_000,1,1,'veteran') if p.id==qb.id else PlayerContract(4_000_000,3,4,'veteran'),rookie_offer=None) for p in players]
        context=replace_lineup_rosters(replace(self.current,season=3),(('seattle',tuple(players)),))
        board={'complete':True,'picks':[],'draft_season':3}
        with patch('app.career.training_camp',return_value=(board,context)):
            _,result=offseason('seattle',2,1234,self.choices,(other.id,),(),self.current,6,(('drop',other.id),('resign',qb.id)))
            self.assertEqual(len(dict(result)['seattle']),35);self.assertTrue(cap_ready(dict(result)['seattle'],result))
            self.assertTrue(any(p.id.startswith('replacement-') for p in dict(result)['seattle']))
            with self.assertRaisesRegex(ValueError,'Roster must keep'):
                offseason('seattle',2,1234,self.choices,(other.id,),(),self.current,6,(('resign',qb.id),('drop',other.id)))

    def test_legacy_completed_seasons_keep_expired_deals_without_retroactive_renewal(self):
        legacy=lineup_context((),1234,19,rebuild_team='seattle')
        steps=[]
        for season in (1,2):
            current=replay_career('seattle',1234,tuple(steps),19,season,1,'seattle')
            board,_=build_draft('seattle',season,1234,roster_context=current,auto_pick=True,draft_rounds=6)
            _,full=training_camp('seattle',season,1234,tuple(board['manual_picks']),(),current,6)
            keep={p.id for p in cpu_cuts(dict(full)['seattle'],38,35)}
            steps.append((season,(),tuple(board['manual_picks']),tuple(p.id for p in dict(full)['seattle'] if p.id not in keep),19,(),6))
        old=replay_career('seattle',1234,tuple(steps),19,3,1,'seattle')
        upgraded=replay_career('seattle',1234,tuple(steps),20,3,1,'seattle')
        self.assertEqual(tuple(old),tuple(upgraded));self.assertTrue(any(contract_expired(p,3) for p in dict(upgraded)['seattle']))

    def test_signed_active_contracts_are_never_renewed_or_toppped_up(self):
        data=self.call();player=next(p for p in dict(self.camp)['seattle'] if p.contract and not contract_expired(p,3))
        with self.assertRaises(ValueError):renew_player(dict(self.camp)['seattle'],player.id,3,20)
        original={p.id:p.contract for p in dict(self.camp)['seattle'] if p.contract and not contract_expired(p,3)}
        actions,after=self.finish()
        for p in after['profile']['roster']:
            if p['id'] in original:self.assertEqual(p['contract']['annual_salary'],original[p['id']].annual_salary)
