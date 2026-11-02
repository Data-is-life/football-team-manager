from collections import Counter
from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch
from types import SimpleNamespace

from app.development import advance_context
from app.lineups import lineup_context
from app.retirement import FINAL_AGE, retirement_age, retiring, fill_roster
from app.simulation import ROSTER_RULES, roster_for, validate_roster
from app.draft import build_draft, cpu_pick
from app.career import offseason, replay_career
from app.main import CareerRequest, career_action, profile_payload


class RetirementTests(TestCase):
    def test_position_ability_boundaries_and_longevity(self):
        players=list(roster_for('seattle',1234).values())
        with patch('app.development.longevity',return_value=(0,False)):
            for position,age in FINAL_AGE.items():
                player=next(p for p in players if p.position==position)
                for rating,delta in ((59,-2),(60,0),(80,0),(81,2)):
                    self.assertEqual(retirement_age(replace(player,rating=rating),1234),age+delta)
                    context=SimpleNamespace(lineup_rules=10,run_seed=1234)
                    self.assertFalse(retiring(replace(player,rating=rating,age=age+delta-1),context))
                    self.assertTrue(retiring(replace(player,rating=rating,age=age+delta),context))
        with patch('app.development.longevity',return_value=(4,True)):
            self.assertEqual(retirement_age(replace(players[0],position='QB',rating=81),1234),46)

    def aging_context(self):
        # Every season-1 player is ending their career: exercise empty positions,
        # draft shortages, filling, all 30 teams and next-season replay together.
        base=lineup_context((),1234,10,rebuild_team='seattle')
        from app.lineups import replace_lineup_rosters
        return replace_lineup_rosters(base,tuple((owner,tuple(replace(p,age=60) for p in players)) for owner,players in base))

    def test_marks_stable_during_play_and_legacy_does_not_retire(self):
        base=lineup_context((),1234,10,rebuild_team='seattle')
        before=profile_payload('seattle',dict(base)['seattle'],1234,base)
        self.assertTrue(all('retiring_after_season' in p for p in before['roster']))
        for week in (1,8,17):
            body=CareerRequest(action='week',week=week,run_seed=1234,lineup_rules=10,rebuild_team='seattle')
            career_action('seattle',body)
            self.assertEqual(before,profile_payload('seattle',dict(base)['seattle'],1234,base))
        legacy=lineup_context((),1234,9,rebuild_team='seattle')
        self.assertTrue(all(not retiring(replace(p,age=99),legacy) for _,players in legacy for p in players))

    def test_retirement_before_draft_fill_only_after_final_pick(self):
        context=self.aging_context()
        for owner,players in context:self.assertTrue(all(retiring(p,context) for p in players))
        draft,partial=build_draft('seattle',1,1234,roster_context=context,draft_rounds=6)
        self.assertEqual(partial,[])
        self.assertFalse(draft['complete']);self.assertEqual(draft['replacements'],[])
        self.assertEqual(len(draft['retirements']),38)
        profile_payload('seattle',partial,1234,context) # No divide by zero for an empty offseason unit.
        complete,league=build_draft('seattle',1,1234,roster_context=context,draft_rounds=6,auto_pick=True,return_league=True)
        self.assertTrue(complete['complete'])
        for owner,players in league.items():
            self.assertEqual(len(players),38);validate_roster(players)
            self.assertFalse(any(p.age==60 for p in players))
            replacements=[p for p in players if p.id.startswith('replacement-')]
            self.assertEqual(len(replacements),32)
            self.assertTrue(all(40<=p.rating<=55 for p in replacements))
            self.assertEqual(len({p.id for p in players}),38)
        self.assertEqual((complete,league),build_draft('seattle',1,1234,tuple(complete['manual_picks']),roster_context=context,draft_rounds=6,return_league=True))

    def test_release_fillers_replays_without_resurrecting_ids(self):
        context=self.aging_context()
        complete,players=build_draft('seattle',1,1234,roster_context=context,draft_rounds=6,auto_pick=True)
        ids=[]
        for _ in range(3):
            current=players if not ids else dict(result)['seattle']
            counts=Counter(p.position for p in current)
            drop=next(p for p in current if p.id.startswith('replacement-') and counts[p.position]>ROSTER_RULES[p.position][1])
            ids.append(drop.id)
            draft,result=offseason('seattle',1,1234,tuple(complete['manual_picks']),tuple(ids),roster_context=context,draft_rounds=6)
            retained=dict(result)['seattle'];self.assertEqual(len(retained),38)
            self.assertFalse(set(ids)&{p.id for p in retained});validate_roster(retained)
            self.assertEqual((draft,result),offseason('seattle',1,1234,tuple(complete['manual_picks']),tuple(ids),roster_context=context,draft_rounds=6))
        next_year=advance_context(result,1234,2,lineup_rules=10)
        self.assertFalse(any(p.age>50 for _,players in next_year for p in players))
        for _,players in next_year:validate_roster(players)
        for identity,state in next_year.development:
            if identity.startswith('replacement-'):self.assertLessEqual(state.potential,60)

    def test_oversized_rosters_fill_minimums_without_discarding_draft_picks(self):
        players=list(roster_for('seattle',1234).values())
        qbs=[replace(players[0],id=f'q-{i}',position='QB') for i in range(40)]
        filled=fill_roster(qbs,'seattle',1,1234)
        self.assertGreater(len(filled),38);validate_roster(filled)
        self.assertTrue({p.id for p in qbs}<={p.id for p in filled})

    def test_real_career_rollover_excludes_retired_and_remains_deterministic(self):
        context=lineup_context((),1234,10,rebuild_team='seattle')
        retired={p.id for _,players in context for p in players if retiring(p,context)}
        self.assertTrue(retired)
        draft,players=build_draft('seattle',1,1234,roster_context=context,draft_rounds=6,auto_pick=True)
        from app.career import cpu_cuts
        keep={p.id for p in cpu_cuts(players)}
        drops=tuple(p.id for p in players if p.id not in keep)
        step=(1,(),tuple(draft['manual_picks']),drops,10,(),6)
        result=replay_career('seattle',1234,(step,),10,2,1,'seattle')
        self.assertFalse(retired & {p.id for _,players in result for p in players})
        self.assertEqual(result,replay_career('seattle',1234,(step,),10,2,1,'seattle'))
        for _,players in result:self.assertEqual(len(players),38);validate_roster(players)

    def test_ten_seasons_keep_all_teams_playable_and_do_not_resurrect_retirees(self):
        from dataclasses import asdict
        from app.league import TEAMS
        from app.career import cpu_cuts
        order=[dict(team=asdict(team),record='0–0') for team in TEAMS]
        context=self.aging_context()
        departed=set()
        # Isolate roster lifecycle from standings work, already covered by the
        # real-order replay test above and end-to-end UI seasons.
        with patch('app.draft.draft_order',return_value=order):
            for season in range(1,11):
                retired={p.id for _,players in context for p in players if retiring(p,context)}
                departed |= retired
                board,players=build_draft('seattle',season,1234,roster_context=context,draft_rounds=6,auto_pick=True)
                kept={p.id for p in cpu_cuts(players)}
                cuts=tuple(p.id for p in players if p.id not in kept)
                _,context=offseason('seattle',season,1234,tuple(board['manual_picks']),cuts,roster_context=context,draft_rounds=6)
                context=advance_context(context,1234,season+1,lineup_rules=10)
                identities=[p.id for _,players in context for p in players]
                self.assertFalse(departed & set(identities))
                self.assertEqual(len(identities),len(set(identities)))
                for _,players in context:
                    self.assertEqual(len(players),38);validate_roster(players)
