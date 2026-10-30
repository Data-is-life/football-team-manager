"""Build deterministic, valid saved-career workloads for restoration benchmarks."""
from app.career import cpu_cuts, offseason
from app.draft import build_draft
from app.lineups import lineup_context
from app.simulation import simulate_through_week
from app.playoffs import playoffs_through_round


def fixture(seasons=4, week=17, draft=False):
    owner, seed, rules = 'seattle', 1234, 6
    context, prior, career, history = (), (), [], []
    for year in range(1, seasons):
        context = lineup_context(context, seed, rules, year, 1, owner)
        regular = simulate_through_week(owner, year, 17, seed, prior, context)
        final = playoffs_through_round(owner, year, 4, seed, prior, context)
        board, players = build_draft(owner, year, seed, (), prior, context, auto_pick=True)
        kept = {p.id for p in cpu_cuts(players)}
        dropped = [p.id for p in players if p.id not in kept]
        _, context = offseason(owner, year, seed, tuple(board['manual_picks']), tuple(dropped), prior, context)
        career.append(dict(season=year, prior_standings=dict(prior) or None, manual_picks=board['manual_picks'], dropped=dropped, lineup_rules=rules))
        own_rounds = [r for r in final['rounds'] if any(owner in (g['home']['team']['id'], g['away']['team']['id']) for g in r['games'])]
        history.append(dict(season=year, **regular['record'], championId=final['champion']['team']['id'], playoffFinish='Champions' if final['champion']['team']['id']==owner else 'Missed playoffs' if not final['qualified'] else 'Lost in '+own_rounds[-1]['name']))
        prior = tuple(sorted((row['team']['id'], row['rank']) for group in regular['standings']['groups'] for row in group['teams']))
    result = dict(version=12, contracts=False, teamId=owner, runSeed=seed, season=seasons, week=week, playoffRound=4 if week==17 else None, lineupRules=rules, developmentStart=1, rebuildTeam=owner, priorStandings=dict(prior), history=history, career=career, draftChoices=None, dropped=[])
    if draft:
        context = lineup_context(context, seed, rules, seasons, 1, owner)
        board, players = build_draft(owner, seasons, seed, (), prior, context, auto_pick=True)
        kept = {p.id for p in cpu_cuts(players)}
        result.update(draftChoices=board['manual_picks'], dropped=[p.id for p in players if p.id not in kept])
    return result


if __name__ == '__main__':
    import json
    from pathlib import Path
    for name, years, week, draft in [('fresh', 1, 0, False), ('year4', 4, 17, True), ('year8', 8, 8, False)]:
        target = Path(__file__).parent / (name + '.json')
        target.write_text(json.dumps(fixture(years, week, draft)))
        print(target.name, flush=True)
