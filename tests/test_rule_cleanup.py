"""Regression snapshots captured from main before the rule cleanup."""
import hashlib
import json
from dataclasses import asdict, is_dataclass
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from unittest import TestCase

from pydantic import TypeAdapter, ValidationError

from simple_offseason_fixtures import simple_fixture
from snapshot_metadata import without_rookie_origin
from app.main import CareerRequest, career_action
from app.lineups import lineup_context
from app.simple_offseason import run


def snapshot_value(value):
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, (Decimal, Fraction)):
        return str(value)
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    raise TypeError(type(value).__name__)


def digest(value):
    encoded = json.dumps(value, sort_keys=True, separators=(',', ':'), default=snapshot_value)
    encoded = json.dumps(json.loads(encoded,object_hook=without_rookie_origin),
                         sort_keys=True,separators=(',', ':'))
    return hashlib.sha256(encoded.encode()).hexdigest()


def snapshot_cases():
    checks = {}
    for rules in (42, 43, 44):
        fixture = simple_fixture(rules)
        args, own = fixture['request'], fixture['actions']
        checks[f'{rules}-own'] = digest(fixture['own'])
        for count in (1, len(own)-1, len(own)):
            payload = career_action('seattle', CareerRequest(
                action='own_players', own_actions=own[:count], **args))
            checks[f'{rules}-own-prefix-{count}'] = digest(payload)
        market = career_action('seattle', CareerRequest(
            action='free_agency', own_actions=own, free_agency=[dict(kind='finish')], **args))
        checks[f'{rules}-market'] = digest(market)
        plan = market['payroll_floor_adjustment']
        review = [dict(kind='raise', player_id=plan['player_id'])] if plan else []
        done = career_action('seattle', CareerRequest(
            action='trades', own_actions=own, free_agency=[dict(kind='finish')],
            pre_camp_actions=review, trade_actions=[dict(kind='finish')], **args))
        checks[f'{rules}-done'] = digest(done)
        root = lineup_context((), 1234, rules, rebuild_team='seattle')
        own_log = tuple((a['kind'], a['player_id']) for a in own)
        review_log = tuple((a['kind'], a['player_id']) for a in review)
        _, context = run('seattle', 1, 1234, tuple(args['manual_picks']), (), root, 6,
                         own_log, (('finish', ''),), review_log, (('finish', '', '', ''),))
        checks[f'{rules}-context'] = digest(context)
    return checks


class RuleCleanupTests(TestCase):
    def test_modern_offseason_payloads_and_saved_contexts_are_unchanged(self):
        expected = json.loads(Path(__file__).with_name('rule_cleanup_baseline.json').read_text())
        self.assertEqual(snapshot_cases(), expected)

    def test_rule_validation_preserves_all_existing_versions(self):
        from app.rules import LineupRules
        adapter = TypeAdapter(LineupRules)
        for version in range(1, 47):
            self.assertEqual(adapter.validate_python(version), version)
        for invalid in (0, 47, '46', None):
            with self.subTest(version=invalid), self.assertRaises(ValidationError):
                adapter.validate_python(invalid)

    def test_salary_potential_matches_display_for_saved_and_missing_states(self):
        from dataclasses import replace
        from app.development import rating_view
        from app.player_contracts import contract_potential
        for rules in (3, 8, 9, 43, 44):
            context = lineup_context((), 1234, rules)
            players = dict(context)['seattle']
            for position in ('QB', 'K'):
                player = next(p for p in players if p.position == position)
                for candidate in (context, replace(context, development=())):
                    with self.subTest(rules=rules, position=position,
                                      saved=bool(candidate.development)):
                        expected = rating_view(player, candidate)['potential_rating']
                        self.assertEqual(contract_potential(player, candidate), expected)
                        self.assertEqual(contract_potential(
                            player, candidate, dict(candidate.development)), expected)
        with self.assertRaises(ValueError):
            contract_potential(player, None)
