from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch

from app.lineups import lineup_context, replace_lineup_rosters
from app.position_ratings import position_ratings, weighted_unit_ratings, POSITION_SLOT_WEIGHTS
from app.simulation import (team_ratings, league_week_scores, simulate_league_week,
    _team_box)
from app.league import TEAM_BY_ID
from app.main import team_profile
from app.development import advance_context


class WeightedPositionRatingTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = lineup_context((),1234,38,rebuild_team='seattle')
        cls.player = dict(cls.root)['seattle'][0]

    def group(self, position, ratings):
        return [replace(self.player,position=position,id=f'{position}-{i}',rating=rating,depth=i+1)
                for i,rating in enumerate(ratings)]

    def test_exact_agreed_position_formulas(self):
        cases = {'QB':([80,60],79), 'WR':([90,80,70,60],80),
                 'RB':([80,60],75), 'TE':([80,60],75),
                 'OL':([90,85,80,75,70,60,50],76.5),
                 'DL':([90,85,80,75,60,50],76.375),
                 'LB':([90,80,70,60,50],74.5),
                 'CB':([90,80,60,50],78.25), 'S':([90,80,60],78.75),
                 'K':([80,60],80)}
        for position,(ratings,expected) in cases.items():
            self.assertEqual(position_ratings(self.group(position,ratings))[position],expected)
        self.assertTrue(all(sum(weights)==10_000 for weights in POSITION_SLOT_WEIGHTS.values()))

    def test_missing_slots_are_zero_and_depth_can_only_help(self):
        self.assertEqual(position_ratings(self.group('QB',[80]))['QB'],76)
        self.assertEqual(position_ratings(self.group('RB',[80]))['RB'],60)
        self.assertEqual(position_ratings(self.group('OL',[80]*5))['OL'],68)
        self.assertEqual(position_ratings(self.group('DL',[80]*4))['DL'],60)
        for pos,weights in POSITION_SLOT_WEIGHTS.items():
            for length in range(1,len(weights)+1):
                players = self.group(pos,[80]*min(length,len(weights)))
                before=position_ratings(players)[pos]
                after=position_ratings(players+[replace(p,id=p.id+'-reserve') for p in self.group(pos,[60])])[pos]
                self.assertGreaterEqual(after,before)
            self.assertEqual(position_ratings(self.group(pos,[80]*len(weights)))[pos],80)
        self.assertEqual(weighted_unit_ratings([]),(0,0))

    def test_unit_formula_precision_current_ability_order_and_unused_depth(self):
        groups={'QB':[90,70], 'WR':[80]*4, 'RB':[70]*2, 'TE':[60]*2,
                'OL':[85]*7, 'DL':[80]*6, 'LB':[70]*5, 'CB':[60]*4, 'S':[50]*3, 'K':[99]}
        players=[p for pos,ratings in groups.items() for p in self.group(pos,ratings)]
        # QB = 89, other position ratings equal their uniform current ability.
        self.assertEqual(weighted_unit_ratings(players),(78.36,65))
        shuffled=list(reversed([replace(p,depth=999) for p in players]))
        self.assertEqual(weighted_unit_ratings(shuffled),(78.36,65))
        self.assertEqual(weighted_unit_ratings(players+self.group('K',[1])),(78.36,65))
        qb=self.group('QB',[81,60]); self.assertEqual(position_ratings(qb)['QB'],79.95)
        # Even one OL reserve point propagates beyond two decimal places.
        players2=[replace(p,rating=84) if p.id=='OL-6' else p for p in players]
        self.assertEqual(weighted_unit_ratings(players2),(78.348,65))

    def test_new_careers_preserve_generated_players_and_legacy_games(self):
        old=lineup_context((),1234,37,rebuild_team='seattle')
        self.assertEqual(old.rosters,self.root.rosters)
        self.assertEqual(old.development,self.root.development)
        with self.assertRaisesRegex(ValueError,'new career'):
            advance_context(old,1234,2,lineup_rules=38)
        ratings=team_ratings('seattle',1234,self.root)
        self.assertEqual((ratings.offense,ratings.defense),weighted_unit_ratings(dict(self.root)['seattle']))
        self.assertNotEqual(ratings,team_ratings('seattle',1234,old))
        # The versioned helper is never involved in an older career.
        with patch('app.position_ratings.weighted_unit_ratings',side_effect=AssertionError('legacy')):
            self.assertEqual(team_ratings('seattle',1234,old),team_ratings('seattle',1234,old))

    def test_rankings_profiles_standings_and_scores_share_the_same_ratings(self):
        profile=team_profile('seattle',run_seed=1234,lineup_rules=38,rebuild_team='seattle')
        for row in profile['rankings']:
            expected=team_ratings(row['team']['id'],1234,self.root)
            self.assertEqual(row['ratings'],dict(offense=expected.offense,defense=expected.defense,overall=expected.overall))
        games=simulate_league_week(1,17,1234,roster_context=self.root)
        scores=tuple((g['home']['team']['id'],g['away']['team']['id'],g['home']['score'],g['away']['score']) for g in games)
        self.assertEqual(league_week_scores(1,17,1234,roster_context=self.root),scores)
        # Capture the scoring mean to prove expected points use unrounded new O/D.
        import random
        rng=random.Random(12)
        with patch.object(rng,'gauss',wraps=rng.gauss) as gauss:
            _team_box(TEAM_BY_ID['seattle'],TEAM_BY_ID['miami'],True,rng,1234,self.root)
            own=team_ratings('seattle',1234,self.root)
            other=team_ratings('miami',1234,self.root)
            self.assertAlmostEqual(gauss.call_args_list[0].args[0],(22+(own.offense-other.defense)*.48+1.6)/8.2)

    def test_cuts_immediately_lower_the_exact_position_and_unit_rating(self):
        players=dict(self.root)['seattle']
        rb=sorted([p for p in players if p.position=='RB'],key=lambda p:-p.rating)
        before=team_ratings('seattle',1234,self.root)
        context=replace_lineup_rosters(self.root,tuple((owner,tuple(p for p in ps if p.id!=rb[-1].id)) for owner,ps in self.root))
        after=team_ratings('seattle',1234,context)
        self.assertAlmostEqual(before.offense-after.offense,rb[-1].rating*.25*.90/5)
        self.assertEqual(before.defense,after.defense)
