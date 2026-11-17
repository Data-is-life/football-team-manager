"""Rules 42: draft -> own contracts -> fixed-price market -> trades -> season."""
import json
from dataclasses import replace
from .lineups import replace_lineup_rosters
from .player_contracts import (renew_player, pending_renewals, cap_ready,
    sign_retained_rookies)
from .preseason import prepare, release_player, raise_to_floor, raise_plan, cpu_review, financial_ready
from .development import advance_context
from .simulation import roster_limit, roster_minimum, validate_roster


def expire_pool(context, year):
    """One carryover: first listed in Y remains through Y+1, never Y+2."""
    entries=dict(context.free_agent_entries)
    agents=tuple(p for p in context.free_agents if year-entries.get(p.id,year)<=1)
    ids={p.id for p in agents}
    return replace(context,free_agents=agents,free_agent_entries=tuple(sorted((i,y) for i,y in entries.items() if i in ids)))


def stamp_pool(context, year):
    entries=dict(context.free_agent_entries)
    agents=tuple(p for p in context.free_agents if not p.id.startswith('replacement-'))
    return replace(context,free_agents=agents,
        free_agent_entries=tuple(sorted((p.id,entries.get(p.id,year)) for p in agents)))


def run(team,season,seed,choices,prior,root,rounds,own_actions=(),market_actions=(),review_actions=(),trade_actions=()):
    from .free_agency import free_agency, free_agency_order, team_market_premiums
    root=expire_pool(root,season+1)
    raw,context=prepare(team,season,seed,choices,prior,root,rounds)
    board=json.loads(raw)
    # CPU own-player decisions already happened in prepare; commit their retained picks.
    rosters=tuple((o,tuple(replace(p,contract=p.rookie_offer,rookie_offer=None)
        if p.rookie_offer and (o!=team or p.id.startswith('replacement-')) else p for p in ps)) for o,ps in context)
    context=replace_lineup_rosters(context,rosters)
    own_complete=False
    for kind,identity in own_actions:
        if own_complete: raise ValueError('Own-player signing is already finished')
        # Emergency minimum-roster placeholders are automatic, not draft decisions.
        updated=tuple((o,tuple(replace(p,contract=p.rookie_offer,rookie_offer=None)
            if p.rookie_offer and p.id.startswith('replacement-') else p for p in ps)) for o,ps in context)
        context=replace_lineup_rosters(context,updated)
        players=dict(context)[team]
        if kind=='finish':
            if identity: raise ValueError('Finish signing cannot contain a player')
            if pending_renewals(players,context) or any(p.rookie_offer for p in players):
                raise ValueError('Sign or release every expired player and drafted rookie first')
            if not cap_ready(players,context,context.season,team): raise ValueError('Resolve the salary cap before free agency')
            own_complete=True
        elif kind=='drop': context=release_player(context,team,identity)
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
    context=replace_lineup_rosters(context,tuple((o,tuple(replace(p,contract=p.rookie_offer,rookie_offer=None)
        if p.rookie_offer and p.id.startswith('replacement-') else p for p in ps)) for o,ps in context))
    context=stamp_pool(context,season+1)
    market=None;trading=None;development=[]
    if not own_complete:
        if market_actions or review_actions or trade_actions: raise ValueError('Finish own-player signing before free agency')
    else:
        premiums=team_market_premiums(season,seed,prior,root)
        market,context=free_agency(team,season,seed,context,free_agency_order(season,seed,prior,root),market_actions,premiums=premiums)
        if not market['complete']:
            if review_actions or trade_actions: raise ValueError('End free agency before trading')
        else:
            context=cpu_review(context,team)
            for kind,identity in review_actions:
                if kind=='drop': context=release_player(context,team,identity,final=True)
                elif kind=='raise': context=raise_to_floor(context,team,identity)
                else: raise ValueError('Only releases and payroll-minimum adjustments are available')
            context=sign_retained_rookies(context,season+1)
            from .trades import replay
            trading,context=replay(context,team,trade_actions)
            if trading['complete']:
                # The only annual development pass. Previewing/signing/trading never ages anyone.
                context=advance_context(replace(context,season=season),seed,season+1,lineup_rules=context.lineup_rules)
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
