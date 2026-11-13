"""Annual cap draws, financial scales and immutable, career-specific replay."""
from dataclasses import replace
from decimal import Decimal, ROUND_HALF_UP
import random
from statistics import mean, pstdev
from unittest import TestCase

from app.development import advance_context
from app.free_agency import asking_contract
from app.lineups import lineup_context, replace_lineup_rosters
from app.main import CareerRequest, career_action, DraftRequest, rookie_draft
from app.player_contracts import (SALARY_CAP, cap_growth_basis_points, cap_ready,
    minimum_salary, salary_cap, payroll_floor, rookie_contract, payroll_payload,
    market_salary, starting_contract, public_player_fields)
from app.preseason import financial_ready, raise_plan
from app.retirement import fill_roster


class SeededCapTests(TestCase):
    def test_rates_are_bounded_bell_shaped_and_independent_of_call_order(self):
        values = [cap_growth_basis_points(2, seed) for seed in range(1000)]
        self.assertTrue(all(200 <= value <= 1000 for value in values))
        self.assertAlmostEqual(mean(values), 600, delta=15)
        self.assertTrue(150 < pstdev(values) < 195)
        self.assertTrue(.65 < sum(400 <= v <= 800 for v in values)/len(values) < .8)
        expected = {year: cap_growth_basis_points(year, 1234) for year in (2, 4, 9)}
        self.assertGreater(len(set(expected.values())), 1)
        cap_growth_basis_points.cache_clear()
        state = random.getstate()
        self.assertEqual({year: cap_growth_basis_points(year, 1234) for year in (9, 2, 4)}, expected)
        self.assertEqual(random.getstate(), state)
        self.assertNotEqual([cap_growth_basis_points(s, 1234) for s in range(2, 12)],
                            [cap_growth_basis_points(s, 5678) for s in range(2, 12)])

    def test_caps_compound_with_hard_bounds_and_exact_floor(self):
        for seed in (0, 1, 1234, 5678, 4294967295):
            previous = salary_cap(1, 35, run_seed=seed)
            self.assertEqual(previous, SALARY_CAP)
            for year in range(2, 31):
                cap = salary_cap(year, 35, run_seed=seed)
                self.assertGreaterEqual(cap * 100, previous * 102)
                self.assertLessEqual(cap * 100, previous * 110)
                rate = cap_growth_basis_points(year, seed)
                self.assertLessEqual(abs(cap - previous * (10_000 + rate)/10_000), 10_000)
                self.assertEqual(cap % 10_000, 0)
                self.assertEqual(payroll_floor(year, 35, run_seed=seed) * 100, cap * 60)
                previous = cap
        self.assertNotEqual(salary_cap(8, 35, run_seed=1234), salary_cap(8, 35, run_seed=5678))
        self.assertGreater(salary_cap(999, 35, run_seed=1234), 2**53)
        self.assertIsInstance(minimum_salary(999, 35, run_seed=1234), int)
        for invalid in (0, -1, True, 1.5):
            with self.assertRaises(ValueError):
                salary_cap(invalid, 35, run_seed=1234)

    def test_new_salary_scales_follow_the_same_cap_and_old_rules_keep_five_percent(self):
        for seed in (1234, 5678):
            for year in (2, 4, 8):
                cap = salary_cap(year, 35, run_seed=seed)
                def scaled(base):
                    raw = Decimal(base) * cap / SALARY_CAP
                    return int((raw/10_000).quantize(Decimal('1'), rounding=ROUND_HALF_UP))*10_000
                self.assertEqual(minimum_salary(year, 35, run_seed=seed), scaled(1_000_000))
                for pick in range(1, 181):
                    round_number = (pick-1)//30+1
                    original = rookie_contract(round_number, pick, 1, 35)
                    new = rookie_contract(round_number, pick, year, 35, run_seed=seed)
                    self.assertEqual(new.annual_salary, scaled(original.annual_salary))
                    self.assertEqual(replace(new, annual_salary=original.annual_salary, signed_season=1), original)
                self.assertEqual(market_salary('QB', 99, year, 35, run_seed=seed), scaled(42_000_000))
            self.assertEqual([salary_cap(s, 34, run_seed=seed) for s in range(1, 5)],
                             [200_000_000, 210_000_000, 221_000_000, 232_000_000])
            self.assertEqual(rookie_contract(1, 1, 2, 34, run_seed=seed).annual_salary, 5_250_000)

    def test_signed_contracts_and_replacement_holds_keep_correct_signing_year(self):
        seed = 1234
        root = lineup_context((), seed, 35, rebuild_team='seattle')
        later = advance_context(root, seed, 2, lineup_rules=35)
        original = {p.id: p.contract for _, players in root for p in players}
        self.assertTrue(all(p.contract == original[p.id] for _, players in later for p in players))
        replacements = fill_roster([], 'seattle', 3, seed, context=later)
        for player in replacements:
            self.assertEqual(player.rookie_offer.annual_salary, minimum_salary(4, 35, run_seed=seed))
            self.assertEqual(player.rookie_offer, starting_contract(player, 9, 35, run_seed=seed))

    def test_draft_preview_market_and_renewal_share_the_career_scale(self):
        for seed in (1234, 5678):
            args = dict(run_seed=seed, lineup_rules=35, rebuild_team='seattle', draft_rounds=6)
            draft = career_action('seattle', CareerRequest(action='draft', **args))
            pay = draft['profile']['payroll']
            self.assertEqual(pay['cap'], salary_cap(2, 35, run_seed=seed))
            self.assertEqual(pay['floor'], payroll_floor(2, 35, run_seed=seed))
            self.assertEqual(pay['cap_growth_percent'], cap_growth_basis_points(2, seed)/100)
            self.assertEqual(pay['previous_cap'], SALARY_CAP)
            self.assertEqual(draft['next_contract']['annual_salary'],
                             rookie_contract(1, draft['next_pick'], 2, 35, run_seed=seed).annual_salary)
            self.assertEqual(rookie_draft('seattle', DraftRequest(**args))['profile']['payroll'], pay)
            complete = career_action('seattle', CareerRequest(action='draft', auto_draft=True, **args))
            market = career_action('seattle', CareerRequest(action='free_agency', manual_picks=complete['manual_picks'], **args))
            self.assertEqual(market['profile']['payroll']['cap'], pay['cap'])
            root = lineup_context((), seed, 35, rebuild_team='seattle')
            from app.preseason import prepare
            _, context = prepare('seattle', 1, seed, tuple(complete['manual_picks']), (), root, 6)
            premium = market['free_agency']['destination_premium']['basis_points']
            pool = {p.id: p for p in context.free_agents}
            for quote in market['free_agency']['available'][:5]:
                self.assertEqual(quote['annual_salary'], asking_contract(pool[quote['id']], context, 1,
                                 premium_basis_points=premium).annual_salary)
            renewing = next(p for p in dict(context)['seattle'] if p.contract and p.contract.years == 1)
            offer = public_player_fields(renewing, context, renewal_owner='seattle')['renewal_offer']
            expected = market_salary(renewing.position, offer['demand_rating'], 2, 35, run_seed=seed)
            self.assertEqual(offer['annual_salary'], expected)

    def test_all_teams_and_hard_cap_checks_use_the_career_seed(self):
        seed = 1234
        root = lineup_context((), seed, 35, rebuild_team='seattle')
        context = replace(root, season=2)
        cap = salary_cap(2, 35, run_seed=seed)
        for owner, players in context:
            self.assertEqual(payroll_payload(players, context, owner=owner)['payroll']['cap'], cap)
        rosters = dict(context)
        players = list(rosters['seattle'])
        # One guaranteed deal exactly reaches this career's cap, then exceeds it.
        i = next(i for i, p in enumerate(players) if p.contract.years > 1)
        total = sum(p.contract.annual_salary for p in players)
        player = players[i]
        players[i] = replace(player, contract=replace(player.contract, annual_salary=player.contract.annual_salary+cap-total))
        rosters['seattle'] = tuple(players)
        tight = replace_lineup_rosters(context, tuple(rosters.items()))
        self.assertTrue(cap_ready(players, tight, owner='seattle'))
        self.assertIsNone(raise_plan(players, tight, 'seattle'))
        players[i] = replace(players[i], contract=replace(players[i].contract, annual_salary=players[i].contract.annual_salary+1))
        self.assertFalse(cap_ready(players, tight, owner='seattle'))
        self.assertFalse(financial_ready(players, tight, 'seattle'))
