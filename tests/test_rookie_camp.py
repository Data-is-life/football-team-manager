from collections import Counter
from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch

from app.career import cpu_cuts, offseason
from app.development import DevelopmentState, advance_context, next_player, reveal_rookie
from app.draft import build_draft, draft_class
from app.lineups import lineup_context
from app.main import CareerRequest, career_action
from app.attributes import generate_attributes


def draws(roll, camp=0):
    return lambda seed, identity, purpose: roll if purpose in ('rookie-reveal-v1','rookie-reveal-v2') else camp if purpose=='rookie-camp-v1' else 0


class RookieCampTests(TestCase):
    def setUp(self):
        self.player = replace(next(p for p in draft_class(1,1234) if p.position=='QB'),rating=70)

    def test_exact_twenty_five_seventy_five_outcome_boundaries(self):
        outcomes = Counter()
        for roll in range(100):
            with patch('app.development.number',side_effect=draws(roll)):
                player,state = next_player(self.player,DevelopmentState(75,70),1234,2,rookie_reassessment=True,preseason_growth=True)
            outcomes[state.rookie_outcome] += 1
            self.assertEqual((player.age,player.experience),(self.player.age,0))
            self.assertLessEqual(player.rating,state.potential)
            if state.rookie_outcome=='normal':
                self.assertEqual((player.rating,state.potential,state.change,state.potential_change),(71,75,1,0))
        self.assertEqual(outcomes,{'boom':20,'bust':5,'normal':75})

    def test_all_non_kicker_positions_have_bounded_camp_growth_without_raising_potential(self):
        for position in ('QB','WR','TE','RB','OL','DL','LB','CB','S'):
            original=replace(next(p for p in draft_class(1,1234) if p.position==position),rating=70)
            for camp in (0,1):
                with patch('app.development.number',side_effect=draws(99,camp)):
                    player,state=reveal_rookie(original,DevelopmentState(75,70),1234,True)
                self.assertEqual(player.rating,71+camp)
                self.assertEqual(state.potential,75)
                self.assertEqual(player.attributes,generate_attributes(player.id,position,player.rating,1234))
                self.assertEqual((player,state),reveal_rookie(player,state,1234,True))
        for rating,potential,expected in ((98,99,99),(99,99,99),(70,70,70)):
            with patch('app.development.number',side_effect=draws(99,1)):
                player,state=reveal_rookie(replace(self.player,rating=rating),DevelopmentState(potential,rating),1234,True)
            self.assertEqual(player.rating,expected)
            self.assertEqual(state.potential,potential)

    def test_booms_gain_after_assessment_busts_remain_net_declines_and_kickers_keep_form_model(self):
        with patch('app.development.number',side_effect=draws(0,1)):
            player,state=reveal_rookie(self.player,DevelopmentState(75,70),1234,True)
        self.assertEqual((player.rating,state.potential,state.change,state.potential_change),(74,83,4,8))
        with patch('app.development.number',side_effect=draws(20,1)):
            player,state=reveal_rookie(self.player,DevelopmentState(99,70),1234,True)
        self.assertEqual((player.rating,state.potential,state.change),(69,84,-1))
        kicker=replace(next(p for p in draft_class(1,1234) if p.position=='K'),rating=70)
        for roll,expected in ((0,72),(20,55),(99,70)):
            with patch('app.development.number',side_effect=draws(roll,1)):
                player,state=reveal_rookie(kicker,DevelopmentState(70,70),1234,True)
            self.assertEqual((player.rating,state.potential,state.baseline),(expected,expected,expected))

    def test_version_upgrade_is_entry_only_and_repeated_profiles_cannot_apply_camp_twice(self):
        base=lineup_context((),1234,7,rebuild_team='seattle')
        board,players=build_draft('seattle',1,1234,auto_pick=True,roster_context=base,draft_rounds=6)
        kept={p.id for p in cpu_cuts(players)}
        drops=tuple(p.id for p in players if p.id not in kept)
        _,closed=offseason('seattle',1,1234,tuple(board['manual_picks']),drops,(),base,6)
        entered=advance_context(closed,1234,2,lineup_rules=8)
        before={p.id:p for _,roster in closed for p in roster};after={p.id:p for _,roster in entered for p in roster}
        for identity,player in before.items():
            if not identity.startswith('rookie-'):continue
            actual,state=reveal_rookie(player,dict(closed.development)[identity],1234,True)
            self.assertEqual(after[identity],replace(actual,depth=after[identity].depth))
            self.assertEqual(dict(entered.development)[identity],replace(state,rotation_share=dict(entered.development)[identity].rotation_share))
        self.assertEqual(entered,advance_context(entered,1234,2,lineup_rules=8))
        legacy=advance_context(closed,1234,2,lineup_rules=7)
        upgrade=advance_context(legacy,1234,2,lineup_rules=8)
        self.assertEqual(legacy.rosters,upgrade.rosters)
        self.assertEqual(legacy.development,upgrade.development)
        # Actual request replay stays identical throughout weekly play, including rookies.
        step=dict(season=1,lineup_rules=7,draft_rounds=6,manual_picks=board['manual_picks'],dropped=list(drops))
        body=dict(run_seed=1234,season=2,lineup_rules=8,rebuild_team='seattle',career=[step])
        profile=career_action('seattle',CareerRequest(action='profile',**body))
        for week in (1,8,17):
            career_action('seattle',CareerRequest(action='week',week=week,**body))
            self.assertEqual(profile,career_action('seattle',CareerRequest(action='profile',**body)))

    def test_initial_exp_zero_players_and_unentered_rookies_do_not_receive_camp(self):
        initial=replace(self.player,id='seattle-qb1',experience=0)
        for original,season in ((initial,1),(self.player,1)):
            player,state=next_player(original,DevelopmentState(75,70),1234,season,rookie_reassessment=True,preseason_growth=True)
            self.assertEqual(player,original)
            self.assertFalse(state.rookie_revealed)
