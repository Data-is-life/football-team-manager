from dataclasses import replace
from decimal import Decimal, ROUND_HALF_UP
from unittest import TestCase

from app.development import advance_context, rating_view
from app.lineups import lineup_context, replace_lineup_rosters
from app.main import CareerRequest, career_action
from app.player_contracts import (POSITION_CAP_PERCENT, snapshot_salary_anchors,
    market_salary, minimum_salary, salary_cap, salary_demand_rating, veteran_contract,
    public_player_fields, renew_player)
from app.free_agency import asking_contract
from app.preseason import prepare


class PositionSalaryAnchorTests(TestCase):
    def test_all_ten_percentages_and_half_point_leaders(self):
        self.assertEqual(POSITION_CAP_PERCENT, {'QB':21,'WR':14,'RB':7.5,'TE':6,
            'OL':10,'DL':12,'LB':16,'CB':11,'S':8,'K':2.5})
        for season in (1, 2, 10):
            cap = salary_cap(season, 36, run_seed=1234)
            for position, percent in POSITION_CAP_PERCENT.items():
                expected = int((Decimal(str(percent))*cap/100/10_000).quantize(
                    Decimal('1'), rounding=ROUND_HALF_UP))*10_000
                for anchor in (Decimal('87.5'), 99, 60, 40):
                    self.assertEqual(market_salary(position, anchor, season, 36,
                        run_seed=1234, anchor_rating=anchor), expected)
                values = [market_salary(position, Decimal(n)/2, season, 36,
                    run_seed=1234, anchor_rating=Decimal('87.5')) for n in range(2, 176)]
                self.assertEqual(values, sorted(values))
                self.assertEqual(values[0], minimum_salary(season, 36, run_seed=1234))
                self.assertLess(values[-2], values[-1])
                self.assertTrue(all(v % 10_000 == 0 for v in values))
        with self.assertRaises(ValueError):
            market_salary('QB', 80, 1, 36)

    def test_snapshot_uses_every_team_free_agents_and_exact_average(self):
        root = lineup_context((), 1234, 36, rebuild_team='seattle')
        expected = {}
        for _, players in root:
            for p in players:
                value = salary_demand_rating(p, rating_view(p, root)['potential_rating'])
                expected[p.position] = max(value, expected.get(p.position, 0))
        self.assertEqual(dict(root.salary_anchors), expected)
        p = replace(dict(root)['seattle'][0], id='unsigned-anchor', position='LB', rating=98)
        state = replace(dict(root.development)[dict(root)['seattle'][0].id], potential=99)
        context = replace(root, free_agents=(p,), development=root.development+((p.id,state),))
        self.assertEqual(dict(snapshot_salary_anchors(context))['LB'], Decimal('98.5'))
        signed = veteran_contract(p, 1, 36, 99, context=replace(context,
            salary_anchors=snapshot_salary_anchors(context)))
        self.assertEqual(signed.annual_salary, 32_000_000)
        self.assertEqual(asking_contract(p, replace(context, salary_anchors=snapshot_salary_anchors(context)),
            1, premium_basis_points=2000).annual_salary, 46_080_000)

    def test_legacy_contracts_rookie_pay_and_terms_stay_unchanged(self):
        old = lineup_context((), 1234, 35, rebuild_team='seattle')
        new = lineup_context((), 1234, 36, rebuild_team='seattle')
        self.assertEqual(old.rosters, new.rosters)
        with self.assertRaisesRegex(ValueError, 'new career'):
            advance_context(old, 1234, 2, lineup_rules=36)
        for _, players in new:
            for p in players:
                potential = rating_view(p, new)['potential_rating']
                legacy = veteran_contract(p, 2, 35, potential, run_seed=1234)
                anchored = veteran_contract(p, 2, 36, potential, run_seed=1234, context=new)
                self.assertEqual(legacy.years, anchored.years)
        self.assertEqual(market_salary('LB', 99, 1, 35), 14_000_000)
        self.assertEqual(new.salary_anchors, advance_context(new, 1234, 2, lineup_rules=36).salary_anchors)

    def test_offseason_snapshot_renewal_market_and_replay(self):
        seed = 1234
        args = dict(run_seed=seed, lineup_rules=36, rebuild_team='seattle', draft_rounds=6)
        draft = career_action('seattle', CareerRequest(action='draft', auto_draft=True, **args))
        choices = tuple(draft['manual_picks'])
        root = lineup_context((), seed, 36, rebuild_team='seattle')
        _, context = prepare('seattle', 1, seed, choices, (), root, 6)
        self.assertEqual(len(context.salary_anchors), 10)
        stale = replace(root, salary_anchors=tuple((pos, Decimal(60)) for pos in POSITION_CAP_PERCENT))
        _, refreshed = prepare('seattle', 1, seed, choices, (), stale, 6)
        self.assertEqual(refreshed.salary_anchors, context.salary_anchors)
        from app.draft import draft_class
        from app.retirement import retiring
        from app.development import initial_state
        candidates = [p for _, ps in root for p in ps if not retiring(p,root)]
        candidates += list(draft_class(1,seed))
        expected = {}
        states = dict(root.development)
        for p in candidates:
            potential = (states.get(p.id) or initial_state(p,seed,True)).potential
            value = salary_demand_rating(p,potential)
            expected[p.position] = max(expected.get(p.position,0),value)
        self.assertEqual(dict(context.salary_anchors),expected)
        p = next(p for p in dict(context)['seattle'] if p.contract and p.contract.years == 1)
        offer = public_player_fields(p, context, renewal_owner='seattle')['renewal_offer']
        updated = renew_player(dict(context)['seattle'], p.id, 2, 36, context, 'seattle')
        self.assertEqual(next(v for v in updated if v.id == p.id).contract.annual_salary, offer['annual_salary'])
        changed = replace_lineup_rosters(context, tuple((o, tuple(updated) if o=='seattle' else ps)
            for o, ps in context))
        self.assertEqual(changed.salary_anchors, context.salary_anchors)
        market_args = dict(args, action='free_agency', manual_picks=list(choices))
        before = career_action('seattle', CareerRequest(**market_args))
        premium = before['free_agency']['destination_premium']['basis_points']
        pool = {p.id:p for p in context.free_agents}
        for quote in before['free_agency']['available']:
            self.assertEqual(quote['annual_salary'], asking_contract(pool[quote['id']], context, 1,
                premium_basis_points=premium).annual_salary)
        # CPU renewals also quote from this same frozen positional market.
        for owner, ps in context:
            if owner == 'seattle': continue
            for p in ps:
                if p.contract and p.contract.signed_season == 2 and p.contract.category != 'replacement':
                    expected = veteran_contract(p, 2, 36, rating_view(p, context)['potential_rating'],
                        run_seed=seed, context=context)
                    self.assertEqual(p.contract, expected)
        prepare.cache_clear()
        self.assertEqual(before, career_action('seattle', CareerRequest(**market_args)))
