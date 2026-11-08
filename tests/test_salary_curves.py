from dataclasses import replace
from decimal import Decimal
from unittest import TestCase
from app.lineups import lineup_context
from app.development import rating_view
from app.player_contracts import (MARKET_SALARIES,market_salary,minimum_salary,salary_cap,
    veteran_contract,rookie_contract,cap_ready)
from app.career import replay_career,offseason,training_camp
from app.main import CareerRequest,career_action
import test_re_signing as fixtures


class SalaryCurveTests(TestCase):
    @classmethod
    def setUpClass(cls): fixtures.ReSigningTests.setUpClass.__func__(cls)

    def test_floor_ceiling_monotonicity_and_acceleration_for_every_position(self):
        for position,anchors in MARKET_SALARIES.items():
            for season in (1,3,10):
                values=[market_salary(position,Decimal(n)/2,season,27) for n in range(2,199)]
                self.assertEqual(values,sorted(values))
                self.assertEqual(values[118],minimum_salary(season,27)) # rating 60
                self.assertEqual(values[0],minimum_salary(season,27))
                self.assertTrue(all(v%10_000==0 for v in values))
                self.assertEqual(values[-1],market_salary(position,99,season,26))
            v=[market_salary(position,r,1,27) for r in (60,70,80,90,99)]
            slopes=[Decimal(b-a)/(rb-ra) for a,b,ra,rb in zip(v,v[1:],(60,70,80,90),(70,80,90,99))]
            self.assertEqual(slopes,sorted(slopes))
            self.assertEqual(v[-1],anchors[-1])
        self.assertEqual([market_salary('QB',r,1,27) for r in (60,70,80,90,99)],
                         [1_000_000,4_950_000,12_630_000,25_300_000,42_000_000])

    def test_representative_35_player_market_budgets_reward_affordable_depth(self):
        from app.simulation import ROSTER_RULES
        players=dict(lineup_context((),1234,27,rebuild_team='seattle'))['seattle']
        self.assertEqual(len(players),35)
        def quote(starter,bench):
            return sum(market_salary(p.position,starter if p.depth<=ROSTER_RULES[p.position][1] else bench,1,27) for p in players)
        self.assertLess(quote(75,60),quote(80,65))
        self.assertGreaterEqual(quote(80,65),160_000_000)
        self.assertLess(quote(80,65),salary_cap(1,27))
        self.assertGreater(quote(85,70),salary_cap(1,27))

    def test_exact_average_cap_scaling_and_contract_terms(self):
        p=replace(dict(self.current)['seattle'][0],position='QB',rating=75,age=25)
        deal=veteran_contract(p,3,27,86)
        self.assertEqual(deal.annual_salary,market_salary('QB',Decimal('80.5'),3,27))
        self.assertNotEqual(deal.annual_salary,market_salary('QB',80,3,27))
        self.assertEqual(deal.years,3)
        self.assertEqual(veteran_contract(replace(p,rating=90),1,27,99).years,5)
        self.assertEqual(veteran_contract(replace(p,rating=69),1,27,99).years,2)
        self.assertEqual(veteran_contract(replace(p,age=30),1,27,86).years,4)
        self.assertEqual(market_salary('QB',60,3,27),1_100_000)
        self.assertEqual(market_salary('QB',99,3,27),46_410_000)
        self.assertEqual(salary_cap(3,27),221_000_000)

    def test_offers_acceptance_and_guarantees_use_identical_curve(self):
        request={**self.request,'lineup_rules':27}
        before=career_action('seattle',CareerRequest(action='camp',**request))
        old=career_action('seattle',CareerRequest(action='camp',**{**request,'lineup_rules':26}))
        self.assertEqual(before['profile']['payroll'],old['profile']['payroll'])
        offers=[p for p in before['profile']['roster'] if p.get('renewal_offer')]
        self.assertTrue(offers)
        for p in offers:
            self.assertEqual(p['renewal_offer']['annual_salary'],market_salary(p['position'],Decimal(p['current_rating']+p['potential_rating'])/2,3,27))
        p=next(p for p in offers if p['renewal_offer']['affordable'])
        actions=[dict(kind='resign',player_id=p['id'])]
        after=career_action('seattle',CareerRequest(action='resign',roster_actions=actions,**request))
        signed=next(v for v in after['profile']['roster'] if v['id']==p['id'])
        self.assertEqual(signed['contract']['annual_salary'],p['renewal_offer']['annual_salary'])
        self.assertEqual(after['profile']['payroll']['total']-before['profile']['payroll']['total'],p['renewal_offer']['annual_change'])
        preview=signed['release_preview']
        self.assertEqual(preview['total_obligation'],signed['contract']['annual_salary']*signed['contract']['years'])
        training_camp.cache_clear();replay_career.cache_clear()
        self.assertEqual(after,career_action('seattle',CareerRequest(action='resign',roster_actions=actions,**request)))

    def test_cpu_renewals_fit_the_cap_and_signed_rookie_inherited_deals_are_unchanged(self):
        old=lineup_context((),1234,26,rebuild_team='seattle')
        new=lineup_context((),1234,27,rebuild_team='seattle')
        self.assertEqual(old.rosters,new.rosters)
        for season in (1,3,8):
            for overall in range(1,181):
                self.assertEqual(rookie_contract((overall-1)//30+1,overall,season,26),rookie_contract((overall-1)//30+1,overall,season,27))
        current=replay_career('seattle',1234,(self.step,),27,2,1,'seattle')
        _,context=offseason('seattle',2,1234,self.choices,(),(),current,6,())
        verified=0
        for owner,players in context:
            if owner=='seattle':continue
            self.assertTrue(cap_ready(players,context,owner=owner))
            for p in players:
                if p.contract and p.contract.signed_season==3 and p.contract.category not in ('rookie','replacement'):
                    self.assertEqual(p.contract,veteran_contract(p,3,27,rating_view(p,context)['potential_rating']))
                    verified+=1
        self.assertGreater(verified,0)
