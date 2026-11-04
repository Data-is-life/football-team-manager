from collections import Counter
from dataclasses import asdict, replace
from unittest import TestCase
from unittest.mock import patch

from fastapi import HTTPException
from app.career import cpu_cuts, drop_players, offseason, replay_career
from app.draft import build_draft
from app.development import advance_context
from app.league import TEAMS
from app.lineups import lineup_context, replace_lineup_rosters
from app.main import CareerRequest, career_action, profile_payload
from app.simulation import roster_fill_target, roster_limit, roster_minimum, validate_roster


class RosterRangeTests(TestCase):
    def test_initial_targets_and_versioned_total_bounds(self):
        for rules, minimum, maximum, target in ((10,0,38,38),(11,0,31,31),(12,0,31,31),(13,31,38,31)):
            ctx=lineup_context((),1234,rules,rebuild_team='seattle')
            self.assertEqual((roster_minimum(ctx),roster_limit(ctx),roster_fill_target(ctx)),(minimum,maximum,target))
            for _,players in ctx:self.assertEqual(len(players),target)
            payload=profile_payload('seattle',dict(ctx)['seattle'],1234,ctx)
            if rules==13:self.assertEqual(payload['roster_limits'],dict(minimum=31,maximum=38))
            else:self.assertNotIn('roster_limits',payload)
        before=lineup_context((),1234,12,rebuild_team='seattle')
        after=lineup_context((),1234,13,rebuild_team='seattle')
        self.assertEqual(before.rosters,after.rosters)
        self.assertEqual(before.development,after.development)

    def test_release_floor_and_position_minimum_are_independently_protected(self):
        players=dict(lineup_context((),1234,13,rebuild_team='seattle'))['seattle']
        receiver=next(p for p in players if p.position=='WR')
        with self.assertRaisesRegex(ValueError,'at least 31'):
            drop_players(players,[receiver.id],31)
        qb=next(p for p in players if p.position=='QB')
        expanded=(*players,replace(qb,id='extra-qb',depth=3))
        kept=drop_players(expanded,[receiver.id],31)
        self.assertEqual(len(kept),31)
        with self.assertRaisesRegex(ValueError,'at least 31'):
            drop_players(expanded,[receiver.id,qb.id],31)
        kicker=next(p for p in players if p.position=='K')
        with self.assertRaisesRegex(ValueError,'K must keep at least 1'):
            drop_players(expanded,[kicker.id],31)
        self.assertEqual(len(players),31);self.assertEqual(len(expanded),32)

    def test_draft_retention_cpu_maximum_and_optional_cuts_over_multiple_years(self):
        ctx=lineup_context((),1234,13,rebuild_team='seattle')
        ctx=replace_lineup_rosters(ctx,tuple((owner,tuple(replace(p,age=23) for p in players)) for owner,players in ctx))
        order=[dict(team=asdict(team),record='0–0') for team in TEAMS]
        with patch('app.draft.draft_order',return_value=order):
            first,players=build_draft('seattle',1,1234,roster_context=ctx,auto_pick=True,draft_rounds=6)
            self.assertEqual(len(players),37)
            self.assertEqual(first['replacements'],[])
            _,ctx=offseason('seattle',1,1234,tuple(first['manual_picks']),(),roster_context=ctx,draft_rounds=6)
            for _,roster in ctx:self.assertEqual(len(roster),37)
            ctx=advance_context(ctx,1234,2,lineup_rules=13)
            second,players=build_draft('seattle',2,1234,roster_context=ctx,auto_pick=True,draft_rounds=6)
            self.assertEqual(len(players),43)
            picked={p.id for p in cpu_cuts(players,38,31)}
            cuts=tuple(p.id for p in players if p.id not in picked)
            self.assertEqual(len(cuts),5)
            _,ctx=offseason('seattle',2,1234,tuple(second['manual_picks']),cuts,roster_context=ctx,draft_rounds=6)
            for _,roster in ctx:
                self.assertEqual(len(roster),38)
                validate_roster(roster,minimum_total=31,maximum_total=38)
            for season in (3,4):
                ctx=advance_context(ctx,1234,season,lineup_rules=13)
                board,players=build_draft('seattle',season,1234,roster_context=ctx,auto_pick=True,draft_rounds=6)
                keep={p.id for p in cpu_cuts(players,31,31)}
                cuts=tuple(p.id for p in players if p.id not in keep)
                _,ctx=offseason('seattle',season,1234,tuple(board['manual_picks']),cuts,roster_context=ctx,draft_rounds=6)
                self.assertEqual(len(dict(ctx)['seattle']),31)
                for _,roster in ctx:validate_roster(roster,minimum_total=31,maximum_total=38)

    def test_retirement_fill_stops_at_31_and_does_not_fill_optional_slots(self):
        ctx=lineup_context((),1234,13,rebuild_team='seattle')
        young=replace_lineup_rosters(ctx,tuple((owner,tuple(replace(p,age=60) for p in players)) for owner,players in ctx))
        board,rosters=build_draft('seattle',1,1234,roster_context=young,auto_pick=True,draft_rounds=6,return_league=True)
        self.assertEqual(len(board['retirements']),31)
        self.assertEqual(len(board['replacements']),25)
        for roster in rosters.values():
            self.assertEqual(len(roster),31)
            validate_roster(roster,minimum_total=31,maximum_total=38)
        eligible=next(p for p in rosters['seattle'] if Counter(x.position for x in rosters['seattle'])[p.position]>next(r['minimum'] for r in profile_payload('seattle',rosters['seattle'],1234,young)['roster_rules'] if r['position']==p.position))
        with self.assertRaisesRegex(ValueError,'at least 31'):
            offseason('seattle',1,1234,tuple(board['manual_picks']),(eligible.id,),roster_context=young,draft_rounds=6)

    def test_real_api_history_accepts_retained_bench_and_rejects_under_minimum(self):
        args=dict(run_seed=1234,lineup_rules=13,rebuild_team='seattle',draft_rounds=6)
        draft=career_action('seattle',CareerRequest(action='draft',auto_draft=True,**args))
        picks=draft['manual_picks']
        result=career_action('seattle',CareerRequest(action='cuts',manual_picks=picks,**args))
        count=len(result['profile']['roster'])
        self.assertTrue(31<=count<=38);self.assertTrue(result['can_continue'])
        self.assertEqual(result['profile']['roster_limits'],dict(minimum=31,maximum=38))
        # Replay all picks without forced cuts to 31: they remain in the next year.
        step=(1,(),tuple(picks),(),13,(),6)
        next_year=replay_career('seattle',1234,(step,),13,2,1,'seattle')
        self.assertEqual(len(dict(next_year)['seattle']),count)
        players=dict(lineup_context((),1234,13,rebuild_team='seattle'))['seattle']
        board,players=build_draft('seattle',1,1234,tuple(picks),roster_context=lineup_context((),1234,13,rebuild_team='seattle'),draft_rounds=6)
        retained={p.id for p in cpu_cuts(players,31,31)}
        dropped=[p.id for p in players if p.id not in retained]
        valid=career_action('seattle',CareerRequest(action='cuts',manual_picks=picks,dropped=dropped,**args))
        self.assertEqual(len(valid['profile']['roster']),31)
        counts=Counter(p['position'] for p in valid['profile']['roster'])
        minima={r['position']:r['minimum'] for r in valid['profile']['roster_rules']}
        surplus=next(p['id'] for p in valid['profile']['roster'] if counts[p['position']]>minima[p['position']])
        with self.assertRaises(HTTPException) as error:
            career_action('seattle',CareerRequest(action='cuts',manual_picks=picks,dropped=dropped+[surplus],**args))
        self.assertEqual(error.exception.status_code,422);self.assertIn('at least 31',error.exception.detail)
        self.assertEqual(career_action('seattle',CareerRequest(action='cuts',manual_picks=picks,dropped=dropped,**args)),valid)

    def test_api_39_blocks_and_38_allows_continuation_and_history_replay(self):
        ctx=lineup_context((),1234,13,rebuild_team='seattle')
        first,_=build_draft('seattle',1,1234,roster_context=ctx,auto_pick=True,draft_rounds=6)
        step1=dict(season=1,lineup_rules=13,draft_rounds=6,manual_picks=first['manual_picks'],dropped=[])
        _,finished=offseason('seattle',1,1234,tuple(first['manual_picks']),(),roster_context=ctx,draft_rounds=6)
        second_ctx=advance_context(finished,1234,2,lineup_rules=13)
        second,players=build_draft('seattle',2,1234,roster_context=second_ctx,auto_pick=True,draft_rounds=6)
        self.assertGreaterEqual(len(players),39)
        results={}
        for limit in (39,38):
            keep={p.id for p in cpu_cuts(players,limit,31)}
            cuts=[p.id for p in players if p.id not in keep]
            args=dict(season=2,run_seed=1234,lineup_rules=13,rebuild_team='seattle',draft_rounds=6,career=[step1],manual_picks=second['manual_picks'],dropped=cuts)
            data=career_action('seattle',CareerRequest(action='cuts',**args))
            self.assertEqual(len(data['profile']['roster']),limit)
            self.assertEqual(data['can_continue'],limit==38)
            results[limit]=dict(season=2,lineup_rules=13,draft_rounds=6,manual_picks=second['manual_picks'],dropped=cuts)
        for limit in (39,38):
            request=CareerRequest(action='profile',season=3,run_seed=1234,lineup_rules=13,rebuild_team='seattle',career=[step1,results[limit]])
            if limit==39:
                with self.assertRaises(HTTPException) as error:career_action('seattle',request)
                self.assertEqual(error.exception.status_code,422);self.assertIn('38 players or fewer',error.exception.detail)
            else:
                data=career_action('seattle',request)
                self.assertEqual(len(data['roster']),38)

    def test_rules_12_to_13_preserves_played_results_and_stats(self):
        args=dict(run_seed=1234,rebuild_team='seattle')
        old=career_action('seattle',CareerRequest(action='week',week=17,lineup_rules=12,**args))
        new=career_action('seattle',CareerRequest(action='week',week=17,lineup_rules=13,**args))
        for key in ('record','result','game_results','standings','roster_stats'):
            self.assertEqual(new[key],old[key])
