from dataclasses import asdict, replace
from unittest import TestCase
from fastapi import HTTPException

from app.career import cpu_cuts, offseason, replay_career
from app.development import advance_context
from app.draft import build_draft
from app.lineups import lineup_context, replace_lineup_rosters
from app.main import CareerRequest, career_action
from app.player_contracts import BASE_SALARIES, MINIMUM_SALARY, contract_payload, rookie_contract, starting_contract
from app.simulation import roster_for


class PlayerSalaryTests(TestCase):
    def test_starting_salary_scale_and_contract_categories(self):
        source=next(iter(roster_for('seattle',1234).values()))
        for position,base in BASE_SALARIES.items():
            player=replace(source,position=position,rating=75,age=25)
            self.assertEqual(starting_contract(player,1).annual_salary,base)
            self.assertGreater(starting_contract(replace(player,rating=90),1).annual_salary,base)
            self.assertGreaterEqual(starting_contract(replace(player,rating=1),1).annual_salary,MINIMUM_SALARY)
            self.assertEqual(starting_contract(player,1).annual_salary%10_000,0)
        for rating,age,category,years in ((90,23,'franchise',5),(90,35,'franchise',5),(69,35,'low_rated',2),(70,28,'veteran',4),(89,28,'veteran',4),(70,27,'young',3),(89,27,'young',3)):
            deal=starting_contract(replace(source,rating=rating,age=age),1)
            self.assertEqual((deal.category,deal.years),(category,years))

    def test_initial_pay_schedule_is_fixed_without_cap_or_inflation(self):
        player=next(iter(roster_for('seattle',1234).values()))
        self.assertEqual(starting_contract(player,1).annual_salary,starting_contract(player,8).annual_salary)
        self.assertEqual(rookie_contract(1,1,2).annual_salary,5_000_000)
        self.assertEqual(rookie_contract(1,1,8).annual_salary,5_000_000)
        first=career_action('seattle',CareerRequest(action='profile',run_seed=1234,lineup_rules=15,rebuild_team='seattle'))
        self.assertEqual(first['roster'][0]['contract']['annual_salary'],7_170_000)
        self.assertNotIn('salary_cap',first);self.assertNotIn('payroll_floor',first)
        with self.assertRaises(HTTPException):
            career_action('seattle',CareerRequest(action='profile',season=2,run_seed=1234,lineup_rules=15,career=[dict(season=1,lineup_rules=1,draft_rounds=4,manual_picks=['a','b','c','d'])]))

    def test_every_draft_pick_uses_actual_slot_and_exact_terms(self):
        for overall in range(1,181):
            round_number=(overall-1)//30+1
            contract=rookie_contract(round_number,overall,2)
            expected=(5_000_000 if overall==1 else 4_500_000 if overall<=5 else 4_000_000 if overall<=15 else 3_500_000) if round_number==1 else {2:3_000_000,3:2_500_000,4:2_000_000,5:1_500_000,6:1_000_000}[round_number]
            self.assertEqual(contract.annual_salary,expected)
            self.assertEqual(contract.years,4 if round_number==1 else 3 if round_number<=3 else 2)
            self.assertEqual(contract.signed_season,2)
            self.assertEqual(contract.overall_pick,overall)
        for round_number,overall in ((1,31),(2,30),(0,1),(7,181)):
            with self.assertRaises(ValueError):rookie_contract(round_number,overall,2)

    def test_all_starting_teams_have_pay_without_changing_gameplay(self):
        old=lineup_context((),1234,14,rebuild_team='seattle')
        new=lineup_context((),1234,15,rebuild_team='seattle')
        for owner,players in new:
            self.assertEqual(tuple(replace(p,contract=None) for p in players),dict(old)[owner])
            self.assertTrue(all(p.contract is not None and p.contract.annual_salary>=1_000_000 for p in players))
        for rules in (14,15):
            data=career_action('seattle',CareerRequest(action='week',week=17,run_seed=1234,lineup_rules=rules,rebuild_team='seattle'))
            if rules==14:before=data
            else:
                for key in ('record','result','game_results','standings','roster_stats'):self.assertEqual(data[key],before[key])
        legacy=career_action('seattle',CareerRequest(action='profile',run_seed=1234,lineup_rules=14,rebuild_team='seattle'))
        self.assertTrue(all('contract' not in p for p in legacy['roster']))

    def test_fixed_salary_and_original_terms_survive_development_and_expiry(self):
        context=lineup_context((),1234,15,rebuild_team='seattle')
        originals={p.id:p.contract for _,players in context for p in players}
        changed=False
        before={p.id:p.rating for _,players in context for p in players}
        for year in range(2,8):
            context=advance_context(context,1234,year,lineup_rules=15)
            for _,players in context:
                for p in players:
                    self.assertEqual(p.contract,originals[p.id])
                    changed |= p.rating!=before[p.id]
        self.assertTrue(changed)
        self.assertTrue(all(contract_payload(p.contract,7)['status']=='renewal_due' for _,players in context for p in players))
        self.assertEqual(len(originals),sum(len(players) for _,players in context))

    def test_draft_preview_selection_replay_and_upcoming_year_count(self):
        context=lineup_context((),1234,15,rebuild_team='seattle')
        partial,players=build_draft('seattle',1,1234,roster_context=context,draft_rounds=6)
        preview=partial['next_contract']
        self.assertEqual(preview['status'],'upcoming');self.assertEqual(preview['years_remaining'],4)
        self.assertEqual(preview['overall_pick'],partial['next_pick'])
        self.assertTrue(all('contract' not in p for p in partial['available']))
        board,players=build_draft('seattle',1,1234,roster_context=context,auto_pick=True,draft_rounds=6)
        for pick in board['picks']:
            self.assertEqual(pick['player']['contract'],contract_payload(rookie_contract(pick['round'],pick['overall'],2),1))
        self.assertEqual(board['picks'],build_draft('seattle',1,1234,tuple(board['manual_picks']),roster_context=context,draft_rounds=6)[0]['picks'])
        self.assertIsNone(board['next_contract'])
        keep={p.id for p in cpu_cuts(players,35,35)}
        cuts=tuple(p.id for p in players if p.id not in keep)
        _,completed=offseason('seattle',1,1234,tuple(board['manual_picks']),cuts,roster_context=context,draft_rounds=6)
        advanced=advance_context(completed,1234,2,lineup_rules=15)
        contracts={pick['player']['id']:pick['player']['contract'] for pick in board['picks']}
        for _,roster in advanced:
            for p in roster:
                if p.id in contracts:
                    self.assertEqual(p.contract.annual_salary,contracts[p.id]['annual_salary'])
                    self.assertEqual(contract_payload(p.contract,2)['years_remaining'],p.contract.years)

    def test_saved_legacy_draft_recovers_slot_pay_on_upgrade(self):
        old=lineup_context((),1234,14,rebuild_team='seattle')
        board,players=build_draft('seattle',1,1234,roster_context=old,auto_pick=True,draft_rounds=6)
        keep={p.id for p in cpu_cuts(players,35,35)}
        cuts=tuple(p.id for p in players if p.id not in keep)
        step=(1,(),tuple(board['manual_picks']),cuts,14,(),6)
        result=replay_career('seattle',1234,(step,),15,2,1,'seattle')
        expected={pick['player']['id']:rookie_contract(pick['round'],pick['overall'],2) for pick in board['picks']}
        for _,players in result:
            for p in players:
                self.assertIsNotNone(p.contract)
                if p.id in expected:self.assertEqual(p.contract,expected[p.id])
        self.assertEqual(result,replay_career('seattle',1234,(step,),15,2,1,'seattle'))

    def test_replacements_have_one_year_minimum_salary(self):
        context=lineup_context((),1234,15,rebuild_team='seattle')
        aged=replace_lineup_rosters(context,tuple((owner,tuple(replace(p,age=60) for p in players)) for owner,players in context))
        board,rosters=build_draft('seattle',1,1234,roster_context=aged,auto_pick=True,draft_rounds=6,return_league=True)
        self.assertEqual(len(board['replacements']),29)
        for replacement in board['replacements']:
            self.assertEqual(replacement['contract']['annual_salary'],1_000_000)
            self.assertEqual(replacement['contract']['years'],1)
            self.assertEqual(replacement['contract']['signed_season'],2)
        for players in rosters.values():self.assertTrue(all(p.contract is not None for p in players))
