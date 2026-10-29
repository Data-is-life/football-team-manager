from dataclasses import replace
import unittest

from fastapi import HTTPException
from app.attributes import generate_attributes
from app.career import cpu_cuts, offseason, replay_career
from app.development import advance_context, initial_state, with_rosters
from app.draft import build_draft
from app.league import TEAMS
from app.lineups import initial_hierarchy, lineup_context
from app.main import team_profile, career_action, CareerRequest, rookie_draft, DraftRequest
from app.simulation import ROSTER_RULES, roster_for, simulate_through_week, team_ratings


class RebuildTests(unittest.TestCase):
    def test_any_selected_city_gets_a_weak_roster_without_weakening_opponents(self):
        for seed in (1234,5678):
            normal=dict(initial_hierarchy(seed))
            for team in TEAMS:
                context=lineup_context((),seed,4,rebuild_team=team.id)
                self.assertEqual(context.rebuild_team,team.id)
                world=dict(context)
                for other in TEAMS:
                    if other.id != team.id:self.assertEqual(world[other.id],normal[other.id])
                players=world[team.id]
                self.assertEqual(len(players),38)
                old={p.id:p for p in normal[team.id]}
                for p in players:
                    self.assertIn(p.rating,range(48,70))
                    self.assertEqual((p.name,p.age,p.experience),(old[p.id].name,old[p.id].age,old[p.id].experience))
                    self.assertEqual(p.attributes,generate_attributes(p.id,p.position,p.rating,seed))
                for position,(count,starters) in ROSTER_RULES.items():
                    group=[p for p in players if p.position==position]
                    self.assertEqual(len(group),count)
                    self.assertEqual([p.depth for p in group],list(range(1,count+1)))
                    self.assertLess(max(p.rating for p in group[starters:]),min(p.rating for p in group[:starters]))
                rating=team_ratings(team.id,seed,context)
                self.assertLess(rating.offense,min(team_ratings(t.id,seed,context).offense for t in TEAMS if t.id!=team.id))
                self.assertLess(rating.defense,min(team_ratings(t.id,seed,context).defense for t in TEAMS if t.id!=team.id))
                self.assertEqual(context,lineup_context((),seed,4,rebuild_team=team.id))

    def test_growth_and_drafted_stars_are_not_capped_again(self):
        context=lineup_context((),1234,4,rebuild_team='seattle')
        rosters=dict(context)
        base=rosters['seattle'][0]
        rookie=replace(base,id='rookie-1234-2-999',rating=95,age=22,experience=0)
        rosters['seattle']=(*rosters['seattle'],rookie)
        drafted=with_rosters(context,tuple(rosters.items()))
        year2=advance_context(drafted,1234,2)
        self.assertEqual(year2.rebuild_team,'seattle')
        self.assertEqual(roster_for('seattle',1234,year2)['QB1'].rating,95)
        self.assertEqual(year2,advance_context(year2,1234,2))
        young=replace(base,age=22,rating=65)
        self.assertGreater(initial_state(young,1234).potential,young.rating)
        with self.assertRaises(ValueError):lineup_context(context,1234,4,rebuild_team='miami')

    def test_api_scouting_and_games_share_the_managed_team_world(self):
        seed=1234
        context=lineup_context((),seed,4,rebuild_team='seattle')
        profile=team_profile('seattle',seed,4,1,1,'seattle')
        self.assertEqual(profile['rebuild_team'],'seattle')
        self.assertEqual(profile,career_action('seattle',CareerRequest(action='profile',run_seed=seed,lineup_rules=4,rebuild_team='seattle')))
        scout=career_action('seattle',CareerRequest(action='profile',view_team='miami',run_seed=seed,lineup_rules=4,rebuild_team='seattle'))
        self.assertEqual(scout,team_profile('miami',seed,4,1,1,'seattle'))
        self.assertEqual(scout['roster'],team_profile('miami',seed,4)['roster'])
        week=career_action('seattle',CareerRequest(action='week',run_seed=seed,lineup_rules=4,rebuild_team='seattle'))
        self.assertEqual(week,simulate_through_week('seattle',1,1,seed,(),context))
        normal=lineup_context((),seed,4)
        legacy=simulate_through_week('seattle',1,1,seed,(),normal)
        self.assertNotEqual(week,legacy)
        self.assertEqual(legacy,simulate_through_week('seattle',1,1,seed,(),normal))
        other=lineup_context((),seed,4,rebuild_team='miami')
        self.assertNotEqual(context,other)
        self.assertNotEqual(hash(context),hash(other))

    def test_draft_cut_replay_and_later_seasons_keep_origin(self):
        seed=1234
        context=lineup_context((),seed,4,rebuild_team='seattle')
        choices=[]
        for _ in range(4):
            data,_=build_draft('seattle',1,seed,tuple(choices),(),context)
            choices.append(data['available'][0]['id'])
        data,players=build_draft('seattle',1,seed,tuple(choices),(),context)
        retained={p.id for p in cpu_cuts(players)}
        drops=tuple(p.id for p in players if p.id not in retained)
        _,finished=offseason('seattle',1,seed,tuple(choices),drops,(),context)
        self.assertEqual(finished.rebuild_team,'seattle')
        expected=advance_context(finished,seed,2)
        replayed=replay_career('seattle',seed,((1,(),tuple(choices),drops,4),),4,2,1,'seattle')
        self.assertEqual(replayed,expected)
        self.assertEqual({p.id for p in dict(replayed)['seattle']},retained)

    def test_invalid_rebuild_origins_are_rejected_and_old_profiles_are_unchanged(self):
        for owner,rules,start in [('unknown',4,1),('',4,1),('seattle',3,1),('seattle',4,2)]:
            with self.assertRaises(HTTPException) as caught:team_profile('seattle',1234,rules,start,start,owner)
            self.assertEqual(caught.exception.status_code,422)
        with self.assertRaises(HTTPException):
            career_action('seattle',CareerRequest(action='profile',run_seed=1234,lineup_rules=4,rebuild_team='miami'))
        with self.assertRaises(HTTPException):
            rookie_draft('seattle',DraftRequest(run_seed=1234,lineup_rules=4,rebuild_team='miami'))
        for rules in (1,2,3,4):
            old=team_profile('seattle',1234,rules)
            self.assertNotIn('rebuild_team',old)
            self.assertEqual(old,team_profile('seattle',1234,rules))


if __name__=='__main__':unittest.main()
