"""Compare complete drafts against the pre-cleanup CPU selection policy."""
from dataclasses import asdict
from unittest import TestCase
from unittest.mock import patch

from app.draft import build_draft, cpu_pick
from app.league import TEAMS
from app.lineups import lineup_context
from app.simulation import ROSTER_RULES, roster_for


def original_cpu_pick(available, current, additions, retirement_rules=False):
    quality = {position: sum(p.rating for p in current if p.position == position)
               / max(1, sum(p.position == position for p in current))
               for position in ROSTER_RULES}
    if retirement_rules:
        counts = {position: sum(p.position == position for p in current)
                  for position in ROSTER_RULES}
        shortages = [p for p in available if counts[p.position] < ROSTER_RULES[p.position][1]]
        if shortages:
            available = shortages
    return max(available, key=lambda p: (
        p.rating - .25 * quality[p.position] - 12 * additions.get(p.position, 0),
        p.rating, p.id))


class DraftPolicyParityTests(TestCase):
    def test_empty_short_and_full_rosters_preserve_selection_and_inputs(self):
        players = list(roster_for('seattle', 1234).values())
        available = list(reversed(players))
        additions = {'QB': 2, 'WR': 1}
        for current in ([], players[:3], players):
            before = (list(current), list(available), dict(additions))
            for retirement_rules in (False, True):
                self.assertEqual(cpu_pick(available, current, additions, retirement_rules),
                                 original_cpu_pick(available, current, additions, retirement_rules))
                self.assertEqual((current, available, additions), before)

    def test_complete_drafts_and_rosters_match_original_policy(self):
        # Fixed order isolates selection from the separately tested schedule engine.
        order = [dict(team=asdict(team), record='0–0') for team in TEAMS]
        with patch('app.draft.draft_order', return_value=order):
            for rules, rounds in ((1, 4), (10, 6), (28, 6)):
                for seed in (1234, 5678):
                    with self.subTest(rules=rules, rounds=rounds, seed=seed):
                        context = lineup_context((), seed, rules)
                        kwargs = dict(roster_context=context, draft_rounds=rounds,
                                      auto_pick=True, return_league=True)
                        actual = build_draft('seattle', 1, seed, **kwargs)
                        with patch('app.draft.cpu_pick', side_effect=original_cpu_pick):
                            expected = build_draft('seattle', 1, seed, **kwargs)
                        self.assertEqual(actual, expected)
