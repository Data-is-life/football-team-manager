"""Versioned immutable lineups, so saved seasons retain their original results."""
from dataclasses import dataclass, replace
from functools import lru_cache

from .league import TEAMS
from .simulation import ROSTER_RULES, roster_for, ranked_players
from .attributes import generate_attributes
import hashlib


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


def starter_hierarchy(players, run_seed):
    """Initial ability only: protect the starting unit and trim surplus depth."""
    ranked = ranked_players(players)
    result = []
    for position, (_, starters) in ROSTER_RULES.items():
        group = [player for player in ranked if player.position == position]
        weakest = group[starters-1].rating
        for player in group:
            if player.depth <= starters:
                result.append(player)
                continue
            draw = int.from_bytes(hashlib.sha256(
                f'initial-hierarchy-v1:{run_seed}:{player.id}'.encode()).digest()[:8], 'big')
            gap = 8 + draw % 7 if weakest >= 70 else 1 + draw % 4
            ceiling = weakest - gap
            if position in ('QB', 'K'):
                ceiling = min(ceiling, 74)
            rating = max(1, min(player.rating, ceiling))
            result.append(replace(player, rating=rating,
                attributes=generate_attributes(player.id, position, rating, run_seed)))
    return ranked_players(result)


@lru_cache(maxsize=16)
def initial_hierarchy(run_seed):
    return tuple((team.id, starter_hierarchy(roster_for(team.id, run_seed).values(), run_seed))
                 for team in TEAMS)


@lru_cache(maxsize=32)
def rebuild_lineups(run_seed, team_id, balanced=False):
    """Only the hired GM's initial roster changes; opponents keep normal ability."""
    if team_id not in {team.id for team in TEAMS}:
        raise ValueError('Unknown rebuild team')
    rosters = dict(initial_hierarchy(run_seed))
    players = []
    for player in rosters[team_id]:
        draw = int.from_bytes(hashlib.sha256(
            f"{'rebuild-v2' if balanced else 'rebuild-v1'}:{run_seed}:{player.id}".encode()).digest()[:8], 'big')
        if balanced:
            # With 71–73 starters and 57–64 reserves after hierarchy caps,
            # round(.8 * starters + .2 * bench) stays inside 68–72.
            rating = 71 + draw % 3 if player.depth <= ROSTER_RULES[player.position][1] else 60 + draw % 5
        else:
            rating = 52 + draw % 18
        players.append(replace(player, rating=rating,
            attributes=generate_attributes(player.id, player.position, rating, run_seed)))
    rosters[team_id] = starter_hierarchy(players, run_seed)
    return tuple(rosters.items())


def lineup_context(context, run_seed, rules, season=1, development_start=1, rebuild_team=None):
    if rebuild_team is not None and rules < 4:
        raise ValueError('Rebuild careers require lineup rules 4 or later')
    if rules in (3, 4, 5, 6, 7, 8, 9):
        from .development import advance_context
        if getattr(context, 'lineup_rules', 1) > rules:
            raise ValueError('Lineup rules cannot be downgraded')
        return advance_context(context,run_seed,season,development_start,rules,rebuild_team)
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
    from .starter_choices import StarterPlan
    if isinstance(context, StarterPlan):
        # Preserve its latest participation metadata, but future seasons get a new plan.
        context = context.latest
    if getattr(context,'lineup_rules',1)>=3:
        from .development import with_rosters
        return with_rosters(context,rosters)
    return LineupContext(tuple(rosters)) if getattr(context,'lineup_rules',1)==2 else tuple(rosters)
