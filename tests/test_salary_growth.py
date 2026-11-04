from dataclasses import replace
from decimal import Decimal, ROUND_HALF_UP, localcontext
from unittest import TestCase
from unittest.mock import patch

from app.career import cpu_cuts, replay_career
from app.development import advance_context
from app.draft import build_draft
from app.lineups import lineup_context, replace_lineup_rosters
from app.main import CareerRequest, career_action
from app.player_contracts import (annual_amount, minimum_salary, salary_cap, payroll_floor,
    rookie_contract, starting_contract, payroll, payroll_payload, cap_ready, cap_release, cpu_cap_cuts)
from app.simulation import validate_roster


class SalaryGrowthTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context=lineup_context((),1234,17,rebuild_team='seattle')

    def test_exact_annual_sequences_and_half_up_salary_ties(self):
        self.assertEqual([salary_cap(s,17) for s in range(1,7)],[200_000_000,210_000_000,221_000_000,232_000_000,244_000_000,256_000_000])
        self.assertEqual([payroll_floor(s,17) for s in range(1,7)],[160_000_000,168_000_000,177_000_000,186_000_000,195_000_000,205_000_000])
        self.assertEqual([minimum_salary(s,17) for s in range(1,7)],[1_000_000,1_050_000,1_100_000,1_160_000,1_220_000,1_280_000])
        self.assertEqual(rookie_contract(1,2,2,17).annual_salary,4_730_000) # 4.725 -> 4.73
        self.assertEqual(rookie_contract(1,16,2,17).annual_salary,3_680_000) # 3.675 -> 3.68
        # Independently verify long careers using Decimal, including beyond float-safe dollars.
        with localcontext() as ctx:
            ctx.prec=60
            for base,unit in [(200_000_000,1_000_000),(1_000_000,10_000),(4_500_000,10_000)]:
                amount=Decimal(base)
                for season in range(1,1000):
                    if season>1:amount=(amount*Decimal('1.05')/unit).quantize(Decimal(1),rounding=ROUND_HALF_UP)*unit
                    self.assertEqual(annual_amount(base,season,unit),int(amount))
        for invalid in (0,-1,1.5,True):
            with self.assertRaises(ValueError):annual_amount(1_000_000,invalid,10_000)

    def test_all_180_actual_slots_inflate_by_signing_year_without_changing_terms(self):
        for season in (1,2,4,8):
            for overall in range(1,181):
                round_number=(overall-1)//30+1
                original=rookie_contract(round_number,overall,season,16)
                new=rookie_contract(round_number,overall,season,17)
                self.assertEqual(new.annual_salary,annual_amount(original.annual_salary,season,10_000))
                self.assertEqual(replace(new,annual_salary=original.annual_salary),original)
                self.assertGreaterEqual(new.annual_salary,minimum_salary(season,17))
        self.assertEqual(rookie_contract(1,1,2,17).annual_salary,5_250_000)

    def test_signed_deals_are_fixed_and_older_pay_schedules_stay_fixed(self):
        old=lineup_context((),1234,16,rebuild_team='seattle')
        self.assertEqual(tuple(old),tuple(self.context))
        originals={p.id:p.contract for _,players in old for p in players}
        advanced=advance_context(old,1234,5,lineup_rules=17)
        for _,players in advanced:
            for p in players:self.assertEqual(p.contract,originals[p.id])
        self.assertTrue(any(p.contract.annual_salary<minimum_salary(5,17) for _,players in advanced for p in players))
        for season in (2,5,9):
            self.assertEqual(salary_cap(season,16),200_000_000)
            self.assertEqual(payroll_floor(season,16),160_000_000)
            self.assertEqual(minimum_salary(season,16),1_000_000)
            self.assertEqual(rookie_contract(1,1,season,16).annual_salary,5_000_000)

    def test_replacement_uses_its_signing_season_and_new_minimum_only(self):
        players=dict(self.context)['seattle'];kicker=next(p for p in players if p.position=='K')
        remaining=cap_release(players,kicker.id,'seattle',3,1234,self.context,[kicker.id])
        replacement=next(p for p in remaining if p.position=='K')
        self.assertEqual(replacement.contract.annual_salary,1_160_000)
        self.assertEqual((replacement.contract.signed_season,replacement.contract.years),(4,1))
        for p in remaining:
            if p.id!=replacement.id:self.assertEqual(p.contract,next(old.contract for old in players if old.id==p.id))
        legacy=starting_contract(replacement,4,16)
        self.assertEqual(legacy.annual_salary,1_000_000)
        # Reconstructing a replacement later still uses the original signing year.
        self.assertEqual(starting_contract(replacement,9,17),replacement.contract)

    def test_draft_previews_and_both_api_paths_use_next_season_budget(self):
        request=dict(run_seed=1234,lineup_rules=17,rebuild_team='seattle',draft_rounds=6)
        partial=career_action('seattle',CareerRequest(action='draft',**request))
        pay=partial['profile']['payroll']
        self.assertEqual((pay['season'],pay['cap'],pay['floor'],pay['minimum_salary']),(2,210_000_000,168_000_000,1_050_000))
        self.assertEqual(partial['next_contract']['annual_salary'],rookie_contract(1,partial['next_pick'],2,17).annual_salary)
        board=career_action('seattle',CareerRequest(action='draft',auto_draft=True,**request))
        for pick in board['picks']:
            self.assertEqual(pick['player']['contract']['annual_salary'],rookie_contract(pick['round'],pick['overall'],2,17).annual_salary)
        from app.main import rookie_draft, DraftRequest
        standalone=rookie_draft('seattle',DraftRequest(**request))
        self.assertEqual(standalone['profile']['payroll'],partial['profile']['payroll'])
        self.assertEqual(standalone['next_contract'],partial['next_contract'])
        active=career_action('seattle',CareerRequest(action='profile',**request))
        self.assertEqual((active['payroll']['season'],active['payroll']['cap']),(1,200_000_000))

    def test_next_year_cap_applies_to_cut_gate_cpu_and_history_not_current_cap(self):
        # An exactly $210M roster is over this year's $200M, but legal for next year.
        context=replace_lineup_rosters(self.context,tuple((owner,tuple(replace(p,contract=replace(p.contract,annual_salary=6_000_000)) for p in players)) for owner,players in self.context))
        players=dict(context)['seattle']
        self.assertFalse(cap_ready(players,context));self.assertTrue(cap_ready(players,context,2))
        self.assertEqual(cpu_cap_cuts(players,'seattle',1,1234,context),list(players))
        with patch('app.career.lineup_context',return_value=context),patch('app.career.offseason',return_value=({'picks':[],'draft_season':2},context)):
            result=replay_career.__wrapped__('seattle',1234,((1,(),('a','b','c','d'),(),17,(),4),),17,2,1,'seattle')
            self.assertEqual(tuple(result),tuple(context))
        # One dollar over the upcoming cap still fails independent of frontend state.
        expensive=replace(players[0],contract=replace(players[0].contract,annual_salary=6_000_001))
        rosters=dict(context);rosters['seattle']=(expensive,*players[1:])
        over=replace_lineup_rosters(context,tuple(rosters.items()))
        self.assertFalse(cap_ready(dict(over)['seattle'],over,2))
        with patch('app.career.lineup_context',return_value=over),patch('app.career.offseason',return_value=({'picks':[],'draft_season':2},over)):
            with self.assertRaisesRegex(ValueError,'cap space'):
                replay_career.__wrapped__('seattle',1234,((1,(),('a','b','c','d'),(),17,(),4),),17,2,1,'seattle')

    def test_cpu_cap_releases_sign_replacements_at_upcoming_minimum(self):
        context=replace(self.context,season=3)
        players=[replace(p,contract=replace(p.contract,annual_salary=8_000_000)) for p in dict(context)['seattle']]
        result=cpu_cap_cuts(players,'seattle',3,1234,context)
        validate_roster(result,minimum_total=35,maximum_total=38)
        self.assertLessEqual(payroll(result),232_000_000)
        replacements=[p for p in result if p.id.startswith('replacement-')]
        self.assertTrue(replacements)
        self.assertTrue(all(p.contract.annual_salary==1_160_000 and p.contract.signed_season==4 for p in replacements))
        self.assertEqual(result,cpu_cap_cuts(players,'seattle',3,1234,context))

    def test_real_rollover_replay_preserves_old_salaries_and_inflated_rookie_deals(self):
        board,players=build_draft('seattle',1,1234,roster_context=self.context,auto_pick=True,draft_rounds=6)
        keep={p.id for p in cpu_cuts(players,38,35)}
        cuts=tuple(p.id for p in players if p.id not in keep)
        step=(1,(),tuple(board['manual_picks']),cuts,17,(),6)
        context=replay_career('seattle',1234,(step,),17,2,1,'seattle')
        expected={p.id:p.contract for _,roster in self.context for p in roster}
        expected.update({pick['player']['id']:rookie_contract(pick['round'],pick['overall'],2,17) for pick in board['picks']})
        for owner,roster in context:
            validate_roster(roster,minimum_total=35,maximum_total=38)
            self.assertLessEqual(payroll(roster),210_000_000)
            for p in roster:
                if p.id in expected:self.assertEqual(p.contract,expected[p.id])
        self.assertEqual(context,replay_career('seattle',1234,(step,),17,2,1,'seattle'))
        # A legacy draft remains on its old salary scale after adopting growth rules.
        legacy=replace(self.context,lineup_rules=16)
        old_board,old_players=build_draft('seattle',1,1234,roster_context=legacy,auto_pick=True,draft_rounds=6)
        keep={p.id for p in cpu_cuts(old_players,38,35)}
        old_step=(1,(),tuple(old_board['manual_picks']),tuple(p.id for p in old_players if p.id not in keep),16,(),6)
        upgraded=replay_career('seattle',1234,(old_step,),17,2,1,'seattle')
        legacy_deals={pick['player']['id']:rookie_contract(pick['round'],pick['overall'],2,16) for pick in old_board['picks']}
        for _,roster in upgraded:
            for p in roster:
                if p.id in legacy_deals:self.assertEqual(p.contract,legacy_deals[p.id])
        self.assertEqual(payroll_payload(dict(upgraded)['seattle'],upgraded)['payroll']['cap'],210_000_000)
