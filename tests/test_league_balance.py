from statistics import mean, pstdev
from unittest import TestCase
from unittest.mock import patch

from app.attributes import generate_attributes
from app.development import advance_context
from app.league import TEAMS
from app.league_balance import opponent_targets
from app.lineups import lineup_context
from app.main import CareerRequest, career_action
from app.simulation import team_ratings


class LeagueBalanceTests(TestCase):
    def test_seeded_normal_targets_center_and_spread(self):
        owners = tuple(sorted(t.id for t in TEAMS if t.id != 'seattle'))
        sample = []
        for seed in range(200):
            targets = opponent_targets(seed, owners)
            self.assertEqual(targets, opponent_targets(seed, owners))
            self.assertEqual(mean(o for _,o,_ in targets),75)
            self.assertEqual(mean(d for _,_,d in targets),75)
            self.assertTrue(all(60<=o<=90 and 60<=d<=90 for _,o,d in targets))
            sample.extend((o+d)/2 for _,o,d in targets)
        self.assertGreater(pstdev(sample),3.5);self.assertLess(pstdev(sample),4.5)
        self.assertGreater(sum(abs(x-75)<=4 for x in sample)/len(sample),.63)
        self.assertLess(sum(abs(x-75)<=4 for x in sample)/len(sample),.78)
        self.assertGreater(sum(abs(x-75)<=8 for x in sample)/len(sample),.93)
        self.assertNotEqual(opponent_targets(1,owners),opponent_targets(2,owners))

    def test_actual_ratings_match_targets_and_managed_team_is_unchanged(self):
        for seed in (0,1234,5678,4294967295):
            for owner in ('seattle','las-vegas','miami'):
                old=lineup_context((),seed,11,rebuild_team=owner)
                new=lineup_context((),seed,12,rebuild_team=owner)
                self.assertEqual(dict(new)[owner],dict(old)[owner])
                own=team_ratings(owner,seed,new)
                self.assertTrue(68<=own.offense<=72 and 68<=own.defense<=72)
                targets={team:(o,d) for team,o,d in opponent_targets(seed,tuple(sorted(t.id for t in TEAMS if t.id!=owner)))}
                for team,players in new:
                    self.assertEqual(len(players),31)
                    prior={p.id:p for p in dict(old)[team]}
                    self.assertEqual(set(prior),{p.id for p in players})
                    if team==owner:continue
                    ratings=team_ratings(team,seed,new)
                    self.assertEqual((ratings.offense,ratings.defense),targets[team])
                    for p in players:
                        self.assertEqual((p.name,p.position,p.age,p.experience),(prior[p.id].name,prior[p.id].position,prior[p.id].age,prior[p.id].experience))
                        self.assertEqual(p.attributes,generate_attributes(p.id,p.position,p.rating,seed))
                        state=dict(new.development)[p.id]
                        self.assertGreaterEqual(state.potential,p.rating)
                self.assertEqual(old,lineup_context((),seed,11,rebuild_team=owner))

    def test_existing_compact_career_upgrades_once_between_seasons(self):
        old=lineup_context((),1234,11,rebuild_team='seattle')
        expected=advance_context(old,1234,2,lineup_rules=11)
        upgraded=advance_context(old,1234,2,lineup_rules=12)
        self.assertEqual(dict(expected)['seattle'],dict(upgraded)['seattle'])
        own_ids={p.id for p in dict(expected)['seattle']}
        self.assertEqual({k:v for k,v in expected.development if k in own_ids},{k:v for k,v in upgraded.development if k in own_ids})
        for team,players in upgraded:
            self.assertEqual({p.id for p in players},{p.id for p in dict(expected)[team]})
            if team=='seattle':continue
            before={p.id:p for p in dict(expected)[team]}
            old_states=dict(expected.development);states=dict(upgraded.development)
            for p in players:
                self.assertEqual(states[p.id].change,old_states[p.id].change+p.rating-before[p.id].rating)
                self.assertGreaterEqual(states[p.id].potential,p.rating)
        with self.assertRaisesRegex(ValueError,'next season'):
            advance_context(old,1234,1,lineup_rules=12)
        with patch('app.league_balance.balance_existing_context',side_effect=AssertionError('Must not rebalance every year')):
            third=advance_context(upgraded,1234,3,lineup_rules=12)
        self.assertEqual(third.lineup_rules,12)
        self.assertEqual(advance_context(upgraded,1234,2,lineup_rules=12),upgraded)

    def test_profiles_scouting_and_standings_share_the_same_world(self):
        args=dict(run_seed=1234,lineup_rules=12,rebuild_team='seattle')
        final=career_action('seattle',CareerRequest(action='week',week=17,**args))
        for group in final['standings']['groups']:
            for row in group['teams']:
                profile=career_action('seattle',CareerRequest(action='profile',view_team=row['team']['id'],**args))
                self.assertEqual(profile['ratings'],row['ratings'])
                self.assertEqual(len(profile['roster']),31)
