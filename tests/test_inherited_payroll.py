from dataclasses import replace
from collections import Counter
from unittest import TestCase
from app.lineups import lineup_context
from app.simulation import team_ratings,simulate_through_week,validate_roster
from app.player_contracts import (payroll,payroll_floor,salary_cap,minimum_salary,inherited_payroll,
    rookie_contract,cap_ready)
from app.main import career_action,CareerRequest
from app.career import replay_career


class InheritedPayrollTests(TestCase):
    def test_seeded_floor_to_cap_payroll_and_three_bad_guaranteed_deals(self):
        totals=set();bad_ids=set()
        for seed in (0,1,1234,5678,4294967295):
            for owner in ('seattle','miami','dallas','las-vegas'):
                context=lineup_context((),seed,25,rebuild_team=owner)
                players=dict(context)[owner];amount=payroll(players)
                self.assertEqual(len(players),35);validate_roster(players,minimum_total=31,maximum_total=38)
                self.assertTrue(160_000_000<=amount<=200_000_000)
                self.assertEqual(amount%1_000_000,0);totals.add(amount)
                self.assertTrue(all(p.contract.annual_salary>=minimum_salary(1,25) and p.contract.annual_salary%10_000==0 for p in players))
                bad=[p for p in players if p.contract.category=='inherited_bad']
                self.assertEqual(len(bad),3);self.assertTrue(all(p.rating<70 for p in bad))
                self.assertTrue(all(p.contract.years in (3,4) for p in bad))
                self.assertTrue(all(p.contract.annual_salary>=7_000_000 for p in bad))
                self.assertEqual(sum(p.position=='QB' for p in bad),1)
                bad_ids.add(tuple(sorted(p.id for p in bad)))
        self.assertGreater(len(totals),10);self.assertGreater(len(bad_ids),4)

    def test_only_finances_of_the_selected_initial_team_change(self):
        old=lineup_context((),1234,24,rebuild_team='seattle')
        new=lineup_context((),1234,25,rebuild_team='seattle')
        for owner,players in new:
            if owner!='seattle':self.assertEqual(players,dict(old)[owner])
            else:
                self.assertEqual(tuple(replace(p,contract=None) for p in players),tuple(replace(p,contract=None) for p in dict(old)[owner]))
            self.assertEqual(team_ratings(owner,1234,new),team_ratings(owner,1234,old))
        for rules in (24,25):
            context=old if rules==24 else new
            data=simulate_through_week('seattle',1,16,1234,roster_context=context)
            self.assertEqual(data['record'],dict(wins=3,losses=13,ties=0))
        a=simulate_through_week('seattle',1,17,1234,roster_context=old)
        b=simulate_through_week('seattle',1,17,1234,roster_context=new)
        for key in ('record','game_results','roster_stats','result','standings'):self.assertEqual(a[key],b[key])

    def test_existing_context_is_never_repriced_on_upgrade_or_advance(self):
        old=lineup_context((),1234,24,rebuild_team='seattle')
        adopted=lineup_context(old,1234,25,1,1,'seattle')
        self.assertEqual(old.rosters,adopted.rosters)
        future=lineup_context(adopted,1234,25,2,1,'seattle')
        self.assertEqual({p.id:p.contract for p in dict(old)['seattle']},{p.id:p.contract for p in dict(future)['seattle']})
        new=lineup_context((),1234,25,rebuild_team='seattle')
        self.assertEqual(new.rosters,inherited_payroll(new.rosters,'seattle',1234,1))
        same=lineup_context(new,1234,25,1,1,'seattle')
        self.assertEqual(same,new)
        future=lineup_context(new,1234,25,2,1,'seattle')
        self.assertEqual({p.id:p.contract for p in dict(new)['seattle']},{p.id:p.contract for p in dict(future)['seattle']})
        for overall in range(1,181):self.assertEqual(rookie_contract((overall-1)//30+1,overall,2,25),rookie_contract((overall-1)//30+1,overall,2,24))

    def test_allocator_uses_the_given_seasons_floor_cap_and_minimum(self):
        base=lineup_context((),1234,24,rebuild_team='seattle')
        for season in (1,2,4,10):
            roster=inherited_payroll(base.rosters,'seattle',5678,season)
            amount=payroll(dict(roster)['seattle'])
            self.assertTrue(payroll_floor(season,25)<=amount<=salary_cap(season,25))
            self.assertTrue(all(p.contract.annual_salary>=minimum_salary(season,25) for p in dict(roster)['seattle']))
            self.assertEqual(roster,inherited_payroll(base.rosters,'seattle',5678,season))

    def test_first_offseason_is_playable_and_releasing_bad_deal_keeps_dead_cap(self):
        req=dict(season=1,run_seed=1234,lineup_rules=25,rebuild_team='seattle',draft_rounds=6)
        initial=career_action('seattle',CareerRequest(action='profile',**req))
        self.assertEqual(initial['payroll']['dead_cap'],0)
        self.assertEqual(initial['payroll']['below_floor'],0)
        board=career_action('seattle',CareerRequest(action='draft',auto_draft=True,**req))
        req.update(manual_picks=board['manual_picks'],training_camp=True)
        data=career_action('seattle',CareerRequest(action='camp',**req))
        bad=next(p for p in data['profile']['roster'] if p.get('contract',{}).get('category')=='inherited_bad' and p['position']=='QB')
        actions=[dict(kind='drop',player_id=bad['id'])];cuts=[bad['id']]
        data=career_action('seattle',CareerRequest(action='cuts',dropped=cuts,roster_actions=actions,**req))
        self.assertEqual(data['profile']['payroll']['dead_cap'],bad['contract']['annual_salary'])
        for _ in range(12):
            if data['can_continue']:break
            players=data['profile']['roster'];counts=Counter(p['position'] for p in players)
            if data['profile']['payroll']['over_cap']:
                candidate=max((p for p in players if p.get('contract_offer')),key=lambda p:p['contract_offer']['annual_salary'])
            else:
                from app.simulation import EXPANDED_ROSTER_RULES
                candidate=next(p for p in players if counts[p['position']]>EXPANDED_ROSTER_RULES[p['position']][1])
            cuts.append(candidate['id']);actions.append(dict(kind='drop',player_id=candidate['id']))
            data=career_action('seattle',CareerRequest(action='cuts',dropped=cuts,roster_actions=actions,**req))
        self.assertTrue(data['can_continue'])
        step=(1,(),tuple(board['manual_picks']),tuple(cuts),25,(),6,tuple((a['kind'],a['player_id']) for a in actions))
        context=replay_career('seattle',1234,(step,),25,2,1,'seattle')
        self.assertTrue(cap_ready(dict(context)['seattle'],context,owner='seattle'))
        self.assertEqual(context,replay_career('seattle',1234,(step,),25,2,1,'seattle'))

    def test_historical_origin_keeps_old_contract_book_after_api_rollover(self):
        args=dict(run_seed=1234,lineup_rules=24,rebuild_team='seattle',draft_rounds=6)
        draft=career_action('seattle',CareerRequest(action='draft',auto_draft=True,**args))
        data=career_action('seattle',CareerRequest(action='camp',manual_picks=draft['manual_picks'],**args))
        cuts=[];actions=[]
        while len(data['profile']['roster'])>38:
            candidate=next(p for p in data['profile']['roster'] if p.get('contract_offer'))
            cuts.append(candidate['id']);actions.append(dict(kind='drop',player_id=candidate['id']))
            data=career_action('seattle',CareerRequest(action='cuts',manual_picks=draft['manual_picks'],training_camp=True,dropped=cuts,roster_actions=actions,**args))
        past=dict(season=1,lineup_rules=24,draft_rounds=6,manual_picks=draft['manual_picks'],dropped=cuts,roster_actions=actions)
        old=career_action('seattle',CareerRequest(action='profile',season=2,career=[past],**args))
        new=career_action('seattle',CareerRequest(action='profile',season=2,career=[past],**{**args,'lineup_rules':25}))
        self.assertEqual(old['payroll'],new['payroll'])
        self.assertEqual([p['contract'] for p in old['roster']],[p['contract'] for p in new['roster']])
        self.assertFalse(any(p['contract']['category']=='inherited_bad' for p in new['roster']))
