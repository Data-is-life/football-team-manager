from dataclasses import replace
import unittest
from fastapi import HTTPException
from pydantic import ValidationError
from app.main import CareerRequest, career_action, team_profile
from app.career import cpu_cuts, offseason, replay_career
from app.draft import build_draft
from app.lineups import lineup_context
from app.starter_choices import with_starters, context_for_week, selected_roster
from app.simulation import ROSTER_RULES, roster_for, team_ratings, simulate_through_week, league_week_scores, simulate_league_week
from app.playoffs import playoffs_through_round


def choices(context, owner='seattle', weakest=False):
    players=list(roster_for(owner,1234,context).values())
    return tuple(p.id for position,(_,minimum) in ROSTER_RULES.items()
                 for p in sorted((p for p in players if p.position==position),key=lambda p:p.rating,reverse=not weakest)[:minimum])


class StarterChoiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base=lineup_context((),1234,6,rebuild_team='seattle')
        cls.ids=choices(cls.base,weakest=True)

    def test_explicit_starters_change_all_units_and_keep_other_rosters(self):
        plan=with_starters(self.base,'seattle',1234,((1,self.ids),))
        roster=roster_for('seattle',1234,plan)
        for position,(_,minimum) in ROSTER_RULES.items():
            self.assertEqual({p.id for p in roster.values() if p.position==position and p.depth<=minimum},
                             {p.id for p in roster.values() if p.position==position and p.id in self.ids})
        self.assertLess(team_ratings('seattle',1234,plan).offense,team_ratings('seattle',1234,self.base).offense)
        self.assertLess(team_ratings('seattle',1234,plan).defense,team_ratings('seattle',1234,self.base).defense)
        for owner,players in self.base:
            if owner!='seattle':self.assertEqual(tuple(roster_for(owner,1234,plan).values()),players)
        game=simulate_through_week('seattle',1,1,1234,roster_context=plan)['result']
        own=next(game[side] for side in ('home','away') if game[side]['team']['id']=='seattle')
        self.assertEqual(own['passing'][0]['player_id'],roster['QB1'].id)
        self.assertEqual(own['kicking'][0]['player_id'],roster['K1'].id)
        blocking={p['player_id']:p for p in own['blocking']}
        starters=[blocking[p.id]['pass_block_snaps']+blocking[p.id]['run_block_snaps'] for p in roster.values() if p.position=='OL' and p.depth<=5]
        reserves=[blocking[p.id]['pass_block_snaps']+blocking[p.id]['run_block_snaps'] for p in roster.values() if p.position=='OL' and p.depth>5]
        self.assertGreater(min(starters),max(reserves))

    def test_week_effective_changes_preserve_completed_scores_and_boxes(self):
        plan=with_starters(self.base,'seattle',1234,((9,self.ids),(12,())))
        for week in (1,8,9,11,12,17):
            expected=self.base if week<9 or week>=12 else with_starters(self.base,'seattle',1234,((1,self.ids),))
            actual=simulate_league_week(1,week,1234,roster_context=plan)
            self.assertEqual(actual,simulate_league_week(1,week,1234,roster_context=expected))
            scores=tuple((g['home']['team']['id'],g['away']['team']['id'],g['home']['score'],g['away']['score']) for g in actual)
            self.assertEqual(league_week_scores(1,week,1234,roster_context=plan),scores)
        before=simulate_through_week('seattle',1,8,1234,roster_context=self.base)
        after=simulate_through_week('seattle',1,8,1234,roster_context=plan)
        self.assertEqual(before['game_results'],after['game_results']);self.assertEqual(before['result'],after['result'])
        self.assertIs(context_for_week(self.base,10),self.base)

    def test_playoff_change_preserves_field_and_completed_rounds(self):
        # A post-regular-season change cannot reseed/replay Week 1–17 or prior rounds.
        automatic=playoffs_through_round('seattle',1,2,1234,roster_context=self.base)
        owner=automatic['survivors'][0]['team']['id']
        ids=choices(self.base,owner,weakest=True)
        plan=with_starters(self.base,owner,1234,((20,ids),))
        after=playoffs_through_round(owner,1,2,1234,roster_context=plan)
        self.assertEqual(automatic['rounds'],after['rounds'])
        self.assertEqual([p['team']['id'] for p in automatic['field']],[p['team']['id'] for p in after['field']])
        semifinal=playoffs_through_round(owner,1,3,1234,roster_context=plan)
        game=next(g for g in semifinal['rounds'][-1]['games'] if owner in (g['home']['team']['id'],g['away']['team']['id']))
        own=next(game['result'][side] for side in ('home','away') if game['result'][side]['team']['id']==owner)
        selected=roster_for(owner,1234,plan)
        self.assertEqual(own['passing'][0]['player_id'],selected['QB1'].id)
        self.assertEqual(own['kicking'][0]['player_id'],selected['K1'].id)

    def test_api_validation_profile_and_readonly_scouting(self):
        body=dict(action='profile',run_seed=1234,lineup_rules=6,rebuild_team='seattle',lineup_changes=[dict(week=1,starters=self.ids)])
        profile=career_action('seattle',CareerRequest(**body))
        self.assertEqual({p['id'] for p in profile['roster'] if p['depth']<=ROSTER_RULES[p['position']][1]},set(self.ids))
        scout=career_action('seattle',CareerRequest(**{**body,'view_team':'miami'}))
        self.assertEqual(scout,team_profile('miami',1234,6,1,1,'seattle'))
        for change in ([dict(week=1,starters=self.ids[:-1])], [dict(week=1,starters=[self.ids[0]]*22)],
                       [dict(week=1,starters=['miami-qb1',*self.ids[1:]])], [dict(week=22,starters=[])],
                       [dict(week=True,starters=[])], [dict(week=2,starters=[]),dict(week=1,starters=[])],
                       [dict(week=1,starters=[]),dict(week=1,starters=[])]):
            with self.subTest(change=change), self.assertRaises((HTTPException, ValidationError)):
                career_action('seattle',CareerRequest(**{**body,'lineup_changes':change}))

    def test_draft_cuts_and_replay_keep_historical_choices(self):
        events=((1,self.ids),(9,()))
        plan=with_starters(self.base,'seattle',1234,events)
        draft,players=build_draft('seattle',1,1234,(),(),plan,auto_pick=True)
        kept={p.id for p in cpu_cuts(players)};drops=tuple(p.id for p in players if p.id not in kept)
        _,context=offseason('seattle',1,1234,tuple(draft['manual_picks']),drops,(),plan)
        expected=lineup_context(context,1234,6,2,1,'seattle')
        steps=((1,(),tuple(draft['manual_picks']),drops,6,events),)
        actual=replay_career('seattle',1234,steps,6,2,1,'seattle')
        self.assertEqual(expected,actual)
        body=dict(action='cuts',run_seed=1234,lineup_rules=6,rebuild_team='seattle',manual_picks=draft['manual_picks'],dropped=drops,lineup_changes=[dict(week=w,starters=s) for w,s in events])
        self.assertTrue(career_action('seattle',CareerRequest(**body))['cuts_applied'])

    def test_legacy_no_choices_and_auto_reset_preserve_original_rules(self):
        for rules in range(1,7):
            base=lineup_context((),1234,rules)
            self.assertIs(with_starters(base,'seattle',1234,()),base)
            plan=with_starters(base,'seattle',1234,((1,choices(base,weakest=True)),(2,())))
            actual=roster_for('seattle',1234,context_for_week(plan,2))
            for position,(_,minimum) in ROSTER_RULES.items():
                ordered=sorted((p for p in actual.values() if p.position==position),key=lambda p:p.depth)
                self.assertGreaterEqual(min(p.rating for p in ordered[:minimum]),max((p.rating for p in ordered[minimum:]),default=0))
