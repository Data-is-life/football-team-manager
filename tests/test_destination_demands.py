"""Destination pricing uses a frozen concluded season and applies to every buyer."""
from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch

from app.free_agency import (asking_contract, free_agency, free_agency_order,
                             market_premium, team_market_premiums)
from app.league import TEAM_BY_ID
from app.lineups import lineup_context, replace_lineup_rosters
from app.main import CareerRequest, career_action
from app.player_contracts import cap_payroll, minimum_salary, salary_cap
from app.preseason import prepare
from app.standings import standings_through_week


class DestinationDemandTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = lineup_context((), 1234, 34, rebuild_team='seattle')
        cls.args = dict(run_seed=1234, lineup_rules=34, rebuild_team='seattle', draft_rounds=6)
        draft = career_action('seattle', CareerRequest(action='draft', auto_draft=True, **cls.args))
        cls.choices = tuple(draft['manual_picks'])
        _, cls.context = prepare('seattle', 1, 1234, cls.choices, (), cls.root, 6)
        cls.order = free_agency_order(1, 1234, (), cls.root)
        cls.premiums = team_market_premiums(1, 1234, (), cls.root)

    def market(self, actions=(), context=None, premiums=None):
        return free_agency('seattle', 1, 1234, context or self.context, self.order, actions,
                           premiums=self.premiums if premiums is None else premiums)

    def test_formula_bounds_and_ties(self):
        self.assertEqual(market_premium(75, 75, 8, 8, 1), (0, 0))
        self.assertEqual(market_premium(90, 90, 14, 3, 0), (0, 0))
        self.assertEqual(market_premium(65, 65, 0, 17, 0), (1000, 1000))
        self.assertEqual(market_premium(1, 1, 0, 17, 0), (1000, 1000))
        self.assertEqual(market_premium(70, 70, 3, 14, 0), (500, 647))
        self.assertEqual(market_premium(70, 70, 0, 0, 0), (500, 0))
        self.assertEqual(market_premium(75, 75, 0, 0, 17), (0, 0))
        self.assertEqual(market_premium(74, 75, 7, 8, 2), (50, 59))
        self.assertLess(sum(market_premium(73, 73, 5, 12, 0)),
                        sum(market_premium(70, 70, 3, 14, 0)))

    def test_snapshot_comes_from_the_concluded_season_and_changes_next_year(self):
        tables = standings_through_week(1, 17, 1234, (), self.root)
        self.assertEqual(set(self.premiums), set(TEAM_BY_ID))
        for group in tables['groups']:
            for row in group['teams']:
                expected = market_premium(**row['ratings'], wins=row['wins'], losses=row['losses'], ties=row['ties'])
                self.assertEqual(self.premiums[row['team']['id']], expected)
        fake = {'groups': [{'teams': [dict(row, wins=17, losses=0, ties=0,
                    ratings={'offense': 90, 'defense': 90})
                    for group in tables['groups'] for row in group['teams']]}]}
        with patch('app.standings.standings_through_week', return_value=fake) as standings:
            next_year = team_market_premiums(2, 1234, (), self.root)
        standings.assert_called_once_with(2, 17, 1234, (), self.root)
        self.assertTrue(all(parts == (0, 0) for parts in next_year.values()))
        self.assertNotEqual(self.premiums, next_year)

    def test_wave_prices_round_once_and_keep_the_minimum_and_legacy_prices(self):
        player = max(self.context.free_agents, key=lambda p: p.rating)
        premiums = {owner: (1000, 1000) for owner in TEAM_BY_ID}
        opened, _ = self.market(premiums=premiums)
        quoted = next(p for p in opened['available'] if p['id'] == player.id)
        self.assertEqual(quoted['annual_salary'], asking_contract(player, self.context, 1,
                         premium_basis_points=2000).annual_salary)
        normal = asking_contract(player, self.context, 4).annual_salary
        self.assertEqual(quoted['annual_salary'], int((normal * 144 + 500_000) // 1_000_000) * 10_000)
        for premium in (0, 1147, 2000):
            prices = [asking_contract(player, self.context, wave, premium_basis_points=premium).annual_salary
                      for wave in range(1, 25)]
            self.assertEqual(prices, sorted(prices, reverse=True))
            self.assertGreaterEqual(prices[-1], minimum_salary(2, 34))
        cheap = replace(player, rating=1)
        self.assertEqual(asking_contract(cheap, self.context, 24, premium_basis_points=2000).annual_salary,
                         minimum_salary(2, 34))
        legacy = replace(self.context, lineup_rules=33)
        self.assertEqual(asking_contract(player, legacy, 1, premium_basis_points=2000),
                         asking_contract(player, legacy, 1))
        result, _ = free_agency('seattle', 1, 1234, legacy, self.order)
        self.assertNotIn('destination_premium', result)
        with self.assertRaisesRegex(ValueError, 'premiums'):
            free_agency('seattle', 1, 1234, self.context, self.order)

    def test_user_and_cpu_sign_their_own_quoted_price_and_replay(self):
        opened, _ = self.market()
        target = next(p for p in opened['available'] if p['affordable'])
        actions = (('sign', target['id']),)
        result, context = self.market(actions)
        self.assertEqual((result, context), self.market(actions))
        self.assertEqual(result['destination_premium'], opened['destination_premium'])
        signed = next(p for p in dict(context)['seattle'] if p.id == target['id'])
        self.assertEqual(signed.contract.annual_salary, target['annual_salary'])
        pool = {p.id: p for p in self.context.free_agents}
        self.assertGreater(len(result['transactions']), 1)
        for transaction in result['transactions']:
            owner = transaction['team']['id']
            expected = asking_contract(pool[transaction['player_id']], self.context, 1,
                                      premium_basis_points=sum(self.premiums[owner]))
            self.assertEqual(transaction['annual_salary'], expected.annual_salary)
            self.assertLessEqual(cap_payroll(dict(context)[owner], context, 2, owner), salary_cap(2, 34))
        first = {p['id']: p['annual_salary'] for p in opened['available']}
        self.assertTrue(all(p['annual_salary'] <= first[p['id']] for p in result['available']))

    def test_cap_checks_use_the_increased_salary(self):
        zero = {owner: (0, 0) for owner in TEAM_BY_ID}
        extra = {owner: (1000, 1000) for owner in TEAM_BY_ID}
        opened, _ = self.market(premiums=zero)
        target = max((p for p in opened['available'] if p['affordable']), key=lambda p: p['annual_salary'])
        rosters = dict(self.context)
        players = list(rosters['seattle'])
        index = next(i for i, p in enumerate(players) if p.contract and p.contract.signed_season + p.contract.years > 2)
        space = salary_cap(2, 34) - cap_payroll(players, self.context, 2, 'seattle')
        extra_salary = space - target['annual_salary'] - 10_000
        self.assertGreaterEqual(extra_salary, 0)
        player = players[index]
        players[index] = replace(player, contract=replace(player.contract,
                                 annual_salary=player.contract.annual_salary + extra_salary))
        rosters['seattle'] = tuple(players)
        tight = replace_lineup_rosters(self.context, tuple(rosters.items()))
        cheap, _ = self.market(context=tight, premiums=zero)
        costly, _ = self.market(context=tight, premiums=extra)
        self.assertTrue(next(p for p in cheap['available'] if p['id'] == target['id'])['affordable'])
        self.assertFalse(next(p for p in costly['available'] if p['id'] == target['id'])['affordable'])
        with self.assertRaisesRegex(ValueError, 'salary cap'):
            self.market((('sign', target['id']),), context=tight, premiums=extra)

    def test_api_premium_survives_roster_decisions_and_saved_action_replay(self):
        req = dict(manual_picks=list(self.choices), action='free_agency', **self.args)
        opened = career_action('seattle', CareerRequest(**req))
        release = next(p for p in opened['profile']['roster'] if p.get('renewal_offer'))
        actions = [dict(kind='drop', player_id=release['id'])]
        updated = career_action('seattle', CareerRequest(free_agency=actions, **req))
        self.assertEqual(updated['free_agency']['destination_premium'], opened['free_agency']['destination_premium'])
        target = next(p for p in updated['free_agency']['available'] if p['affordable'])
        actions.append(dict(kind='sign', player_id=target['id']))
        signed = career_action('seattle', CareerRequest(free_agency=actions, **req))
        self.assertEqual(signed, career_action('seattle', CareerRequest(free_agency=actions, **req)))
        self.assertEqual(signed['free_agency']['destination_premium'], opened['free_agency']['destination_premium'])
        self.assertEqual(next(p for p in signed['profile']['roster'] if p['id'] == target['id'])['contract']['annual_salary'],
                         target['annual_salary'])
