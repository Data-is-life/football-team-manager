"""Current roster strength, independent of game results and playoff seeding."""
from dataclasses import asdict

from .league import TEAMS
from .simulation import team_ratings


def league_team_rankings(run_seed=0, roster_context=()):
    rows = []
    for team in TEAMS:
        ratings = team_ratings(team.id, run_seed, roster_context)
        rows.append({'team': asdict(team), 'ratings': {**asdict(ratings), 'overall': ratings.overall}})
    rows.sort(key=lambda row: (-row['ratings']['overall'], row['team']['city'], row['team']['id']))
    return [dict(row, rank=index) for index, row in enumerate(rows, 1)]
