from collections import Counter
from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch
from app.development import DevelopmentState, advance_context, with_rosters, reveal_rookie
from app.draft import draft_class
from app.lineups import lineup_context


class UserRookieOutcomesTests(TestCase):
    def test_exact_odds_and_idempotence(self):
        p = draft_class(1, 1234, 50)[0]
        for user, expected in ((True, {'boom':25,'bust':5,'normal':70}),
                               (False, {'boom':25,'bust':25,'normal':50})):
            counts = Counter()
            for roll in range(100):
                with patch('app.development.number', return_value=roll):
                    out, state = reveal_rookie(p, DevelopmentState(90,p.rating),1234,True,True,True,user)
                    counts[state.rookie_outcome] += 1
                    self.assertEqual(reveal_rookie(out,state,1234,True,True,True,user),(out,state))
            self.assertEqual(counts,expected)

    def test_real_transition_targets_only_managed_roster_and_preserves_legacy(self):
        rookies = draft_class(1,1234,50)[:3]
        for rules in (49,50):
            context = lineup_context((),1234,rules,rebuild_team='seattle')
            rookies = tuple(replace(p,contract=context.rosters[0][1][0].contract) for p in rookies)
            rosters = tuple((owner,players+((rookies[0],) if owner=='seattle' else (rookies[1],) if owner=='boston' else ()))
                            for owner,players in context)
            context = with_rosters(context,rosters)
            context = replace(context,free_agents=(rookies[2],))
            context = with_rosters(context,context.rosters)
            with patch('app.development.number',return_value=30):
                result = advance_context(context,1234,2,lineup_rules=rules)
            states = dict(result.development)
            self.assertEqual(states[rookies[0].id].rookie_outcome,'normal' if rules==50 else 'bust')
            self.assertEqual(states[rookies[1].id].rookie_outcome,'bust')
            self.assertEqual(states[rookies[2].id].rookie_outcome,'bust')
            self.assertEqual(advance_context(result,1234,2,lineup_rules=rules),result)
