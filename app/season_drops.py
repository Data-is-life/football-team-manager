"""Week-effective releases; past games retain their original rosters."""
from dataclasses import dataclass, replace
from functools import lru_cache
from .simulation import ROSTER_RULES, roster_minimum, ranked_players


def release(context, owner, identity):
    from .player_contracts import record_release
    from .lineups import replace_lineup_rosters
    players = dict(context)[owner]
    player = next((p for p in players if p.id == identity), None)
    if player is None:
        raise ValueError('Player is not on this roster')
    if len(players) <= roster_minimum(context):
        raise ValueError('Keep the roster minimum during the season')
    if sum(p.position == player.position for p in players) <= ROSTER_RULES[player.position][1]:
        raise ValueError('Keep the position minimum during the season')
    charged = record_release(context, owner, player, context.season)
    pool = {p.id:p for p in charged.free_agents}
    pool[identity] = replace(player, contract=None, rookie_offer=None,
        rookie_origin='released' if player.id.startswith('rookie-') else player.rookie_origin)
    charged = replace(charged, free_agents=tuple(pool[k] for k in sorted(pool)))
    return replace_lineup_rosters(charged, tuple((team, ranked_players(tuple(p for p in roster if p.id != identity))
        if team == owner else roster) for team, roster in charged))


@dataclass(frozen=True)
class SeasonDropPlan:
    base: object
    owner: str
    drops: tuple
    latest: object

    def __iter__(self): return iter(self.latest)
    def __getattr__(self, name): return getattr(self.latest, name)


@lru_cache(maxsize=32)
def with_season_drops(base, owner, drops):
    if not drops: return base
    if base.lineup_rules < 42:
        raise ValueError('In-season releases require current career rules')
    previous = 0
    for week, identity in drops:
        if not 1 <= week <= 22 or week < previous:
            raise ValueError('Releases must have increasing effective weeks from 1 to 22')
        previous = week
    plan = SeasonDropPlan(base, owner, drops, base)
    return replace(plan, latest=drop_context_for_week(plan,22))


@lru_cache(maxsize=128)
def drop_context_for_week(plan, week):
    from .starter_choices import context_for_week
    context = context_for_week(plan.base,week)
    for effective, identity in plan.drops:
        if effective <= week: context = release(context,plan.owner,identity)
    return context


def statistical_roster(context, owner, seed, week):
    """Include released players so their completed production remains archived."""
    from .simulation import roster_for
    from .starter_choices import context_for_week
    current = roster_for(owner,seed,context_for_week(context,week))
    if isinstance(context, SeasonDropPlan):
        original = roster_for(owner,seed,context_for_week(context.base,week))
        return {p.id:p for p in (*original.values(), *current.values())}.values()
    return current.values()
