"""Deterministic, post-camp 1-for-1 trades; contracts transfer unchanged."""
from .lineups import replace_lineup_rosters
from .simulation import ranked_players, validate_roster, roster_minimum, roster_limit, team_ratings
from .player_contracts import (contract_expired, contract_potential, veteran_contract,
    salary_cap, minimum_salary, cap_payroll, payroll_floor, pending_renewals)
from .position_ratings import position_ratings
from .development import CURVES, KICKER_CURVE
from .league import TEAM_BY_ID


def eligibility(player, context):
    if player.contract is None or player.rookie_offer or contract_expired(player,context.season):
        return 'Only players with active signed contracts can be traded.'
    if player.id.startswith('rookie-') and int(player.id.split('-')[-2]) == context.season:
        return 'Players cannot be traded in their draft year.'
    if player.contract.category == 'free_agent' and player.contract.signed_season == context.season:
        return 'Players signed in this offseason’s free agency cannot be traded.'
    if player.id.startswith('replacement-'):
        return 'Emergency replacement players cannot be traded.'
    return None


def player_value(player, context):
    potential=contract_potential(player,context)
    decline=(KICKER_CURVE if player.position=='K' else CURVES[player.position])[1]
    age_factor=max(.35,min(1.10,1-(player.age-decline)*.06))
    importance={'QB':1.2,'OL':1.2,'WR':.9,'RB':.9,'TE':.8,'K':.25}.get(player.position,1)
    talent=(max(0,player.rating-40)**2+20*max(0,potential-player.rating))*age_factor*importance
    normal=veteran_contract(player,context.season,context.lineup_rules,potential,
        run_seed=context.run_seed,context=context).annual_salary
    years=player.contract.signed_season+player.contract.years-context.season
    factor=max(-.5,min(1.5,1+.25*(normal-player.contract.annual_salary)/max(normal,minimum_salary(context.season,context.lineup_rules,run_seed=context.run_seed))*min(years,3)))
    return talent*factor


def swap_context(context, owner, other, outgoing, incoming):
    rosters=dict(context)
    rosters[owner]=ranked_players([p for p in rosters[owner] if p.id!=outgoing.id]+[incoming])
    rosters[other]=ranked_players([p for p in rosters[other] if p.id!=incoming.id]+[outgoing])
    return replace_lineup_rosters(context,tuple(rosters.items()))


def evaluate(context, owner, other, give_id, receive_id):
    from .preseason import floor_payroll
    rosters=dict(context)
    if other not in rosters or other==owner:
        return {'accepted':False,'reasons':['Choose another league team.']}
    outgoing=next((p for p in rosters[owner] if p.id==give_id),None)
    incoming=next((p for p in rosters[other] if p.id==receive_id),None)
    if outgoing is None or incoming is None:
        return {'accepted':False,'reasons':['A selected player is no longer on the selected roster.']}
    reasons=[reason for p in (outgoing,incoming) if (reason:=eligibility(p,context))]
    updated=swap_context(context,owner,other,outgoing,incoming)
    budgets={}
    for team in (owner,other):
        players=dict(updated)[team]
        budgets[team]={'before':cap_payroll(rosters[team],context,owner=team),
                       'after':cap_payroll(players,updated,owner=team),
                       'cap':salary_cap(context.season,context.lineup_rules,run_seed=context.run_seed)}
        try:validate_roster(players,minimum_total=roster_minimum(context),maximum_total=roster_limit(context),context=context,owner=team)
        except ValueError as e:reasons.append(f'{TEAM_BY_ID[team].city}: {e}')
        if budgets[team]['after']>budgets[team]['cap']:
            reasons.append(f'{TEAM_BY_ID[team].city}: too much guaranteed salary for the salary cap.')
        if floor_payroll(players,updated)<payroll_floor(context.season,context.lineup_rules,run_seed=context.run_seed):
            reasons.append(f'{TEAM_BY_ID[team].city}: payroll would be below the required minimum.')
        if pending_renewals(players,updated):
            reasons.append(f'{TEAM_BY_ID[team].city}: resolve unsigned or expired contracts first.')
    offered=player_value(outgoing,context);requested=player_value(incoming,context)
    gain=offered-requested
    fit=team_ratings(other,context.run_seed,updated).overall-team_ratings(other,context.run_seed,context).overall
    qb_loss=position_ratings(rosters[other])['QB']-position_ratings(dict(updated)[other])['QB']
    tolerance=max(25,abs(requested)*.10);margin=max(10,abs(requested)*.02)
    if offered < requested-tolerance:reasons.append('Insufficient value for the CPU player and contract.')
    if qb_loss>3:reasons.append('Losing too much at quarterback.')
    if fit < -.25:reasons.append('The exchange weakens the CPU roster too much.')
    if gain < margin and fit < .05:reasons.append('Insufficient value or positional improvement to justify the trade.')
    accepted=not reasons
    return {'accepted':accepted,'reasons':reasons or ['Accepted: the exchange provides sufficient value or positional improvement.'],
        'cpu_incoming_value':round(offered,2),'cpu_outgoing_value':round(requested,2),
        'cpu_overall_change':round(fit,4),'payroll':budgets,
        'outgoing':outgoing.name,'incoming':incoming.name}


def replay(context, owner, actions):
    complete=False;transactions=[]
    for kind,other,give,receive in actions:
        if complete:raise ValueError('The trading period is already finished')
        if kind=='finish':
            if other or give or receive:raise ValueError('Finish trading cannot contain player selections')
            complete=True;continue
        if kind!='swap':raise ValueError('Unknown trade action')
        decision=evaluate(context,owner,other,give,receive)
        if not decision['accepted']:raise ValueError('; '.join(decision['reasons']))
        rosters=dict(context)
        outgoing=next(p for p in rosters[owner] if p.id==give)
        incoming=next(p for p in rosters[other] if p.id==receive)
        context=swap_context(context,owner,other,outgoing,incoming)
        transactions.append({'team':TEAM_BY_ID[other].city,'outgoing':outgoing.name,'incoming':incoming.name})
    from .preseason import financial_ready
    if complete:
        validate_roster(dict(context)[owner],minimum_total=roster_minimum(context),maximum_total=roster_limit(context),context=context,owner=owner)
    if complete and not financial_ready(dict(context)[owner],context,owner):
        raise ValueError('Resolve roster and payroll before finishing trading')
    def player(p):
        return {'id':p.id,'name':p.name,'position':p.position,'rating':p.rating,
            'potential':contract_potential(p,context),'age':p.age,
            'salary':p.contract.annual_salary,'years':p.contract.signed_season+p.contract.years-context.season}
    teams=[{'id':o,'city':TEAM_BY_ID[o].city,'players':[player(p) for p in ps if not eligibility(p,context)]}
           for o,ps in context if o!=owner]
    return {'complete':complete,'actions':[{'kind':k,'other_team':o,'give_id':g,'receive_id':r} for k,o,g,r in actions],
        'own_players':[player(p) for p in dict(context)[owner] if not eligibility(p,context)],
        'teams':sorted(teams,key=lambda t:t['city']),'transactions':transactions},context
