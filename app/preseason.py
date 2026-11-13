"""Rules 31: market and contract decisions precede development and final cuts."""
from collections import Counter
from dataclasses import replace
from functools import lru_cache
import json

from .development import initial_state, advance_context
from .draft import build_draft, draft_class
from .lineups import replace_lineup_rosters
from .player_contracts import (cap_payroll, salary_cap, payroll_floor, contract_expired,
    contract_terms, record_release, guaranteed_cpu_offseason, pending_renewals,
    cpu_contract_priorities, dead_cap_total, sign_retained_rookies)
from .retirement import retiring, fill_roster
from .simulation import ranked_players, roster_rules, roster_limit, roster_minimum, validate_roster


def floor_payroll(players, context):
    return sum(contract_terms(p).annual_salary for p in players
               if p.rookie_offer is not None or (p.contract is not None and not contract_expired(p,context.season)))


def financial_ready(players, context, owner):
    return (not pending_renewals(players,context)
            and cap_payroll(players,context,context.season,owner)<=salary_cap(context.season,context.lineup_rules, run_seed=getattr(context,'run_seed',0))
            and floor_payroll(players,context)>=payroll_floor(context.season,context.lineup_rules, run_seed=getattr(context,'run_seed',0)))


def raise_plan(players, context, owner):
    deficit=max(0,payroll_floor(context.season,context.lineup_rules, run_seed=getattr(context,'run_seed',0))-floor_payroll(players,context))
    if not deficit:
        return None
    eligible=[p for p in players if p.rookie_offer is not None or (p.contract and not contract_expired(p,context.season))]
    if not eligible:
        return None
    player=max(eligible,key=lambda p:(p.rating,p.id))
    terms=contract_terms(player)
    return {'player_id':player.id,'name':player.name,'added_salary':deficit,
            'annual_salary':terms.annual_salary+deficit,
            'years':terms.signed_season+terms.years-context.season,
            'allowed':cap_payroll(players,context,context.season,owner)+deficit<=salary_cap(context.season,context.lineup_rules, run_seed=getattr(context,'run_seed',0))}


def raise_to_floor(context, owner, identity):
    rosters=dict(context); players=list(rosters[owner]); plan=raise_plan(players,context,owner)
    if plan is None or identity!=plan['player_id']:
        raise ValueError('Payroll minimum adjustment is not needed or the target has changed')
    if not plan['allowed']:
        raise ValueError('Guaranteed obligations leave no room to meet the payroll minimum')
    updated=[]
    for p in players:
        if p.id==identity:
            terms=contract_terms(p)
            category='free_agent' if terms.category=='free_agent' else 'floor_adjustment'
            terms=replace(terms,annual_salary=plan['annual_salary'],signed_season=context.season,
                          years=plan['years'],category=category)
            p=replace(p,contract=terms,rookie_offer=None)
        updated.append(p)
    rosters[owner]=tuple(updated)
    return replace_lineup_rosters(context,tuple(rosters.items()))


def release_player(context, owner, identity, *, final=False):
    rosters=dict(context); players=list(rosters[owner]); player=next((p for p in players if p.id==identity),None)
    if player is None:
        raise ValueError('Player is not on this roster')
    charged=record_release(context,owner,player,context.season)
    if dead_cap_total(charged,owner,context.season)+payroll_floor(context.season,context.lineup_rules, run_seed=getattr(context,'run_seed',0))>salary_cap(context.season,context.lineup_rules, run_seed=getattr(context,'run_seed',0)):
        raise ValueError('This release would make the hard payroll minimum and maximum impossible to meet')
    pool={p.id:p for p in charged.free_agents}
    pool[identity]=replace(player,contract=None,rookie_offer=None)
    remaining=[p for p in players if p.id!=identity]
    excluded=set(pool)|{p.id for _,ps in context for p in ps}
    remaining=fill_roster(remaining,owner,context.season-1,context.run_seed,excluded,context=charged,
                          identity_suffix='-review')
    rosters[owner]=tuple(remaining)
    charged=replace(charged,free_agents=tuple(pool[k] for k in sorted(pool)))
    charged=replace_lineup_rosters(charged,tuple(rosters.items()))
    guaranteed=sum(p.contract.annual_salary for p in remaining if p.contract and not contract_expired(p,charged.season))
    required=sum(p.rookie_offer.annual_salary for p in remaining if p.rookie_offer and p.rookie_offer.category=='replacement')
    if guaranteed+required+dead_cap_total(charged,owner,charged.season)>salary_cap(charged.season,charged.lineup_rules, run_seed=getattr(context,'run_seed',0)):
        raise ValueError('This release cannot fit its guarantee and required replacements under the cap')
    if final and not financial_ready(remaining,charged,owner):
        raise ValueError('Final cuts must preserve the hard payroll minimum and maximum')
    return charged


@lru_cache(maxsize=32)
def prepare(team,season,seed,choices,prior,root,rounds):
    board,rosters=build_draft(team,season,seed,choices,prior,root,return_league=True,draft_rounds=rounds)
    if not board['complete']:
        raise ValueError('Complete the draft before opening free agency')
    prefix=f'replacement-{seed}-{season+1}-'
    rosters={owner:list(ps) for owner,ps in rosters.items()}
    source=[p for ps in rosters.values() for p in ps if not p.id.startswith(prefix)]
    # Relabel the upcoming financial year without running development.
    context=replace(getattr(root,'latest',root),season=season+1)
    context=replace_lineup_rosters(context,tuple((o,tuple(ps)) for o,ps in rosters.items()))
    if context.lineup_rules >= 36:
        from .player_contracts import snapshot_salary_anchors
        # Include the full incoming class, including undrafted free agents,
        # before CPU renewals or any market actions can alter the reference.
        context=replace(context,free_agents=tuple(p for p in context.free_agents if not retiring(p,root)))
        context=replace(context,salary_anchors=snapshot_salary_anchors(context,draft_class(season,seed)))
    for owner in rosters:
        if owner!=team:
            rosters[owner],context=guaranteed_cpu_offseason(rosters[owner],owner,season,seed,context)
    retained={p.id for ps in rosters.values() for p in ps}
    pool={p.id:p for p in root.free_agents if not retiring(p,root)}
    pool.update((p.id,p) for p in source if p.id not in retained)
    picked={p['player']['id'] for p in board['picks']}
    pool.update((p.id,p) for p in draft_class(season,seed) if p.id not in picked)
    states=dict(root.development)
    for p in pool.values():
        if p.id not in states: states[p.id]=initial_state(p,seed,True)
    context=replace(context,free_agents=tuple(replace(p,contract=None,rookie_offer=None)
        for identity,p in sorted(pool.items()) if identity not in retained),development=tuple(sorted(states.items())))
    context=replace_lineup_rosters(context,tuple((o,tuple(ps)) for o,ps in rosters.items()))
    # JSON is immutable; callers get fresh board dictionaries.
    return json.dumps(board),context


def cpu_review(context, team):
    for owner,original in tuple(context):
        if owner==team: continue
        players=list(original)
        priorities=cpu_contract_priorities(players,context,context.season)
        while len(players)>roster_limit(context):
            counts=Counter(p.position for p in players)
            eligible=[p for p in players if counts[p.position]>roster_rules(context)[p.position][1]]
            eligible.sort(key=lambda p:(p.contract is not None and not contract_expired(p,context.season),priorities[p.id],-contract_terms(p).annual_salary,p.id))
            for p in eligible:
                try: next_context=release_player(context,owner,p.id)
                except ValueError: continue
                break
            else: raise ValueError('CPU roster has no financially legal cut')
            context=next_context; players=list(dict(context)[owner])
        plan=raise_plan(players,context,owner)
        if plan: context=raise_to_floor(context,owner,plan['player_id'])
    return context


def run(team,season,seed,choices,prior,root,rounds,market_actions=(),pre_actions=(),camp=False,camp_actions=()):
    from .free_agency import free_agency,free_agency_order,team_market_premiums
    raw,context=prepare(team,season,seed,choices,prior,root,rounds)
    board=json.loads(raw)
    premiums = team_market_premiums(season,seed,prior,root) if root.lineup_rules >= 34 else None
    market,context=free_agency(team,season,seed,context,free_agency_order(season,seed,prior,root),market_actions,premiums=premiums)
    if not market['complete']:
        if pre_actions or camp or camp_actions: raise ValueError('Finish free agency before roster review or training camp')
    else:
        context=cpu_review(context,team)
        for kind,identity in pre_actions:
            if kind=='drop': context=release_player(context,team,identity)
            elif kind=='raise': context=raise_to_floor(context,team,identity)
            else: raise ValueError('Initial review only allows releases and payroll-minimum adjustments')
    development_roster=[]
    if camp:
        context=sign_retained_rookies(context,season+1)
        for owner,players in context:
            validate_roster(players,minimum_total=roster_minimum(context),maximum_total=roster_limit(context))
            if not financial_ready(players,context,owner):
                raise ValueError('Meet the hard payroll minimum and maximum before training camp')
        context=advance_context(replace(context,season=season),seed,season+1,lineup_rules=root.lineup_rules)
        from .draft import player_payload
        development_roster=[player_payload(p,context) for p in dict(context)[team]]
        for kind,identity in camp_actions:
            if kind!='drop': raise ValueError('Only releases are available after training camp')
            context=release_player(context,team,identity,final=True)
    elif camp_actions: raise ValueError('Start training camp before final cuts')
    players=dict(context)[team]
    ready=market['complete'] and roster_minimum(context)<=len(players)<=roster_limit(context) and financial_ready(players,context,team)
    return {**board,'training_camp':camp,'development_season':season+1,
        'development_roster':development_roster,'dropped':[], 'roster_actions':[],
        'free_agency':market,'pre_camp_actions':[{'kind':k,'player_id':i} for k,i in pre_actions],
        'camp_actions':[{'kind':k,'player_id':i} for k,i in camp_actions],
        'can_continue':ready,'contracts_pending':pending_renewals(players,context),
        'payroll_floor_adjustment':raise_plan(players,context,team) if market['complete'] and not camp else None},context
