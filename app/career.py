"""Immutable roster decisions shared by every career API and simulation cache."""
from collections import Counter
from functools import lru_cache

from .draft import build_draft
from .simulation import ROSTER_RULES, validate_roster, ranked_players
from .lineups import LineupContext, lineup_context

ROSTER_MAX = 38


def drop_players(players, dropped):
    """Allow a position to reach its minimum, but never go below it."""
    if len(dropped) != len(set(dropped)):
        raise ValueError('A player cannot be dropped twice')
    remaining = list(players)
    for player_id in dropped:
        player = next((p for p in remaining if p.id == player_id), None)
        if player is None:
            raise ValueError('Player is not on this roster')
        minimum = ROSTER_RULES[player.position][1]
        if sum(p.position == player.position for p in remaining) <= minimum:
            raise ValueError(f'{player.position} must keep at least {minimum} players')
        remaining.remove(player)
    validate_roster(remaining)
    return remaining


def arrange_depth(players):
    """The strongest retained players start; IDs remain permanent as depth changes."""
    return ranked_players(players)


def cpu_cuts(players):
    remaining = list(players)
    while len(remaining) > ROSTER_MAX:
        counts = Counter(p.position for p in remaining)
        eligible = [p for p in remaining if counts[p.position] > ROSTER_RULES[p.position][1]]
        if not eligible:
            raise ValueError('No legal CPU cut is available')
        remaining.remove(min(eligible, key=lambda p: (p.rating, -p.depth, p.id)))
    validate_roster(remaining)
    return arrange_depth(remaining)


def offseason(team_id, season, run_seed, choices, dropped, prior=(), roster_context=()):
    draft, rosters = build_draft(team_id, season, run_seed, choices, prior, roster_context, return_league=True)
    if not draft['complete']:
        raise ValueError('Complete all four draft picks before dropping players')
    rosters[team_id] = arrange_depth(drop_players(rosters[team_id], dropped))
    for other in rosters:
        if other != team_id:
            rosters[other] = cpu_cuts(rosters[other])
    context = tuple((owner, tuple(rosters[owner])) for owner in sorted(rosters))
    if getattr(roster_context, 'lineup_rules', 1) == 2:
        context = LineupContext(context)
    return draft, context


@lru_cache(maxsize=32)
def replay_career(team_id: str, run_seed: int, steps: tuple, lineup_rules: int = 1) -> tuple:
    context = ()
    previous = 0
    for step in steps:
        season, prior, choices, dropped = step[:4]
        rules = step[4] if len(step) > 4 else 1
        context = lineup_context(context, run_seed, rules)
        if season <= previous:
            raise ValueError('Career offseason years must be in increasing order')
        _, context = offseason(team_id, season, run_seed, choices, dropped, prior, context)
        if len(dict(context)[team_id]) > ROSTER_MAX:
            raise ValueError('Finalize each past roster at 38 players or fewer')
        previous = season
    return lineup_context(context, run_seed, lineup_rules)
