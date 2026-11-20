from unittest import TestCase
from fastapi import HTTPException
from app.main import CareerRequest, career_action
from app.lineups import lineup_context
from app.season_drops import with_season_drops
from app.starter_choices import context_for_week
from app.simulation import ROSTER_RULES


class SeasonDropsTests(TestCase):
    def setUp(self):
        self.args=dict(run_seed=1234,lineup_rules=50,rebuild_team='seattle')
        self.base=lineup_context((),1234,50,rebuild_team='seattle')
        self.players=dict(self.base)['seattle']
        self.player=next(p for p in self.players if p.position=='QB' and p.depth==2)

    def call(self,action,**extra):
        return career_action('seattle',CareerRequest(action=action,**self.args,**extra))

    def test_timed_release_keeps_past_games_and_guaranteed_salary(self):
        before=self.call('week',week=3)
        drops=[dict(week=4,player_id=self.player.id)]
        profile=self.call('season_drop',week=4,season_drops=drops)
        self.assertNotIn(self.player.id,{p['id'] for p in profile['roster']})
        self.assertEqual(len(profile['roster']),34)
        original=self.call('profile')
        self.assertEqual(original['payroll']['total'],profile['payroll']['total'])
        self.assertGreater(profile['payroll']['dead_cap'],original['payroll']['dead_cap'])
        self.assertEqual(before,self.call('week',week=3,season_drops=drops))
        self.assertEqual(self.call('week',week=4,season_drops=drops),self.call('week',week=4,season_drops=drops))
        self.assertEqual(profile,self.call('profile',season_drops=drops))

    def test_minimums_unknown_duplicates_and_order(self):
        first=(4,self.player.id)
        plan=with_season_drops(self.base,'seattle',(first,))
        self.assertEqual(context_for_week(plan,3),self.base)
        self.assertEqual(len(dict(context_for_week(plan,4))['seattle']),34)
        for drops in ((first,first),((4,'missing'),),((4,self.players[0].id),(3,self.players[1].id))):
            with self.assertRaises(ValueError):with_season_drops(self.base,'seattle',drops)
        remaining=dict(plan)['seattle'];qb=next(p for p in remaining if p.position=='QB')
        with self.assertRaisesRegex(ValueError,'position minimum'):
            with_season_drops(self.base,'seattle',(first,(4,qb.id)))
        log=[];context=self.base
        while len(dict(context)['seattle'])>31:
            ps=dict(context)['seattle']
            p=next(p for p in ps if sum(o.position==p.position for o in ps)>ROSTER_RULES[p.position][1])
            log.append((4,p.id));context=with_season_drops(self.base,'seattle',tuple(log))
        p=next(p for p in dict(context)['seattle'] if sum(o.position==p.position for o in dict(context)['seattle'])>ROSTER_RULES[p.position][1])
        with self.assertRaisesRegex(ValueError,'roster minimum'):with_season_drops(self.base,'seattle',tuple(log+[(4,p.id)]))
        with self.assertRaises(HTTPException):self.call('season_drop',week=3,season_drops=[dict(week=4,player_id=self.player.id)])

    def test_postseason_and_draft_accept_history(self):
        drops=[dict(week=19,player_id=self.player.id)]
        before=self.call('playoffs',round_number=1)
        self.assertEqual(before,self.call('playoffs',round_number=1,season_drops=drops))
        self.call('season_drop',week=18,round_number=1,season_drops=drops)
        draft=self.call('draft',season_drops=drops,auto_draft=True,draft_rounds=6)
        self.assertTrue(draft['complete'])
        own=self.call('own_players',season_drops=drops,manual_picks=draft['manual_picks'],draft_rounds=6)
        self.assertIn('profile',own)

    def test_release_history_survives_full_offseason_and_replay(self):
        from app.career import replay_career
        drops=[dict(week=4,player_id=self.player.id)]
        draft=self.call('draft',season_drops=drops,auto_draft=True,draft_rounds=6)
        args=dict(season_drops=drops,manual_picks=draft['manual_picks'],draft_rounds=6)
        own=self.call('own_players',**args)
        actions=[]
        for p in own['profile']['roster']:
            if p.get('renewal_offer'):actions.append(dict(kind='drop',player_id=p['id']))
            elif p.get('contract_offer'):actions.append(dict(kind='sign',player_id=p['id']))
        args['own_actions']=actions+[dict(kind='finish',player_id='')]
        args['free_agency']=[dict(kind='finish',player_id='')]
        market=self.call('free_agency',**args)
        # Keep legal roster/position counts with affordable minimum players if needed.
        for _ in range(20):
            profile=market['profile'];ps=profile['roster']
            missing=next((r['position'] for r in profile['roster_rules'] if r['count']<r['minimum']),None)
            if len(ps)>=31 and not missing:break
            options=[p for p in market['free_agency']['available'] if p['affordable'] and (not missing or p['position']==missing)]
            p=min(options,key=lambda p:p['annual_salary'])
            args['free_agency'] += [dict(kind='sign',player_id=p['id']),dict(kind='finish',player_id='')]
            market=self.call('free_agency',**args)
        plan=market['payroll_floor_adjustment']
        if plan:
            args['free_agency'] += [dict(kind='raise',player_id=plan['player_id'])]
        args['trade_actions']=[dict(kind='finish')]
        done=self.call('trades',**args)
        self.assertTrue(done['can_continue'])
        step=dict(season=1,lineup_rules=50,**args)
        args2=dict(season=2,career=[step])
        profile=self.call('profile',**args2)
        replay_career.cache_clear()
        self.assertEqual(profile,self.call('profile',**args2))
        self.assertNotIn(self.player.id,{p['id'] for p in profile['roster']})
        self.call('leaders',week=4,season_drops=drops)

    def test_existing_simplified_careers_can_release_without_migration(self):
        for rules in (42,48,49):
            root=lineup_context((),1234,rules,rebuild_team='seattle')
            p=next(p for p in dict(root)['seattle'] if p.position=='QB')
            plan=with_season_drops(root,'seattle',((4,p.id),))
            self.assertEqual(plan.lineup_rules,rules)
            self.assertNotIn(p.id,{p.id for p in dict(plan)['seattle']})
