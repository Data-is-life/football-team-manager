from dataclasses import replace
import random
import unittest

from app.career import cpu_cuts, offseason, replay_career
from app.development import DevelopmentState, advance_context, next_player, with_rosters
from app.draft import build_draft
from app.league import generate_schedule
from app.lineups import lineup_context
from app.player_stats import aggregate_player_stats
from app.rotation import SLOTS, position_roles, position_snaps
from app.simulation import roster_for, simulate_game, simulate_league_week


class RotationTests(unittest.TestCase):
    def test_roles_favor_starters_and_current_ability_with_youth_floor(self):
        base=list(roster_for('seattle',1234).values())
        for position,slots in SLOTS.items():
            group=[replace(p,rating=80,age=30) for p in base if p.position==position]
            roles=position_roles(group,position)
            self.assertAlmostEqual(sum(roles.values()),slots)
            starters=[p for p in group if p.depth<=slots]
            reserves=[p for p in group if p.depth>slots]
            self.assertGreater(min(roles[p.id] for p in starters),max(roles[p.id] for p in reserves))
            young=[replace(p,age=24) if p.depth>slots else p for p in group]
            young_roles=position_roles(young,position)
            if position in ('QB','K'):
                self.assertTrue(all(young_roles[p.id]==0 for p in reserves))
            else:
                self.assertTrue(all(young_roles[p.id]>=.05 for p in reserves))
                snaps=position_snaps(young,position,60)
                self.assertTrue(all(snaps[p.id]>=3 for p in reserves))
                lower=next(p for p in group if p.depth>slots)
                stronger=[replace(p,rating=95) if p.id==lower.id else p for p in group]
                self.assertGreater(position_roles(stronger,position)[lower.id],roles[lower.id])
            if position=='OL':self.assertGreater(sum(roles[p.id] for p in starters)/slots,.95)
        # Rotation ordering is a game-design policy: DL > LB > CB/S reserve work.
        shares={pos:sum(position_roles([replace(p,rating=80,age=30) for p in base],pos)[p.id]
                 for p in base if p.position==pos and p.depth>SLOTS[pos])/SLOTS[pos] for pos in ('DL','LB','CB','S')}
        self.assertGreater(shares['DL'],shares['LB'])
        self.assertGreater(shares['LB'],shares['CB'])
        self.assertGreater(shares['LB'],shares['S'])

    def test_overstaffed_positions_share_a_bounded_youth_budget(self):
        p=next(p for p in roster_for('seattle',1234).values() if p.position=='RB')
        group=[replace(p,id=f'back-{i}',depth=i+1,rating=80-i,age=22) for i in range(21)]
        roles=position_roles(group,'RB')
        self.assertAlmostEqual(sum(roles.values()),1)
        self.assertGreater(roles[group[0].id],max(roles[p.id] for p in group[1:]))
        snaps=position_snaps(group,'RB',50)
        self.assertEqual(sum(snaps.values()),50)
        self.assertTrue(all(0<=count<=50 for count in snaps.values()))

    def test_all_boxes_conserve_targets_production_and_position_snaps(self):
        context=lineup_context((),1234,5,rebuild_team='seattle')
        boxes=[]
        for week in (1,9,17):
            detailed=simulate_league_week(1,week,1234,roster_context=context)
            compact=simulate_league_week(1,week,1234,roster_context=context,include_defense_and_blocking=False)
            for result,light in zip(detailed,compact):
                for side,other in (('home','away'),('away','home')):
                    box,opponent=result[side],result[other]
                    self.assertEqual(box['score'],light[side]['score'])
                    self.assertEqual(box['participation'],light[side]['participation'])
                    players=list(roster_for(box['team']['id'],1234,context).values())
                    by_id={p.id:p for p in players}
                    snaps={row['player_id']:row['snaps'] for row in box['participation']}
                    offense=box['team_stats']['total_plays']+box['team_stats']['sacks_allowed']
                    defense=opponent['team_stats']['total_plays']+opponent['team_stats']['sacks_allowed']
                    kicks=sum(p['field_goals_attempted']+p['extra_points_attempted'] for p in box['kicking'])
                    for position,slots in SLOTS.items():
                        total=kicks if position=='K' else defense if position in ('DL','LB','CB','S') else offense
                        rows=[p for p in players if p.position==position]
                        self.assertEqual(sum(snaps[p.id] for p in rows),slots*total)
                        for p in rows:
                            self.assertTrue(0<=snaps[p.id]<=total)
                            if p.age<25 and p.depth>slots and position not in ('QB','K'):
                                self.assertGreaterEqual(snaps[p.id],1)
                    self.assertEqual(len(box['passing']),1)
                    self.assertEqual(by_id[box['passing'][0]['player_id']].depth,1)
                    self.assertEqual(by_id[box['kicking'][0]['player_id']].depth,1)
                    self.assertEqual(sum(row['targets'] for row in box['receiving']),box['team_stats']['pass_attempts'])
                    self.assertEqual(sum(row['receptions'] for row in box['receiving']),box['passing'][0]['completions'])
                    self.assertEqual(sum(row['yards'] for row in box['receiving']),box['team_stats']['passing_yards'])
                    self.assertEqual(sum(row['touchdowns'] for row in box['receiving']),box['passing'][0]['touchdowns'])
                    for row in box['receiving']:self.assertTrue(row['touchdowns']<=row['receptions']<=row['targets'])
                    self.assertEqual(sum(row['attempts'] for row in box['rushing']),box['team_stats']['rush_attempts'])
                    self.assertEqual(sum(row['yards'] for row in box['rushing']),box['team_stats']['rushing_yards'])
                    for row in box['rushing']:
                        self.assertLessEqual(row['touchdowns'],row['attempts'])
                        if not row['attempts']:self.assertEqual(row['yards'],0)
                    for row in box['blocking']:
                        self.assertEqual(snaps[row['player_id']],row['pass_block_snaps']+row['run_block_snaps'])
                        self.assertLessEqual(row['sacks_allowed'],row['pass_block_snaps'])
                    self.assertEqual(sum(p['sacks_allowed'] for p in box['blocking']),box['team_stats']['sacks_allowed'])
                    for row in box['defense']:
                        self.assertEqual(snaps[row['player_id']],row['snaps'])
                        self.assertTrue(row['sacks']<=row['tackles']<=row['snaps'])
                    if box['team']['id']=='seattle':boxes.append(box)
        players=roster_for('seattle',1234,context).values()
        totals=aggregate_player_stats(players,(box for box in boxes))
        self.assertEqual(totals['games'],3)
        for entry in totals['players']:
            self.assertEqual(entry['snaps'],sum(next(row['snaps'] for row in box['participation'] if row['player_id']==entry['player_id']) for box in boxes))
            if 'receiving' in entry:self.assertEqual(entry['receiving']['targets'],sum(next((row['targets'] for row in box['receiving'] if row['player_id']==entry['player_id']),0) for box in boxes))

    def test_youth_growth_is_bounded_and_qb_k_age_25_and_rookies_are_excluded(self):
        for position in SLOTS:
            p=next(p for p in roster_for('seattle',1234).values() if p.position==position)
            for age in (24,25):
                player=replace(p,age=age,rating=65)
                state=DevelopmentState(90,65,rotation_share=.10)
                old,_=next_player(player,state,1234,2)
                new,_=next_player(player,state,1234,2,rotation_growth=True)
                expected=1 if age<25 and position not in ('QB','K') else 0
                self.assertEqual(new.rating-old.rating,expected)
            player=replace(p,age=22,rating=65)
            state=DevelopmentState(65,65,rotation_share=.10)
            new,_=next_player(player,state,1234,2,rotation_growth=True)
            self.assertLessEqual(new.rating,65)
            rookie=replace(player,id='rookie-1234-2-999',experience=0)
            self.assertEqual(next_player(rookie,state,1234,2,rotation_growth=True)[0],rookie)

    def test_draft_and_cut_replay_preserve_previous_season_roles(self):
        context=lineup_context((),1234,5,rebuild_team='seattle')
        original=dict(context.development)
        choices=[]
        for _ in range(4):
            draft,_=build_draft('seattle',1,1234,tuple(choices),(),context)
            choices.append(draft['available'][0]['id'])
        draft,players=build_draft('seattle',1,1234,tuple(choices),(),context)
        kept={p.id for p in cpu_cuts(players)}
        drops=tuple(p.id for p in players if p.id not in kept)
        _,final=offseason('seattle',1,1234,tuple(choices),drops,(),context)
        for identity,state in final.development:
            if identity in original:self.assertEqual(state.rotation_share,original[identity].rotation_share)
            else:self.assertEqual(state.rotation_share,0)
        expected=advance_context(final,1234,2)
        replay=replay_career('seattle',1234,((1,(),tuple(choices),drops,5),),5,2,1,'seattle')
        self.assertEqual(expected,replay)
        self.assertEqual(replay,advance_context(replay,1234,2))
        self.assertTrue(any(state.rotation_share>0 for identity,state in replay.development if identity in choices))

    def test_legacy_boxes_and_development_remain_separate(self):
        game=generate_schedule('seattle')[0]
        old=lineup_context((),1234,4,rebuild_team='seattle')
        new=lineup_context((),1234,5,rebuild_team='seattle')
        baseline=simulate_game('seattle',game,1,run_seed=1234,roster_context=old)
        actual=simulate_game('seattle',game,1,run_seed=1234,roster_context=new)
        for side in ('home','away'):
            self.assertEqual(baseline[side]['score'],actual[side]['score'])
            self.assertNotIn('participation',baseline[side])
            self.assertNotIn('targets',baseline[side]['receiving'][0])
        self.assertEqual(baseline,simulate_game('seattle',game,1,run_seed=1234,roster_context=old))


if __name__=='__main__':unittest.main()
