from collections import Counter
from dataclasses import replace
from unittest import TestCase
from app.career import cpu_cuts, drop_players, offseason, replay_career, training_camp
from app.draft import build_draft
from app.lineups import lineup_context, replace_lineup_rosters
from app.main import CareerRequest, career_action
from app.player_contracts import (rookie_contract, ensure_contracts, contract_terms, payroll,
    payroll_payload, cap_ready, cpu_cap_cuts, sign_retained_rookies)
from app.simulation import ROSTER_RULES, validate_roster


class RookieSigningTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context=lineup_context((),1234,19,rebuild_team='seattle')
        cls.board,cls.players=build_draft('seattle',1,1234,roster_context=cls.context,auto_pick=True,draft_rounds=6)
        cls.choices=tuple(cls.board['manual_picks'])
        _,cls.full=training_camp('seattle',1,1234,cls.choices,(),cls.context,6)
        cls.request=dict(season=1,run_seed=1234,lineup_rules=19,rebuild_team='seattle',draft_rounds=6,manual_picks=list(cls.choices))

    def test_draft_all_slots_are_unsigned_offers_and_previews_match(self):
        for pick in self.board['picks']:
            player=pick['player'];self.assertNotIn('contract',player)
            offer=player['contract_offer']
            expected=rookie_contract(pick['round'],pick['overall'],2,19)
            self.assertEqual((offer['annual_salary'],offer['years'],offer['starts_season']),(expected.annual_salary,expected.years,2))
            self.assertEqual(offer['status'],'provisional')
            self.assertNotIn('signed_season',offer);self.assertNotIn('years_remaining',offer)
        for p in self.players:
            if p.id.startswith('rookie-'):
                self.assertIsNone(p.contract);self.assertIsNotNone(p.rookie_offer)
        partial,_=build_draft('seattle',1,1234,roster_context=self.context,draft_rounds=6)
        next_offer=partial['next_contract']
        self.assertEqual(next_offer['status'],'provisional')
        self.assertEqual(next_offer['annual_salary'],rookie_contract(1,partial['next_pick'],2,19).annual_salary)
        manual,_=build_draft('seattle',1,1234,self.choices,roster_context=self.context,draft_rounds=6)
        self.assertEqual(self.board['picks'],manual['picks'])
        self.assertTrue(all('contract_offer' not in p and 'contract' not in p for p in partial['available']))

    def test_development_and_camp_retries_do_not_sign_or_reprice_offers(self):
        self.assertEqual(ensure_contracts(self.full,2),self.full)
        offers={p.id:p.rookie_offer for p in self.players if p.rookie_offer is not None}
        first=career_action('seattle',CareerRequest(action='camp',**self.request))
        training_camp.cache_clear()
        self.assertEqual(first,career_action('seattle',CareerRequest(action='camp',training_camp=True,**self.request)))
        for p in first['profile']['roster']:
            if p['id'] in offers:
                self.assertNotIn('contract',p);self.assertEqual(p['contract_offer']['status'],'provisional')
                self.assertEqual(p['contract_offer']['annual_salary'],offers[p['id']].annual_salary)
        self.assertTrue(any(p['rookie_outcome'] in ('boom','bust','normal') for p in first['development_roster'] if p['id'] in offers))

    def cut_plan(self,release_rookie=False):
        players=list(dict(self.full)['seattle']);forced=[]
        if release_rookie:
            counts=Counter(p.position for p in players)
            rookie=next(p for p in players if p.rookie_offer and counts[p.position]>ROSTER_RULES[p.position][1])
            forced.append(rookie.id);players=drop_players(players,forced,35)
        kept=cpu_cap_cuts(cpu_cuts(players,38,35),'seattle',1,1234,self.full)
        retained={p.id for p in kept}
        return tuple(forced+[p.id for p in players if p.id not in retained])

    def test_released_rookie_leaves_no_contract_or_hold_before_and_after_finalization(self):
        cuts=self.cut_plan(True)
        before=career_action('seattle',CareerRequest(action='camp',**self.request))
        cut=career_action('seattle',CareerRequest(action='cuts',training_camp=True,dropped=list(cuts),**self.request))
        self.assertTrue(cut['can_continue'])
        removed=[p for p in before['profile']['roster'] if p['id'] in cuts]
        self.assertTrue(any('contract_offer' in p for p in removed))
        expected_removed=sum((p.get('contract') or p['contract_offer'])['annual_salary'] for p in removed)
        self.assertEqual(before['profile']['payroll']['total']-cut['profile']['payroll']['total'],expected_removed)
        self.assertTrue(all(p['id'] not in cuts for p in cut['profile']['roster']))
        step=(1,(),self.choices,cuts,19,(),6)
        final=replay_career('seattle',1234,(step,),19,2,1,'seattle')
        self.assertTrue(all(p.id not in cuts for _,roster in final for p in roster))
        self.assertEqual(payroll(dict(final)['seattle']),cut['profile']['payroll']['total'])
        # Recaps retain the original unsigned draft-day estimate, including the released pick.
        self.assertEqual(cut['picks'],before['picks'])
        self.assertTrue(all('contract' not in pick['player'] for pick in cut['picks']))

    def test_finalization_signs_only_retained_rookies_for_all_teams_with_full_term(self):
        cuts=self.cut_plan();_,camp=offseason('seattle',1,1234,self.choices,cuts,(),self.context,6)
        step=(1,(),self.choices,cuts,19,(),6)
        final=replay_career('seattle',1234,(step,),19,2,1,'seattle')
        for owner,players in final:
            validate_roster(players,minimum_total=35,maximum_total=38)
            originals={p.id:p for p in dict(camp)[owner]}
            self.assertEqual(payroll(players),payroll(dict(camp)[owner]))
            for p in players:
                original=originals[p.id]
                self.assertIsNone(p.rookie_offer)
                if original.rookie_offer:
                    self.assertEqual(p.contract,original.rookie_offer)
                    self.assertEqual(replace(p,contract=None,rookie_offer=original.rookie_offer),original)
                else:self.assertEqual(p,original)
        request=dict(action='profile',season=2,run_seed=1234,lineup_rules=19,rebuild_team='seattle',career=[dict(season=1,lineup_rules=19,draft_rounds=6,manual_picks=list(self.choices),dropped=list(cuts))])
        first=career_action('seattle',CareerRequest(**request))
        replay_career.cache_clear();training_camp.cache_clear()
        self.assertEqual(first,career_action('seattle',CareerRequest(**request)))
        self.assertEqual(first['payroll']['rookie_holds'],0)
        self.assertEqual(first['payroll']['committed'],first['payroll']['total'])
        for p in first['roster']:
            self.assertNotIn('contract_offer',p)
            if p['id'].startswith('rookie-'):
                self.assertEqual(p['contract']['status'],'active')
                self.assertEqual(p['contract']['years_remaining'],p['contract']['years'])
        with self.assertRaisesRegex(ValueError,'38 players'):
            replay_career('seattle',1234,((1,(),self.choices,(),19,(),6),),19,2,1,'seattle')

    def test_holds_count_toward_cap_but_do_not_satisfy_floor(self):
        players=list(dict(self.full)['seattle']);pay=payroll_payload(players,self.full)['payroll']
        signed=sum(p.contract.annual_salary for p in players if p.contract)
        holds=sum(p.rookie_offer.annual_salary for p in players if p.rookie_offer)
        self.assertEqual((pay['committed'],pay['rookie_holds'],pay['total']),(signed,holds,signed+holds))
        self.assertEqual(pay['below_floor'],max(0,pay['floor']-signed))
        first=next(i for i,p in enumerate(players) if p.contract)
        old=players[first]
        players[first]=replace(old,contract=replace(old.contract,annual_salary=old.contract.annual_salary+pay['cap']-pay['total']))
        self.assertTrue(cap_ready(players,self.full))
        players[first]=replace(players[first],contract=replace(players[first].contract,annual_salary=players[first].contract.annual_salary+1))
        self.assertFalse(cap_ready(players,self.full))
        self.assertGreater(payroll(players),sum(p.contract.annual_salary for p in players if p.contract))

    def test_cpu_releases_and_replacements_respect_unsigned_budget(self):
        for owner,players in self.full:
            expensive=[replace(p,contract=replace(p.contract,annual_salary=8_000_000)) if p.contract else p for p in players]
            result=cpu_cap_cuts(cpu_cuts(expensive,38,35),owner,1,1234,self.full)
            validate_roster(result,minimum_total=35,maximum_total=38)
            self.assertTrue(cap_ready(result,self.full))
            self.assertTrue(all(p.contract is None for p in result if p.rookie_offer))
            self.assertEqual(result,cpu_cap_cuts(cpu_cuts(expensive,38,35),owner,1,1234,self.full))

    def test_old_signed_drafts_survive_upgrade_while_future_class_is_provisional(self):
        legacy=lineup_context((),1234,18,rebuild_team='seattle')
        board,players=build_draft('seattle',1,1234,roster_context=legacy,auto_pick=True,draft_rounds=6)
        _,full=training_camp('seattle',1,1234,tuple(board['manual_picks']),(),legacy,6)
        keep={p.id for p in cpu_cuts(dict(full)['seattle'],38,35)}
        step=(1,(),tuple(board['manual_picks']),tuple(p.id for p in dict(full)['seattle'] if p.id not in keep),18,(),6)
        old=replay_career('seattle',1234,(step,),18,2,1,'seattle')
        upgraded=replay_career('seattle',1234,(step,),19,2,1,'seattle')
        self.assertEqual(tuple(old),tuple(upgraded))
        deals={p.id:p.contract for _,roster in upgraded for p in roster}
        board,players=build_draft('seattle',2,1234,roster_context=upgraded,auto_pick=True,draft_rounds=6)
        for p in players:
            if p.id in deals:self.assertEqual(p.contract,deals[p.id]);self.assertIsNone(p.rookie_offer)
            elif p.id.startswith('rookie-'):self.assertIsNone(p.contract);self.assertIsNotNone(p.rookie_offer)
        self.assertTrue(all('contract_offer' in pick['player'] for pick in board['picks']))

    def test_signing_is_idempotent_and_rejects_wrong_season_or_missing_terms(self):
        signed=sign_retained_rookies(self.full,2)
        self.assertEqual(signed,sign_retained_rookies(signed,2))
        with self.assertRaisesRegex(ValueError,'playing season'):sign_retained_rookies(self.full,3)
        rookie=next(p for p in dict(self.full)['seattle'] if p.rookie_offer)
        with self.assertRaises(ValueError):contract_terms(replace(rookie,contract=rookie.rookie_offer))
        with self.assertRaises(ValueError):contract_terms(replace(rookie,rookie_offer=None))
