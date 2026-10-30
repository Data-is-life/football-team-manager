from dataclasses import replace
import unittest
from unittest.mock import patch

from app.career import cpu_cuts, offseason
from app.development import DevelopmentState, next_player, reveal_rookie, advance_context
from app.draft import draft_class, build_draft
from app.lineups import lineup_context
from app.main import CareerRequest, career_action
from app.ratings import rating_payload
from app.simulation import roster_for


def draw(outcome, current=1, potential=2):
    return lambda seed, identity, purpose: outcome if purpose=='rookie-reveal-v1' else current if purpose=='rookie-current-v1' else potential


class RookieRevealTests(unittest.TestCase):
    def setUp(self):
        self.player=replace(next(p for p in draft_class(1,1234) if p.position=='QB'),rating=70)

    def test_outcome_boundaries_and_example_ceiling_swings(self):
        for roll, expected in ((0,'boom'),(14,'boom'),(15,'bust'),(29,'bust'),(30,'normal'),(99,'normal')):
            with self.subTest(roll=roll), patch('app.development.number',side_effect=draw(roll)):
                player,state=next_player(self.player,DevelopmentState(75,70),1234,2,rookie_reassessment=True)
                self.assertEqual(state.rookie_outcome,expected)
                self.assertEqual(player.age,self.player.age);self.assertEqual(player.experience,0)
                self.assertGreaterEqual(state.potential,player.rating)
                if expected=='normal':self.assertEqual((player.rating,state.potential,state.change,state.potential_change),(70,75,0,0))
        with patch('app.development.number',side_effect=draw(0)):
            player,state=reveal_rookie(self.player,DevelopmentState(75,70),1234)
            self.assertEqual((player.rating,state.potential,state.change,state.potential_change),(73,85,3,10))
        with patch('app.development.number',side_effect=draw(15,potential=10)):
            player,state=reveal_rookie(replace(self.player,rating=90),DevelopmentState(95,90),1234)
            self.assertEqual((player.rating,state.potential,state.change,state.potential_change),(70,70,-20,-25))

    def test_bounds_no_double_reveal_and_no_early_or_veteran_reassessment(self):
        for roll in (0,15):
            with patch('app.development.number',side_effect=draw(roll,potential=10)):
                for rating,potential in ((98,99),(45,45),(70,75)):
                    original=replace(self.player,rating=rating)
                    player,state=reveal_rookie(original,DevelopmentState(potential,rating),1234)
                    self.assertTrue(40<=player.rating<=state.potential<=99)
                    self.assertEqual((player,state),reveal_rookie(player,state,9999))
                    self.assertEqual((player,state),next_player(player,state,1234,2,rookie_reassessment=True))
        before,state=next_player(self.player,DevelopmentState(75,70),1234,1,rookie_reassessment=True)
        self.assertEqual(before,self.player);self.assertFalse(state.rookie_revealed)
        veteran=replace(self.player,id='seattle-qb1',experience=0)
        _,state=next_player(veteran,DevelopmentState(75,70),1234,2,rookie_reassessment=True)
        self.assertFalse(state.rookie_revealed)

    def test_kicker_reveal_changes_the_permanent_form_anchor(self):
        kicker=replace(next(p for p in draft_class(1,1234) if p.position=='K'),rating=70)
        with patch('app.development.number',side_effect=draw(0)):
            player,state=next_player(kicker,DevelopmentState(70,70),1234,2,rookie_reassessment=True)
        self.assertEqual((player.rating,state.potential,state.baseline),(73,73,73))
        for year in range(3,10):
            player,state=next_player(player,state,1234,year,rookie_reassessment=True)
            self.assertIn(player.rating,range(69,78));self.assertEqual(state.potential,player.rating)

    def test_all_retained_rookies_reveal_at_entry_and_draft_estimates_stay_frozen(self):
        context=lineup_context((),1234,7,rebuild_team='seattle')
        board,players=build_draft('seattle',1,1234,(),(),context,auto_pick=True)
        old_board=repr(board);old_class=draft_class(1,1234)
        kept={p.id for p in cpu_cuts(players)};drops=tuple(p.id for p in players if p.id not in kept)
        _,closed=offseason('seattle',1,1234,tuple(board['manual_picks']),drops,(),context)
        before={p.id:p for _,roster in closed for p in roster}
        states=dict(closed.development)
        self.assertTrue(all(not states[p.id].rookie_revealed for p in before.values() if p.id.startswith('rookie-')))
        entered=advance_context(closed,1234,2)
        after={p.id:p for _,roster in entered for p in roster};new_states=dict(entered.development)
        rookies=[p for p in before.values() if p.id.startswith('rookie-')]
        self.assertTrue(len(rookies)>4)
        self.assertEqual({new_states[p.id].rookie_outcome for p in rookies},{'boom','bust','normal'})
        for p in rookies:
            actual,state=reveal_rookie(p,states[p.id],1234)
            self.assertEqual(after[p.id].rating,actual.rating)
            self.assertEqual(new_states[p.id].potential,state.potential)
            self.assertEqual(after[p.id].age,p.age);self.assertEqual(after[p.id].experience,0)
            self.assertTrue(new_states[p.id].rookie_revealed)
        self.assertEqual(entered,advance_context(entered,1234,2))
        self.assertEqual(old_class,draft_class(1,1234));self.assertEqual(old_board,repr(board))
        self.assertEqual(board,build_draft('seattle',1,1234,tuple(board['manual_picks']),(),context)[0])
        # An already-entered legacy rookie is not revealed retroactively by a rules-label upgrade.
        old=lineup_context((),1234,6,rebuild_team='seattle')
        old_board,old_players=build_draft('seattle',1,1234,(),(),old,auto_pick=True)
        old_kept={p.id for p in cpu_cuts(old_players)};old_drops=tuple(p.id for p in old_players if p.id not in old_kept)
        _,old_closed=offseason('seattle',1,1234,tuple(old_board['manual_picks']),old_drops,(),old)
        legacy=advance_context(old_closed,1234,2)
        upgraded=advance_context(legacy,1234,2,lineup_rules=7)
        self.assertEqual(legacy.rosters,upgraded.rosters)
        self.assertTrue(all(not state.rookie_revealed for _,state in upgraded.development))

    def test_rating_payload_arrows_and_legacy_payload_compatibility(self):
        context=lineup_context((),1234,7,rebuild_team='seattle')
        player=next(iter(roster_for('seattle',1234,context).values()))
        self.assertIn('potential_change',rating_payload(player,context))
        legacy=lineup_context((),1234,6,rebuild_team='seattle')
        self.assertNotIn('potential_change',rating_payload(player,legacy))
        self.assertNotIn('rookie_outcome',rating_payload(player,legacy))
        # Both the first-season profile and replay APIs accept the versioned rules.
        profile=career_action('seattle',CareerRequest(action='profile',run_seed=1234,lineup_rules=7,rebuild_team='seattle'))
        self.assertEqual(profile['lineup_rules'],7)
        self.assertTrue(all(p['potential_rating']>=p['current_rating'] for p in profile['roster']))
