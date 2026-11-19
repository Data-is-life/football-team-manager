from collections import Counter
from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch
from app import cpu_identity as ci
from app.lineups import lineup_context
from app.league import TEAMS
from app.draft import need_aware_pick,draft_class
from app.player_contracts import cpu_contract_priorities
from app.development import advance_context
from app.main import CareerRequest,career_action
from app.simple_offseason import run
from app.career import replay_career
from app.preseason import financial_ready
from simple_offseason_fixtures import simple_fixture

class RedefinedOwnershipTests(TestCase):
 def test_new_names_preserve_seeded_eras_and_patient_policy(self):
  old=lineup_context((),1234,46,rebuild_team='seattle');new=lineup_context((),1234,47,rebuild_team='seattle')
  self.assertEqual(Counter(ci.for_team(new,t.id,1).kind for t in TEAMS if t.id!='seattle'),{'patient':10,'expensive_peaks':10,'talent_hoarder':9})
  mapping={'patient':'patient','reactive':'expensive_peaks','gambler':'talent_hoarder'}
  for team in TEAMS:
   if team.id=='seattle':continue
   for year in (1,2,24,25,48,70):
    a=ci.for_team(old,team.id,year);b=ci.for_team(new,team.id,year)
    self.assertEqual(replace(a,kind=mapping[a.kind]),b)
    if a.kind=='patient':self.assertEqual(a,b)
  self.assertIsNone(ci.for_team(new,'seattle',2))
  with self.assertRaisesRegex(ValueError,'new career'):advance_context(old,1234,2,lineup_rules=47)

 def test_target_age_windows(self):
  for pos,age in (('QB',33),('RB',27),('OL',31)):
   p=replace(draft_class(1,1234,47)[0],position=pos)
   self.assertEqual(ci.peak_age(pos),age)
   for delta in (-2,-1,0,1,2):self.assertEqual(ci.peak_window(replace(p,age=age+delta)),abs(delta)<=1)

 def test_hoarder_drafts_best_current_despite_filled_position(self):
  root=lineup_context((),1234,47,rebuild_team='seattle')
  owner=next(t.id for t in TEAMS if t.id!='seattle' and ci.for_team(root,t.id,2).kind=='talent_hoarder')
  players=dict(root)[owner];template=draft_class(1,1234,47)[0]
  qb=replace(template,id='best-qb',position='QB',rating=90);wr=replace(template,id='needed-wr',position='WR',rating=80)
  self.assertEqual(need_aware_pick([qb,wr],players,{'QB':5},root,owner=owner),qb)

 def test_hoarder_retention_values_backups_without_price_penalty(self):
  root=lineup_context((),1234,47,rebuild_team='seattle');p=dict(root)['dallas'][0]
  a=replace(p,id='a',position='QB',rating=85);b=replace(a,id='b',depth=2,contract=replace(a.contract,annual_salary=a.contract.annual_salary*2))
  # Match potential to isolate the absence of depth and salary penalties.
  with patch('app.player_contracts.contract_potential',return_value=90),patch.object(ci,'for_team',return_value=ci.Identity('talent_hoarder',1,26,(),False)):
   values=cpu_contract_priorities([a,b],root,1,owner='dallas')
  self.assertEqual(values['a'],values['b'])

 def test_real_offseason_hidden_legal_and_saved_replay(self):
  f=simple_fixture(47);args=f['request'];own=f['actions']
  with patch.object(ci,'peak_window',wraps=ci.peak_window) as hook:
   data=career_action('seattle',CareerRequest(action='free_agency',own_actions=own,free_agency=[dict(kind='finish')],**args))
   self.assertGreater(hook.call_count,0)
  for text in ('patient','expensive_peaks','talent_hoarder','ownership'):self.assertNotIn(text,str(data))
  plan=data['payroll_floor_adjustment'];review=(('raise',plan['player_id']),) if plan else ()
  root=lineup_context((),1234,47,rebuild_team='seattle');choices=tuple(args['manual_picks']);ownlog=tuple((a['kind'],a['player_id']) for a in own)
  _,context=run('seattle',1,1234,choices,(),root,6,ownlog,(('finish',''),),review,(('finish','','',''),))
  for owner,players in context:self.assertTrue(financial_ready(players,context,owner),owner)
  step=(1,(),choices,(),47,(),6,(),(('finish',''),),review,(),(('finish','','',''),),ownlog)
  replay_career.cache_clear();self.assertEqual(context,replay_career('seattle',1234,(step,),47,2,1,'seattle'))
