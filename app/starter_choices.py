"""Immutable, week-effective starter choices. Completed games keep their lineups."""
from dataclasses import dataclass, replace
from functools import lru_cache

from .league import TEAMS
from .simulation import ROSTER_RULES, ranked_players, roster_for

STARTER_COUNT = sum(minimum for _, minimum in ROSTER_RULES.values())


def selected_roster(players, starters, *, fill=False):
    players = tuple(players)
    selected = set(starters)
    if len(selected) != len(starters):
        raise ValueError('A player cannot occupy two starter slots')
    known = {p.id for p in players}
    if not fill and selected - known:
        raise ValueError('Starters must belong to the managed roster')
    if not starters:
        return ranked_players(players)
    if not fill and (len(starters) != STARTER_COUNT or any(
            sum(p.id in selected and p.position == position for p in players) != minimum
            for position, (_, minimum) in ROSTER_RULES.items())):
        raise ValueError('Choose exactly the required starters for every position')
    result = []
    for position, (_, minimum) in ROSTER_RULES.items():
        group = sorted((p for p in players if p.position == position), key=lambda p: (-p.rating, p.depth, p.id))
        preferred = [p for p in group if p.id in selected][:minimum]
        if fill:
            preferred += [p for p in group if p not in preferred][:minimum-len(preferred)]
        ids = {p.id for p in preferred}
        ordered = preferred + [p for p in group if p.id not in ids]
        result.extend(replace(p, depth=i+1) for i, p in enumerate(ordered))
    return tuple(result)


def _selected_context(base, owner, seed, starters):
    from .lineups import replace_lineup_rosters
    rosters = dict(base) if base else {team.id: tuple(roster_for(team.id, seed).values()) for team in TEAMS}
    rosters[owner] = selected_roster(rosters[owner], starters)
    result = replace_lineup_rosters(base, tuple(rosters.items()))
    if getattr(result, 'lineup_rules', 1) >= 5:
        from .development import capture_rotation
        result = capture_rotation(result)
    return result


@dataclass(frozen=True)
class StarterPlan:
    base: object
    owner: str
    seed: int
    changes: tuple
    latest: object

    def __iter__(self):
        return iter(self.latest)

    def __getattr__(self, name):
        return getattr(self.latest, name)


def with_starters(base, owner, seed, changes):
    if not changes:
        return base
    return _with_starters(base, owner, seed, changes)


@lru_cache(maxsize=16)
def _with_starters(base, owner, seed, changes):
    if owner not in {team.id for team in TEAMS}:
        raise ValueError('Unknown managed team')
    previous = 0
    latest = base
    for week, starters in changes:
        if not 1 <= week <= 21 or week <= previous:
            raise ValueError('Lineup changes must have increasing effective weeks from 1 to 21')
        latest = _selected_context(base, owner, seed, starters)
        previous = week
    return StarterPlan(base, owner, seed, changes, latest)


def context_for_week(context, week):
    if not isinstance(context, StarterPlan):
        return context
    return _planned_context_for_week(context, week)


@lru_cache(maxsize=128)
def _planned_context_for_week(context, week):
    changes = [starters for effective, starters in context.changes if effective <= week]
    return _selected_context(context.base, context.owner, context.seed, changes[-1]) if changes else context.base


def current_starters(context):
    return context.changes[-1][1] if isinstance(context, StarterPlan) else ()
