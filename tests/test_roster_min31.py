from collections import Counter
from dataclasses import replace
from unittest import TestCase
from app.lineups import lineup_context
from app.simulation import EXPANDED_ROSTER_RULES,roster_minimum,roster_limit,roster_fill_target,validate_roster
from app.retirement import fill_roster
from app.career import cpu_cuts,drop_players,replay_career
from app.main import CareerRequest,career_action
from app.player_contracts import cap_ready


class Starting35Minimum31Tests(TestCase):
    def test_all_teams_start_35_with_unchanged_position_minimums(self):
        for seed in (0,1234,4294967295):
            context=lineup_context((),seed,24,rebuild_team='seattle')
            self.assertEqual((roster_minimum(context),roster_limit(context),roster_fill_target(context)),(31,38,35))
            for _,players in context:
                self.assertEqual(len(players),35)
                self.assertEqual(Counter(p.position for p in players),{p:n for p,(n,_) in EXPANDED_ROSTER_RULES.items()})
                validate_roster(players,minimum_total=31,maximum_total=38)

    def test_refills_honor_31_and_every_position_minimum(self):
        context=lineup_context((),1234,24,rebuild_team='seattle')
        kept=cpu_cuts(dict(context)['seattle'],31,31)
        self.assertEqual(tuple(kept),tuple(fill_roster(kept,'seattle',1,1234,context=context)))
        counts=Counter(p.position for p in kept)
        surplus=next(p for p in kept if counts[p.position]>EXPANDED_ROSTER_RULES[p.position][1])
        with self.assertRaisesRegex(ValueError,'at least 31'):drop_players(kept,[surplus.id],31)
        trimmed=[p for p in kept if p.id!=surplus.id]
        filled=fill_roster(trimmed,'seattle',1,1234,context=context)
        self.assertEqual(len(filled),31);validate_roster(filled,minimum_total=31,maximum_total=38)
        kicker=next(p for p in kept if p.position=='K')
        with self.assertRaisesRegex(ValueError,'K must keep at least 1'):drop_players(kept,[kicker.id],31)
        filled=fill_roster([p for p in kept if p.id!=kicker.id],'seattle',1,1234,context=context)
        self.assertEqual(len(filled),31);self.assertTrue(any(p.position=='K' for p in filled))

    def test_api_cut_to_31_then_rollover_keeps_31_and_dead_cap(self):
        req=dict(season=1,run_seed=1234,lineup_rules=24,rebuild_team='seattle',draft_rounds=6)
        draft=career_action('seattle',CareerRequest(action='draft',auto_draft=True,**req))
        req.update(manual_picks=draft['manual_picks'],training_camp=True)
        data=career_action('seattle',CareerRequest(action='camp',**req))
        actions=[];cuts=[]
        while len(data['profile']['roster'])>31:
            players=data['profile']['roster'];counts=Counter(p['position'] for p in players)
            candidate=next(p for p in players if counts[p['position']]>EXPANDED_ROSTER_RULES[p['position']][1])
            cuts.append(candidate['id']);actions.append(dict(kind='drop',player_id=candidate['id']))
            previous=len(players)
            data=career_action('seattle',CareerRequest(action='cuts',dropped=cuts,roster_actions=actions,**req))
            self.assertEqual(len(data['profile']['roster']),previous-1)
            self.assertEqual(data['profile']['roster_limits'],dict(minimum=31,maximum=38))
        self.assertTrue(data['can_continue']);self.assertGreater(data['profile']['payroll']['dead_cap'],0)
        step=(1,(),tuple(draft['manual_picks']),tuple(cuts),24,(),6,tuple((a['kind'],a['player_id']) for a in actions))
        context=replay_career('seattle',1234,(step,),24,2,1,'seattle')
        self.assertEqual(len(dict(context)['seattle']),31)
        for owner,players in context:
            validate_roster(players,minimum_total=31,maximum_total=38)
            self.assertTrue(cap_ready(players,context,owner=owner))
        self.assertEqual(context,replay_career('seattle',1234,(step,),24,2,1,'seattle'))
        # Atomic replacements can keep a required slot filled, but cannot produce 30.
        players=data['profile']['roster'];kicker=next(p for p in players if p['position']=='K')
        after=career_action('seattle',CareerRequest(action='cuts',dropped=cuts+[kicker['id']],roster_actions=actions+[dict(kind='drop',player_id=kicker['id'])],**req))
        self.assertGreaterEqual(len(after['profile']['roster']),31)
        self.assertTrue(any(p['position']=='K' for p in after['profile']['roster']))

    def test_existing_35_policy_stays_versioned(self):
        old=lineup_context((),1234,23,rebuild_team='seattle')
        new=lineup_context(old,1234,24,1,1,'seattle')
        self.assertEqual(old.rosters,new.rosters);self.assertEqual(old.dead_cap,new.dead_cap)
        self.assertEqual(roster_minimum(old),35);self.assertEqual(roster_minimum(new),31)
        kept=cpu_cuts(dict(old)['seattle'],31,31)
        self.assertEqual(len(fill_roster(kept,'seattle',1,1234,context=old)),35)
        self.assertEqual(len(fill_roster(kept,'seattle',1,1234,context=new)),31)
