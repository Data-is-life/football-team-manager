"""Rules 42: draft -> own contracts -> fixed-price market -> trades -> season."""
import json
from dataclasses import replace
from functools import lru_cache
from .lineups import replace_lineup_rosters
from .player_contracts import (renew_player, pending_renewals, cap_ready,
    sign_retained_rookies)
from .preseason import prepare, release_player, raise_to_floor, raise_plan, cpu_review, financial_ready
from .development import advance_context
from .simulation import roster_limit, roster_minimum, validate_roster


def expire_pool(context, year):
    """One carryover: first listed in Y remains through Y+1, never Y+2."""
    from .season_drops import SeasonDropPlan
    if isinstance(context, SeasonDropPlan):
        return replace(context,base=expire_pool(context.base,year),latest=expire_pool(context.latest,year))
    entries=dict(context.free_agent_entries)
    agents=tuple(p for p in context.free_agents if year-entries.get(p.id,year)<=1)
    ids={p.id for p in agents}
    return replace(context,free_agents=agents,free_agent_entries=tuple(sorted((i,y) for i,y in entries.items() if i in ids)))


def stamp_pool(context, year):
    entries=dict(context.free_agent_entries)
    agents=tuple(p for p in context.free_agents if not p.id.startswith('replacement-'))
    return replace(context,free_agents=agents,
        free_agent_entries=tuple(sorted((p.id,entries.get(p.id,year)) for p in agents)))


def _sign_automatic_offers(context, managed, *, emergency_only=False):
    """Normalize provisional CPU/emergency deals only when something changes."""
    changed = False
    rosters = []
    for owner, players in context:
        updated = []
        for player in players:
            if player.rookie_offer and (player.id.startswith('replacement-')
                                      or (not emergency_only and owner != managed)):
                player = replace(player,contract=player.rookie_offer,rookie_offer=None)
                changed = True
            updated.append(player)
        rosters.append((owner,tuple(updated)))
    return replace_lineup_rosters(context,tuple(rosters)) if changed else context


@lru_cache(maxsize=8)
def _own_phase(team, season, seed, choices, prior, root, rounds, own_actions):
    """Cache the signing log separately from later market decisions."""
    raw,context=prepare(team,season,seed,choices,prior,root,rounds)
    # CPU own-player decisions already happened in prepare; commit their retained picks.
    context=_sign_automatic_offers(context,team)
    own_complete=False
    for kind,identity in own_actions:
        if own_complete: raise ValueError('Own-player signing is already finished')
        # Emergency minimum-roster placeholders are automatic, not draft decisions.
        context=_sign_automatic_offers(context,team,emergency_only=True)
        players=dict(context)[team]
        if kind=='finish':
            if identity: raise ValueError('Finish signing cannot contain a player')
            if pending_renewals(players,context) or any(p.rookie_offer for p in players):
                raise ValueError('Sign or release every expired player and drafted rookie first')
            if not cap_ready(players,context,context.season,team): raise ValueError('Resolve the salary cap before free agency')
            own_complete=True
        elif kind=='drop': context=release_player(context,team,identity,flexible=root.lineup_rules>=48)
        elif kind=='resign':
            updated=renew_player(players,identity,context.season,context.lineup_rules,context,team)
            context=replace_lineup_rosters(context,tuple((o,tuple(updated) if o==team else ps) for o,ps in context))
        elif kind=='sign':
            player=next((p for p in players if p.id==identity),None)
            if player is None or player.rookie_offer is None: raise ValueError('Select an unsigned drafted rookie')
            updated=tuple(replace(p,contract=p.rookie_offer,rookie_offer=None) if p.id==identity else p for p in players)
            if not cap_ready(updated,context,context.season,team): raise ValueError('Signing the rookie would exceed the salary cap')
            context=replace_lineup_rosters(context,tuple((o,updated if o==team else ps) for o,ps in context))
        else: raise ValueError('Unknown own-player signing action')
    # Do not expose automatically supplied emergency contracts as rookie decisions.
    context=_sign_automatic_offers(context,team,emergency_only=True)
    context=stamp_pool(context,season+1)
    return raw, context, own_complete


@lru_cache(maxsize=8)
def _market_phase(team, season, seed, prior, root, context, market_actions):
    """Keep only immutable data; each request decodes its own market response."""
    from .free_agency import free_agency, free_agency_order, team_market_premiums
    premiums = team_market_premiums(season, seed, prior, root)
    market, context = free_agency(team, season, seed, context,
        free_agency_order(season, seed, prior, root), market_actions, premiums=premiums)
    if market['complete'] and root.lineup_rules < 48:
        context = cpu_review(context, team)
    return json.dumps(market), context


@lru_cache(maxsize=8)
def _finalize_phase(team, season, seed, context, trade_actions):
    context = sign_retained_rookies(context, season+1)
    from .trades import replay
    trading, context = replay(context, team, trade_actions)
    if trading['complete']:
        # Reuse this annual development pass when the season starts after review.
        context = advance_context(replace(context,season=season),seed,season+1,lineup_rules=context.lineup_rules)
    return json.dumps(trading), context


def run(team,season,seed,choices,prior,root,rounds,own_actions=(),market_actions=(),review_actions=(),trade_actions=()):
    if root.lineup_rules >= 48 and review_actions:
        raise ValueError('Record roster review decisions in the market action log')
    root = expire_pool(root, season+1)
    raw, context, own_complete = _own_phase(team, season, seed, choices, prior, root, rounds, own_actions)
    board = json.loads(raw)
    market=None;trading=None;development=[]
    if not own_complete:
        if market_actions or review_actions or trade_actions: raise ValueError('Finish own-player signing before free agency')
    else:
        raw_market, context = _market_phase(team, season, seed, prior, root, context, market_actions)
        market = json.loads(raw_market)
        if not market['complete']:
            if review_actions or trade_actions: raise ValueError('End free agency before trading')
        else:
            for kind,identity in review_actions:
                if kind=='drop': context=release_player(context,team,identity,final=True)
                elif kind=='raise': context=raise_to_floor(context,team,identity)
                else: raise ValueError('Only releases and payroll-minimum adjustments are available')
            raw_trading,context=_finalize_phase(team,season,seed,context,trade_actions)
            trading=json.loads(raw_trading)
            if trading['complete']:
                from .draft import player_payload
                development=[player_payload(p,context) for p in dict(context)[team]]
    context=stamp_pool(context,season+1)
    players=dict(context)[team]
    ready=bool(trading and trading['complete']) and financial_ready(players,context,team)
    if ready:
        validate_roster(players,minimum_total=roster_minimum(context),maximum_total=roster_limit(context),context=context,owner=team)
    return {**board,'own_players':{'complete':own_complete,'actions':[{'kind':k,'player_id':i} for k,i in own_actions]},
        'free_agency':market,'trading':trading,'training_camp':bool(market and market['complete']),
        'development_season':season+1,'development_roster':development,
        'dropped':[],'roster_actions':[],'pre_camp_actions':[{'kind':k,'player_id':i} for k,i in review_actions],
        'camp_actions':[],'can_continue':ready,'contracts_pending':pending_renewals(players,context),
        'payroll_floor_adjustment':raise_plan(players,context,team) if market and market['complete'] and not ready else None},context
