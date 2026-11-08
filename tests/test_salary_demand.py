from dataclasses import replace
from decimal import Decimal
from unittest import TestCase
from app.lineups import lineup_context,replace_lineup_rosters
from app.development import rating_view
from app.player_contracts import (veteran_contract,market_salary,salary_demand_rating,renew_player,
    rookie_contract,cap_ready,record_release,dead_cap_total)
from app.career import replay_career,offseason,training_camp
from app.main import career_action,CareerRequest
import test_re_signing as fixtures


class SalaryDemandTests(TestCase):
    @classmethod
    def setUpClass(cls):fixtures.ReSigningTests.setUpClass.__func__(cls)

    def test_average_and_half_points_use_the_existing_position_curve(self):
        source=dict(self.current)['seattle'][0]
        for position in ('QB','WR','TE','RB','OL','DL','LB','CB','S','K'):
            p=replace(source,position=position,rating=75,age=25)
            self.assertEqual(veteran_contract(p,3,26,85).annual_salary,market_salary(position,80,3))
            self.assertEqual(salary_demand_rating(p,86),Decimal('80.5'))
            self.assertEqual(veteran_contract(p,3,26,86).annual_salary,market_salary(position,Decimal('80.5'),3))
        te=replace(source,position='TE',rating=75)
        self.assertEqual(veteran_contract(te,1,25).annual_salary,4_500_000)
        self.assertEqual(veteran_contract(te,1,26,85).annual_salary,8_000_000)
        self.assertEqual(veteran_contract(te,1,26,86).annual_salary,8_200_000)
        self.assertEqual(veteran_contract(te,3,26,86).annual_salary,9_060_000)

    def test_equal_potential_keeps_price_and_terms_still_use_current_rating(self):
        source=dict(self.current)['seattle'][0]
        for rating in (1,60,69,75,85,90,99):
            p=replace(source,rating=rating)
            self.assertEqual(veteran_contract(p,3,26,rating),veteran_contract(p,3,25))
        for rating,potential,age,years in ((85,95,25,3),(69,99,25,2),(90,99,25,5),(80,85,30,4)):
            self.assertEqual(veteran_contract(replace(source,rating=rating,age=age),3,26,potential).years,years)
        for potential in (None,0,100,True,85.5):
            with self.assertRaises(ValueError):veteran_contract(source,3,26,potential)

    def test_post_camp_public_offer_and_acceptance_use_the_same_average(self):
        request={**self.request,'lineup_rules':26}
        before=career_action('seattle',CareerRequest(action='camp',**request))
        old=career_action('seattle',CareerRequest(action='camp',**{**self.request,'lineup_rules':25}))
        self.assertEqual(before['profile']['payroll'],old['profile']['payroll'])
        offers=[p for p in before['profile']['roster'] if p.get('renewal_offer')]
        self.assertTrue(offers)
        for p in offers:
            rating=Decimal(p['current_rating']+p['potential_rating'])/2
            self.assertEqual(p['renewal_offer']['demand_rating'],float(rating))
            self.assertEqual(p['renewal_offer']['annual_salary'],market_salary(p['position'],rating,3))
        p=next(p for p in offers if p['renewal_offer']['affordable'])
        actions=[dict(kind='resign',player_id=p['id'])]
        after=career_action('seattle',CareerRequest(action='resign',roster_actions=actions,**request))
        signed=next(v for v in after['profile']['roster'] if v['id']==p['id'])
        self.assertEqual(signed['contract']['annual_salary'],p['renewal_offer']['annual_salary'])
        self.assertEqual(after['profile']['payroll']['total']-before['profile']['payroll']['total'],p['renewal_offer']['annual_change'])
        training_camp.cache_clear();replay_career.cache_clear()
        self.assertEqual(after,career_action('seattle',CareerRequest(action='resign',roster_actions=actions,**request)))

    def test_cpu_renewals_and_cap_checks_use_identical_potential_pricing(self):
        current=replay_career('seattle',1234,(self.step,),26,2,1,'seattle')
        _,context=offseason('seattle',2,1234,self.choices,(),(),current,6,())
        verified=0
        for owner,players in context:
            if owner=='seattle':continue
            self.assertTrue(cap_ready(players,context,owner=owner))
            for p in players:
                if p.contract and p.contract.signed_season==3 and p.contract.category not in ('rookie','replacement'):
                    self.assertEqual(p.contract,veteran_contract(p,3,26,rating_view(p,context)['potential_rating']))
                    verified+=1
        self.assertGreater(verified,0)

    def test_starting_deals_rookie_slots_and_signed_salaries_stay_fixed(self):
        old=lineup_context((),1234,25,rebuild_team='seattle')
        new=lineup_context((),1234,26,rebuild_team='seattle')
        self.assertEqual(old.rosters,new.rosters)
        for season in (1,3,8):
            for overall in range(1,181):
                self.assertEqual(rookie_contract((overall-1)//30+1,overall,season,25),rookie_contract((overall-1)//30+1,overall,season,26))
        current=replay_career('seattle',1234,(self.step,),26,2,1,'seattle')
        _,camp=training_camp('seattle',2,1234,self.choices,(),current,6)
        p=next(p for p in dict(camp)['seattle'] if p.contract and p.contract.signed_season+p.contract.years<=3)
        signed=renew_player(dict(camp)['seattle'],p.id,3,26,camp,'seattle')
        renewed=next(v for v in signed if v.id==p.id)
        context=replace_lineup_rosters(camp,tuple((o,tuple(signed) if o=='seattle' else ps) for o,ps in camp))
        future=lineup_context(context,1234,26,4,1,'seattle')
        self.assertEqual(next(v.contract for v in dict(future)['seattle'] if v.id==p.id),renewed.contract)
        released=record_release(context,'seattle',renewed,3)
        self.assertEqual(dead_cap_total(released,'seattle',3),renewed.contract.annual_salary)
