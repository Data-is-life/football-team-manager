"""Unsigned asks must not reserve cap room or create guaranteed obligations."""
from dataclasses import replace
import json
from unittest import TestCase
from unittest.mock import patch

from app.lineups import lineup_context, replace_lineup_rosters
from app.player_contracts import (
    DeadCapCharge, PlayerContract, cap_payroll, cap_ready,
    contract_potential, payroll_payload, payroll_breakdown, public_player_fields,
    record_release, renew_player, salary_cap, veteran_contract,
)
from app.preseason import floor_payroll
from app.simple_offseason import _own_phase


class UnsignedBudgetTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = lineup_context((), 1234, 45, rebuild_team='seattle')

    def context(self, room=6_000_000):
        players = dict(self.root)['seattle'][:4]
        cap = salary_cap(2, 45, run_seed=1234)
        roster = (
            replace(players[0], contract=PlayerContract(cap-room-2_000_000, 2, 3, 'veteran'), rookie_offer=None),
            replace(players[1], contract=PlayerContract(cap, 1, 1, 'veteran'), rookie_offer=None),
            replace(players[2], contract=None, rookie_offer=PlayerContract(5_000_000, 2, 4, 'rookie', 1, 1)),
            replace(players[3], contract=None, rookie_offer=PlayerContract(cap, 2, 4, 'rookie', 1, 2)),
        )
        charge = DeadCapCharge('seattle', 'prior-cut', 'Prior Cut', 2_000_000, 2, 3, 1)
        context = replace(self.root, season=2, dead_cap=(charge,))
        context = replace_lineup_rosters(context, tuple(
            (owner, roster if owner=='seattle' else ps) for owner, ps in context))
        return context, roster

    def test_cap_and_breakdown_count_only_signed_salary_and_dead_cap(self):
        context, players = self.context()
        pay = payroll_payload(players, context, owner='seattle')['payroll']
        self.assertEqual(pay['total'], players[0].contract.annual_salary+2_000_000)
        self.assertEqual(pay['committed'], players[0].contract.annual_salary)
        self.assertEqual((pay['rookie_holds'], pay['expired_holds']), (0, 0))
        self.assertEqual(pay['cap_space'], 6_000_000)
        self.assertTrue(cap_ready(players, context, owner='seattle'))
        self.assertFalse(cap_ready(players, replace(context,lineup_rules=44), owner='seattle'))
        detail = payroll_breakdown(players, context, owner='seattle')['payroll_breakdown']
        self.assertEqual([g['kind'] for g in detail['categories']], ['signed','dead_cap'])
        self.assertEqual(sum(g['total'] for g in detail['categories']), pay['total'])
        self.assertEqual(detail['floor_payroll'], players[0].contract.annual_salary)
        self.assertEqual(floor_payroll(players,context), detail['floor_payroll'])

    def test_one_rookie_can_sign_without_reserving_other_unsigned_offers(self):
        context, players = self.context()
        with patch('app.simple_offseason.prepare', return_value=(json.dumps({}),context)):
            _, signed, _ = _own_phase.__wrapped__('seattle',1,1234,(),(),context,6,
                                                (('sign',players[2].id),))
            retained = dict(signed)['seattle']
            self.assertIsNotNone(next(p for p in retained if p.id==players[2].id).contract)
            self.assertIsNotNone(next(p for p in retained if p.id==players[3].id).rookie_offer)
            self.assertEqual(cap_payroll(retained,signed,owner='seattle'),
                             cap_payroll(players,context,owner='seattle')+5_000_000)
            with self.assertRaisesRegex(ValueError,'exceed the salary cap'):
                _own_phase.__wrapped__('seattle',1,1234,(),(),context,6,
                                       (('sign',players[2].id),('sign',players[3].id)))

    def test_renewal_preview_and_acceptance_use_the_same_real_cap_room(self):
        context, players = self.context()
        target = players[1]
        deal = veteran_contract(target,2,45,contract_potential(target,context),
                                 run_seed=1234,context=context)
        context, players = self.context(room=deal.annual_salary)
        target = players[1]
        offer = public_player_fields(target,context)['renewal_offer']
        self.assertTrue(offer['affordable'])
        signed = renew_player(players,target.id,2,45,context,'seattle')
        self.assertEqual(cap_payroll(signed,context,owner='seattle'),salary_cap(2,45,run_seed=1234))
        tight, players = self.context(room=deal.annual_salary-1)
        self.assertFalse(public_player_fields(players[1],tight)['renewal_offer']['affordable'])
        with self.assertRaisesRegex(ValueError,'exceed the salary cap'):
            renew_player(players,players[1].id,2,45,tight,'seattle')

    def test_releasing_a_signed_player_keeps_its_guarantee_as_dead_cap(self):
        context, players = self.context()
        charged = record_release(context,'seattle',players[0],2)
        self.assertEqual(cap_payroll(players[1:],charged,owner='seattle'),
                         cap_payroll(players,context,owner='seattle'))
        self.assertEqual(record_release(context,'seattle',players[2],2),context)
        self.assertEqual(record_release(context,'seattle',players[1],2),context)

    def test_three_completed_offseasons_keep_cpu_and_user_budgets_valid(self):
        from app.main import CareerRequest, career_action
        from app.career import replay_career
        from app.player_contracts import payroll_floor
        from app.simulation import validate_roster, roster_minimum, roster_limit
        history = []

        def call(args, action, **extra):
            return career_action('seattle',CareerRequest(action=action,**args,**extra))

        for season in range(1,4):
            args = dict(season=season,run_seed=1234,lineup_rules=45,
                        rebuild_team='seattle',draft_rounds=6,career=list(history))
            draft = call(args,'draft',auto_draft=True)
            args['manual_picks'] = draft['manual_picks']
            own = call(args,'own_players')
            actions = []
            for player in own['profile']['roster']:
                if player.get('renewal_offer'):
                    kind = 'drop'
                elif player.get('contract_offer'):
                    kind = ('sign' if player['contract_offer']['annual_salary']
                            <=own['profile']['payroll']['cap_space'] else 'drop')
                else:
                    continue
                actions.append(dict(kind=kind,player_id=player['id']))
                own = call(args,'own_players',own_actions=list(actions))
                pay = own['profile']['payroll']
                self.assertEqual(pay['total'],pay['committed']+pay['dead_cap'])
            actions.append(dict(kind='finish'))
            args['own_actions'] = actions
            market = call(args,'free_agency',free_agency=[dict(kind='finish')])
            plan = market['payroll_floor_adjustment']
            review = [dict(kind='raise',player_id=plan['player_id'])] if plan else []
            args.update(free_agency=[dict(kind='finish')],pre_camp_actions=review,
                        trade_actions=[dict(kind='finish')])
            done = call(args,'trades')
            self.assertTrue(done['can_continue'])
            step = {key:value for key,value in args.items() if key!='career' and key not in ('run_seed','rebuild_team')}
            history.append(step)
            next_args = dict(season=season+1,run_seed=1234,lineup_rules=45,
                             rebuild_team='seattle',career=list(history))
            profile = call(next_args,'profile')
            steps = tuple((s['season'],(),tuple(s['manual_picks']),(),45,(),6,(),
                           (('finish',''),),tuple((a['kind'],a['player_id']) for a in s['pre_camp_actions']),
                           (), (('finish','','',''),), tuple((a['kind'],a.get('player_id','')) for a in s['own_actions']))
                          for s in history)
            context = replay_career('seattle',1234,steps,45,season+1,1,'seattle')
            for owner,players in context:
                with self.subTest(season=season,team=owner):
                    self.assertFalse(any(p.rookie_offer for p in players))
                    self.assertLessEqual(cap_payroll(players,context,owner=owner),salary_cap(season+1,45,run_seed=1234))
                    self.assertGreaterEqual(floor_payroll(players,context),payroll_floor(season+1,45,run_seed=1234))
                    validate_roster(players,minimum_total=roster_minimum(context),
                                    maximum_total=roster_limit(context),context=context,owner=owner)
            replay_career.cache_clear()
            self.assertEqual(call(next_args,'profile'),profile)
