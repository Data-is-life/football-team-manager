from collections import Counter
from dataclasses import replace
from unittest import TestCase
from app.lineups import lineup_context
from app.simulation import roster_rules,validate_roster,roster_limit
from app.retirement import fill_roster
from app.main import CareerRequest,career_action
from app.preseason import run,financial_ready
from app.draft import build_draft
from app.player_contracts import smart_cpu_roster_cuts

EXPECTED={'QB':2,'WR':3,'RB':2,'TE':2,'OL':6,'K':1,'DL':5,'LB':4,'CB':3,'S':3}

class CpuBenchDepthTests(TestCase):
    def test_owner_specific_minimums_and_legacy_isolation(self):
        root=lineup_context((),1234,39,rebuild_team='seattle')
        self.assertEqual({p:v[1] for p,v in roster_rules(root,'miami').items()},EXPECTED)
        self.assertEqual(sum(EXPECTED.values()),31)
        self.assertEqual(roster_rules(root,'seattle'),roster_rules(root))
        old=lineup_context((),1234,38,rebuild_team='seattle')
        self.assertEqual(old.rosters,root.rosters)
        self.assertEqual(roster_rules(old,'miami'),roster_rules(old))
        from app.development import advance_context
        with self.assertRaisesRegex(ValueError,'new career'):advance_context(old,1234,2,lineup_rules=39)

    def test_fill_and_validation_protect_each_cpu_backup_but_not_user(self):
        root=lineup_context((),1234,39,rebuild_team='seattle')
        for owner in ('miami','seattle'):
            players=list(dict(root)[owner])
            # QB1 remains; force all remaining roster size into WR depth.
            players=[p for p in players if p.position!='QB' or p.depth==1]
            counts=Counter(p.position for p in players)
            filled=fill_roster(players,owner,1,1234,context=root)
            self.assertEqual(Counter(p.position for p in filled)['QB'],2 if owner=='miami' else 1)
            if owner=='miami':
                with self.assertRaisesRegex(ValueError,'QB'):validate_roster(players,context=root,owner=owner)
                validate_roster(filled,context=root,owner=owner)
                extras=[replace(next(p for p in filled if p.position=='WR'),id=f'extra-wr-{i}',rating=40) for i in range(5)]
                cut=smart_cpu_roster_cuts(list(filled)+extras,root,2,owner=owner)
                self.assertEqual(len(cut),35)
                self.assertTrue(all(Counter(p.position for p in cut)[pos]>=n for pos,n in EXPECTED.items()))

    def test_two_seasons_market_camp_cap_and_replay_for_every_cpu_team(self):
        for seed in (1234,5678):
            root=lineup_context((),seed,39,rebuild_team='seattle')
            for season in (1,2):
                board,_=build_draft('seattle',season,seed,roster_context=root,auto_pick=True,draft_rounds=6)
                choices=tuple(board['manual_picks'])
                args=('seattle',season,seed,choices,(),root,6)
                opened,context=run(*args)
                actions=tuple(('drop',p.id) for p in dict(context)['seattle'] if p.rookie_offer or (p.contract and p.contract.signed_season+p.contract.years<=season+1))+(('finish',''),)
                market,context=run(*args,market_actions=actions)
                plan=market['payroll_floor_adjustment']
                pre=(('raise',plan['player_id']),) if plan else ()
                camp,context=run(*args,market_actions=actions,pre_actions=pre,camp=True)
                self.assertTrue(camp['can_continue'])
                for owner,players in context:
                    self.assertTrue(financial_ready(players,context,owner))
                    self.assertLessEqual(len(players),38)
                    if owner!='seattle':
                        counts=Counter(p.position for p in players)
                        self.assertTrue(all(counts[pos]>=n for pos,n in EXPECTED.items()),(seed,season,owner,counts))
                again,replay=run(*args,market_actions=actions,pre_actions=pre,camp=True)
                self.assertEqual(context,replay)
                self.assertEqual(camp,again)
                root=context
