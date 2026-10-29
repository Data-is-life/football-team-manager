from dataclasses import replace
import unittest

from app.attributes import generate_attributes
from app.career import cpu_cuts, offseason, replay_career
from app.development import advance_context, with_rosters, rating_view
from app.draft import build_draft
from app.league import TEAMS
from app.lineups import lineup_context, starter_hierarchy
from app.main import team_profile, career_action, CareerRequest
from app.simulation import ROSTER_RULES, ranked_players, roster_for, team_ratings


class InitialHierarchyTests(unittest.TestCase):
    def test_all_teams_positions_have_a_clear_seeded_initial_hierarchy(self):
        snapshots = []
        for seed in (0, 1234, 5678, 4294967295):
            context = lineup_context((), seed, 4)
            for team in TEAMS:
                original = {p.id:p for p in ranked_players(roster_for(team.id, seed).values())}
                players = dict(context)[team.id]
                self.assertEqual(len(players), 38)
                self.assertEqual(set(original), {p.id for p in players})
                for position, (count, starters) in ROSTER_RULES.items():
                    group = [p for p in players if p.position == position]
                    self.assertEqual(len(group), count)
                    self.assertEqual([p.depth for p in group], list(range(1, count+1)))
                    weakest = group[starters-1].rating
                    minimum_gap = 8 if weakest >= 70 else 1
                    for player in group:
                        before = original[player.id]
                        if player.depth <= starters:
                            self.assertEqual(player, before, 'Initial starters are unchanged')
                        else:
                            self.assertLessEqual(player.rating, weakest-minimum_gap)
                            if position in ('QB','K'):self.assertLessEqual(player.rating, 74)
                            self.assertEqual((player.name,player.age,player.experience), (before.name,before.age,before.experience))
                            self.assertLessEqual(player.rating, before.rating)
                            self.assertEqual(player.attributes, generate_attributes(player.id,position,player.rating,seed))
                            view = rating_view(player,context)
                            self.assertGreaterEqual(view['potential_rating'],player.rating)
                            self.assertEqual(view['rating_change'],0)
            self.assertEqual(context,lineup_context((),seed,4))
            snapshots.append(dict(context)['seattle'])
        self.assertNotEqual(snapshots[0],snapshots[1])

    def test_weak_units_can_compete_and_70_is_the_exact_boundary(self):
        base = list(roster_for('seattle',1234).values())
        for starter_rating in (69,70,90):
            # All players begin equal so every final gap comes from the new rule.
            players = starter_hierarchy([replace(p,rating=starter_rating) for p in base],1234)
            for position, (_,count) in ROSTER_RULES.items():
                group = [p for p in players if p.position == position]
                self.assertTrue(all(p.rating==starter_rating for p in group[:count]))
                for p in group[count:]:
                    gap = starter_rating-p.rating
                    if starter_rating < 70:self.assertIn(gap,range(1,5))
                    elif position not in ('QB','K') or starter_rating == 70:self.assertIn(gap,range(8,15))
                    else:self.assertLessEqual(p.rating,74)

    def test_hierarchy_is_not_reapplied_to_drafted_players_or_existing_rosters(self):
        seed=1234
        original=lineup_context((),seed,3)
        adopted=lineup_context(original,seed,4)
        self.assertEqual(tuple(adopted),tuple(original),'Existing careers are not reshaped')
        context=lineup_context((),seed,4)
        rosters=dict(context)
        qb=next(p for p in rosters['seattle'] if p.position=='QB')
        rookie=replace(qb,id='rookie-1234-2-999',rating=99,age=22,experience=0,depth=3)
        rosters['seattle']=(*rosters['seattle'],rookie)
        drafted=with_rosters(context,tuple(rosters.items()))
        next_year=advance_context(drafted,seed,2)
        self.assertEqual(next_year.lineup_rules,4)
        starting_qb=roster_for('seattle',seed,next_year)['QB1']
        self.assertEqual(starting_qb.id,rookie.id)
        self.assertEqual(starting_qb.rating,99)
        self.assertEqual(advance_context(next_year,seed,2),next_year)
        with self.assertRaises(ValueError):lineup_context(next_year,seed,3,2)

    def test_draft_cuts_and_next_season_replay_keep_the_initial_rules(self):
        seed=1234
        context=lineup_context((),seed,4)
        choices=[]
        for _ in range(4):
            data,_=build_draft('seattle',1,seed,tuple(choices),(),context)
            choices.append(data['available'][0]['id'])
        data,players=build_draft('seattle',1,seed,tuple(choices),(),context)
        retained={p.id for p in cpu_cuts(players)}
        drops=tuple(p.id for p in players if p.id not in retained)
        _,finished=offseason('seattle',1,seed,tuple(choices),drops,(),context)
        expected=advance_context(finished,seed,2)
        step=(1,(),tuple(choices),drops,4)
        replayed=replay_career('seattle',seed,(step,),4,2)
        self.assertEqual(replayed,expected)
        self.assertEqual(replayed.lineup_rules,4)
        self.assertEqual(len(dict(replayed)['seattle']),38)
        profile=career_action('seattle',CareerRequest(action='profile',season=2,run_seed=seed,lineup_rules=4,
            career=[dict(season=1,manual_picks=choices,dropped=drops,lineup_rules=4)]))
        self.assertEqual(profile['lineup_rules'],4)
        self.assertEqual({p['id'] for p in profile['roster']},retained)
        self.assertEqual(profile['ratings']['offense'],team_ratings('seattle',seed,replayed).offense)

    def test_new_profiles_use_hierarchy_while_legacy_profiles_remain_distinct(self):
        new=team_profile('seattle',1234,4)
        self.assertEqual(new['lineup_rules'],4)
        old=team_profile('seattle',1234,3)
        self.assertNotEqual(new,old)
        self.assertEqual(old,team_profile('seattle',1234,3))
        self.assertEqual(new,career_action('seattle',CareerRequest(action='profile',run_seed=1234,lineup_rules=4)))


if __name__=='__main__':unittest.main()
