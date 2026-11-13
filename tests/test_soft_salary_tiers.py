from dataclasses import replace
from decimal import Decimal, ROUND_HALF_UP
from unittest import TestCase

from app.development import advance_context, rating_view
from app.lineups import lineup_context
from app.main import CareerRequest, career_action
from app.player_contracts import (soft_salary_weight, market_salary, veteran_contract,
    minimum_salary, salary_cap, POSITION_CAP_PERCENT, public_player_fields, renew_player)
from app.preseason import prepare
from app.free_agency import asking_contract


class SoftSalaryTierTests(TestCase):
    def test_user_examples_and_continuity(self):
        for rating, amount in [(60,2),(69,'3.8'),(70,4),(71,'4.4'),(80,8),
                               (85,12),(90,16),(99,'30.4'),(100,32)]:
            self.assertEqual(soft_salary_weight(rating), Decimal(str(amount)))
        self.assertEqual(soft_salary_weight('69.5'), Decimal('3.9'))
        for boundary in (60,70,80,90):
            left = soft_salary_weight(Decimal(boundary)-Decimal('.001'))
            right = soft_salary_weight(Decimal(boundary)+Decimal('.001'))
            self.assertLess(right-left, Decimal('.003'))
        self.assertEqual(soft_salary_weight(40),0)
        self.assertEqual(soft_salary_weight(50),1)

    def test_all_positions_exact_leaders_floor_and_interpolation(self):
        for year in (1,2,10):
            for pos, percent in POSITION_CAP_PERCENT.items():
                cap = salary_cap(year,37,run_seed=1234)
                ceiling = Decimal(str(percent))*cap/100
                for anchor in (Decimal('87.5'),99,40):
                    expected = int((ceiling/10_000).quantize(Decimal(1),rounding=ROUND_HALF_UP))*10_000
                    self.assertEqual(market_salary(pos,anchor,year,37,run_seed=1234,anchor_rating=anchor),expected)
                values = [market_salary(pos,Decimal(n)/2,year,37,run_seed=1234,anchor_rating=99) for n in range(2,199)]
                self.assertEqual(values,sorted(values))
                self.assertEqual(values[0],minimum_salary(year,37,run_seed=1234))
                self.assertTrue(all(v%10_000==0 for v in values))
                # 85 lies exactly halfway between 80 and 90, before dollar rounding.
                expected = max(minimum_salary(year,37,run_seed=1234), int((ceiling*12/Decimal('30.4')/10_000).quantize(Decimal(1),rounding=ROUND_HALF_UP))*10_000)
                self.assertEqual(market_salary(pos,85,year,37,run_seed=1234,anchor_rating=99),expected)

    def test_term_boundaries_use_exact_average_and_ignore_age(self):
        context = lineup_context((),1234,37,rebuild_team='seattle')
        p = dict(context)['seattle'][0]
        for current,potential,years in [(69,69,2),(69,70,2),(69,71,3),(79,80,3),
                                        (79,81,4),(89,90,4),(89,91,5),(99,99,5)]:
            for age in (21,30,39):
                player = replace(p,rating=current,age=age)
                deal = veteran_contract(player,2,37,potential,run_seed=1234,context=context)
                self.assertEqual(deal.years,years)
        old = lineup_context((),1234,36,rebuild_team='seattle')
        self.assertEqual(old.rosters,context.rosters)
        with self.assertRaisesRegex(ValueError,'new career'):
            advance_context(old,1234,2,lineup_rules=37)
        legacy = replace(p,rating=75,age=30)
        self.assertEqual(veteran_contract(legacy,2,36,75,context=old).years,4)
        self.assertEqual(veteran_contract(legacy,2,37,75,context=context).years,3)

    def test_market_and_renewals_share_amounts_and_terms_with_replay(self):
        args = dict(run_seed=1234,lineup_rules=37,rebuild_team='seattle',draft_rounds=6)
        board = career_action('seattle',CareerRequest(action='draft',auto_draft=True,**args))
        choices = tuple(board['manual_picks'])
        root = lineup_context((),1234,37,rebuild_team='seattle')
        _,context = prepare('seattle',1,1234,choices,(),root,6)
        market_args = dict(args,action='free_agency',manual_picks=list(choices))
        market = career_action('seattle',CareerRequest(**market_args))
        pool = {p.id:p for p in context.free_agents}
        premium = market['free_agency']['destination_premium']['basis_points']
        for quote in market['free_agency']['available']:
            deal = asking_contract(pool[quote['id']],context,1,premium_basis_points=premium)
            self.assertEqual((quote['annual_salary'],quote['years']),(deal.annual_salary,deal.years))
        quote = next(p for p in market['free_agency']['available'] if p['affordable'])
        signed = career_action('seattle',CareerRequest(**market_args,
            free_agency=[{'kind':'sign','player_id':quote['id']}]))
        contract = next(p for p in signed['profile']['roster'] if p['id']==quote['id'])['contract']
        self.assertEqual((contract['annual_salary'],contract['years']),
                         (quote['annual_salary'],quote['years']))
        self.assertLessEqual(signed['profile']['payroll']['total'],signed['profile']['payroll']['cap'])
        p = next(p for p in dict(context)['seattle'] if p.contract and p.contract.years==1)
        offer = public_player_fields(p,context,renewal_owner='seattle')['renewal_offer']
        updated = renew_player(dict(context)['seattle'],p.id,2,37,context,'seattle')
        deal = next(v for v in updated if v.id==p.id).contract
        self.assertEqual((offer['annual_salary'],offer['years']),(deal.annual_salary,deal.years))
        count = 0
        for owner,players in context:
            if owner=='seattle': continue
            for p in players:
                if p.contract and p.contract.signed_season==2 and p.contract.category!='replacement':
                    self.assertEqual(p.contract,veteran_contract(p,2,37,rating_view(p,context)['potential_rating'],run_seed=1234,context=context))
                    count += 1
        self.assertGreater(count,0)
        prepare.cache_clear()
        self.assertEqual(market,career_action('seattle',CareerRequest(**market_args)))
