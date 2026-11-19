from collections import Counter
from dataclasses import asdict
from random import Random
from unittest import TestCase
from app.league import TEAMS,GROUPS,generate_league_schedule,generate_schedule,_generate_league_schedule_cached,_required_matchups,default_standings
from app.lineups import lineup_context
from app.simulation import simulate_league_week,league_week_scores
from app.main import team_schedule
from app.development import advance_context

class VenueStreakTests(TestCase):
 def validate(self,games,season,ranks):
  required,_=_required_matchups(season,ranks)
  self.assertEqual(Counter(tuple(sorted((g.home_id,g.away_id))) for g in games),required)
  for week in range(1,18):
   subset=[g for g in games if g.week==week]
   self.assertEqual(len(subset),15)
   self.assertEqual(Counter(t for g in subset for t in (g.home_id,g.away_id)),Counter(t.id for t in TEAMS))
  for team in TEAMS:
   own=sorted([g for g in games if team.id in (g.home_id,g.away_id)],key=lambda g:g.week)
   venues=[g.home_id==team.id for g in own]
   self.assertIn(sum(venues),(8,9))
   self.assertTrue(all(not(venues[i]==venues[i+1]==venues[i+2]) for i in range(15)),team.id)
   for other in TEAMS:
    if other.group==team.group and other.id!=team.id:
     pair=[g.home_id for g in own if other.id in (g.home_id,g.away_id)]
     self.assertCountEqual(pair,[team.id,other.id])
 def test_rotations_and_shuffled_standings(self):
  for seed in range(6):
   ranks={};rng=Random(seed)
   for group in GROUPS:
    ids=[t.id for t in TEAMS if t.group==group];rng.shuffle(ids)
    ranks.update((t,i+1) for i,t in enumerate(ids))
   for season in (1,2,3,4,5):
    with self.subTest(seed=seed,season=season):self.validate(generate_league_schedule(season,ranks,49),season,ranks)
 def test_cache_clear_replay_legacy_and_upgrade_guard(self):
  ranks=default_standings();a=generate_league_schedule(1,ranks,49);_generate_league_schedule_cached.cache_clear()
  self.assertEqual(a,generate_league_schedule(1,ranks,49))
  old=generate_league_schedule(1,ranks,48)
  self.assertEqual(old,generate_league_schedule(1,ranks,1))
  self.assertNotEqual(a,old)
  root=lineup_context((),1234,48,rebuild_team='seattle')
  with self.assertRaisesRegex(ValueError,'new career'):advance_context(root,1234,2,lineup_rules=49)
 def test_api_and_simulation_use_identical_venues(self):
  context=lineup_context((),1234,49,rebuild_team='seattle')
  api=team_schedule('seattle',season=1,prior_standings=None,lineup_rules=49)
  own=generate_schedule('seattle',lineup_rules=49)
  self.assertEqual(api['games'],[asdict(g) for g in own])
  for week in (1,8,17):
   expected={(g.home_id,g.away_id) for g in generate_league_schedule(lineup_rules=49) if g.week==week}
   games=simulate_league_week(1,week,1234,roster_context=context)
   self.assertEqual(expected,{(g['home']['team']['id'],g['away']['team']['id']) for g in games})
   scores=league_week_scores(1,week,1234,roster_context=context)
   self.assertEqual(scores,tuple((g['home']['team']['id'],g['away']['team']['id'],g['home']['score'],g['away']['score']) for g in games))

 def test_reproducible_across_python_hash_seeds(self):
  import os,subprocess,sys
  code="import json;from dataclasses import asdict;from app.league import generate_league_schedule;print(json.dumps([asdict(g) for g in generate_league_schedule(1,lineup_rules=49)]))"
  results=[subprocess.check_output([sys.executable,'-c',code],env={**os.environ,'PYTHONHASHSEED':str(seed)},text=True) for seed in (1,2)]
  self.assertEqual(*results)
