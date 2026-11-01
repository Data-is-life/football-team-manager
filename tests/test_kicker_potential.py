from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch
from app.development import initial_state, next_player, advance_context, rating_view
from app.lineups import lineup_context
from app.draft import draft_class
from app.main import career_action, CareerRequest
from app.simulation import roster_for


class KickerPotentialTests(TestCase):
    def setUp(self):
        self.player = replace(next(p for p in roster_for('seattle',1234).values() if p.position=='K'),age=23,rating=70)

    def test_young_ceiling_growth_form_and_cap(self):
        state=initial_state(self.player,1234,True)
        self.assertIn(state.potential,range(76,89))
        player=self.player
        for season in range(2,9):
            old=state.baseline
            player,state=next_player(player,state,1234,season,kicker_potential=True)
            if player.age<=29:self.assertIn(state.baseline-old,(1,2))
            else:self.assertEqual(state.baseline,old)
            self.assertLessEqual(player.rating,state.potential)
            self.assertLessEqual(abs(player.rating-state.baseline),4)
        capped=replace(state,potential=71,baseline=70)
        _,capped=next_player(self.player,capped,1234,2,kicker_potential=True)
        self.assertEqual(capped.baseline,71)

    def test_prime_anchor_and_old_decline_do_not_accumulate_form(self):
        player=replace(self.player,age=30)
        state=initial_state(player,1234,True)
        with patch('app.development.longevity',return_value=(0,False)):
            for season in range(2,7):
                player,state=next_player(player,state,1234,season,kicker_potential=True)
                self.assertEqual(state.baseline,70)
            player=replace(player,age=36)
            for season in range(7,15):
                old=state.baseline
                player,state=next_player(player,state,1234,season,kicker_potential=True)
                self.assertIn(old-state.baseline,(1,2) if player.age<40 else (3,4))
                self.assertEqual(state.potential,player.rating)
                self.assertLessEqual(abs(player.rating-state.baseline),4)

    def test_rookie_assessment_retains_potential_camp_and_anchor_once(self):
        rookie=replace(next(p for p in draft_class(1,1234) if p.position=='K'),rating=70)
        for roll,outcome in ((0,'boom'),(20,'bust'),(99,'normal')):
            state=replace(initial_state(rookie,1234,True),potential=85)
            def draw(seed,identity,purpose):
                return roll if purpose=='rookie-reveal-v2' else 0
            with patch('app.development.number',side_effect=draw):
                player,result=next_player(rookie,state,1234,2,rookie_reassessment=True,preseason_growth=True,kicker_potential=True)
            self.assertEqual(result.rookie_outcome,outcome)
            self.assertEqual(result.baseline,player.rating)
            self.assertLessEqual(player.rating,result.potential)
            self.assertEqual((player.age,player.experience),(rookie.age,0))
            self.assertEqual(result.potential_change,result.potential-85)
            self.assertEqual((player,result),next_player(player,result,1234,2,rookie_reassessment=True,preseason_growth=True,kicker_potential=True))
            if outcome=='normal':self.assertEqual((player.rating,result.potential),(71,85))
            if outcome=='boom':self.assertGreater(result.potential,85)
            if outcome=='bust':self.assertLess(result.potential,85)

    def test_upgrade_waits_for_transition_and_weekly_profiles_are_stable(self):
        old=lineup_context((),1234,8,rebuild_team='seattle')
        upgraded=advance_context(old,1234,1,lineup_rules=9)
        self.assertEqual(old.development,upgraded.development)
        self.assertEqual(old.rosters,upgraded.rosters)
        entered=advance_context(old,1234,2,lineup_rules=9)
        self.assertEqual(entered,advance_context(entered,1234,2,lineup_rules=9))
        old_states=dict(old.development)
        for _,players in entered:
            for p in players:
                if p.position!='K':continue
                state=dict(entered.development)[p.id]
                self.assertTrue(state.kicker_development)
                self.assertEqual(state.potential_change,state.potential-old_states[p.id].potential)
                self.assertLessEqual(p.rating,state.potential)
        board=career_action('seattle',CareerRequest(action='draft',run_seed=1234,lineup_rules=9,rebuild_team='seattle'))
        self.assertTrue(all(p['potential_rating']>p['current_rating'] for p in board['available'] if p['position']=='K'))
        body=dict(run_seed=1234,lineup_rules=9,rebuild_team='seattle')
        profile=career_action('seattle',CareerRequest(action='profile',**body))
        for week in (1,8,17):
            career_action('seattle',CareerRequest(action='week',week=week,**body))
            self.assertEqual(profile,career_action('seattle',CareerRequest(action='profile',**body)))
        self.assertTrue(any(p['potential_rating']>p['current_rating'] for p in profile['roster'] if p['position']=='K'))

    def test_longevity_delays_decline_without_guaranteeing_talent(self):
        player=replace(self.player,age=36,rating=60)
        state=replace(initial_state(player,1234,True),potential=70)
        with patch('app.development.longevity',return_value=(4,True)):
            _,result=next_player(player,state,1234,2,kicker_potential=True)
        self.assertEqual(result.baseline,60)
        self.assertEqual(result.potential,70)
        with patch('app.development.longevity',return_value=(0,False)):
            _,result=next_player(player,state,1234,2,kicker_potential=True)
        self.assertLess(result.baseline,60)
