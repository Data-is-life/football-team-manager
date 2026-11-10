"""Versioned CPU decisions value participating depth and preserve cap guarantees."""
from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch
from app.lineups import lineup_context
from app.player_contracts import (cpu_contract_priorities, cap_ready,
                                  smart_cpu_offseason, smart_cpu_roster_cuts)
from app.career import replay_career, offseason
import test_re_signing as fixtures


class CpuContractStrategyTests(TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.ReSigningTests.setUpClass.__func__(cls)

    def test_role_value_when_rating_and_salary_are_equal(self):
        context = lineup_context((), 1234, 28, rebuild_team='seattle')
        roster = dict(context)['seattle']
        selected = []
        for position, count in (('QB',2),('WR',4),('CB',4)):
            group = sorted((p for p in roster if p.position == position),key=lambda p:p.id)
            selected.extend(replace(p,rating=80,
                contract=replace(p.contract,annual_salary=5_000_000))
                for p in group[:count])
        scores = cpu_contract_priorities(selected,context,1)
        qb = sorted((p for p in selected if p.position=='QB'),key=lambda p:p.id)
        wr = sorted((p for p in selected if p.position=='WR'),key=lambda p:p.id)
        cb = sorted((p for p in selected if p.position=='CB'),key=lambda p:p.id)
        self.assertGreater(scores[qb[0].id],scores[qb[1].id])
        self.assertGreater(scores[wr[2].id],scores[qb[1].id])
        self.assertGreater(scores[cb[2].id],scores[qb[1].id])

    def test_priority_scoring_ignores_input_order_and_does_not_mutate_players(self):
        context = lineup_context((), 1234, 28, rebuild_team='seattle')
        roster = dict(context)['seattle']
        original = tuple(roster)
        forward = cpu_contract_priorities(roster, context, 1)
        backward = cpu_contract_priorities(tuple(reversed(roster)), context, 1)
        self.assertEqual(forward, backward)
        self.assertEqual(tuple(roster), original)
        self.assertEqual(set(forward), {player.id for player in roster})

    def test_cpu_offseason_fits_cap_and_replays_deterministically(self):
        current = replay_career('seattle',1234,(self.step,),28,2,1,'seattle')
        _,context = offseason('seattle',2,1234,self.choices,(),(),current,6,())
        for owner,players in context:
            if owner!='seattle':
                self.assertTrue(cap_ready(players,context,owner=owner))
        _,again = offseason('seattle',2,1234,self.choices,(),(),current,6,())
        self.assertEqual(context,again)

    def test_reused_priorities_preserve_full_offseason_and_score_once(self):
        # Exercise oversized rosters and expired renewals, including cap relief.
        # The comparison deliberately restores the old second scoring pass.
        def recomputing_cuts(players, context, year, *, priorities=None):
            return smart_cpu_roster_cuts(players, context, year)

        for seed in (1234, 5678):
            context = lineup_context((), seed, 28, rebuild_team='seattle')
            for owner in ('seattle', 'chicago'):
                with self.subTest(seed=seed, owner=owner):
                    players = [replace(p, contract=replace(p.contract, years=1))
                               for p in dict(context)[owner]]
                    players.extend(replace(p, id=f'{p.id}-surplus')
                                   for p in players[:6])
                    before = tuple(players)
                    with patch('app.player_contracts.cpu_contract_priorities',
                               wraps=cpu_contract_priorities) as score:
                        actual = smart_cpu_offseason(players, owner, 1, seed, context)
                    self.assertEqual(score.call_count, 1)
                    with patch('app.player_contracts.smart_cpu_roster_cuts',
                               side_effect=recomputing_cuts):
                        expected = smart_cpu_offseason(players, owner, 1, seed, context)
                    self.assertEqual(actual, expected)
                    self.assertEqual(tuple(players), before)
                    self.assertTrue(cap_ready(actual[0], actual[1], 2, owner))
