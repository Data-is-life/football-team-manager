"""Market pricing, cap behavior and preservation of already signed agreements."""
from dataclasses import replace
from unittest import TestCase
from app.career import offseason, replay_career
from app.lineups import lineup_context
from app.main import CareerRequest, career_action
from app.player_contracts import (MARKET_SALARIES, market_salary, minimum_salary,
    salary_cap, veteran_contract, starting_contract, rookie_contract, cap_ready, payroll)
from app.simulation import roster_for, validate_roster
import test_re_signing as fixtures


class SalaryMarketTests(TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.ReSigningTests.setUpClass.__func__(cls)

    def test_position_market_prices_at_good_and_elite_ratings(self):
        expected={'QB':(20,34),'WR':(10,20),'TE':(8,12),'RB':(7,12),'OL':(8,14),
                  'DL':(10,20),'LB':(6,11),'CB':(9,16),'S':(6,11),'K':(2.5,4)}
        for pos,(good,elite) in expected.items():
            self.assertEqual(market_salary(pos,80,1),int(good*1_000_000))
            self.assertEqual(market_salary(pos,90,1),int(elite*1_000_000))
        p=next(iter(roster_for('seattle',1234).values()))
        self.assertEqual(veteran_contract(replace(p,position='TE',rating=80),1,20).annual_salary,3_410_000)
        self.assertEqual(veteran_contract(replace(p,position='TE',rating=80),1,21).annual_salary,8_000_000)

    def test_curve_is_monotone_bounded_rounded_and_uses_current_not_potential(self):
        for pos in MARKET_SALARIES:
            for season in (1,3,10):
                values=[market_salary(pos,rating,season) for rating in range(1,101)]
                self.assertEqual(values,sorted(values))
                self.assertTrue(all(v>=minimum_salary(season,21) and v%10_000==0 for v in values))
        self.assertEqual(market_salary('TE',85,1),10_000_000)
        self.assertEqual(market_salary('QB',100,1),42_000_000)
        p=next(iter(roster_for('seattle',1234).values()))
        for rating,age,years in ((95,35,5),(60,35,2),(80,30,4),(80,25,3)):
            self.assertEqual(veteran_contract(replace(p,rating=rating,age=age),3,21).years,years)

    def test_new_offers_follow_rounded_signing_season_cap(self):
        self.assertEqual(salary_cap(3,21),221_000_000)
        self.assertEqual(market_salary('QB',80,3),22_100_000)
        self.assertEqual(market_salary('TE',80,3),8_840_000)
        self.assertEqual(market_salary('K',1,4),1_160_000)
        for overall in range(1,181):
            r=(overall-1)//30+1
            self.assertEqual(rookie_contract(r,overall,4,21),rookie_contract(r,overall,4,20))

    def test_inherited_contracts_and_existing_career_are_not_repriced(self):
        old=lineup_context((),1234,20,rebuild_team='seattle')
        new=lineup_context((),1234,21,rebuild_team='seattle')
        self.assertEqual(old.rosters,new.rosters)
        for _,players in new:
            for p in players:self.assertEqual(starting_contract(p,1,21),starting_contract(p,1,20))
        upgraded=replay_career('seattle',1234,(self.step,),21,2,1,'seattle')
        self.assertEqual(upgraded.rosters,self.current.rosters)

    def test_api_quote_acceptance_retry_and_old_contract_holds(self):
        req={**self.request,'lineup_rules':21}
        before=career_action('seattle',CareerRequest(action='camp',**req))
        old=career_action('seattle',CareerRequest(action='camp',**self.request))
        self.assertEqual(before['profile']['payroll'],old['profile']['payroll'])
        p=next(p for p in before['profile']['roster'] if p.get('renewal_offer'))
        quote=p['renewal_offer']
        self.assertEqual(quote['annual_salary'],market_salary(p['position'],p['rating'],3))
        decision=[dict(kind='resign',player_id=p['id'])]
        after=career_action('seattle',CareerRequest(action='resign',roster_actions=decision,**req))
        signed=next(v for v in after['profile']['roster'] if v['id']==p['id'])
        self.assertEqual(signed['contract']['annual_salary'],quote['annual_salary'])
        self.assertEqual(after['profile']['payroll']['total']-before['profile']['payroll']['total'],quote['annual_change'])
        self.assertEqual(after,career_action('seattle',CareerRequest(action='resign',roster_actions=decision,**req)))
        for v in after['profile']['roster']:
            if v['id']!=p['id']:
                prior=next(x for x in before['profile']['roster'] if x['id']==v['id'])
                self.assertEqual(v.get('contract'),prior.get('contract'))

    def test_cpu_renewals_use_market_and_still_finish_with_legal_budget(self):
        upgraded=replay_career('seattle',1234,(self.step,),21,2,1,'seattle')
        _,result=offseason('seattle',2,1234,self.choices,(),(),upgraded,6,())
        for owner,players in result:
            if owner=='seattle':continue
            validate_roster(players,minimum_total=35,maximum_total=38)
            self.assertTrue(cap_ready(players,result), (owner,payroll(players)))
            for p in players:
                if p.contract and p.contract.signed_season==3 and p.contract.category!='rookie' and not p.id.startswith('replacement-'):
                    self.assertEqual(p.contract,veteran_contract(p,3,21))
