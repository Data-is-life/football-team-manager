from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch
from fastapi import HTTPException

from app.career import offseason, replay_career
from app.draft import build_draft
from app.lineups import lineup_context, replace_lineup_rosters
from app.main import CareerRequest, career_action, profile_payload
from app.player_contracts import (SALARY_CAP, PAYROLL_FLOOR, payroll, payroll_payload,
                                 cap_ready, cap_release, cpu_cap_cuts)
from app.simulation import validate_roster


class SalaryCapTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = lineup_context((),1234,16,rebuild_team='seattle')

    def expensive(self):
        return replace_lineup_rosters(self.context,tuple((owner,tuple(
            replace(p,contract=replace(p.contract,annual_salary=8_000_000)) for p in players))
            for owner,players in self.context))

    def test_exact_boundaries_floor_warning_and_fixed_future_limits(self):
        players = dict(self.context)['seattle']
        for total,over,below in [(200_000_000,0,0),(200_000_001,1,0),(160_000_000,0,0),(159_999_999,0,1)]:
            base = [replace(p,contract=replace(p.contract,annual_salary=1_000_000)) for p in players]
            base[0] = replace(base[0],contract=replace(base[0].contract,annual_salary=total-34_000_000))
            pay=payroll_payload(base,self.context)['payroll']
            self.assertEqual((pay['total'],pay['cap'],pay['floor']),(total,200_000_000,160_000_000))
            self.assertEqual((pay['over_cap'],pay['below_floor']),(over,below))
            self.assertEqual(cap_ready(base,self.context),not over)
            self.assertFalse(pay['floor_enforced'])
            self.assertEqual(payroll_payload(base,replace(self.context,season=7))['payroll'],pay)
        self.assertEqual(payroll_payload(players,replace(self.context,lineup_rules=15)),{})
        self.assertTrue(cap_ready(players,replace(self.context,lineup_rules=15)))

    def test_all_retained_contracts_count_even_expired_without_repricing(self):
        context=replace(self.context,season=9)
        players=dict(context)['seattle']
        profile=profile_payload('seattle',players,1234,context)
        self.assertTrue(all(p['contract']['status']=='renewal_due' for p in profile['roster']))
        self.assertEqual(profile['payroll']['total'],sum(p.contract.annual_salary for p in players))
        self.assertEqual([p.contract for p in players],[p.contract for p in dict(self.context)['seattle']])

    def test_cap_cuts_atomically_preserve_total_and_position_minimums(self):
        context=self.expensive();players=dict(context)['seattle']
        # A lone kicker normally cannot be cut. Over-cap release replaces it atomically.
        kicker=next(p for p in players if p.position=='K')
        result=cap_release(players,kicker.id,'seattle',1,1234,context,[kicker.id])
        validate_roster(result,minimum_total=35,maximum_total=38)
        self.assertEqual(len(result),35)
        replacement=next(p for p in result if p.position=='K')
        self.assertNotEqual(replacement.id,kicker.id)
        self.assertEqual(replacement.contract.annual_salary,1_000_000)
        self.assertEqual(payroll(players)-payroll(result),7_000_000)
        self.assertLessEqual(replacement.rating,55)
        for p in result:
            if p.id in {old.id for old in players}:self.assertEqual(p.contract,next(old.contract for old in players if old.id==p.id))

    def test_all_cpu_rosters_fit_deterministically_without_floor_topups(self):
        context=self.expensive()
        for owner,players in context:
            result=cpu_cap_cuts(players,owner,1,1234,context)
            self.assertLessEqual(payroll(result),SALARY_CAP)
            validate_roster(result,minimum_total=35,maximum_total=38)
            self.assertEqual(result,cpu_cap_cuts(players,owner,1,1234,context))
        players=dict(self.context)['seattle']
        self.assertLess(payroll(players),PAYROLL_FLOOR)
        self.assertEqual(cpu_cap_cuts(players,'seattle',1,1234,self.context),list(players))

    def test_draft_can_exceed_cap_and_api_blocks_continuation_until_legal(self):
        context=self.expensive()
        with patch('app.main.replay_career',return_value=context):
            request=dict(season=1,run_seed=1234,lineup_rules=16,rebuild_team='seattle',draft_rounds=6)
            board=career_action('seattle',CareerRequest(action='draft',auto_draft=True,**request))
            self.assertTrue(board['complete']);self.assertGreater(board['profile']['payroll']['over_cap'],0)
            choices=board['manual_picks'];dropped=[]
            data=career_action('seattle',CareerRequest(action='cuts',manual_picks=choices,**request))
            self.assertFalse(data['can_continue'])
            while not data['can_continue']:
                players=data['profile']['roster']
                if data['profile']['payroll']['over_cap']:
                    player=max(players,key=lambda p:p['contract']['annual_salary'])
                else:
                    counts={r['position']:(r['count'],r['minimum']) for r in data['profile']['roster_rules']}
                    player=min((p for p in players if counts[p['position']][0]>counts[p['position']][1]),key=lambda p:p['rating'])
                dropped.append(player['id'])
                data=career_action('seattle',CareerRequest(action='cuts',manual_picks=choices,dropped=dropped,**request))
                self.assertLess(len(dropped),44)
            self.assertLessEqual(data['profile']['payroll']['total'],SALARY_CAP)
            self.assertTrue(35<=len(data['profile']['roster'])<=38)
            # Replaying the exact transaction yields the exact profile and cap.
            self.assertEqual(data,career_action('seattle',CareerRequest(action='cuts',manual_picks=choices,dropped=dropped,**request)))
            with self.assertRaises(HTTPException):
                career_action('seattle',CareerRequest(action='cuts',manual_picks=choices,dropped=[dropped[0],dropped[0]],**request))

    def test_saved_history_cannot_advance_with_over_cap_rules16_roster(self):
        context=self.expensive()
        # Exercise server-side finalization, independent of the frontend button.
        with patch('app.career.lineup_context',return_value=context),patch('app.career.offseason',return_value=({'picks':[],'draft_season':2},context)):
            with self.assertRaisesRegex(ValueError,'cap space'):
                replay_career.__wrapped__('seattle',1234,((1,(),('a','b','c','d'),(),16,(),4),),16,2,1,'seattle')

    def test_rule15_career_upgrades_without_changing_roster_or_played_games(self):
        legacy=lineup_context((),1234,15,rebuild_team='seattle')
        self.assertEqual(tuple(legacy),tuple(self.context))
        old=career_action('seattle',CareerRequest(action='week',week=17,run_seed=1234,lineup_rules=15,rebuild_team='seattle'))
        new=career_action('seattle',CareerRequest(action='week',week=17,run_seed=1234,lineup_rules=16,rebuild_team='seattle'))
        self.assertEqual(old,new)
        # Completed pre-cap offseasons remain valid and get accounting, not retroactive cuts.
        board,players=build_draft('seattle',1,1234,roster_context=legacy,auto_pick=True,draft_rounds=6)
        from app.career import cpu_cuts
        keep={p.id for p in cpu_cuts(players,38,35)}
        dropped=tuple(p.id for p in players if p.id not in keep)
        step=(1,(),tuple(board['manual_picks']),dropped,15,(),6)
        advanced=replay_career('seattle',1234,(step,),16,2,1,'seattle')
        before=replay_career('seattle',1234,(step,),15,2,1,'seattle')
        self.assertEqual(tuple(advanced),tuple(before))
        self.assertIn('payroll',profile_payload('seattle',dict(advanced)['seattle'],1234,advanced))
