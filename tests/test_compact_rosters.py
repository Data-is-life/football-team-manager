from collections import Counter
from dataclasses import asdict, replace
from unittest import TestCase
from unittest.mock import patch

from app.career import cpu_cuts, drop_players, offseason, replay_career
from app.development import advance_context
from app.draft import build_draft
from app.league import TEAMS
from app.lineups import lineup_context, replace_lineup_rosters
from app.main import CareerRequest, career_action, profile_payload
from app.simulation import COMPACT_ROSTER_RULES, ROSTER_RULES, roster_limit, validate_roster


class CompactRosterTests(TestCase):
    def test_initial_shape_all_teams_and_legacy_rosters_unchanged(self):
        self.assertEqual(sum(n for n, _ in COMPACT_ROSTER_RULES.values()), 31)
        self.assertEqual(sum(n for p, (n, _) in COMPACT_ROSTER_RULES.items() if p in ('QB','WR','TE','RB','OL')), 15)
        self.assertEqual(sum(n for p, (n, _) in COMPACT_ROSTER_RULES.items() if p in ('DL','LB','CB','S')), 15)
        self.assertEqual({p:m for p,(_,m) in ROSTER_RULES.items()}, {p:m for p,(_,m) in COMPACT_ROSTER_RULES.items()})
        for seed in (0, 1, 1234):
            legacy = lineup_context((), seed, 10, rebuild_team='seattle')
            compact = lineup_context((), seed, 11, rebuild_team='seattle')
            for owner, players in compact:
                self.assertEqual(len(players), 31); validate_roster(players)
                self.assertEqual(Counter(p.position for p in players), {p:n for p,(n,_) in COMPACT_ROSTER_RULES.items()})
                old = dict(legacy)[owner]
                self.assertEqual(len(old), 38)
                self.assertEqual(players, tuple(p for p in old if p.depth <= COMPACT_ROSTER_RULES[p.position][0]))
            profile = profile_payload('seattle', dict(compact)['seattle'], seed, compact)
            self.assertEqual({r['position']:r['initial'] for r in profile['roster_rules']}, {p:n for p,(n,_) in COMPACT_ROSTER_RULES.items()})
            self.assertTrue(68 <= profile['ratings']['offense'] <= 72)
            self.assertTrue(68 <= profile['ratings']['defense'] <= 72)
            self.assertEqual(legacy, lineup_context((), seed, 10, rebuild_team='seattle'))

    def test_single_kicker_minimum_and_complete_season(self):
        context = lineup_context((), 1234, 11, rebuild_team='seattle')
        players = dict(context)['seattle']
        kicker = next(p for p in players if p.position == 'K')
        with self.assertRaisesRegex(ValueError, 'at least 1'):
            drop_players(players, [kicker.id])
        request = dict(run_seed=1234, lineup_rules=11, rebuild_team='seattle')
        final = career_action('seattle', CareerRequest(action='week', week=17, **request))
        self.assertEqual(len(final['roster_stats']['players']), 31)
        self.assertEqual(len(final['game_results']), 17)
        postseason = career_action('seattle', CareerRequest(action='playoffs', round_number=4, **request))
        self.assertTrue(postseason['postseason_complete'])
        own = final['result']['home'] if final['result']['home']['team']['id']=='seattle' else final['result']['away']
        self.assertEqual([p['player_id'] for p in own['kicking']], [kicker.id])

    def test_six_round_draft_cuts_and_replay_use_31_for_all_teams(self):
        seed = 1234
        context = lineup_context((), seed, 11, rebuild_team='seattle')
        board, players = build_draft('seattle',1,seed,roster_context=context,auto_pick=True,draft_rounds=6)
        picks = tuple(board['manual_picks'])
        self.assertEqual(len(picks),6)
        keep = {p.id for p in cpu_cuts(players,31)}
        cuts = tuple(p.id for p in players if p.id not in keep)
        _, finished = offseason('seattle',1,seed,picks,cuts,roster_context=context,draft_rounds=6)
        for _, roster in finished:
            self.assertEqual(len(roster),31); validate_roster(roster)
        step = (1,(),picks,cuts,11,(),6)
        replay = replay_career('seattle',seed,(step,),11,2,1,'seattle')
        expected = advance_context(finished,seed,2,lineup_rules=11)
        self.assertEqual(replay,expected)
        for _, roster in replay:self.assertEqual(len(roster),31)
        profile = career_action('seattle', CareerRequest(action='cuts',run_seed=seed,lineup_rules=11,rebuild_team='seattle',draft_rounds=6,manual_picks=list(picks),dropped=list(cuts)))
        self.assertTrue(profile['can_continue']);self.assertEqual(len(profile['profile']['roster']),31)
        if cuts:
            oversized = career_action('seattle', CareerRequest(action='cuts',run_seed=seed,lineup_rules=11,rebuild_team='seattle',draft_rounds=6,manual_picks=list(picks),dropped=list(cuts[:-1])))
            self.assertFalse(oversized['can_continue'])

    def test_retirement_replacements_and_multi_year_lifecycle(self):
        context = lineup_context((),1234,11,rebuild_team='seattle')
        context = replace_lineup_rosters(context,tuple((owner,tuple(replace(p,age=60) for p in players)) for owner,players in context))
        order = [dict(team=asdict(team),record='0–0') for team in TEAMS]
        with patch('app.draft.draft_order',return_value=order):
            board, players = build_draft('seattle',1,1234,roster_context=context,auto_pick=True,draft_rounds=6)
            self.assertEqual(len(board['retirements']),31)
            self.assertEqual(len(players),31)
            self.assertEqual(len(board['replacements']),25)
            for season in range(1,5):
                board, players = build_draft('seattle',season,1234,roster_context=context,auto_pick=True,draft_rounds=6)
                keep = {p.id for p in cpu_cuts(players,31)}
                cuts = tuple(p.id for p in players if p.id not in keep)
                _, context = offseason('seattle',season,1234,tuple(board['manual_picks']),cuts,roster_context=context,draft_rounds=6)
                for _, roster in context:self.assertEqual(len(roster),31);validate_roster(roster)
                context = advance_context(context,1234,season+1,lineup_rules=11)

    def test_existing_career_cannot_silently_switch_roster_formats(self):
        legacy = lineup_context((),1234,10,rebuild_team='seattle')
        self.assertEqual(roster_limit(legacy),38)
        with self.assertRaisesRegex(ValueError,'new career'):
            advance_context(legacy,1234,2,lineup_rules=11)
        self.assertEqual(len(dict(advance_context(legacy,1234,2,lineup_rules=10))['seattle']),38)
