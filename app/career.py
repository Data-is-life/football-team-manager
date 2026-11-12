"""Immutable roster decisions shared by every career API and simulation cache."""
from collections import Counter
from functools import lru_cache

from .draft import build_draft, player_payload
from .simulation import ROSTER_RULES, validate_roster, ranked_players, roster_limit, roster_minimum
from .lineups import lineup_context, replace_lineup_rosters
from .starter_choices import with_starters
from .player_contracts import cap_ready, cap_release, cpu_cap_cuts, salary_cap, pending_renewals, contract_expired, renew_player, record_release, cap_payroll, guaranteed_cpu_offseason

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


@lru_cache(maxsize=32)
def training_camp(team_id, season, run_seed, choices, prior=(), roster_context=(), draft_rounds=4):
    if getattr(roster_context,'lineup_rules',1) < 18:
        raise ValueError('Training camp requires the new offseason rules')
    draft, rosters = build_draft(team_id,season,run_seed,choices,prior,roster_context,
                                 return_league=True,draft_rounds=draft_rounds)
    if not draft['complete']:
        raise ValueError('Complete all draft picks before starting training camp')
    context = replace_lineup_rosters(roster_context,tuple((owner,tuple(players)) for owner,players in sorted(rosters.items())))
    context = lineup_context(context,run_seed,context.lineup_rules,season+1)
    return draft, context


def offseason(team_id, season, run_seed, choices, dropped, prior=(), roster_context=(), draft_rounds=4, roster_actions=()):
    if getattr(roster_context,'lineup_rules',1) >= 18:
        board, roster_context = training_camp(team_id,season,run_seed,choices,prior,roster_context,draft_rounds)
        draft = {**board,'training_camp':True,'development_season':season+1,
                 'development_roster':[player_payload(p,roster_context) for p in dict(roster_context)[team_id]]}
        rosters = {owner:list(players) for owner,players in roster_context}
    else:
        draft, rosters = build_draft(team_id, season, run_seed, choices, prior, roster_context, return_league=True, draft_rounds=draft_rounds)
    if not draft['complete']:
        raise ValueError('Complete all draft picks before dropping players')
    market_source = [p for _, players in rosters.items() for p in players]
    if getattr(roster_context,'lineup_rules',1) >= 10:
        from .retirement import fill_roster
        if len(dropped) != len(set(dropped)): raise ValueError('A player cannot be dropped twice')
        excluded = []
        decisions = roster_actions if getattr(roster_context,'lineup_rules',1) >= 20 else tuple(('drop',identity) for identity in dropped)
        if getattr(roster_context,'lineup_rules',1) >= 20 and tuple(identity for kind,identity in decisions if kind=='drop') != tuple(dropped):
            raise ValueError('Roster actions must preserve the recorded drop order')
        for kind,identity in decisions:
            if kind == 'resign':
                rosters[team_id] = renew_player(rosters[team_id],identity,season+1,roster_context.lineup_rules,roster_context,team_id)
                continue
            if kind != 'drop': raise ValueError('Unknown roster action')
            released=next((p for p in rosters[team_id] if p.id==identity),None)
            if released is None:raise ValueError('Player is not on this roster')
            market_source.append(released)
            excluded.append(identity)
            if getattr(roster_context,'lineup_rules',1)>=23 or not cap_ready(rosters[team_id],roster_context,season+1,team_id):
                rosters[team_id] = cap_release(rosters[team_id],identity,team_id,season,run_seed,roster_context,excluded)
            else:
                rosters[team_id] = drop_players(rosters[team_id], [identity], roster_minimum(roster_context))
                rosters[team_id] = fill_roster(rosters[team_id],team_id,season,run_seed,excluded,context=roster_context)
            roster_context=record_release(roster_context,team_id,released,season+1)
            if roster_context.lineup_rules>=23:
                from .player_contracts import dead_cap_total
                guaranteed=sum(p.contract.annual_salary for p in rosters[team_id] if p.contract is not None and not contract_expired(p,season+1))
                guaranteed += sum(p.rookie_offer.annual_salary for p in rosters[team_id]
                                  if p.rookie_offer is not None and p.rookie_offer.category == 'replacement')
                if guaranteed+dead_cap_total(roster_context,team_id,season+1)>salary_cap(season+1,roster_context.lineup_rules, run_seed=run_seed):
                    raise ValueError('This release cannot fit its guaranteed salary plus required replacement under the cap')
        rosters[team_id] = arrange_depth(rosters[team_id])
        draft['replacements'] = [player_payload(p,roster_context) for p in rosters[team_id] if p.id.startswith(f'replacement-{run_seed}-{season+1}-')]
    else:
        rosters[team_id] = arrange_depth(drop_players(rosters[team_id], dropped))
    if getattr(roster_context,'lineup_rules',1) >= 20:
        draft['roster_actions'] = [{'kind':kind,'player_id':identity} for kind,identity in roster_actions]
    for other in rosters:
        if other != team_id:
            if getattr(roster_context,'lineup_rules',1)>=23:
                rosters[other],roster_context=guaranteed_cpu_offseason(rosters[other],other,season,run_seed,roster_context)
                continue
            if getattr(roster_context,'lineup_rules',1) >= 20:
                for p in tuple(rosters[other]):
                    if contract_expired(p,season+1):
                        rosters[other] = renew_player(rosters[other],p.id,season+1,roster_context.lineup_rules)
            rosters[other] = cpu_cuts(rosters[other], roster_limit(roster_context), roster_minimum(roster_context))
            if getattr(roster_context,"lineup_rules",1) >= 16:
                rosters[other] = cpu_cap_cuts(rosters[other],other,season,run_seed,roster_context)
    context = tuple((owner, tuple(rosters[owner])) for owner in sorted(rosters))
    if getattr(roster_context, 'lineup_rules', 1) >= 29:
        from dataclasses import replace
        from .draft import draft_class
        from .development import initial_state, next_player
        retained = {p.id for _, players in context for p in players}
        picked = {pick['player']['id'] for pick in draft['picks']}
        pool = {p.id: p for p in roster_context.free_agents}
        pool.update((p.id, p) for p in market_source if p.id not in retained)
        states = dict(roster_context.development)
        for p in draft_class(season, run_seed):
            if p.id not in picked:
                p, state = next_player(p, initial_state(p, run_seed, True), run_seed,
                                      season + 1, False, True, True, True)
                pool[p.id] = p
                states[p.id] = state
        roster_context = replace(roster_context,
            free_agents=tuple(replace(p, contract=None, rookie_offer=None)
                              for identity, p in sorted(pool.items()) if identity not in retained),
            development=tuple(sorted(states.items())))
    context = replace_lineup_rosters(roster_context,context)
    if getattr(context,"lineup_rules",1) >= 18:
        from .development import capture_rotation
        context = capture_rotation(context)
    return draft, context


@lru_cache(maxsize=32)
def prepare_free_agency(team_id, season, run_seed, choices, dropped, prior=(),
                        roster_context=(), draft_rounds=4, roster_actions=()):
    """Cache immutable preparation only; never share a mutable board/response."""
    return offseason(team_id,season,run_seed,choices,dropped,prior,
                     roster_context,draft_rounds,roster_actions)[1]


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
        if rules >= 31:
            if dropped or (len(step)>7 and step[7]):
                raise ValueError('New offseasons require ordered market and camp logs')
            from .preseason import run
            data, context = run(team_id,season,run_seed,choices,prior,context,
                step[6] if len(step)>6 else 6,step[8] if len(step)>8 else (),
                step[9] if len(step)>9 else (),True,step[10] if len(step)>10 else ())
            if not data['can_continue']:
                raise ValueError('Complete training camp and resolve final roster and payroll before next season')
            from .player_contracts import sign_retained_rookies
            context=sign_retained_rookies(context,season+1)
            previous=season
            continue
        if rules >= 29:
            from .free_agency import free_agency_order
            market_order = free_agency_order(season,run_seed,prior,context)
        board, context = offseason(team_id, season, run_seed, choices, dropped, prior, context, step[6] if len(step) > 6 else 4, step[7] if len(step)>7 else ())
        if rules >= 29:
            from .free_agency import free_agency
            market, context = free_agency(team_id, season, request_seed=run_seed,
                context=context, order=market_order,
                actions=step[8] if len(step)>8 else ())
            if not market['complete']:
                raise ValueError('Finish free agency before starting the next season')
        if lineup_rules >= 15:
            from .player_contracts import attach_historical_draft_contracts
            context = attach_historical_draft_contracts(context,board)
        if not cap_ready(dict(context)[team_id],context,season+1,team_id):
            raise ValueError(f'Clear ${ (cap_payroll(dict(context)[team_id],context,season+1,team_id)-salary_cap(season+1,context.lineup_rules, run_seed=run_seed))/1_000_000:.2f}M in cap space before starting the next season')
        if len(dict(context)[team_id]) > roster_limit(context):
            raise ValueError(f'Finalize each past roster at {roster_limit(context)} players or fewer')
        if len(dict(context)[team_id]) < roster_minimum(context):
            raise ValueError(f'Finalize each past roster with at least {roster_minimum(context)} players')
        if pending_renewals(dict(context)[team_id],context):
            raise ValueError('Re-sign or release all players with expired contracts before the next season')
        if rules >= 19:
            from .player_contracts import sign_retained_rookies
            context = sign_retained_rookies(context,season+1)
        previous = season
    return lineup_context(context, run_seed, lineup_rules, target_season, development_start, rebuild_team)
