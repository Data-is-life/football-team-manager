from collections import Counter
import unittest

from fastapi import HTTPException
from app.career import drop_players, cpu_cuts, offseason, replay_career
from app.draft import build_draft
from app.main import career_action, CareerRequest, CareerStep
from app.simulation import ROSTER_RULES, roster_for, simulate_through_week, league_week_scores
from app.standings import standings_through_week
from app.playoffs import postseason_snapshot


def complete_draft(team='seattle', season=1, prior=(), context=()):
    choices = []
    for turn in range(4):
        draft, _ = build_draft(team, season, 1234, tuple(choices), prior, context)
        choices.append(draft['available'][0]['id'])
    return tuple(choices)


def legal_cuts(players, target=38, keep=()):
    result = list(players)
    removed = []
    while len(result) > target:
        counts = Counter(p.position for p in result)
        player = min((p for p in result if p.id not in keep and counts[p.position] > ROSTER_RULES[p.position][1]),
                     key=lambda p: (p.rating, p.id))
        result.remove(player)
        removed.append(player.id)
    return tuple(removed)


class CareerRosterTests(unittest.TestCase):
    def test_drop_reaches_each_minimum_then_blocks_last_required_player(self):
        original = list(roster_for('seattle', 1234).values())
        for position, (_, minimum) in ROSTER_RULES.items():
            same = [p for p in original if p.position == position]
            released = [p.id for p in same[minimum:]]
            result = drop_players(original, released)
            self.assertEqual(sum(p.position == position for p in result), minimum)
            with self.assertRaisesRegex(ValueError, 'at least'):
                drop_players(original, released + [same[0].id])
        self.assertEqual(original, list(roster_for('seattle', 1234).values()))
        for dropped in (['missing'], [original[0].id] * 2):
            with self.assertRaises(ValueError):
                drop_players(original, dropped)

    def test_cpu_cuts_and_depths_preserve_ids_and_position_minimums(self):
        choices = complete_draft()
        draft, rosters = build_draft('seattle', 1, 1234, choices, return_league=True)
        for team, players in rosters.items():
            kept = cpu_cuts(players)
            self.assertEqual(len(kept), 38)
            self.assertTrue({p.id for p in kept} <= {p.id for p in players})
            for position, (_, minimum) in ROSTER_RULES.items():
                group = [p for p in kept if p.position == position]
                self.assertGreaterEqual(len(group), minimum)
                self.assertEqual([p.depth for p in group], list(range(1, len(group) + 1)))
                self.assertEqual([p.rating for p in group], sorted((p.rating for p in group), reverse=True))

    def test_rosters_survive_two_offseasons_and_all_game_paths_use_them(self):
        owner, seed = 'seattle', 1234
        choices = complete_draft(owner)
        draft, rosters = build_draft(owner, 1, seed, choices, return_league=True)
        rookie_ids = {p['player']['id'] for p in draft['picks'] if p['team']['id'] == owner}
        cuts = legal_cuts(rosters[owner], keep=rookie_ids)
        step = (1, (), choices, cuts)
        ctx = replay_career(owner, seed, (step,))
        self.assertEqual(len(dict(ctx)[owner]), 38)
        self.assertTrue(rookie_ids <= {p.id for p in dict(ctx)[owner]})
        self.assertTrue(set(cuts).isdisjoint(p.id for p in dict(ctx)[owner]))
        ranks = tuple(sorted((row['team']['id'], row['rank']) for g in standings_through_week(1, 17, seed)['groups'] for row in g['teams']))
        final = simulate_through_week(owner, 2, 17, seed, ranks, ctx)
        ids = {p.id for p in dict(ctx)[owner]}
        self.assertEqual({p['player_id'] for p in final['roster_stats']['players']}, ids)
        self.assertTrue(set(cuts).isdisjoint(p['player_id'] for p in final['roster_stats']['players']))
        for category in ('passing', 'rushing', 'receiving', 'kicking', 'defense', 'blocking'):
            own = final['result']['home'] if final['result']['home']['team']['id'] == owner else final['result']['away']
            self.assertTrue({p['player_id'] for p in own[category]} <= ids)
        post = postseason_snapshot(2, 4, seed, ranks, ctx)
        self.assertEqual(post['field'], final['standings']['playoff_race'])
        profile = career_action(owner, CareerRequest(action='profile', season=2, run_seed=seed,
              career=[CareerStep(season=1, manual_picks=list(choices), dropped=list(cuts))]))
        self.assertEqual({p['id'] for p in profile['roster']}, ids)
        row = next(row for g in final['standings']['groups'] for row in g['teams'] if row['team']['id'] == owner)
        self.assertEqual(row['ratings'], profile['ratings'])
        self.assertEqual(final['record'], {key: row[key] for key in ('wins', 'losses', 'ties')})
        again_choices = complete_draft(owner, 2, ranks, ctx)
        again, rosters = build_draft(owner, 2, seed, again_choices, ranks, ctx, return_league=True)
        cuts2 = legal_cuts(rosters[owner], keep=rookie_ids)
        ctx2 = replay_career(owner, seed, (step, (2, ranks, again_choices, cuts2)))
        self.assertTrue(rookie_ids <= {p.id for p in dict(ctx2)[owner]})
        self.assertEqual(ctx2, replay_career(owner, seed, (step, (2, ranks, again_choices, cuts2))))

    def test_one_rb_and_one_te_are_valid_for_simulation(self):
        choices = complete_draft()
        _, rosters = build_draft('seattle', 1, 1234, choices, return_league=True)
        players = rosters['seattle']
        drop = tuple(p.id for position in ('RB', 'TE') for p in [p for p in players if p.position == position][1:])
        _, ctx = offseason('seattle', 1, 1234, choices, drop)
        # Trim the rest legally to be a valid next-season roster.
        own = dict(ctx)['seattle']
        more = legal_cuts(own)
        _, ctx = offseason('seattle', 1, 1234, choices, drop + more)
        result = simulate_through_week('seattle', 2, 17, 1234, (), ctx)
        own_box = result['result']['home'] if result['result']['home']['team']['id'] == 'seattle' else result['result']['away']
        self.assertEqual(len(own_box['rushing']), 1)
        self.assertEqual(sum(row['attempts'] for row in own_box['rushing']), own_box['team_stats']['rush_attempts'])

    def test_bad_career_or_partial_draft_cannot_bypass_api_limits(self):
        choices = complete_draft()
        for request in (CareerRequest(action='cuts', manual_picks=[], dropped=[]),
                        CareerRequest(action='cuts', run_seed=1234, manual_picks=list(choices), dropped=['missing']),
                        CareerRequest(action='profile', season=2, run_seed=1234, career=[CareerStep(season=1, manual_picks=list(choices))])):
            with self.assertRaises(HTTPException) as error:
                career_action('seattle', request)
            self.assertEqual(error.exception.status_code, 422)

    def test_context_isolation_in_score_standings_and_playoff_caches(self):
        choices = complete_draft()
        _, rosters = build_draft('seattle', 1, 1234, choices, return_league=True)
        cuts = legal_cuts(rosters['seattle'])
        ctx = replay_career('seattle', 1234, ((1, (), choices, cuts),))
        for cached, args in ((league_week_scores, (2, 1, 1234, ())),
                             (standings_through_week, (2, 17, 1234, ())),
                             (postseason_snapshot, (2, 4, 1234, ()))):
            baseline = cached(*args)
            modified = cached(*args, ctx)
            self.assertNotEqual(baseline, modified)
            self.assertEqual(baseline, cached(*args))
            self.assertEqual(modified, cached(*args, ctx))


if __name__ == '__main__':
    unittest.main()
