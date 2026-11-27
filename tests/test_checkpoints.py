import unittest
from unittest.mock import patch

from app import checkpoints, main
from app.main import CareerRequest, career_action
from simple_offseason_fixtures import simple_fixture


class LeagueCheckpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = simple_fixture(50)
        team = cls.team = 'seattle'
        draft = fixture['request']
        own_actions = fixture['actions']
        market = [{'kind': 'finish'}]
        body = {**draft, 'own_actions': own_actions, 'free_agency': market}
        finished = career_action(team, CareerRequest(action='free_agency', **body))
        plan = finished['payroll_floor_adjustment']
        if plan:
            market.append({'kind': 'raise', 'player_id': plan['player_id']})
        step = dict(season=1, lineup_rules=50, draft_rounds=draft['draft_rounds'],
                    manual_picks=draft['manual_picks'], own_actions=own_actions,
                    free_agency=market, trade_actions=[{'kind': 'finish'}])
        cls.body = dict(season=2, lineup_rules=50, run_seed=draft['run_seed'],
                        rebuild_team=team, career=[step])
        profile = career_action(team, CareerRequest(action='profile', save_checkpoint=True, **cls.body))
        cls.token = profile.pop('checkpoint')
        cls.profile = profile
        cls.week = career_action(team, CareerRequest(action='week', week=3, **cls.body))
        cls.draft = career_action(team, CareerRequest(action='draft', **cls.body))

    def setUp(self):
        checkpoints._restored.clear()

    def tearDown(self):
        checkpoints._restored.clear()

    def test_restore_and_dependent_requests_bypass_career_replay(self):
        with patch('app.main.replay_career', side_effect=AssertionError('Historical replay')):
            restored = career_action(self.team, CareerRequest(
                action='profile', checkpoint=self.token, save_checkpoint=True, **self.body))
            self.assertEqual(restored, self.profile)
            self.assertEqual(career_action(self.team, CareerRequest(action='week', week=3, **self.body)),
                             self.week)
            self.assertEqual(career_action(self.team, CareerRequest(action='draft', **self.body)), self.draft)

    def test_restore_logs_sources_and_timings_without_checkpoint_contents(self):
        restore_id = 'f25cac9b-fb74-4957-a994-a12473ede1b5'
        with self.assertLogs(main.restore_logger, level='INFO') as entries:
            for action, token in (
                ('profile', 'invalid-token-marker'),
                ('profile', self.token),
                ('week', None),
            ):
                career_action(self.team, CareerRequest(
                    action=action, checkpoint=token, restore_id=restore_id,
                    week=3, **self.body,
                ))
        for entry, source in zip(entries.output, (
            'context_source=history_replay checkpoint=rejected',
            'context_source=checkpoint checkpoint=accepted',
            'context_source=memory checkpoint=missing',
        ), strict=True):
            self.assertIn(source, entry)
            self.assertIn(f'id={restore_id}', entry)
            self.assertRegex(entry, r'context_ms=\d+\.\d stage_ms=\d+\.\d')
            self.assertNotIn('invalid-token-marker', entry)
            self.assertNotIn(self.token, entry)

    def test_invalid_token_falls_back_and_is_replaced(self):
        replacement = ('X' if self.token[10] != 'X' else 'Y')
        tampered = self.token[:10] + replacement + self.token[11:]
        with patch('app.main.replay_career', wraps=main.replay_career) as replay:
            refreshed = career_action(self.team, CareerRequest(
                action='profile', checkpoint=tampered, save_checkpoint=True, **self.body))
        replay.assert_called_once()
        self.assertNotEqual(refreshed.pop('checkpoint'), tampered)
        self.assertEqual(refreshed, self.profile)

    def test_checkpoint_is_bound_to_entire_career_and_schema(self):
        step = self.body['career'][0]
        changed_history = {**self.body, 'career': [{**step, 'free_agency': []}]}
        for other in ({**self.body, 'run_seed': self.body['run_seed'] + 1}, changed_history):
            with patch('app.main.replay_career', side_effect=AssertionError('Expected replay')):
                with self.assertRaisesRegex(AssertionError, 'Expected replay'):
                    career_action(self.team, CareerRequest(action='profile', checkpoint=self.token, **other))
        with patch.object(checkpoints, 'CHECKPOINT_VERSION', checkpoints.CHECKPOINT_VERSION + 1):
            with patch('app.main.replay_career', wraps=main.replay_career) as replay:
                restored = career_action(self.team, CareerRequest(
                    action='profile', checkpoint=self.token, **self.body))
            replay.assert_called_once()
            self.assertEqual(restored, self.profile)
