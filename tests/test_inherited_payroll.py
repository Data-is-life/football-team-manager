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

    def test_new_careers_have_first_season_expiries_without_repricing(self):
        from app.retirement import retirement_age
        selections=set()
        for seed in (0,1,1234,5678):
            old=lineup_context((),seed,31,rebuild_team='seattle')
            new=lineup_context((),seed,32,rebuild_team='seattle')
            self.assertEqual(new,lineup_context((),seed,32,rebuild_team='seattle'))
            for owner,players in new:
                previous={p.id:p for p in dict(old)[owner]}
                expiring=[p for p in players if p.contract.years==1]
                self.assertEqual(len(expiring),len(players)//4)
                self.assertTrue(all(retirement_age(p,seed)>p.age for p in expiring))
                self.assertTrue(any(p.contract.years>1 for p in players))
                for player in players:
                    before=previous[player.id]
                    self.assertEqual(replace(player,contract=before.contract),before)
                    self.assertEqual(player.contract.annual_salary,before.contract.annual_salary)
                    if player.contract.category=='inherited_bad':
                        self.assertEqual(player.contract,before.contract)
                self.assertEqual(payroll(players),payroll(dict(old)[owner]))
            selections.add(tuple(p.id for p in dict(new)['seattle'] if p.contract.years==1))
        self.assertEqual(len(selections),4)

    def test_first_market_requires_resolving_new_starting_expiries(self):
        self.assert_first_market_and_saved_rollover(32)

    def test_rules_33_market_camp_and_saved_rollover(self):
        self.assert_first_market_and_saved_rollover(33)

    def test_rules_34_market_camp_and_saved_rollover(self):
        self.assert_first_market_and_saved_rollover(34)

    def test_rules_35_market_camp_and_saved_rollover(self):
        self.assert_first_market_and_saved_rollover(35)

    def assert_first_market_and_saved_rollover(self, rules):
        from fastapi import HTTPException
        from app.preseason import run
        from app.player_contracts import contract_expired
        seed=1234
        root=lineup_context((),seed,rules,rebuild_team='seattle')
        args=dict(run_seed=seed,lineup_rules=rules,rebuild_team='seattle',draft_rounds=6)
        draft=career_action('seattle',CareerRequest(action='draft',auto_draft=True,**args))
        req=dict(manual_picks=draft['manual_picks'],**args)
        market=career_action('seattle',CareerRequest(action='free_agency',**req))
        expired=[p for p in market['profile']['roster'] if p.get('renewal_offer')]
        self.assertEqual(len(expired),8)
        self.assertTrue(all(p['contract']['years_remaining']==0 for p in expired))
        self.assertTrue(all(p.contract.years>=2 for p in dict(lineup_context((),seed,31,rebuild_team='seattle'))['seattle']))
        with self.assertRaises(HTTPException):
            career_action('seattle',CareerRequest(action='free_agency',free_agency=[dict(kind='finish')],**req))
        target=min((p for p in expired if p['renewal_offer']['affordable']),key=lambda p:p['renewal_offer']['annual_salary'])
        actions=[dict(kind='resign',player_id=target['id'])]+[dict(kind='drop',player_id=p['id']) for p in expired if p['id']!=target['id']]+[dict(kind='finish')]
        review=career_action('seattle',CareerRequest(action='free_agency',free_agency=actions,**req))
        self.assertTrue(review['free_agency']['complete'])
        self.assertFalse(review['training_camp'])
        signed=next(p for p in review['profile']['roster'] if p['id']==target['id'])
        self.assertEqual(signed['contract']['annual_salary'],target['renewal_offer']['annual_salary'])
        self.assertEqual(signed['contract']['signed_season'],2)
        self.assertEqual(review,career_action('seattle',CareerRequest(action='free_agency',free_agency=actions,**req)))
        # All CPU teams resolve their expired contracts in the same first market.
        _,context=run('seattle',1,seed,tuple(draft['manual_picks']),(),root,6,tuple((a['kind'],a.get('player_id','')) for a in actions))
        self.assertTrue(all(not contract_expired(p,2) for owner,players in context for p in players))
        pre=[]
        if review['payroll_floor_adjustment']:
            pre=[dict(kind='raise',player_id=review['payroll_floor_adjustment']['player_id'])]
        camp=career_action('seattle',CareerRequest(action='camp',free_agency=actions,pre_camp_actions=pre,**req))
        self.assertTrue(camp['can_continue'])
        past=dict(season=1,lineup_rules=rules,draft_rounds=6,manual_picks=draft['manual_picks'],
                  free_agency=actions,pre_camp_actions=pre,camp_actions=[])
        next_req=dict(action='profile',season=2,career=[past],**args)
        next_profile=career_action('seattle',CareerRequest(**next_req))
        self.assertEqual(next_profile,career_action('seattle',CareerRequest(**next_req)))
        renewed=next(p for p in next_profile['roster'] if p['id']==target['id'])
        self.assertEqual(renewed['contract']['signed_season'],2)
        self.assertEqual(renewed['contract']['annual_salary'],signed['contract']['annual_salary'])
        self.assertEqual(next_profile['lineup_rules'],rules)
