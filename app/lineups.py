"""Versioned immutable lineups, so saved seasons retain their original results."""
from dataclasses import dataclass
from functools import lru_cache

from .league import TEAMS
from .simulation import roster_for, ranked_players


@dataclass(frozen=True)
class LineupContext:
    rosters: tuple
    lineup_rules: int = 2

    def __iter__(self):
        return iter(self.rosters)


@lru_cache(maxsize=16)
def initial_lineups(run_seed):
    return LineupContext(tuple((team.id, ranked_players(roster_for(team.id, run_seed).values()))
                              for team in TEAMS))


def lineup_context(context, run_seed, rules, season=1, development_start=1):
    if rules == 3:
        from .development import advance_context
        return advance_context(context,run_seed,season,development_start)
    if rules == 1:
        if getattr(context, 'lineup_rules', 1) != 1:
            raise ValueError('Lineup rules cannot be downgraded')
        return context
    if getattr(context, 'lineup_rules', 1) > rules:
        raise ValueError('Lineup rules cannot be downgraded')
    if rules != 2:
        raise ValueError('Unknown lineup rules')
    if not context:
        return initial_lineups(run_seed)
    return LineupContext(tuple((team, ranked_players(players)) for team, players in context))


def replace_lineup_rosters(context, rosters):
    if getattr(context,'lineup_rules',1)==3:
        from .development import with_rosters
        return with_rosters(context,rosters)
    return LineupContext(tuple(rosters)) if getattr(context,'lineup_rules',1)==2 else tuple(rosters)
