from dataclasses import replace, asdict
import unittest

from app.league import TEAMS
from app.lineups import initial_lineups, LineupContext, lineup_context
from app.main import team_profile
from app.simulation import ROSTER_RULES, roster_for, team_ratings, lineup_unit_rating, simulate_through_week
from app.career import replay_career
from app.draft import build_draft


class StarterRatingTests(unittest.TestCase):
    def test_every_new_team_starts_highest_current_players_at_each_position(self):
        for seed in (0, 1234, 5678):
            context = initial_lineups(seed)
            for team in TEAMS:
                profile = team_profile(team.id, seed, 2)
                legacy = team_profile(team.id, seed, 1)
                self.assertEqual({p['id'] for p in profile['roster']}, {p['id'] for p in legacy['roster']})
                for position, (_, count) in ROSTER_RULES.items():
                    group = [p for p in profile['roster'] if p['position'] == position]
                    self.assertEqual([p['current_rating'] for p in group], sorted((p['current_rating'] for p in group), reverse=True))
                    self.assertEqual([p['depth'] for p in group], list(range(1, len(group) + 1)))
                    self.assertEqual([p['current_rating'] for p in group[:count]], sorted((p['current_rating'] for p in group), reverse=True)[:count])
                self.assertEqual(profile['ratings'], asdict(team_ratings(team.id, seed, context)))

    def test_weighted_rating_uses_bench_and_not_potential_or_kicker(self):
        base = list(roster_for('seattle', 1234).values())
        controlled = [replace(p, rating=90 if p.depth <= ROSTER_RULES[p.position][1] else 50) for p in base]
        context = LineupContext((('seattle', tuple(controlled)),))
        self.assertEqual(asdict(team_ratings('seattle', 1234, context)), {'offense':82, 'defense':82})
        weaker_bench = tuple(replace(p, rating=10) if p.depth > ROSTER_RULES[p.position][1] else p for p in controlled)
        self.assertEqual(asdict(team_ratings('seattle', 1234, LineupContext((('seattle', weaker_bench),)))), {'offense':74,'defense':74})
        no_bench = [p for p in controlled if p.depth <= ROSTER_RULES[p.position][1]]
        self.assertEqual(lineup_unit_rating(no_bench, {'QB','WR','RB','TE','OL'}),90)
        kickers = tuple(replace(p,rating=1) if p.position=='K' else p for p in controlled)
        self.assertEqual(team_ratings('seattle',1234,LineupContext((('seattle',kickers),))),team_ratings('seattle',1234,context))

    def test_legacy_and_new_worlds_are_isolated_and_games_use_best_qb(self):
        seed = 1234
        legacy = simulate_through_week('seattle',1,1,seed)
        context = initial_lineups(seed)
        updated = simulate_through_week('seattle',1,1,seed,(),context)
        own = updated['result']['home'] if updated['result']['home']['team']['id']=='seattle' else updated['result']['away']
        best = roster_for('seattle',seed,context)['QB1']
        self.assertEqual(own['passing'][0]['player_id'],best.id)
        self.assertEqual(best.rating,max(p.rating for p in roster_for('seattle',seed).values() if p.position=='QB'))
        self.assertEqual(legacy,simulate_through_week('seattle',1,1,seed))
        self.assertEqual(updated,simulate_through_week('seattle',1,1,seed,(),context))
        self.assertNotEqual(updated,legacy)

    def test_drafted_rookies_are_reranked_in_the_visible_profile(self):
        from app.main import rookie_draft, DraftRequest
        from app.draft import draft_order
        context=initial_lineups(1234)
        owner=draft_order(1,1234,(),context)[0]['team']['id']
        initial=rookie_draft(owner,DraftRequest(run_seed=1234,lineup_rules=2))
        rookie=next(p for p in initial['available'] if p['position']=='QB')
        signed=rookie_draft(owner,DraftRequest(run_seed=1234,lineup_rules=2,manual_picks=[rookie['id']]))
        group=[p for p in signed['profile']['roster'] if p['position']=='QB']
        self.assertEqual([p['current_rating'] for p in group],sorted((p['current_rating'] for p in group),reverse=True))
        self.assertIn(rookie['id'],{p['id'] for p in group})
        self.assertEqual(signed['profile']['lineup_rules'],2)

    def test_legacy_draft_decisions_replay_before_upgrading_current_lineup(self):
        choices=[]
        for _ in range(4):
            data,_=build_draft('seattle',1,1234,tuple(choices))
            choices.append(data['available'][0]['id'])
        from app.career import cpu_cuts
        data,players=build_draft('seattle',1,1234,tuple(choices))
        kept={p.id for p in cpu_cuts(players)}
        dropped=tuple(p.id for p in players if p.id not in kept)
        step=(1,(),tuple(choices),dropped,1)
        old=replay_career('seattle',1234,(step,),1)
        new=replay_career('seattle',1234,(step,),2)
        self.assertEqual({p.id for p in dict(old)['seattle']},{p.id for p in dict(new)['seattle']})
        self.assertEqual(getattr(new,'lineup_rules',1),2)
        self.assertEqual(getattr(old,'lineup_rules',1),1)
        with self.assertRaises(ValueError):lineup_context(new,1234,1)


if __name__=='__main__':unittest.main()
