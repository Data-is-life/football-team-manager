"""Immutable roster decisions shared by every career API and simulation cache."""
from collections import Counter
from functools import lru_cache

from .draft import build_draft, player_payload
from .simulation import ROSTER_RULES, validate_roster, ranked_players, roster_limit, roster_minimum
from .lineups import lineup_context, replace_lineup_rosters
from .starter_choices import with_starters
from .player_contracts import cap_ready, cap_release, cpu_cap_cuts, salary_cap, payroll

ROSTER_MAX = 38


def drop_players(players, dropped, minimum_total=0):
    """Protect both position minimums and the versioned total roster floor."""
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
        if len(remaining) <= minimum_total:
            raise ValueError(f'Roster must keep at least {minimum_total} players')
        remaining.remove(player)
    validate_roster(remaining, minimum_total=minimum_total)
    return remaining


def arrange_depth(players):
    """The strongest retained players start; IDs remain permanent as depth changes."""
    return ranked_players(players)


def cpu_cuts(players, limit=ROSTER_MAX, minimum_total=0):
    remaining = list(players)
    while len(remaining) > limit:
        counts = Counter(p.position for p in remaining)
        eligible = [p for p in remaining if counts[p.position] > ROSTER_RULES[p.position][1]]
        if not eligible:
            raise ValueError('No legal CPU cut is available')
        remaining.remove(min(eligible, key=lambda p: (p.rating, -p.depth, p.id)))
    validate_roster(remaining, minimum_total=minimum_total, maximum_total=limit)
    return arrange_depth(remaining)


def offseason(team_id, season, run_seed, choices, dropped, prior=(), roster_context=(), draft_rounds=4):
    draft, rosters = build_draft(team_id, season, run_seed, choices, prior, roster_context, return_league=True, draft_rounds=draft_rounds)
    if not draft['complete']:
        raise ValueError('Complete all draft picks before dropping players')
    if getattr(roster_context,'lineup_rules',1) >= 10:
        from .retirement import fill_roster
        if len(dropped) != len(set(dropped)): raise ValueError('A player cannot be dropped twice')
        excluded = []
        for identity in dropped:
            excluded.append(identity)
            if not cap_ready(rosters[team_id],roster_context,season+1):
                rosters[team_id] = cap_release(rosters[team_id],identity,team_id,season,run_seed,roster_context,excluded)
            else:
                rosters[team_id] = drop_players(rosters[team_id], [identity], roster_minimum(roster_context))
                rosters[team_id] = fill_roster(rosters[team_id],team_id,season,run_seed,excluded,context=roster_context)
        rosters[team_id] = arrange_depth(rosters[team_id])
        draft['replacements'] = [player_payload(p,roster_context) for p in rosters[team_id] if p.id.startswith(f'replacement-{run_seed}-{season+1}-')]
    else:
        rosters[team_id] = arrange_depth(drop_players(rosters[team_id], dropped))
    for other in rosters:
        if other != team_id:
            rosters[other] = cpu_cuts(rosters[other], roster_limit(roster_context), roster_minimum(roster_context))
            if getattr(roster_context,"lineup_rules",1) >= 16:
                rosters[other] = cpu_cap_cuts(rosters[other],other,season,run_seed,roster_context)
    context = tuple((owner, tuple(rosters[owner])) for owner in sorted(rosters))
    context = replace_lineup_rosters(roster_context,context)
    return draft, context


@lru_cache(maxsize=32)
def replay_career(team_id: str, run_seed: int, steps: tuple, lineup_rules: int = 1, season: int = 1, development_start: int = 1, rebuild_team: str | None = None) -> tuple:
    target_season = season
    if lineup_rules >= 15 and any((step[4] if len(step)>4 else 1) < 11 for step in steps):
        raise ValueError('Player salaries require a compact-format career')
    context = ()
    previous = 0
    for step in steps:
        season, prior, choices, dropped = step[:4]
        rules = step[4] if len(step) > 4 else 1
        context = lineup_context(context, run_seed, rules, season, development_start, rebuild_team)
        if lineup_rules >= 15:
            from .player_contracts import ensure_contracts
            context = ensure_contracts(context,season)
        context = with_starters(context, team_id, run_seed, step[5] if len(step) > 5 else ())
        if season <= previous:
            raise ValueError('Career offseason years must be in increasing order')
        board, context = offseason(team_id, season, run_seed, choices, dropped, prior, context, step[6] if len(step) > 6 else 4)
        if lineup_rules >= 15:
            from .player_contracts import attach_historical_draft_contracts
            context = attach_historical_draft_contracts(context,board)
        if not cap_ready(dict(context)[team_id],context,season+1):
            raise ValueError(f'Clear ${ (payroll(dict(context)[team_id])-salary_cap(season+1,context.lineup_rules))/1_000_000:.2f}M in cap space before starting the next season')
        if len(dict(context)[team_id]) > roster_limit(context):
            raise ValueError(f'Finalize each past roster at {roster_limit(context)} players or fewer')
        if len(dict(context)[team_id]) < roster_minimum(context):
            raise ValueError(f'Finalize each past roster with at least {roster_minimum(context)} players')
        previous = season
    return lineup_context(context, run_seed, lineup_rules, target_season, development_start, rebuild_team)
