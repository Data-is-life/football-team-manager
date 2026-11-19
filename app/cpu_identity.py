"""Private, rules-44 CPU decision policies. Never included in public payloads.

Ownership changes are derived from seed/team/year, independent of wins or losses.
Initial owners are partway through their eras so transitions are staggered.
"""
from dataclasses import dataclass, replace
from functools import lru_cache
import hashlib
import math
import random

from .league import TEAMS

KINDS = ('patient', 'reactive', 'gambler')
OFFENSE = ('QB', 'WR', 'RB', 'TE', 'OL')


def number(seed, owner, purpose):
    value = f'cpu-ownership-v1:{seed}:{owner}:{purpose}'.encode()
    return int.from_bytes(hashlib.sha256(value).digest()[:8], 'big')


@lru_cache(maxsize=128)
def initial_kinds(seed, managed):
    teams = sorted(t.id for t in TEAMS if t.id != managed)
    random.Random(number(seed, 'league', 'initial')).shuffle(teams)
    return tuple((owner, KINDS[min(index // 10, 2)]) for index, owner in enumerate(teams))


@dataclass(frozen=True)
class Identity:
    kind: str
    start: int
    end: int  # exclusive; every full ownership era lasts 20–25 seasons
    focus: tuple[str, ...]
    push: bool


@lru_cache(maxsize=8192)
def identity(seed, managed, owner, year):
    kind = dict(initial_kinds(seed, managed))[owner]
    era = 0
    duration = 20 + number(seed, owner, 'duration:0') % 6
    start = 1 - number(seed, owner, 'initial-elapsed') % duration
    while year >= start + duration:
        start += duration
        era += 1
        choices = tuple(k for k in KINDS if k != kind)
        kind = choices[number(seed, owner, f'kind:{era}') % len(choices)]
        duration = 20 + number(seed, owner, f'duration:{era}') % 6
    # A reactive owner changes direction annually, without changing personality.
    plan = f'{era}:{year}' if kind == 'reactive' else str(era)
    positions = list(OFFENSE)
    random.Random(number(seed, owner, f'focus:{plan}')).shuffle(positions)
    push = (year - start) % 4 < 2
    return Identity(kind, start, start + duration, tuple(positions[:2]), push)


def for_team(context, owner, year):
    managed = getattr(context, 'rebuild_team', None)
    if getattr(context, 'lineup_rules', 1) < 44 or owner is None or owner == managed:
        return None
    policy = identity(context.run_seed, managed, owner, year)
    if context.lineup_rules >= 47:
        policy = replace(policy,kind={'reactive':'expensive_peaks','gambler':'talent_hoarder'}.get(policy.kind,policy.kind))
    return policy


def direction(policy, position):
    if policy.kind == 'patient':
        return 1.3 if position in policy.focus else .9
    if policy.kind == 'reactive':
        return 1.7 if position in policy.focus else .7
    return 1.5 if position in policy.focus else .85


def reaction(seed, owner, year, player):
    # Stable for identical circumstances; changes next year, never per request.
    return .65 + number(seed, owner, f'player:{year}:{player.id}') % 701 / 1000


def draft_adjustment(policy, player, potential, seed, owner, year):
    if policy is None:
        return 0
    upside = max(0, potential - player.rating)
    if policy.kind == 'patient':
        return (6 if player.position in policy.focus else -2) + .25 * upside
    if policy.kind == 'reactive':
        return (14 if player.position in policy.focus else -6) + 20 * (reaction(seed, owner, year, player) - 1)
    if policy.push:
        return (8 if player.position in policy.focus else -3) + .3 * (player.rating - 70)
    return .4 * upside + (3 if player.position in policy.focus else 0)


def retention_factor(policy, player, potential, seed, owner, year):
    if policy is None:
        return 1
    factor = direction(policy, player.position)
    upside = max(0, potential - player.rating)
    if policy.kind == 'patient':
        return factor * (1 + upside / 60)
    if policy.kind == 'reactive':
        return factor * reaction(seed, owner, year, player)
    if policy.push:
        return factor * math.exp(max(-.8, min(.8, (player.rating - 78) * .06)))
    return factor * (.55 if player.age >= 29 else 1 + upside / 50)


def market_factor(policy, player, potential, salary, seed, owner, year):
    factor = retention_factor(policy, player, potential, seed, owner, year)
    if policy is not None and policy.kind == 'gambler':
        # Push years cancel the normal price penalty. Retooling years favor value.
        cost = max(1, salary / 1_000_000)
        factor *= cost ** (.3 if policy.push else -.2)
    return factor


# Rules 47 target the final prime/first decline years, without exposing policy metadata.
def peak_age(position):
    from .development import CURVES, KICKER_CURVE

    return 27 if position == 'RB' else (KICKER_CURVE if position == 'K' else CURVES[position])[1]-1


def peak_window(player):
    return abs(player.age-peak_age(player.position)) <= 1
