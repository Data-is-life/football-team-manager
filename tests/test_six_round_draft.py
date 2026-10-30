"""Six-round selections, legacy replay, and roster-limit integration."""
from collections import Counter
import unittest

from fastapi import HTTPException
from pydantic import ValidationError
from app.career import cpu_cuts
from app.draft import build_draft, draft_class, draft_order
from app.main import CareerRequest, CareerStep, DraftRequest, career_action, rookie_draft


class SixRoundDraftTests(unittest.TestCase):
    def test_manual_six_rounds_for_first_middle_and_last_pick(self):
        order = draft_order(1, 1234)
        original = draft_class(1, 1234)
        for entry in (order[0], order[14], order[-1]):
            team = entry['team']['id']
            choices, prior_picks = [], []
            for turn in range(7):
                data, players = build_draft(team, 1, 1234, tuple(choices), draft_rounds=6)
                self.assertEqual(data['rounds'], 6)
                self.assertEqual(data['total_picks'], 180)
                self.assertEqual(data['picks'][:len(prior_picks)], prior_picks)
                self.assertEqual(data['complete'], turn == 6)
                self.assertEqual(len(players), 38 + turn)
                if turn < 6:
                    self.assertEqual(data['next_round'], turn + 1)
                    choices.append(data['available'][0]['id'])
                    prior_picks = data['picks']
            self.assertEqual(len(data['available']), 20)
            self.assertEqual(len({p['player']['id'] for p in data['picks']}), 180)
            self.assertEqual(Counter(p['team']['id'] for p in data['picks']), {x['team']['id']:6 for x in order})
            self.assertEqual([p['team']['id'] for p in data['picks']], [x['team']['id'] for x in order]*6)
        self.assertEqual(original, draft_class(1, 1234))

    def test_auto_finish_from_every_turn_preserves_prefix_and_replays(self):
        choices = []
        for turn in range(7):
            before, _ = build_draft('seattle', 1, 1234, tuple(choices), draft_rounds=6)
            complete, players = build_draft('seattle', 1, 1234, tuple(choices), auto_pick=True, draft_rounds=6)
            self.assertTrue(complete['complete'])
            self.assertEqual(complete['manual_picks'][:turn], choices)
            self.assertEqual(complete['picks'][:len(before['picks'])], before['picks'])
            self.assertEqual(len(players), 44)
            self.assertEqual((complete, players), build_draft('seattle', 1, 1234, tuple(complete['manual_picks']), draft_rounds=6))
            if turn < 6:
                choices.append(before['available'][-1]['id'])

    def test_legacy_four_round_history_then_six_round_cuts_and_rollover(self):
        first, players = build_draft('seattle', 1, 1234, auto_pick=True)
        self.assertEqual(first['rounds'], 4)
        kept = {p.id for p in cpu_cuts(players)}
        step = dict(season=1, manual_picks=first['manual_picks'], dropped=[p.id for p in players if p.id not in kept])
        request = dict(season=2, run_seed=1234, career=[step], draft_rounds=6)
        second = career_action('seattle', CareerRequest(action='draft', **request, auto_draft=True))
        self.assertEqual(len(second['manual_picks']), 6)
        self.assertEqual(len(second['profile']['roster']), 44)
        self.assertEqual(second, career_action('seattle', CareerRequest(action='draft', **request, manual_picks=second['manual_picks'])))
        # Use actual Player records to select legal CPU cuts, then send the same user decisions.
        from app.career import replay_career
        context = replay_career('seattle', 1234, ((1, (), tuple(step['manual_picks']), tuple(step['dropped'])),), season=2)
        _, players = build_draft('seattle', 2, 1234, tuple(second['manual_picks']), roster_context=context, draft_rounds=6)
        kept = {p.id for p in cpu_cuts(players)}
        dropped = [p.id for p in players if p.id not in kept]
        cut = career_action('seattle', CareerRequest(action='cuts', **request, manual_picks=second['manual_picks'], dropped=dropped))
        self.assertTrue(cut['can_continue'])
        self.assertEqual(len(cut['profile']['roster']), 38)
        for player in cut['profile']['roster_rules']:
            self.assertGreaterEqual(player['count'], player['minimum'])
        next_step = dict(season=2, draft_rounds=6, manual_picks=second['manual_picks'], dropped=dropped)
        restored = career_action('seattle', CareerRequest(action='profile', season=3, run_seed=1234, career=[step, next_step]))
        self.assertEqual({p['id'] for p in restored['roster']}, kept)
        with self.assertRaises(HTTPException):
            career_action('seattle', CareerRequest(action='cuts', **request, manual_picks=second['manual_picks'][:4]))

    def test_api_rejects_wrong_rounds_and_incomplete_historical_drafts(self):
        for rounds in (0, 5, 7):
            with self.assertRaises(ValidationError): DraftRequest(draft_rounds=rounds)
        for rounds, count in ((4,5),(4,6),(6,4),(6,5)):
            with self.assertRaises(ValidationError):
                CareerStep(season=1, draft_rounds=rounds, manual_picks=['x']*count)
        data = rookie_draft('seattle', DraftRequest(run_seed=1234, draft_rounds=6, auto_draft=True))
        self.assertEqual(data['rounds'], 6)
        self.assertEqual(len(data['profile']['roster']), 44)
        with self.assertRaises(HTTPException):
            rookie_draft('seattle', DraftRequest(run_seed=1234, manual_picks=data['manual_picks']))
