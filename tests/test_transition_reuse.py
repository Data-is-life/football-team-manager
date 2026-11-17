"""Caching must preserve replay decisions and isolate mutable API responses."""
from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch

from fastapi import HTTPException

from app.main import CareerRequest, career_action
from benchmarks.profile_restore import clear_caches
from scripts.benchmark_transitions import transition_requests


def call(body):
    return career_action('seattle', CareerRequest(**body))


class TransitionReuseTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.requests = transition_requests(2)

    def test_growing_career_replays_only_the_new_offseason(self):
        from app.simple_offseason import run
        clear_caches()
        call(self.requests['1-start-season'])
        with patch('app.simple_offseason.run', wraps=run) as replay:
            extended = call(self.requests['2-start-season'])
        self.assertEqual(replay.call_count, 1)
        clear_caches()
        self.assertEqual(call(self.requests['2-start-season']), extended)
        invalid = deepcopy(self.requests['2-start-season'])
        invalid['career'][0]['own_actions'].append(dict(kind='finish'))
        with self.assertRaises(HTTPException):
            call(invalid)

    def test_draft_response_and_roster_containers_are_isolated(self):
        from app.career import replay_career
        from app.draft import build_draft
        body = self.requests['1-draft-complete']
        root = replay_career('seattle', 1234, (), 44, 1, 1, 'seattle')
        args = ('seattle', 1, 1234, tuple(body['manual_picks']), (), root)
        first = build_draft(*args, return_league=True, draft_rounds=6)
        expected = deepcopy(first)
        first[0]['picks'][0]['player']['name'] = 'Only this response'
        first[0]['available'].clear()
        first[1]['seattle'].clear()
        self.assertEqual(build_draft(*args, return_league=True, draft_rounds=6), expected)
        self.assertEqual(build_draft(*args, draft_rounds=6)[1], expected[1]['seattle'])

    def test_cached_market_accepts_new_decisions_and_isolates_responses(self):
        body = self.requests['1-own-to-market']
        first = call(body)
        expected = deepcopy(first)
        first['free_agency']['available'].clear()
        first['profile']['roster'].clear()
        self.assertEqual(call(body), expected)
        player = next(p for p in expected['free_agency']['available'] if p['affordable'])
        signed_body = dict(body, free_agency=[dict(kind='sign', player_id=player['id'])])
        signed = call(signed_body)
        self.assertNotIn(player['id'], [p['id'] for p in signed['free_agency']['available']])
        self.assertIn(player['id'], [p['id'] for p in signed['profile']['roster']])
        self.assertEqual(call(body), expected)
        self.assertEqual(call(signed_body), signed)
