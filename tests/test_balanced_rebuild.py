from dataclasses import replace
from unittest.mock import patch
import unittest

from app.attributes import generate_attributes
from app.development import advance_context, rating_view, with_rosters
from app.league import TEAMS
from app.lineups import initial_hierarchy, lineup_context
from app.main import CareerRequest, career_action, team_profile
from app.simulation import ROSTER_RULES, roster_for, team_ratings


class BalancedRebuildTests(unittest.TestCase):
    def test_every_city_starts_within_70_plus_or_minus_two(self):
        for seed in (0,1234,5678,4294967295):
            normal=dict(initial_hierarchy(seed))
            for team in TEAMS:
                context=lineup_context((),seed,6,rebuild_team=team.id)
                ratings=team_ratings(team.id,seed,context)
                self.assertIn(ratings.offense,range(68,73))
                self.assertIn(ratings.defense,range(68,73))
                world=dict(context)
                for other in TEAMS:
                    if other.id!=team.id:self.assertEqual(world[other.id],normal[other.id])
                old={p.id:p for p in normal[team.id]}
                players=world[team.id]
                self.assertEqual(len(players),38)
                for p in players:
                    self.assertEqual((p.name,p.age,p.experience),(old[p.id].name,old[p.id].age,old[p.id].experience))
                    self.assertEqual(p.attributes,generate_attributes(p.id,p.position,p.rating,seed))
                    self.assertGreaterEqual(rating_view(p,context)['potential_rating'],p.rating)
                for position,(count,starters) in ROSTER_RULES.items():
                    group=[p for p in players if p.position==position]
                    self.assertEqual(len(group),count)
                    self.assertEqual([p.depth for p in group],list(range(1,count+1)))
                    self.assertTrue(all(71<=p.rating<=73 for p in group[:starters]))
                    self.assertTrue(all(57<=p.rating<=64 for p in group[starters:]))
                    self.assertLessEqual(max(p.rating for p in group[starters:]),min(p.rating for p in group[:starters])-8)
                self.assertEqual(context,lineup_context((),seed,6,rebuild_team=team.id))

    def test_existing_rebuilds_are_distinct_and_not_upgraded(self):
        for rules in (4,5):
            old=lineup_context((),1234,rules,rebuild_team='seattle')
            old_rating=team_ratings('seattle',1234,old)
            self.assertLess(old_rating.offense,68)
            next_year=advance_context(old,1234,2)
            self.assertEqual(next_year.lineup_rules,rules)
            self.assertEqual(old,lineup_context((),1234,rules,rebuild_team='seattle'))
        new=lineup_context((),1234,6,rebuild_team='seattle')
        self.assertNotEqual(dict(new)['seattle'],dict(old)['seattle'])
        self.assertNotEqual(new,lineup_context((),5678,6,rebuild_team='seattle'))

    def test_later_seasons_are_not_rebalanced_and_rookies_can_exceed_the_target(self):
        context=lineup_context((),1234,6,rebuild_team='seattle')
        rosters=dict(context)
        base=next(p for p in rosters['seattle'] if p.position=='QB')
        rookie=replace(base,id='rookie-1234-2-999',rating=95,age=22,experience=0,depth=3)
        rosters['seattle']=(*rosters['seattle'],rookie)
        drafted=with_rosters(context,tuple(rosters.items()))
        with patch('app.lineups.rebuild_lineups',side_effect=AssertionError('Rebalance must run only at creation')):
            second=advance_context(drafted,1234,2)
        self.assertEqual(roster_for('seattle',1234,second)['QB1'].rating,95)
        self.assertEqual(second.lineup_rules,6)
        self.assertEqual(second,advance_context(second,1234,2))

    def test_profile_and_career_requests_share_the_balanced_world(self):
        profile=team_profile('seattle',1234,6,1,1,'seattle')
        self.assertEqual(profile['lineup_rules'],6)
        self.assertEqual(profile,career_action('seattle',CareerRequest(action='profile',run_seed=1234,lineup_rules=6,rebuild_team='seattle')))
        self.assertEqual(profile['ratings'],{'offense':70,'defense':70})
        self.assertEqual(team_profile('miami',1234,6,1,1,'seattle')['roster'],team_profile('miami',1234,5)['roster'])


if __name__=='__main__':unittest.main()
