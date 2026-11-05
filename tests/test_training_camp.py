from dataclasses import replace
from unittest import TestCase
from fastapi import HTTPException
from app.career import training_camp, offseason, cpu_cuts, replay_career
from app.development import advance_context
from app.draft import build_draft
from app.lineups import lineup_context, replace_lineup_rosters
from app.main import CareerRequest, career_action
from app.player_contracts import payroll, salary_cap, cpu_cap_cuts
from app.simulation import validate_roster


class TrainingCampTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context=lineup_context((),1234,18,rebuild_team='seattle')
        cls.board,cls.players=build_draft('seattle',1,1234,roster_context=cls.context,auto_pick=True,draft_rounds=6)
        cls.choices=tuple(cls.board['manual_picks'])
        cls.request=dict(season=1,run_seed=1234,lineup_rules=18,rebuild_team='seattle',draft_rounds=6,manual_picks=list(cls.choices))

    def test_camp_requires_complete_draft_and_api_protects_stage(self):
        for body in [dict(action='camp',manual_picks=[]),dict(action='cuts'),dict(action='camp',dropped=['unknown'])]:
            with self.assertRaises(HTTPException) as error:
                career_action('seattle',CareerRequest(**{**self.request,**body}))
            self.assertEqual(error.exception.status_code,422)
        for body in [dict(action='camp',lineup_rules=17),dict(action='draft',training_camp=True)]:
            with self.assertRaises(HTTPException):career_action('seattle',CareerRequest(**{**self.request,**body}))
        initial=career_action('seattle',CareerRequest(action='draft',**self.request))
        self.assertNotIn('training_camp',initial)
        self.assertTrue(all(p['rating_change']==0 for p in initial['profile']['roster'] if p['id'].startswith('rookie-')))

    def test_all_players_develop_before_any_cut_and_retry_is_exact(self):
        board,full=training_camp('seattle',1,1234,self.choices,(),self.context,6)
        self.assertEqual(full.season,2)
        _,rosters=build_draft('seattle',1,1234,self.choices,roster_context=self.context,return_league=True,draft_rounds=6)
        expected=advance_context(replace_lineup_rosters(self.context,tuple((owner,tuple(players)) for owner,players in sorted(rosters.items()))),1234,2,lineup_rules=18)
        self.assertEqual(full,expected)
        self.assertGreater(len(dict(full)['seattle']),38)
        original={p.id:p for p in self.players}
        for p in dict(full)['seattle']:
            if p.id.startswith('rookie-'):self.assertEqual(p.age,original[p.id].age)
            elif p.id in original:self.assertEqual(p.age,original[p.id].age+1)
            if p.id in original:self.assertEqual(p.contract,original[p.id].contract)
        self.assertEqual(board['picks'],self.board['picks'])
        first=career_action('seattle',CareerRequest(action='camp',**self.request))
        self.assertTrue(first['training_camp']);self.assertEqual(first['development_season'],2)
        self.assertEqual(len(first['development_roster']),len(dict(full)['seattle']))
        self.assertFalse(first['can_continue'])
        training_camp.cache_clear()
        self.assertEqual(first,career_action('seattle',CareerRequest(action='camp',**self.request)))
        self.assertEqual(first,career_action('seattle',CareerRequest(action='camp',training_camp=True,**self.request)))
        # Completed game results still use the old season roster, including in camp requests.
        a=career_action('seattle',CareerRequest(action='week',week=17,**{k:v for k,v in self.request.items() if k!='manual_picks'}))
        b=career_action('seattle',CareerRequest(action='week',week=17,training_camp=True,**self.request))
        self.assertEqual(a,b)

    def legal_cuts(self,context):
        players=dict(context)['seattle']
        keep=cpu_cap_cuts(cpu_cuts(players,38,35),'seattle',context.season-1,1234,context)
        keep_ids={p.id for p in keep}
        return tuple(p.id for p in players if p.id not in keep_ids)

    def test_cuts_use_camp_ratings_and_full_recap_survives_repeated_cuts(self):
        _,full=training_camp('seattle',1,1234,self.choices,(),self.context,6)
        cuts=self.legal_cuts(full)
        first=career_action('seattle',CareerRequest(action='camp',**self.request))
        final=career_action('seattle',CareerRequest(action='cuts',training_camp=True,dropped=list(cuts),**self.request))
        self.assertTrue(final['can_continue'])
        self.assertEqual(final['development_roster'],first['development_roster'])
        originals={p['id']:p for p in first['profile']['roster']}
        for p in final['profile']['roster']:
            self.assertEqual(p['rating'],originals[p['id']]['rating'])
            self.assertEqual(p['rating_change'],originals[p['id']]['rating_change'])
            self.assertEqual(p['potential_rating'],originals[p['id']]['potential_rating'])
        self.assertEqual(final,career_action('seattle',CareerRequest(action='camp',training_camp=True,dropped=list(cuts),**self.request)))
        self.assertEqual(set(originals)-{p['id'] for p in final['profile']['roster']},set(cuts))

    def test_history_rollover_does_not_develop_twice_and_resets_rotation_after_cuts(self):
        _,full=training_camp('seattle',1,1234,self.choices,(),self.context,6)
        cuts=self.legal_cuts(full)
        _,completed=offseason('seattle',1,1234,self.choices,cuts,(),self.context,6)
        step=(1,(),self.choices,cuts,18,(),6)
        actual=replay_career('seattle',1234,(step,),18,2,1,'seattle')
        self.assertEqual(actual,completed)
        self.assertEqual(actual,advance_context(completed,1234,2,lineup_rules=18))
        from app.rotation import season_roles
        shares={identity:share for _,players in actual for identity,share in season_roles(players).items()}
        self.assertTrue(all(state.rotation_share==shares[identity] for identity,state in actual.development))
        before={p.id:p for _,players in full for p in players}
        for _,players in actual:
            for p in players:
                if p.id in before:self.assertEqual(p,before[p.id] if p.depth==before[p.id].depth else replace(before[p.id],depth=p.depth))

    def test_cpu_finalizes_post_development_rosters_under_upcoming_cap(self):
        _,full=training_camp('seattle',1,1234,self.choices,(),self.context,6)
        _,finished=offseason('seattle',1,1234,self.choices,self.legal_cuts(full),(),self.context,6)
        for owner,players in finished:
            validate_roster(players,minimum_total=35,maximum_total=38)
            self.assertLessEqual(payroll(players),salary_cap(2,18))
            if owner!='seattle':
                expected=cpu_cap_cuts(cpu_cuts(dict(full)[owner],38,35),owner,1,1234,full)
                self.assertEqual(set(p.id for p in players),set(p.id for p in expected))

    def test_second_camp_develops_one_year_and_scouting_sees_same_camp(self):
        _,full=training_camp('seattle',1,1234,self.choices,(),self.context,6)
        step=(1,(),self.choices,self.legal_cuts(full),18,(),6)
        current=replay_career('seattle',1234,(step,),18,2,1,'seattle')
        board,_=build_draft('seattle',2,1234,roster_context=current,auto_pick=True,draft_rounds=6)
        _,next_camp=training_camp('seattle',2,1234,tuple(board['manual_picks']),(),current,6)
        self.assertEqual(next_camp.season,3)
        before={p.id:p for _,players in current for p in players}
        for _,players in next_camp:
            for p in players:
                if p.id in before:self.assertEqual(p.age,before[p.id].age+1)
        camp=career_action('seattle',CareerRequest(action='camp',view_team='miami',**self.request))
        self.assertEqual(camp['profile']['team']['id'],'miami')
        self.assertEqual(camp['profile']['payroll']['season'],2)
        self.assertTrue(all(p['id'] in {p.id for p in dict(full)['miami']} for p in camp['profile']['roster']))

    def test_completed_legacy_offseasons_keep_original_cut_development_order(self):
        legacy=lineup_context((),1234,17,rebuild_team='seattle')
        board,players=build_draft('seattle',1,1234,roster_context=legacy,auto_pick=True,draft_rounds=6)
        keep={p.id for p in cpu_cuts(players,38,35)}
        step=(1,(),tuple(board['manual_picks']),tuple(p.id for p in players if p.id not in keep),17,(),6)
        old=replay_career('seattle',1234,(step,),17,2,1,'seattle')
        new=replay_career('seattle',1234,(step,),18,2,1,'seattle')
        self.assertEqual(tuple(old),tuple(new))
        self.assertEqual(old.development,new.development)
