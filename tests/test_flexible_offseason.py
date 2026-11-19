from unittest import TestCase
from fastapi import HTTPException
from app.main import career_action,CareerRequest
from app.simple_offseason import _own_phase,_market_phase
from app.preseason import prepare
from app.career import replay_career
from simple_offseason_fixtures import simple_fixture


def flexible_fixture():
 f=simple_fixture(48)
 own=[dict(kind='drop',player_id=p['id']) for p in f['own']['profile']['roster'] if p.get('renewal_offer') or p.get('contract_offer')]
 args={**f['request'],'own_actions':own+[dict(kind='finish',player_id='')]}
 checkpoint={**f['checkpoint'],'ownActions':args['own_actions'],'freeAgency':[]}
 return dict(request=args,checkpoint=checkpoint)

class FlexibleOffseasonTests(TestCase):
 @classmethod
 def setUpClass(cls):cls.f=flexible_fixture()
 def call(self,actions=(),action='free_agency',**extra):
  return career_action('seattle',CareerRequest(action=action,free_agency=actions,**self.f['request'],**extra))
 def test_own_drops_no_refills_signing_below_minimum_and_preview(self):
  args=self.f['request'];own=args['own_actions'][:-1]
  data=career_action('seattle',CareerRequest(action='own_players',**{**args,'own_actions':own[:-1]}))
  before=len(data['profile']['roster']);self.assertLess(before,31)
  target=next(p for p in data['profile']['roster'] if p.get('contract_offer') or p.get('renewal_offer'))
  kind='sign' if target.get('contract_offer') else 'resign'
  signed=career_action('seattle',CareerRequest(action='own_players',**{**args,'own_actions':own[:-1]+[dict(kind=kind,player_id=target['id'])]}))
  self.assertEqual(len(signed['profile']['roster']),before)
  market=self.call();self.assertLess(len(market['profile']['roster']),31)
  kicker=next(p for p in market['profile']['roster'] if p['position']=='K')
  preview=kicker['release_preview'];self.assertTrue(preview['allowed']);self.assertEqual(preview['replacements'],[])
  dropped=self.call([dict(kind='drop',player_id=kicker['id'])]);self.assertEqual(len(dropped['profile']['roster']),len(market['profile']['roster'])-1)
  self.assertFalse(any(p['position']=='K' for p in dropped['profile']['roster']))
  self.assertEqual(dropped['profile']['payroll']['total'],preview['payroll_after'])
 def test_end_market_short_reopen_sign_and_replay_then_start(self):
  market=self.call([dict(kind='finish')]);self.assertLess(len(market['profile']['roster']),31)
  self.assertFalse(market['can_continue']);self.assertTrue(market['free_agency']['available'])
  with self.assertRaises(HTTPException):self.call([dict(kind='finish')],action='trades',trade_actions=[dict(kind='finish')])
  actions=[dict(kind='finish')]
  kicker=next(p for p in market['profile']['roster'] if p['position']=='K');actions.append(dict(kind='drop',player_id=kicker['id']))
  market=self.call(actions);self.assertFalse(market['free_agency']['complete'])
  # Fill required positions first, then total minimum, using ordinary market prices.
  for _ in range(40):
   roster=market['profile']['roster'];rules=market['profile']['roster_rules']
   missing=[r['position'] for r in rules if sum(p['position']==r['position'] for p in roster)<r['minimum']]
   if not missing and len(roster)>=31:break
   available=[p for p in market['free_agency']['available'] if p['affordable'] and (not missing or p['position']==missing[0])]
   self.assertTrue(available,missing)
   selected=min(available,key=lambda p:(p['annual_salary'],p['id']))
   actions.append(dict(kind='sign',player_id=selected['id']));market=self.call(actions)
  self.assertGreaterEqual(len(market['profile']['roster']),31)
  actions.append(dict(kind='finish'));market=self.call(actions)
  plan=market['payroll_floor_adjustment']
  if plan:actions.append(dict(kind='raise',player_id=plan['player_id']));market=self.call(actions)
  _own_phase.cache_clear();_market_phase.cache_clear();prepare.cache_clear()
  self.assertEqual(market,self.call(actions))
  done=self.call(actions,action='trades',trade_actions=[dict(kind='finish')]);self.assertTrue(done['can_continue'])
  step=dict(season=1,**{k:v for k,v in self.f['request'].items() if k not in ('run_seed','rebuild_team')},free_agency=actions,trade_actions=[dict(kind='finish')])
  args=dict(run_seed=1234,lineup_rules=48,rebuild_team='seattle',season=2,career=[step])
  next_=career_action('seattle',CareerRequest(action='profile',**args));replay_career.cache_clear()
  self.assertEqual(next_,career_action('seattle',CareerRequest(action='profile',**args)))
 def test_position_minimum_blocks_start_even_with_enough_total_players(self):
  f=simple_fixture(48);args={**f['request'],'own_actions':f['actions']}
  data=career_action('seattle',CareerRequest(action='free_agency',**args))
  kicker=next(p for p in data['profile']['roster'] if p['position']=='K')
  actions=[dict(kind='drop',player_id=kicker['id']),dict(kind='finish')]
  data=career_action('seattle',CareerRequest(action='free_agency',free_agency=actions,**args))
  self.assertGreaterEqual(len(data['profile']['roster']),31)
  self.assertFalse(any(p['position']=='K' for p in data['profile']['roster']))
  with self.assertRaises(HTTPException) as error:
   career_action('seattle',CareerRequest(action='trades',free_agency=actions,trade_actions=[dict(kind='finish')],**args))
  self.assertIn('K',str(error.exception.detail))

 def test_release_cannot_make_minimum_repairs_financially_impossible(self):
  from dataclasses import replace
  from app.lineups import lineup_context,replace_lineup_rosters
  from app.preseason import release_player
  from app.player_contracts import salary_cap,cap_payroll,release_preview
  context=lineup_context((),1234,48,rebuild_team='seattle');rosters=dict(context);players=list(rosters['seattle'])
  extra=salary_cap(1,48,run_seed=1234)-cap_payroll(players,context,owner='seattle')
  players[0]=replace(players[0],contract=replace(players[0].contract,annual_salary=players[0].contract.annual_salary+extra))
  rosters['seattle']=tuple(players);context=replace_lineup_rosters(context,tuple(rosters.items()))
  kicker=next(p for p in players if p.position=='K')
  self.assertFalse(release_preview(players,kicker,'seattle',1,1234,context)['allowed'])
  with self.assertRaisesRegex(ValueError,'restore roster minimums'):release_player(context,'seattle',kicker.id,flexible=True)

 def test_finished_cpu_rosters_survive_reopening(self):
  market=self.call([dict(kind='finish')]);identity=market['profile']['roster'][0]['id']
  from app.lineups import lineup_context
  from app.simple_offseason import run
  root=lineup_context((),1234,48,rebuild_team='seattle');args=self.f['request'];own=tuple((a['kind'],a['player_id']) for a in args['own_actions'])
  def state(actions):return run('seattle',1,1234,tuple(args['manual_picks']),(),root,6,own,actions)[1]
  a=state((('finish',''),));b=state((('finish',''),('drop',identity)))
  self.assertEqual({o:ps for o,ps in a if o!='seattle'},{o:ps for o,ps in b if o!='seattle'})

if __name__=='__main__':
 import json
 print(json.dumps(flexible_fixture()))
