from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch
from fastapi import HTTPException
from app.lineups import lineup_context,replace_lineup_rosters
from app.development import advance_context
from app.career import training_camp,offseason,replay_career,cpu_cuts
from app.draft import build_draft
from app.main import CareerRequest,career_action,profile_payload
from app.player_contracts import (PlayerContract,record_release,dead_cap_total,cap_payroll,payroll,
    payroll_payload,cap_ready,renew_player,sign_retained_rookies,contract_expired,guaranteed_cpu_offseason)
from app.retirement import retiring
from app.simulation import validate_roster


class GuaranteedSalaryTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=lineup_context((),1234,23,rebuild_team='seattle')
        board,_=build_draft('seattle',1,1234,roster_context=cls.root,auto_pick=True,draft_rounds=6)
        cls.board=board
        cls.choices=tuple(board['manual_picks'])
        _,cls.camp=training_camp('seattle',1,1234,cls.choices,(),cls.root,6)
        cls.request=dict(season=1,run_seed=1234,lineup_rules=23,rebuild_team='seattle',draft_rounds=6,manual_picks=list(cls.choices),training_camp=True)

    def test_full_remaining_term_is_annual_not_accelerated_and_expires(self):
        p=replace(dict(self.camp)['seattle'][0],contract=PlayerContract(8_000_000,2,3,'young'))
        context=record_release(self.camp,'seattle',p,2)
        self.assertEqual([dead_cap_total(context,'seattle',year) for year in (1,2,3,4,5)],[0,8_000_000,8_000_000,8_000_000,0])
        self.assertEqual(record_release(context,'seattle',p,2),context)
        self.assertEqual(dead_cap_total(context,'miami',2),0)
        self.assertEqual(advance_context(context,1234,3,lineup_rules=23).dead_cap,context.dead_cap)
        self.assertEqual(advance_context(context,1234,5,lineup_rules=23).dead_cap,())
        self.assertEqual(replace_lineup_rosters(context,context.rosters).dead_cap,context.dead_cap)
        self.assertEqual(self.camp.dead_cap,())

    def test_unsigned_and_expired_releases_have_no_charge(self):
        rookie=next(p for p in dict(self.camp)['seattle'] if p.rookie_offer)
        self.assertEqual(record_release(self.camp,'seattle',rookie,2),self.camp)
        p=replace(rookie,rookie_offer=None,contract=PlayerContract(5_000_000,1,1,'veteran'))
        self.assertEqual(record_release(self.camp,'seattle',p,2),self.camp)
        old=replace(self.camp,lineup_rules=22)
        self.assertEqual(record_release(old,'seattle',replace(p,contract=PlayerContract(5_000_000,1,5,'franchise')),2),old)

    def test_active_release_preserves_cap_total_and_updates_public_budget(self):
        before=career_action('seattle',CareerRequest(action='camp',**self.request))
        candidate=next(p for p in before['profile']['roster'] if p.get('contract',{}).get('status')=='active')
        action=[dict(kind='drop',player_id=candidate['id'])]
        after=career_action('seattle',CareerRequest(action='cuts',roster_actions=action,dropped=[candidate['id']],**self.request))
        a,b=after['profile']['payroll'],before['profile']['payroll']
        self.assertNotIn(candidate['id'],[p['id'] for p in after['profile']['roster']])
        self.assertEqual(a['dead_cap'],candidate['contract']['annual_salary'])
        # Mandatory-position/total replacements can add minimum pay, never cap relief.
        self.assertGreaterEqual(a['total'],b['total'])
        self.assertEqual(a['total'],a['committed']+a['rookie_holds']+a['expired_holds']+a['dead_cap'])
        self.assertEqual(a['cap_space'],a['cap']-a['total'])
        self.assertEqual(a['below_floor'],max(0,a['floor']-a['committed']))
        self.assertTrue(candidate['contract']['fully_guaranteed'])
        replay_career.cache_clear();training_camp.cache_clear()
        self.assertEqual(after,career_action('seattle',CareerRequest(action='cuts',roster_actions=action,dropped=[candidate['id']],**self.request)))
        with self.assertRaises(HTTPException):career_action('seattle',CareerRequest(action='cuts',roster_actions=action*2,dropped=[candidate['id']]*2,**self.request))

    def test_unsigned_release_really_frees_its_hold(self):
        before=career_action('seattle',CareerRequest(action='camp',**self.request))
        rookie=next(p for p in before['profile']['roster'] if p.get('contract_offer'))
        after=career_action('seattle',CareerRequest(action='cuts',roster_actions=[dict(kind='drop',player_id=rookie['id'])],dropped=[rookie['id']],**self.request))
        b,a=before['profile']['payroll'],after['profile']['payroll']
        self.assertEqual(a['dead_cap'],0)
        self.assertLess(a['rookie_holds'],b['rookie_holds'])
        self.assertLessEqual(a['total'],b['total'])

    def test_guarantees_count_in_cap_checks_and_unaffordable_renewal_is_atomic(self):
        players=dict(self.camp)['seattle'];p=players[0]
        charge=replace(p,contract=PlayerContract(199_000_000,2,4,'franchise'))
        context=record_release(self.camp,'seattle',charge,2)
        self.assertFalse(cap_ready(players,context,owner='seattle'))
        self.assertEqual(cap_payroll(players,context,owner='seattle'),payroll(players)+199_000_000)
        expired=replace(p,contract=PlayerContract(1_000_000,1,1,'low_rated'),rating=99)
        roster=[expired]+[v for v in players if v.id!=p.id]
        with self.assertRaises(ValueError):renew_player(roster,p.id,2,23,context,'seattle')
        self.assertEqual(expired.contract.annual_salary,1_000_000)

    def test_cpu_accounts_for_guarantees_and_never_cuts_signed_deals_for_cap_relief(self):
        _,context=offseason('seattle',1,1234,self.choices,(),(),self.root,6,())
        for owner,players in context:
            if owner=='seattle':continue
            validate_roster(players,minimum_total=35,maximum_total=38)
            self.assertTrue(cap_ready(players,context,owner=owner))
        self.assertTrue(context.dead_cap)
        # Every recorded release still counts on the appropriate team's budget.
        for owner,players in context:
            pay=payroll_payload(players,context,owner=owner)['payroll']
            self.assertEqual(pay['total'],payroll(players)+dead_cap_total(context,owner,2))

    def test_retirement_clears_obligations_without_creating_dead_cap(self):
        root=lineup_context((),1,23,rebuild_team='seattle')
        retired=[p for p in dict(root)['seattle'] if retiring(p,root)]
        self.assertTrue(retired)
        board,rosters=build_draft('seattle',1,1,roster_context=root,auto_pick=True,draft_rounds=6,return_league=True)
        self.assertFalse({p.id for p in retired}&{p.id for p in rosters['seattle']})
        self.assertEqual(dead_cap_total(root,'seattle',2),0)
        self.assertFalse(root.dead_cap)

    def test_release_survives_real_career_rollover_without_changing_signed_salary(self):
        before=career_action('seattle',CareerRequest(action='camp',**self.request))
        p=next(v for v in before['profile']['roster'] if v.get('contract',{}).get('status')=='active')
        actions=[dict(kind='drop',player_id=p['id'])];dropped=[p['id']]
        after=career_action('seattle',CareerRequest(action='cuts',roster_actions=actions,dropped=dropped,**self.request))
        while len(after['profile']['roster'])>38:
            rookie=next(v for v in after['profile']['roster'] if v.get('contract_offer'))
            dropped.append(rookie['id']);actions.append(dict(kind='drop',player_id=rookie['id']))
            after=career_action('seattle',CareerRequest(action='cuts',roster_actions=actions,dropped=dropped,**self.request))
        self.assertTrue(after['can_continue'])
        step=(1,(),self.choices,tuple(dropped),23,(),6,tuple((a['kind'],a['player_id']) for a in actions))
        context=replay_career('seattle',1234,(step,),23,2,1,'seattle')
        pay=payroll_payload(dict(context)['seattle'],context,owner='seattle')['payroll']
        self.assertEqual(pay['dead_cap'],p['contract']['annual_salary'])
        self.assertEqual(pay['total'],after['profile']['payroll']['total'])
        self.assertNotIn(p['id'],[v.id for v in dict(context)['seattle']])
        self.assertTrue(all(v.rookie_offer is None for v in dict(context)['seattle']))
        replay_career.cache_clear()
        self.assertEqual(context,replay_career('seattle',1234,(step,),23,2,1,'seattle'))

    def test_re_sign_then_release_owes_the_new_full_term(self):
        p=replace(dict(self.camp)['seattle'][0],rating=80,contract=PlayerContract(1_000_000,1,1,'young'))
        roster=[p]+[v for v in dict(self.camp)['seattle'] if v.id!=p.id]
        context=replace_lineup_rosters(self.camp,tuple((o,tuple(roster) if o=='seattle' else ps) for o,ps in self.camp))
        renewed=next(v for v in renew_player(roster,p.id,2,23,context,'seattle') if v.id==p.id)
        released=record_release(context,'seattle',renewed,2)
        for year in range(2,2+renewed.contract.years):
            self.assertEqual(dead_cap_total(released,'seattle',year),renewed.contract.annual_salary)
        self.assertEqual(dead_cap_total(released,'seattle',2+renewed.contract.years),0)


    def test_expired_player_at_position_and_total_minimum_can_be_replaced(self):
        source=dict(self.camp)['seattle']
        only_kicker=next(p for p in source if p.position=='K')
        players=cpu_cuts([p for p in source if p.position!='K' or p.id==only_kicker.id],35,35)
        kicker=next(p for p in players if p.position=='K')
        players=[replace(p,contract=PlayerContract(2_000_000,1,1,'veteran'),rookie_offer=None) if p.id==kicker.id else p for p in players]
        context=replace_lineup_rosters(self.camp,tuple((o,tuple(players) if o=='seattle' else ps) for o,ps in self.camp))
        with patch('app.career.training_camp',return_value=(self.board,context)):
            _,result=offseason('seattle',1,1234,self.choices,(kicker.id,),(),self.root,6,(('drop',kicker.id),))
        own=dict(result)['seattle'];validate_roster(own,minimum_total=35,maximum_total=38)
        self.assertEqual(len(own),35);self.assertEqual(dead_cap_total(result,'seattle',2),0)
        self.assertNotIn(kicker.id,[p.id for p in own])
        self.assertTrue(any(p.position=='K' and p.id.startswith('replacement-') for p in own))

    def test_release_cannot_create_an_unpayable_guaranteed_replacement(self):
        players=cpu_cuts([p for p in dict(self.camp)['seattle'] if p.position!='K' or p.contract is not None],35,35)
        kicker=next(p for p in players if p.position=='K' and p.contract)
        trimmed=replace_lineup_rosters(self.camp,tuple((o,tuple(players) if o=='seattle' else ps) for o,ps in self.camp))
        committed=sum(p.contract.annual_salary for p in players if p.contract and not contract_expired(p,2))
        filler=replace(kicker,id='old-obligation',contract=PlayerContract(210_000_000-committed-500_000,2,4,'veteran'))
        context=record_release(trimmed,'seattle',filler,2)
        with patch('app.career.training_camp',return_value=(self.board,context)):
            with self.assertRaisesRegex(ValueError,'guaranteed salary plus required replacement'):
                offseason('seattle',1,1234,self.choices,(kicker.id,),(),self.root,6,(('drop',kicker.id),))
