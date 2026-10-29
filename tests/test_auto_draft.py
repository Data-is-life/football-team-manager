import unittest

from fastapi import HTTPException
from pydantic import ValidationError
from app.career import cpu_cuts, offseason
from app.draft import build_draft, cpu_pick, draft_class
from app.lineups import lineup_context
from app.main import CareerRequest, DraftRequest, career_action, rookie_draft
from app.simulation import roster_for


class AutoDraftTests(unittest.TestCase):
    def test_full_and_partial_auto_drafts_replay_as_ordinary_saved_choices(self):
        for rules in (1,4,5):
            context=lineup_context((),1234,rules)
            choices=[]
            original=draft_class(1,1234)
            for turn in range(5):
                before,_=build_draft('seattle',1,1234,tuple(choices),(),context)
                completed,players=build_draft('seattle',1,1234,tuple(choices),(),context,auto_pick=True)
                self.assertTrue(completed['complete'])
                self.assertEqual(len(completed['picks']),120)
                self.assertEqual(len(completed['available']),80)
                self.assertEqual(len(players),42)
                self.assertEqual(len(set(p['player']['id'] for p in completed['picks'])),120)
                self.assertEqual(completed['manual_picks'][:len(choices)],choices)
                self.assertEqual(completed['picks'][:len(before['picks'])],before['picks'])
                replay,replayed_players=build_draft('seattle',1,1234,tuple(completed['manual_picks']),(),context)
                self.assertEqual((completed,players),(replay,replayed_players))
                self.assertEqual((completed,players),build_draft('seattle',1,1234,tuple(choices),(),context,auto_pick=True))
                self.assertEqual(draft_class(1,1234),original)
                if turn<4:choices.append(before['available'][-1]['id'])

    def test_auto_picks_use_the_same_cpu_policy_after_manual_picks(self):
        context=lineup_context((),1234,5,rebuild_team='seattle')
        choices=[]
        for _ in range(3):
            before,players=build_draft('seattle',1,1234,tuple(choices),(),context)
            available_ids={p['id'] for p in before['available']}
            available=[p for p in draft_class(1,1234) if p.id in available_ids]
            counts={position:sum(p.position==position for p in players if p.id in choices) for position in {p.position for p in players}}
            expected=cpu_pick(available,players,counts)
            completed,_=build_draft('seattle',1,1234,tuple(choices),(),context,auto_pick=True)
            self.assertEqual(completed['manual_picks'][len(choices)],expected.id)
            choices.append(before['available'][-1]['id'])

    def test_api_auto_draft_keeps_career_rosters_and_cut_review(self):
        first=rookie_draft('seattle',DraftRequest(run_seed=1234,lineup_rules=5,rebuild_team='seattle',auto_draft=True))
        self.assertTrue(first['complete'])
        self.assertEqual(len(first['profile']['roster']),42)
        self.assertEqual(first,rookie_draft('seattle',DraftRequest(run_seed=1234,lineup_rules=5,rebuild_team='seattle',manual_picks=first['manual_picks'])))
        context=lineup_context((),1234,5,rebuild_team='seattle')
        _,players=build_draft('seattle',1,1234,tuple(first['manual_picks']),(),context)
        kept={p.id for p in cpu_cuts(players)}
        dropped=[p.id for p in players if p.id not in kept]
        step=dict(season=1,manual_picks=first['manual_picks'],dropped=dropped,lineup_rules=5)
        request=dict(action='draft',run_seed=1234,lineup_rules=5,rebuild_team='seattle',season=2,career=[step])
        partial=career_action('seattle',CareerRequest(**request))
        choice=partial['available'][-1]['id']
        complete=career_action('seattle',CareerRequest(**request,manual_picks=[choice],auto_draft=True))
        self.assertEqual(complete['manual_picks'][0],choice)
        self.assertEqual(len(complete['profile']['roster']),42)
        self.assertTrue(kept <= {p['id'] for p in complete['profile']['roster']})
        self.assertEqual(complete,career_action('seattle',CareerRequest(**request,manual_picks=complete['manual_picks'])))

    def test_auto_requests_reject_invalid_choices_flags_and_wrong_actions(self):
        for choices in (['missing'],['x','x']):
            with self.assertRaises(HTTPException) as caught:
                rookie_draft('seattle',DraftRequest(run_seed=1234,manual_picks=choices,auto_draft=True))
            self.assertEqual(caught.exception.status_code,422)
        for flag in ('true',1,None):
            with self.assertRaises(ValidationError):DraftRequest(auto_draft=flag)
        for action in ('profile','week','playoffs','cuts'):
            with self.assertRaises(HTTPException):
                career_action('seattle',CareerRequest(action=action,auto_draft=True))
        with self.assertRaises(HTTPException):
            career_action('seattle',CareerRequest(action='draft',auto_draft=True,dropped=['seattle-qb1']))


if __name__=='__main__':unittest.main()
