"""The introductory record must be real league history, never a display override."""
from unittest import TestCase
from app.league import generate_schedule, TEAM_BY_ID
from app.lineups import lineup_context
from app.simulation import (inherited_win_weeks, simulate_game, simulate_through_week,
                            league_week_scores)
from app.main import CareerRequest, career_action


class InheritedRecordTests(TestCase):
    def test_seeded_background_record_and_box_score_accounting(self):
        patterns=set()
        for seed in (0,1,5678):
            for owner in ('seattle','dallas','miami'):
                context=lineup_context((),seed,22,rebuild_team=owner)
                games=generate_schedule(owner,season=1)
                results=[simulate_game(owner,g,1,run_seed=seed,roster_context=context) for g in games[:16]]
                self.assertEqual([r['outcome'] for r in results].count('W'),3)
                self.assertEqual([r['outcome'] for r in results].count('L'),13)
                patterns.add(tuple(sorted(inherited_win_weeks(owner,seed))))
                for result in results:
                    for side in ('home','away'):
                        box=result[side]
                        passing=sum(p['touchdowns'] for p in box['passing'])
                        rushing=sum(p['touchdowns'] for p in box['rushing'])
                        self.assertEqual(sum(p['touchdowns'] for p in box['receiving']),passing)
                        self.assertEqual(passing+rushing,box['scoring']['touchdowns'])
                        self.assertEqual(box['score'],7*(passing+rushing)+3*box['scoring']['field_goals'])
                        self.assertEqual(sum(p['kicking_points'] for p in box['kicking']),3*box['scoring']['field_goals']+passing+rushing)
        self.assertGreater(len(patterns),1)

    def test_schedule_opponent_view_league_scores_and_standings_agree(self):
        seed=5678;owner='seattle';context=lineup_context((),seed,22,rebuild_team=owner)
        own_games=generate_schedule(owner,season=1)
        for game in own_games[:16]:
            result=simulate_game(owner,game,1,run_seed=seed,roster_context=context)
            mirror=next(g for g in generate_schedule(game.opponent_id,season=1) if g.week==game.week)
            opposing=simulate_game(game.opponent_id,mirror,1,run_seed=seed,roster_context=context)
            for side in ('home','away'):self.assertEqual(result[side],opposing[side])
            score=next(s for s in league_week_scores(1,game.week,seed,roster_context=context) if owner in s[:2])
            self.assertEqual(score,(result['home']['team']['id'],result['away']['team']['id'],result['home']['score'],result['away']['score']))
        data=simulate_through_week(owner,1,16,seed,roster_context=context)
        self.assertEqual(data['record'],dict(wins=3,losses=13,ties=0))
        rows=[r for group in data['standings']['groups'] for r in group['teams']]
        own=next(r for r in rows if r['team']['id']==owner)
        self.assertEqual((own['wins'],own['losses'],own['ties']),(3,13,0))
        points_for=sum(r['team_score'] for r in data['game_results'])
        points_against=sum(r['opponent_score'] for r in data['game_results'])
        self.assertEqual((own['points_for'],own['points_against']),(points_for,points_against))
        self.assertEqual(sum(r['wins'] for r in rows),sum(r['losses'] for r in rows))
        self.assertEqual(sum(r['points_for'] for r in rows),sum(r['points_against'] for r in rows))
        self.assertTrue(all(r['wins']+r['losses']+r['ties']==16 for r in rows))

    def test_last_game_other_matchups_and_later_seasons_are_unrestricted(self):
        seed=5678
        old=lineup_context((),seed,21,rebuild_team='seattle')
        new=lineup_context((),seed,22,rebuild_team='seattle')
        self.assertEqual(old.rosters,new.rosters)
        for season,owner,week in ((1,'seattle',17),(1,'miami',1),(2,'seattle',1)):
            game=next(g for g in generate_schedule(owner,season=season) if g.week==week and (owner=='seattle' or g.opponent_id!='seattle'))
            self.assertEqual(simulate_game(owner,game,season,run_seed=seed,roster_context=old),
                             simulate_game(owner,game,season,run_seed=seed,roster_context=new))
        old_neutral=lineup_context((),seed,21)
        new_neutral=lineup_context((),seed,22)
        g=generate_schedule('seattle',season=1)[0]
        self.assertEqual(simulate_game('seattle',g,1,run_seed=seed,roster_context=old_neutral),simulate_game('seattle',g,1,run_seed=seed,roster_context=new_neutral))

    def test_api_replay_keeps_new_record_and_does_not_upgrade_existing_games(self):
        args=dict(action='week',season=1,week=16,run_seed=5678,rebuild_team='seattle')
        new=career_action('seattle',CareerRequest(lineup_rules=22,**args))
        self.assertEqual(new['record'],dict(wins=3,losses=13,ties=0))
        self.assertEqual(new,career_action('seattle',CareerRequest(lineup_rules=22,**args)))
        old=career_action('seattle',CareerRequest(lineup_rules=21,**args))
        self.assertNotEqual(old['record'],new['record'])
        self.assertEqual(old,career_action('seattle',CareerRequest(lineup_rules=21,**args)))
