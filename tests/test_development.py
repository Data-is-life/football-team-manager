from dataclasses import replace
import unittest
from unittest.mock import patch

from app.development import CURVES, DevelopmentState, initial_state, longevity, next_player, advance_context, rating_view
from app.lineups import lineup_context
from app.main import team_profile, career_action, CareerRequest
from app.simulation import roster_for, team_ratings


def sample(position, age, rating=70):
    p=next(p for p in roster_for('seattle',1234).values() if p.position==position)
    # Choose an ordinary ager to test baseline curve boundaries.
    for i in range(1000):
        identity=f'ordinary-{position}-{i}'
        if longevity(1234,identity,position)==(0,False):return replace(p,id=identity,age=age,rating=rating)
    raise AssertionError('No ordinary player')


class DevelopmentTests(unittest.TestCase):
    def test_each_position_enters_decline_and_cliff_at_configured_age(self):
        for position,(grow,decline,cliff,loss,hard) in CURVES.items():
            for entering,bounds in ((decline,loss),(cliff,hard)):
                p=sample(position,entering-1)
                updated,state=next_player(p,DevelopmentState(90,70),1234,2)
                self.assertEqual(updated.age,entering)
                self.assertIn(70-updated.rating,range(bounds[0],bounds[1]+1))
                self.assertEqual(state.potential,updated.rating)
                self.assertEqual(state.change,updated.rating-p.rating)
            p=sample(position,grow-1)
            updated,state=next_player(p,DevelopmentState(71,70),1234,2)
            self.assertLessEqual(updated.rating,71)
            self.assertGreaterEqual(updated.rating,70)
            self.assertEqual(state.potential,71)

    def test_long_lived_journeyman_has_no_talent_bonus_and_trait_is_independent(self):
        p=sample('QB',36,60)
        with patch('app.development.longevity',return_value=(0,False)):
            ordinary_ceiling=initial_state(p,1234)
        with patch('app.development.longevity',return_value=(4,True)):
            self.assertEqual(initial_state(p,1234),ordinary_ceiling)
        for i in range(10000):
            identity=f'journeyman-{i}'
            delay,exceptional=longevity(1234,identity,'QB')
            if exceptional:break
        self.assertTrue(exceptional)
        self.assertGreaterEqual(delay,3)
        p=replace(p,id=identity)
        normal=replace(p,id=sample('QB',36).id)
        long_lived,_=next_player(p,DevelopmentState(60,60),1234,2)
        ordinary,_=next_player(normal,DevelopmentState(60,60),1234,2)
        self.assertLessEqual(long_lived.rating,60)
        self.assertGreaterEqual(long_lived.rating,ordinary.rating)
        self.assertEqual(longevity(1234,p.id,'QB'),longevity(1234,replace(p,rating=99).id,'QB'))
        ancient=replace(p,age=48)
        decreased,_=next_player(ancient,DevelopmentState(60,60),1234,2)
        self.assertLess(decreased.rating,60)

    def test_kicker_form_is_anchored_instead_of_random_walk(self):
        p=sample('K',25,70)
        state=initial_state(p,1234)
        ratings=set()
        for season in range(2,32):
            old=p
            p,state=next_player(p,state,1234,season)
            self.assertIn(p.rating,range(66,75))
            self.assertEqual(state.potential,p.rating)
            self.assertEqual(state.change,p.rating-old.rating)
            ratings.add(p.rating)
        self.assertGreater(len(ratings),1)

    def test_once_per_season_replay_fixed_potential_and_stable_ids(self):
        start=lineup_context((),1234,3,1,1)
        with self.assertRaises(ValueError):advance_context(start,5678,2,1)
        year2=advance_context(start,1234,2,1)
        self.assertEqual(year2,advance_context(year2,1234,2,1))
        year3=advance_context(year2,1234,3,1)
        self.assertEqual(year3,advance_context(start,1234,3,1))
        old={p.id:p for _,players in start for p in players}
        self.assertEqual(set(old),{p.id for _,players in year3 for p in players})
        for _,players in year3:
            for p in players:
                self.assertEqual(p.age,old[p.id].age+2)
                self.assertEqual(p.experience,old[p.id].experience+2)
                self.assertIn(p.rating,range(1,100))
                self.assertGreaterEqual(rating_view(p,year3)['potential_rating'],p.rating)

    def test_rookies_do_not_age_or_develop_before_their_first_season(self):
        p=replace(sample('QB',22),id='rookie-1234-2-1',experience=0)
        state=initial_state(p,1234)
        rookie,first=next_player(p,state,1234,2)
        self.assertEqual(rookie,p)
        self.assertEqual(first.change,0)
        second,_=next_player(rookie,first,1234,3)
        self.assertEqual(second.age,23)
        self.assertEqual(second.experience,1)

    def test_legacy_migration_ages_once_and_hidden_traits_are_not_in_api(self):
        legacy=team_profile('seattle',1234,2)
        migrated=team_profile('seattle',1234,3,6,6)
        ages={p['id']:p['age'] for p in legacy['roster']}
        self.assertTrue(all(p['age']==ages[p['id']]+1 for p in migrated['roster']))
        for p in migrated['roster']:
            self.assertIn('rating_change',p)
            self.assertNotIn('longevity',p)
            self.assertNotIn('baseline',p)
            self.assertNotIn('development',p)
        self.assertEqual(legacy,team_profile('seattle',1234,2))
        api=career_action('seattle',CareerRequest(action='profile',run_seed=1234,lineup_rules=3,season=6,development_start=6))
        self.assertEqual(api,migrated)
        self.assertEqual(api['ratings'],{'offense':team_ratings('seattle',1234,lineup_context((),1234,3,6,6)).offense,
                                          'defense':team_ratings('seattle',1234,lineup_context((),1234,3,6,6)).defense})


if __name__=='__main__':unittest.main()
