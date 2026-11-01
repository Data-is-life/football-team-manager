"""Regular-season leaders from the same completed game boxes as player stats."""
from dataclasses import asdict
from functools import lru_cache

from .league import TEAMS, TEAM_BY_ID
from .simulation import roster_for, simulate_league_week
from .starter_choices import context_for_week

METRICS = (
    ('passing', 'Passing yards', 'passing', 'yards'),
    ('rushing', 'Rushing yards', 'rushing', 'yards'),
    ('receiving', 'Receiving yards', 'receiving', 'yards'),
    ('sacks', 'Sacks', 'defense', 'sacks'),
    ('interceptions', 'Defensive interceptions', 'defense', 'interceptions'),
)


@lru_cache(maxsize=8)
def _season_totals(season, week, run_seed, prior_standings, roster_context):
    """Cache compact immutable totals, never mutable responses or full game boxes."""
    if not 1 <= week <= 17:
        raise ValueError('Leader cutoff must be between Week 1 and Week 17')
    current = context_for_week(roster_context, week)
    totals = {}
    for team in TEAMS:
        for player in roster_for(team.id, run_seed, current).values():
            totals[player.id] = [player.name, player.position, team.id, [0] * len(METRICS)]
    for played_week in range(1, week + 1):
        for game in simulate_league_week(season, played_week, run_seed,
                                        prior_standings=prior_standings, roster_context=roster_context):
            for side in ('home', 'away'):
                box = game[side]
                for index, (_, _, category, field) in enumerate(METRICS):
                    for row in box.get(category, ()):
                        totals[row['player_id']][3][index] += row[field]
    return tuple((player_id, name, position, team, tuple(values))
                 for player_id, (name, position, team, values) in sorted(totals.items()))


def league_leaders(team_id, season, week, run_seed=0, prior_standings=(), roster_context=()):
    if team_id not in TEAM_BY_ID:
        raise ValueError('Unknown managed team')
    totals = _season_totals(season, week, run_seed, prior_standings, roster_context)
    categories = []
    for index, (key, label, _, _) in enumerate(METRICS):
        eligible = sorted((row for row in totals if row[4][index] > 0),
                          key=lambda row: (-row[4][index], row[3], row[0]))
        ranked = []
        previous, rank = None, 0
        for place, (player_id, name, position, owner, values) in enumerate(eligible, 1):
            value = values[index]
            if value != previous:
                rank = place
            ranked.append({'rank': rank, 'player_id': player_id, 'player': name,
                           'position': position, 'team': asdict(TEAM_BY_ID[owner]), 'value': value})
            previous = value
        categories.append({'id': key, 'label': label, 'leaders': ranked[:10],
                           'your_best': next((row for row in ranked if row['team']['id'] == team_id), None)})
    return {'team': asdict(TEAM_BY_ID[team_id]), 'season': season, 'week': week,
            'run_seed': run_seed, 'categories': categories}
