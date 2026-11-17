"""Hidden policies must affect real decisions and survive calendar-based replay."""
import json
from collections import Counter
from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch
from app import cpu_identity as policies
from app.lineups import lineup_context
from app.player_contracts import cpu_contract_priorities
from app.development import advance_context
from app.league import TEAMS
from app.main import CareerRequest,career_action
from app.draft import build_draft
from app.simple_offseason import run
from app.career import replay_career
from app.preseason import financial_ready
from app.simulation import validate_roster,roster_minimum,roster_limit
from simple_offseason_fixtures import simple_fixture


class IdentityTests(TestCase):
 def test_initial_mix_managed_exclusion_and_staggering(self):
  for seed in (0,1234,91000):
   root=lineup_context((),seed,44,rebuild_team='seattle')
   values=[policies.for_team(root,t.id,1) for t in TEAMS if t.id!='seattle']
   self.assertEqual(Counter(p.kind for p in values),{'patient':10,'reactive':10,'gambler':9})
   self.assertGreater(len({p.end for p in values}),10)
   self.assertIsNone(policies.for_team(root,'seattle',1))
   self.assertIsNone(policies.for_team(root,None,1))
   self.assertTrue(all(p.start<=1<p.end and 20<=p.end-p.start<=25 for p in values))

 def test_full_era_durations_boundaries_and_call_order_independence(self):
  root=lineup_context((),1234,44,rebuild_team='seattle')
  for team in TEAMS:
   if team.id=='seattle':continue
   p=policies.for_team(root,team.id,1)
   for _ in range(4):
    end=policies.for_team(root,team.id,p.end-1);next_=policies.for_team(root,team.id,p.end)
    self.assertEqual((p.kind,p.start,p.end),(end.kind,end.start,end.end))
    if p.kind!='reactive':self.assertEqual(p.focus,end.focus)
    self.assertNotEqual(p.kind,next_.kind);self.assertEqual(next_.start,p.end)
    self.assertTrue(20<=next_.end-next_.start<=25);p=next_
  expected=[policies.for_team(root,'dallas',year) for year in (1,2,23,47,68,100)]
  policies.identity.cache_clear();policies.initial_kinds.cache_clear()
  actual={year:policies.for_team(root,'dallas',year) for year in (100,68,47,23,2,1)}
  self.assertEqual(expected,[actual[y] for y in (1,2,23,47,68,100)])

 def test_legacy_and_managed_priorities_unchanged(self):
  old=lineup_context((),1234,43,rebuild_team='seattle');new=lineup_context((),1234,44,rebuild_team='seattle')
  self.assertEqual(old.rosters,new.rosters)
  for owner in ('seattle','dallas'):
   ps=dict(old)[owner]
   self.assertEqual(cpu_contract_priorities(ps,old,2),cpu_contract_priorities(ps,old,2,owner=owner))
  self.assertEqual(cpu_contract_priorities(dict(old)['seattle'],old,2),cpu_contract_priorities(dict(new)['seattle'],new,2,owner='seattle'))
  self.assertNotEqual(cpu_contract_priorities(dict(new)['dallas'],new,2),cpu_contract_priorities(dict(new)['dallas'],new,2,owner='dallas'))
  with self.assertRaisesRegex(ValueError,'new career'):advance_context(old,1234,2,lineup_rules=44)

 def test_styles_have_different_persistent_and_annual_preferences(self):
  root=lineup_context((),1234,44,rebuild_team='seattle');ps=dict(root)['dallas'];p=ps[0]
  policies_={k:policies.Identity(k,1,26,('QB','OL'),True) for k in policies.KINDS}
  values=[policies.retention_factor(v,p,p.rating+10,1234,'dallas',2) for v in policies_.values()]
  self.assertEqual(len(set(values)),3)
  gambler=policies_['gambler']
  self.assertGreater(policies.market_factor(gambler,p,90,30_000_000,1234,'dallas',2),policies.market_factor(replace(gambler,push=False),p,90,30_000_000,1234,'dallas',2))
  reactive=next(t for t in TEAMS if t.id!='seattle' and policies.for_team(root,t.id,1).kind=='reactive')
  start=policies.for_team(root,reactive.id,1).start
  self.assertGreater(len({policies.for_team(root,reactive.id,y).focus for y in range(max(1,start),policies.for_team(root,reactive.id,1).end)}),1)

 def test_real_offseason_hooks_hidden_payload_legal_rosters_and_exact_replay(self):
  # Spy on the production call path, not replacement functions in defining modules.
  with patch.object(policies,'draft_adjustment',wraps=policies.draft_adjustment) as draft_hook,patch.object(policies,'retention_factor',wraps=policies.retention_factor) as retain_hook,patch.object(policies,'market_factor',wraps=policies.market_factor) as market_hook:
   f=simple_fixture(44);args=f['request'];own=f['actions'];market=[dict(kind='finish')]
   data=career_action('seattle',CareerRequest(action='free_agency',own_actions=own,free_agency=market,**args))
   self.assertGreater(draft_hook.call_count,0);self.assertGreater(retain_hook.call_count,0);self.assertGreater(market_hook.call_count,0)
   self.assertTrue(all(c.args[-2]!='seattle' and c.args[-1]==2 for c in draft_hook.call_args_list))
   self.assertTrue(all(c.args[-2]!='seattle' and c.args[-1]==2 for c in market_hook.call_args_list))
  legacy=lineup_context((),1234,43,rebuild_team='seattle')
  board,_=build_draft('seattle',1,1234,roster_context=legacy,auto_pick=True,draft_rounds=6)
  self.assertTrue(any(a['player']['id']!=b['player']['id'] for a,b in zip(board['picks'],f['own']['picks']) if a['team']['id']!='seattle'))
  serialized=json.dumps(data).lower()
  for word in ('patient','reactive','gambler','personality','ownership','era_end'):self.assertNotIn(word,serialized)
  plan=data['payroll_floor_adjustment'];review=[dict(kind='raise',player_id=plan['player_id'])] if plan else []
  done=career_action('seattle',CareerRequest(action='trades',own_actions=own,free_agency=market,pre_camp_actions=review,trade_actions=[dict(kind='finish')],**args))
  self.assertTrue(done['can_continue'])
  root=lineup_context((),1234,44,rebuild_team='seattle')
  ownlog=tuple((a['kind'],a['player_id']) for a in own);reviewlog=tuple((a['kind'],a['player_id']) for a in review)
  _,context=run('seattle',1,1234,tuple(args['manual_picks']),(),root,6,ownlog,(('finish',''),),reviewlog,(('finish','','',''),))
  for owner,players in context:
   validate_roster(players,minimum_total=roster_minimum(context),maximum_total=roster_limit(context),context=context,owner=owner)
   self.assertTrue(financial_ready(players,context,owner),owner)
  step=(1,(),tuple(args['manual_picks']),(),44,(),6,(),(('finish',''),),reviewlog,(),(('finish','','',''),),ownlog)
  replay_career.cache_clear();self.assertEqual(context,replay_career('seattle',1234,(step,),44,2,1,'seattle'))

 def test_auto_managed_draft_is_excluded_even_without_rebuild_metadata(self):
  root=lineup_context((),1234,44)
  with patch.object(policies,'draft_adjustment',wraps=policies.draft_adjustment) as hook:
   build_draft('seattle',1,1234,roster_context=root,auto_pick=True,draft_rounds=6)
   self.assertGreater(hook.call_count,0)
   self.assertTrue(all(c.args[-2]!='seattle' for c in hook.call_args_list))
