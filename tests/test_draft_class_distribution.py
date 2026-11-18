"""Draft-entry scarcity, strict later-round ceiling, and versioned replay."""
from dataclasses import replace
from unittest import TestCase

from app.attributes import generate_attributes
from app.development import advance_context, initial_state
from app.draft import build_draft, draft_class, late_round_prospect, _draft_result
from app.lineups import lineup_context
from app.preseason import prepare


class DraftClassDistributionTests(TestCase):
    def test_class_has_thirty_ready_players_across_seeds_and_years(self):
        for seed in range(20):
            for season in (1, 10, 24):
                players = draft_class(season, seed, 46)
                with self.subTest(seed=seed, season=season):
                    self.assertEqual(len(players), 200)
                    self.assertEqual(sum(p.rating >= 70 for p in players), 30)
                    self.assertTrue(all(45 <= p.rating <= 90 for p in players))
                    original = {p.id:p for p in draft_class(season, seed, 45)}
                    for p in players:
                        self.assertEqual((p.name,p.position,p.age),
                            (original[p.id].name,original[p.id].position,original[p.id].age))
                        self.assertEqual(p.attributes, generate_attributes(p.id,p.position,p.rating,seed))
                    draft_class.cache_clear()
                    self.assertEqual(players, draft_class(season,seed,46))

    def test_exactly_seventy_is_capped_only_for_new_rules(self):
        player = replace(draft_class(1,1234,45)[0],rating=70)
        self.assertIs(late_round_prospect(player,1234,45), player)
        self.assertEqual(late_round_prospect(player,1234,46).rating,69)

    def test_full_draft_udfas_potential_and_manual_replay(self):
        for seed in (1234,91000):
            root = lineup_context((),seed,46,rebuild_team='seattle')
            args = dict(roster_context=root,return_league=True,draft_rounds=6)
            opening, _ = build_draft('seattle',1,seed,**args)
            visible = [p['player'] for p in opening['picks']] + opening['available']
            self.assertEqual(sum(p['current_rating']>=70 for p in visible),30)
            board, rosters = build_draft('seattle',1,seed,auto_pick=True,**args)
            original = {p.id:p for p in draft_class(1,seed,45)}
            adjusted = {p.id:p for p in draft_class(1,seed,46)}
            self.assertTrue(any(p['player']['current_rating']>=70 for p in board['picks'] if p['round']==1))
            for pick in board['picks']:
                p = pick['player']
                self.assertEqual(p['current_rating'], adjusted[p['id']].rating if pick['round']==1
                                 else min(69,adjusted[p['id']].rating))
                self.assertEqual(p['potential_rating'],initial_state(original[p['id']],seed,True).potential)
            choices = tuple(board['manual_picks'])
            _draft_result.cache_clear()
            replay, replay_rosters = build_draft('seattle',1,seed,choices,**args)
            self.assertEqual(board,replay)
            self.assertEqual(rosters,replay_rosters)
            _, context = prepare('seattle',1,seed,choices,(),root,6)
            picked = {p['player']['id'] for p in board['picks']}
            udfas = [p for p in context.free_agents if p.id in original and p.id not in picked]
            self.assertEqual(len(udfas),20)
            self.assertTrue(all(p.rating<70 for p in udfas))
            states = dict(context.development)
            for identity in original:
                self.assertEqual(states[identity].potential,initial_state(original[identity],seed,True).potential)
            prepare.cache_clear()
            self.assertEqual(context,prepare('seattle',1,seed,choices,(),root,6)[1])

    def test_existing_career_cannot_change_draft_generation(self):
        root = lineup_context((),1234,45,rebuild_team='seattle')
        with self.assertRaisesRegex(ValueError,'new career'):
            advance_context(root,1234,2,lineup_rules=46)
