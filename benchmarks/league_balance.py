"""Paired seeded auto-draft careers; descriptive balance check, not a win guarantee.

Run from the repository root: python benchmarks/league_balance.py
"""
import json
from pathlib import Path
import sys
from statistics import mean

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.career import cpu_cuts, offseason
from app.draft import build_draft
from app.lineups import lineup_context
from app.simulation import simulate_through_week, team_ratings


def career(seed, owner, rules):
    context = lineup_context((), seed, rules, rebuild_team=owner)
    opponents = [team_ratings(t,seed,context) for t,_ in context if t!=owner]
    result = dict(seed=seed, team=owner, initial_opponent_mean=mean((r.offense+r.defense)/2 for r in opponents), seasons=[])
    prior = ()
    for season in range(1,6):
        final = simulate_through_week(owner,season,17,seed,prior,context)
        result['seasons'].append(dict(season=season, **final['record'], playoffs=any(row['team']['id']==owner for row in final['standings']['playoff_race'])))
        if season == 5:break
        board,players = build_draft(owner,season,seed,prior_standings=prior,roster_context=context,auto_pick=True,draft_rounds=6)
        kept = {p.id for p in cpu_cuts(players,31)}
        cuts = tuple(p.id for p in players if p.id not in kept)
        _,context = offseason(owner,season,seed,tuple(board['manual_picks']),cuts,prior,context,6)
        prior = tuple(sorted((row['team']['id'],row['rank']) for group in final['standings']['groups'] for row in group['teams']))
        context = lineup_context(context,seed,rules,season+1,1,owner)
    return result


if __name__=='__main__':
    owners=('seattle','miami','dallas','las-vegas')
    output=dict(method='Eight paired seeds/cities per version; six-round auto-draft and lowest-rated legal cuts; Seasons 2–5 are the initial full contract window. No user trades or additional choices. Descriptive sample, not a forecast.', versions={})
    for rules in (11,12):
        careers = [career(seed,owners[(seed-1)%len(owners)],rules) for seed in range(1,9)]
        full = [year for result in careers for year in result['seasons'] if year['season']>=2]
        output['versions'][str(rules)] = dict(initial_opponent_mean=mean(c['initial_opponent_mean'] for c in careers), average_full_season_wins=mean(y['wins'] for y in full), full_season_playoff_appearances=sum(y['playoffs'] for y in full), careers_with_playoffs_in_first_four_full_seasons=sum(any(y['playoffs'] for y in c['seasons'] if y['season']>=2) for c in careers), careers=careers)
        print(f'Completed rules {rules}',file=sys.stderr,flush=True)
    print(json.dumps(output,indent=2))
