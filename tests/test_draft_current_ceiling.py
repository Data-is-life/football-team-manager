from unittest import TestCase
from app.draft import build_draft,draft_class
from app.lineups import lineup_context
from app.preseason import prepare
from app.development import initial_state,advance_context
class DraftCurrentCeilingTests(TestCase):
 def test_picks_pool_potential_and_replay(self):
  for seed in (1234,91000):
   root=lineup_context((),seed,43,rebuild_team='seattle')
   board,rosters=build_draft('seattle',1,seed,roster_context=root,auto_pick=True,return_league=True,draft_rounds=6)
   original={p.id:p for p in draft_class(1,seed,43)}
   self.assertTrue(any(p['player']['current_rating']>70 for p in board['picks'] if p['round']==1))
   for pick in board['picks']:
    p=pick['player'];self.assertEqual(p['current_rating'],original[p['id']].rating if pick['round']==1 else min(70,original[p['id']].rating))
    self.assertEqual(p['potential_rating'],initial_state(original[p['id']],seed,True).potential)
   choices=tuple(board['manual_picks']);_,context=prepare('seattle',1,seed,choices,(),root,6)
   picked={p['player']['id'] for p in board['picks']};udfa=[p for p in context.free_agents if p.id in original and p.id not in picked]
   self.assertEqual(len(udfa),20);self.assertTrue(all(p.rating<=70 for p in udfa))
   for identity,state in context.development:
    if identity in original:self.assertEqual(state.potential,initial_state(original[identity],seed,True).potential)
   prepare.cache_clear();self.assertEqual(context,prepare('seattle',1,seed,choices,(),root,6)[1])
 def test_legacy_unchanged_and_upgrade_rejected(self):
  root=lineup_context((),1234,42,rebuild_team='seattle')
  board,_=build_draft('seattle',1,1234,roster_context=root,auto_pick=True,draft_rounds=6)
  original={p.id:p for p in draft_class(1,1234,42)}
  self.assertTrue(any(p['round']>1 and p['player']['current_rating']>70 for p in board['picks']))
  self.assertTrue(all(p['player']['current_rating']==original[p['player']['id']].rating for p in board['picks']))
  with self.assertRaisesRegex(ValueError,'new career'):advance_context(root,1234,2,lineup_rules=43)
