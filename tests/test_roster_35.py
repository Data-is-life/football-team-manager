from collections import Counter
from dataclasses import replace
from unittest import TestCase

from fastapi import HTTPException
from app.career import cpu_cuts, drop_players, offseason, replay_career
from app.development import advance_context
from app.draft import build_draft
from app.lineups import lineup_context, replace_lineup_rosters
from app.main import CareerRequest, career_action
from app.simulation import EXPANDED_ROSTER_RULES, roster_limit, roster_minimum, team_ratings, validate_roster


class ThirtyFivePlayerRosterTests(TestCase):
    def test_every_team_starts_with_35_and_balanced_units(self):
        expected={position:count for position,(count,_) in EXPANDED_ROSTER_RULES.items()}
        for seed in (0,1234,5678,4294967295):
            context=lineup_context((),seed,14,rebuild_team='seattle')
            self.assertEqual((roster_minimum(context),roster_limit(context)),(35,38))
            rivals=[]
            for owner,players in context:
                self.assertEqual(len(players),35)
                self.assertEqual(Counter(p.position for p in players),expected)
                validate_roster(players,minimum_total=35,maximum_total=38)
                self.assertEqual(sum(p.position in ('QB','WR','TE','RB','OL') for p in players),17)
                self.assertEqual(sum(p.position in ('DL','LB','CB','S') for p in players),17)
                ratings=team_ratings(owner,seed,context)
                if owner=='seattle':self.assertTrue(68<=ratings.offense<=72 and 68<=ratings.defense<=72)
                else:rivals.append(ratings)
            self.assertEqual(sum(r.offense for r in rivals)/29,75)
            self.assertEqual(sum(r.defense for r in rivals)/29,75)

    def test_floor_35_and_position_minimum_are_both_protected(self):
        players=dict(lineup_context((),1234,14,rebuild_team='seattle'))['seattle']
        receiver=next(p for p in players if p.position=='WR')
        with self.assertRaisesRegex(ValueError,'at least 35'):drop_players(players,[receiver.id],35)
        qb=next(p for p in players if p.position=='QB')
        expanded=(*players,replace(qb,id='extra-qb',depth=3))
        self.assertEqual(len(drop_players(expanded,[receiver.id],35)),35)
        kicker=next(p for p in players if p.position=='K')
        with self.assertRaisesRegex(ValueError,'K must keep at least 1'):drop_players(expanded,[kicker.id],35)

    def test_existing_31_player_careers_expand_once_without_recreating_releases(self):
        old=lineup_context((),1234,13,rebuild_team='seattle')
        before=advance_context(old,1234,2,lineup_rules=13)
        upgraded=advance_context(old,1234,2,lineup_rules=14)
        for owner,players in upgraded:
            self.assertEqual(len(players),35)
            old_ids={p.id for p in dict(before)[owner]}
            retained=tuple(p for p in players if p.id in old_ids)
            self.assertEqual({p.id for p in retained},old_ids)
            prior={p.id:p for p in dict(before)[owner]}
            self.assertEqual({p.id:replace(p,depth=prior[p.id].depth) for p in retained},prior)
            added=[p for p in players if p.id not in old_ids]
            self.assertEqual(len(added),4)
            self.assertTrue(all('-expansion-' in p.id and 40<=p.rating<=55 for p in added))
            self.assertTrue(all(dict(upgraded.development)[p.id].potential<=60 for p in added))
        self.assertEqual(upgraded,advance_context(upgraded,1234,2,lineup_rules=14))
        with self.assertRaisesRegex(ValueError,'next season'):advance_context(old,1234,1,lineup_rules=14)
        # The old namespace can contain released IDs; expansion never uses it.
        from app.retirement import fill_roster
        existing=dict(before)['seattle'];normal_fill=fill_roster(existing,'seattle',1,1234,context=upgraded)
        old_released={p.id for p in normal_fill if p.id not in {q.id for q in existing}}
        self.assertTrue(old_released)
        self.assertFalse(old_released & {p.id for p in dict(upgraded)['seattle']})

    def test_retirement_replacements_target_35_not_38(self):
        context=lineup_context((),1234,14,rebuild_team='seattle')
        aged=replace_lineup_rosters(context,tuple((owner,tuple(replace(p,age=60) for p in players)) for owner,players in context))
        board,rosters=build_draft('seattle',1,1234,roster_context=aged,auto_pick=True,draft_rounds=6,return_league=True)
        self.assertEqual(len(board['retirements']),35)
        self.assertEqual(len(board['replacements']),29)
        for roster in rosters.values():self.assertEqual(len(roster),35);validate_roster(roster,minimum_total=35,maximum_total=38)

    def test_api_cuts_and_history_keep_35_to_38(self):
        args=dict(run_seed=1234,lineup_rules=14,rebuild_team='seattle',draft_rounds=6)
        board=career_action('seattle',CareerRequest(action='draft',auto_draft=True,**args))
        context=lineup_context((),1234,14,rebuild_team='seattle')
        _,players=build_draft('seattle',1,1234,tuple(board['manual_picks']),roster_context=context,draft_rounds=6)
        keep={p.id for p in cpu_cuts(players,35,35)}
        cuts=[p.id for p in players if p.id not in keep]
        result=career_action('seattle',CareerRequest(action='cuts',manual_picks=board['manual_picks'],dropped=cuts,**args))
        self.assertEqual(result['profile']['roster_limits'],dict(minimum=35,maximum=38))
        self.assertEqual(len(result['profile']['roster']),35);self.assertTrue(result['can_continue'])
        counts=Counter(p.position for p in players if p.id in keep)
        surplus=next(p.id for p in players if p.id in keep and counts[p.position]>EXPANDED_ROSTER_RULES[p.position][1])
        with self.assertRaises(HTTPException) as error:
            career_action('seattle',CareerRequest(action='cuts',manual_picks=board['manual_picks'],dropped=cuts+[surplus],**args))
        self.assertEqual(error.exception.status_code,422);self.assertIn('35',error.exception.detail)
        step=(1,(),tuple(board['manual_picks']),tuple(cuts),14,(),6)
        next_year=replay_career('seattle',1234,(step,),14,2,1,'seattle')
        for _,roster in next_year:validate_roster(roster,minimum_total=35,maximum_total=38)
