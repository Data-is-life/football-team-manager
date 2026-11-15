from dataclasses import replace
from unittest import TestCase
from app.draft import draft_class,build_draft
from app.lineups import lineup_context
from app.preseason import prepare
from app.main import CareerRequest,career_action

class DraftAgeCapTests(TestCase):
    def test_age_bounds_replay_and_no_unrelated_generation_changes(self):
        for seed in (0,1234,5678):
            for season in (1,2,10):
                old=draft_class(season,seed,39);new=draft_class(season,seed,40)
                self.assertEqual(len(new),200)
                self.assertTrue(all(21<=p.age<=23 for p in new))
                self.assertEqual(set(p.age for p in new),{21,22,23})
                self.assertEqual(tuple(replace(n,age=o.age) for o,n in zip(old,new)),old)
                self.assertEqual(old,draft_class(season,seed))
                self.assertTrue(any(p.age==24 for p in old))
                draft_class.cache_clear()
                self.assertEqual(new,draft_class(season,seed,40))

    def test_all_draft_picks_and_undrafted_rookies_share_entry_ages(self):
        seed=1234;root=lineup_context((),seed,40,rebuild_team='seattle')
        board,_=build_draft('seattle',1,seed,roster_context=root,auto_pick=True,draft_rounds=6)
        generated={p.id:p for p in draft_class(1,seed,40)}
        self.assertEqual(len(board['picks']),180)
        for pick in board['picks']:
            self.assertEqual(pick['player']['age'],generated[pick['player']['id']].age)
        _,context=prepare('seattle',1,seed,tuple(board['manual_picks']),(),root,6)
        picked={p['player']['id'] for p in board['picks']}
        undrafted=[p for p in context.free_agents if p.id in generated and p.id not in picked]
        self.assertEqual(len(undrafted),20)
        for p in undrafted:self.assertEqual(p.age,generated[p.id].age)
        args=dict(run_seed=seed,lineup_rules=40,rebuild_team='seattle',draft_rounds=6,manual_picks=board['manual_picks'],action='free_agency')
        market=career_action('seattle',CareerRequest(**args))
        for p in market['free_agency']['available']:
            if p['id'] in generated:self.assertEqual(p['age'],generated[p['id']].age)
        prepare.cache_clear();draft_class.cache_clear()
        self.assertEqual(market,career_action('seattle',CareerRequest(**args)))

    def test_starting_rosters_and_saved_careers_keep_original_ages(self):
        old=lineup_context((),1234,39,rebuild_team='seattle')
        new=lineup_context((),1234,40,rebuild_team='seattle')
        self.assertEqual(old.rosters,new.rosters)
        from app.development import advance_context
        with self.assertRaisesRegex(ValueError,'new career'):advance_context(old,1234,2,lineup_rules=40)
