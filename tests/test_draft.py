import copy
from collections import Counter
import unittest

from fastapi import HTTPException
from app.draft import build_draft, draft_class, draft_order
from app.league import TEAMS, TEAM_BY_ID
from app.main import DraftRequest, rookie_draft
from app.playoffs import postseason_snapshot
from app.simulation import ROSTER_RULES, roster_for
from app.standings import standings_through_week
from app.attributes import attribute_keys


class DraftTests(unittest.TestCase):
    def test_rookie_class_is_stable_unique_and_has_position_attributes(self):
        original = draft_class(1, 1234)
        self.assertEqual(len(original), 200)
        self.assertEqual(len({p.id for p in original}), 200)
        self.assertEqual(len({p.name for p in original}), 200)
        self.assertEqual(original, draft_class(1, 1234))
        self.assertNotEqual(original, draft_class(2, 1234))
        self.assertNotEqual(original, draft_class(1, 5678))
        self.assertEqual(set(p.position for p in original), set(ROSTER_RULES))
        existing_ids = {p.id for t in TEAMS for p in roster_for(t.id, 1234).values()}
        for p in original:
            self.assertNotIn(p.id, existing_ids)
            self.assertEqual(p.experience, 0)
            self.assertIn(p.age, range(21, 25))
            self.assertIn(p.rating, range(45, 91))
            for key in attribute_keys(p.position):
                self.assertIn(getattr(p.attributes, key), range(1, 100))

    def test_draft_order_follows_playoff_finish_then_worst_record(self):
        for seed in (0, 1234):
            order = draft_order(1, seed)
            ids = [entry['team']['id'] for entry in order]
            self.assertEqual(len(ids), 30)
            self.assertEqual(set(ids), set(TEAM_BY_ID))
            postseason = postseason_snapshot(1, 4, seed)
            field = {row['team']['id'] for row in postseason['field']}
            self.assertEqual(set(ids[:16]), set(TEAM_BY_ID) - field)
            offset = 16
            for r in postseason['rounds']:
                losers = {game['away']['team']['id'] if game['winner']['team']['id'] == game['home']['team']['id']
                          else game['home']['team']['id'] for game in r['games']}
                self.assertEqual(set(ids[offset:offset + len(losers)]), losers)
                offset += len(losers)
            self.assertEqual(ids[-1], postseason['champion']['team']['id'])
            rows = {row['team']['id']: row for group in standings_through_week(1, 17, seed)['groups'] for row in group['teams']}
            def key(t):
                row = rows[t]
                return row['wins'] * 2 + row['ties'], row['point_differential'], row['points_for']
            self.assertEqual([key(t) for t in ids[:16]], sorted(key(t) for t in ids[:16]))

    def test_first_middle_and_last_teams_finish_four_rounds_without_duplicate_picks(self):
        # First, middle, and last pick exercise CPU runs before/after all four turns.
        order = draft_order(1, 1234)
        pristine = {t.id: list(roster_for(t.id, 1234).values()) for t in TEAMS}
        for entry in (order[0], order[14], order[-1]):
            team = entry['team']['id']
            choices = []
            old_picks = []
            for turn in range(5):
                state, roster = build_draft(team, 1, 1234, tuple(choices))
                self.assertEqual(state['picks'][:len(old_picks)], old_picks)
                self.assertEqual(len(roster), 38 + turn)
                self.assertEqual(roster[:38], pristine[team])
                self.assertEqual(len({p.id for p in roster}), len(roster))
                self.assertEqual(state['complete'], turn == 4)
                if turn < 4:
                    owner = state['order'][(state['next_pick'] - 1) % 30]['team']['id']
                    self.assertEqual(owner, team)
                    self.assertEqual(state['next_round'], turn + 1)
                    choices.append(state['available'][0]['id'])
                    old_picks = copy.deepcopy(state['picks'])
            self.assertEqual(len(state['picks']), 120)
            self.assertEqual(len({p['player']['id'] for p in state['picks']}), 120)
            self.assertEqual(Counter(p['team']['id'] for p in state['picks']), {t.id: 4 for t in TEAMS})
            self.assertEqual([p['team']['id'] for p in state['picks']], [t['team']['id'] for t in order] * 4)
            self.assertEqual(len(state['available']), 80)
            self.assertEqual((state, roster), build_draft(team, 1, 1234, tuple(choices)))
        self.assertEqual(pristine, {t.id: list(roster_for(t.id, 1234).values()) for t in TEAMS})

    def test_invalid_or_unavailable_choices_are_rejected(self):
        owner = draft_order(1, 1234)[-1]['team']['id']
        start, _ = build_draft(owner, 1, 1234)
        taken = start['picks'][0]['player']['id']
        for choices in ((taken,), ('missing',), ('x',) * 2, tuple('abcde')):
            with self.subTest(choices=choices):
                with self.assertRaises(ValueError):
                    build_draft(owner, 1, 1234, choices)
        for season in (0, 999):
            with self.assertRaises(ValueError):
                build_draft(owner, season, 1234)
        with self.assertRaises(HTTPException) as error:
            rookie_draft('unknown', DraftRequest())
        self.assertEqual(error.exception.status_code, 404)

    def test_profile_has_zero_stat_rows_for_each_rookie(self):
        choices = []
        for i in range(5):
            result = rookie_draft('seattle', DraftRequest(run_seed=1234, manual_picks=choices))
            self.assertEqual(len(result['profile']['roster']), 38 + i)
            self.assertEqual(len(result['profile']['roster_stats']['players']), 38 + i)
            self.assertEqual(result['profile']['roster_stats']['games'], 0)
            self.assertEqual(sum(rule['count'] for rule in result['profile']['roster_rules']), 38 + i)
            if i < 4:
                choices.append(result['available'][0]['id'])

    def test_later_season_draft_uses_saved_prior_ranks(self):
        ranks = tuple(sorted((row['team']['id'], row['rank'])
                             for g in standings_through_week(1, 17, 1234)['groups'] for row in g['teams']))
        state, _ = build_draft('seattle', 2, 1234, prior_standings=ranks)
        self.assertEqual(state['draft_season'], 3)
        self.assertEqual(state['order'][-1]['team']['id'], postseason_snapshot(2, 4, 1234, ranks)['champion']['team']['id'])
        self.assertNotEqual(state['available'], build_draft('seattle', 1, 1234)[0]['available'])


if __name__ == '__main__':
    unittest.main()
