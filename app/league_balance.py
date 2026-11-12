"""Versioned, one-time opponent balance around a 75 league mean."""
from dataclasses import replace
from functools import lru_cache
import random

from .attributes import generate_attributes
from .simulation import _run_number, lineup_unit_rating, ranked_players

OFFENSE = frozenset(('QB', 'WR', 'TE', 'RB', 'OL'))
DEFENSE = frozenset(('DL', 'LB', 'CB', 'S'))


def centered_ratings(values):
    """Round a Gaussian sample to bounded ratings with an exact mean of 75."""
    mean = sum(values) / len(values)
    raw = [75 + value - mean for value in values]
    ratings = [max(60, min(90, round(value))) for value in raw]
    difference = 75 * len(values) - sum(ratings)
    while difference:
        step = 1 if difference > 0 else -1
        index = min((i for i, value in enumerate(ratings) if 60 <= value + step <= 90),
                    key=lambda i: (abs(ratings[i] + step - raw[i]) - abs(ratings[i] - raw[i]), i))
        ratings[index] += step
        difference -= step
    return ratings


@lru_cache(maxsize=64)
def opponent_targets(seed, owners, lineup_rules=12):
    # Shared strength gives each team a recognizable level; a smaller skew
    # permits different offensive and defensive identities.
    rng = random.Random(_run_number('opponent-balance-v1', seed))
    spread = 6 if lineup_rules >= 33 else 4
    strength = [rng.gauss(0, spread) for _ in owners]
    skew = [rng.gauss(0, 2) for _ in owners]
    offense = centered_ratings([a + b for a, b in zip(strength, skew)])
    defense = centered_ratings([a - b for a, b in zip(strength, skew)])
    return tuple(zip(owners, offense, defense))


def shift_unit(players, positions, target, seed):
    """Translate ability uniformly, retaining positional order and ability gaps."""
    if lineup_unit_rating(players, positions) == target:
        return tuple(players)
    def shifted(offset):
        return tuple(replace(p, rating=max(1, min(99, p.rating + offset))) if p.position in positions else p
                     for p in players)
    low, high = -99, 99
    while low < high:
        middle = (low + high) // 2
        if lineup_unit_rating(shifted(middle), positions) < target:
            low = middle + 1
        else:
            high = middle
    result = shifted(low)
    if lineup_unit_rating(result, positions) != target:
        # Half-even rounding can skip an odd team rating when an integer
        # translation lands exactly on .5. A one-point reserve adjustment
        # resolves that boundary without moving the starting unit.
        from .simulation import ROSTER_RULES
        eligible = sorted((i for i,p in enumerate(result) if p.position in positions and p.rating > 1),
                          key=lambda i: (result[i].depth <= ROSTER_RULES[result[i].position][1], result[i].rating, result[i].id))
        for index in eligible:
            candidate = tuple(replace(p, rating=p.rating-1) if i == index else p for i,p in enumerate(result))
            if lineup_unit_rating(candidate, positions) == target:
                result = candidate
                break
        else:
            raise ValueError('Unable to calibrate team rating')
    return tuple(replace(p, attributes=generate_attributes(p.id, p.position, p.rating, seed))
                 if p.position in positions else p for p in result)


def balance_opponents(rosters, seed, managed_team, lineup_rules=12):
    owners = tuple(sorted(owner for owner, _ in rosters if owner != managed_team))
    targets = {owner: (offense, defense) for owner, offense, defense in opponent_targets(seed, owners, lineup_rules)}
    balanced = []
    for owner, players in rosters:
        if owner in targets:
            offense, defense = targets[owner]
            players = shift_unit(players, OFFENSE, offense, seed)
            players = ranked_players(shift_unit(players, DEFENSE, defense, seed))
        balanced.append((owner, tuple(players)))
    return tuple(balanced)


def balance_existing_context(context):
    """Upgrade between seasons, translating potential/form anchors with ability."""
    old_players = {p.id: p for _, players in context for p in players}
    states = dict(context.development)
    rosters = balance_opponents(context.rosters, context.run_seed, context.rebuild_team)
    for _, players in rosters:
        for player in players:
            delta = player.rating - old_players[player.id].rating
            if not delta:
                continue
            state = states[player.id]
            potential = max(player.rating, min(99, state.potential + delta))
            states[player.id] = replace(state, potential=potential,
                baseline=max(1, min(99, state.baseline + delta)), change=state.change + delta,
                potential_change=state.potential_change + potential - state.potential)
    return replace(context, rosters=rosters, development=tuple(sorted(states.items())))
