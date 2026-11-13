"""Versioned, deterministic user-first free agency, replayed from saved turns."""
from collections import Counter
from dataclasses import asdict, replace
from decimal import Decimal, ROUND_HALF_UP

from .development import capture_rotation
from .league import TEAM_BY_ID
from .lineups import replace_lineup_rosters
from .player_contracts import (CPU_GROUP_IMPORTANCE, cap_payroll, contract_potential,
    minimum_salary, pending_renewals, salary_cap, veteran_contract)
from .ratings import rating_payload
from .retirement import fill_roster
from .simulation import ranked_players, roster_limit, roster_minimum, roster_rules, validate_roster

MAX_WAVES = 24


def free_agency_order(season, seed, prior, context):
    from .standings import standings_through_week
    tables = standings_through_week(season,17,seed,prior,context)
    rows = [row for group in tables['groups'] for row in group['teams']]
    return tuple(row['team']['id'] for row in sorted(rows,key=lambda r:(
        r['wins']*2+r['ties'],r['point_differential'],r['points_for'],r['team']['id'])))


def wave_percent(wave):
    if not 1 <= wave <= MAX_WAVES:
        raise ValueError('Invalid free agency wave')
    return (120, 110, 105)[wave-1] if wave <= 3 else max(0, 100-5*(wave-4))


def market_premium(offense, defense, wins, losses, ties):
    """Basis points: up to 10% each for weak ability and a losing record."""
    overall = (Decimal(offense) + Decimal(defense)) / 2
    strength = max(Decimal(0), min(Decimal(1000), (75 - overall) * 100))
    games = wins + losses + ties
    record = max(Decimal(0), Decimal(1000) * (losses - wins) / games) if games else Decimal(0)
    return (int(strength.quantize(Decimal('1'), rounding=ROUND_HALF_UP)),
            int(record.quantize(Decimal('1'), rounding=ROUND_HALF_UP)))


def team_market_premiums(season, seed, prior, context):
    """Snapshot the concluded season, before drafting, cuts or market signings."""
    from .standings import standings_through_week
    tables = standings_through_week(season, 17, seed, prior, context)
    return {row['team']['id']: market_premium(row['ratings']['offense'], row['ratings']['defense'],
                row['wins'], row['losses'], row['ties'])
            for group in tables['groups'] for row in group['teams']}


def asking_contract(player, context, wave, development_states=None, *, premium_basis_points=0):
    normal = veteran_contract(player, context.season, context.lineup_rules,
                             contract_potential(player, context, development_states), run_seed=getattr(context,'run_seed',0), context=context)
    return wave_contract(normal,context.season,context.lineup_rules,wave,premium_basis_points=premium_basis_points, run_seed=getattr(context,'run_seed',0))


def wave_contract(normal, season, rules, wave, *, premium_basis_points=0, run_seed=0):
    """Apply wave and destination multipliers, then round once and enforce the floor."""
    premium = premium_basis_points if rules >= 34 else 0
    if not 0 <= premium <= 2000:
        raise ValueError('Invalid destination premium')
    amount = Decimal(normal.annual_salary) * wave_percent(wave) / 100 * (10_000 + premium) / 10_000
    rounded = int((amount / 10_000).quantize(Decimal('1'), rounding=ROUND_HALF_UP))*10_000
    return replace(normal, annual_salary=max(minimum_salary(season,rules, run_seed=run_seed),rounded),
                   category='free_agent')


def free_agency(team_id, season, request_seed, context, order, actions=(), *, premiums=None):
    pre_camp = context.lineup_rules >= 31
    if context.lineup_rules < 29 or context.season != season+1 or context.run_seed != request_seed:
        raise ValueError('Invalid free agency context')
    if set(order) != set(TEAM_BY_ID) or len(order) != len(TEAM_BY_ID):
        raise ValueError('Free agency requires all 30 teams')
    if context.lineup_rules >= 34:
        if premiums is None or set(premiums) != set(TEAM_BY_ID) or any(
                len(parts) != 2 or any(type(part) is not int or not 0 <= part <= 1000 for part in parts)
                for parts in premiums.values()):
            raise ValueError('Free agency requires concluded-season premiums for all 30 teams')
    else:
        premiums = {owner: (0, 0) for owner in TEAM_BY_ID}
    order = (team_id,) + tuple(owner for owner in order if owner != team_id)
    # These emergency placeholders were created during draft/cut validation.
    # Real free agents get the vacancies before final emergency filling.
    prefix = f'replacement-{request_seed}-{season+1}-'
    rosters = {owner:[p for p in players if not p.id.startswith(prefix)] for owner,players in context}
    pool = {p.id:p for p in context.free_agents}
    occupied = {p.id for players in rosters.values() for p in players}
    if occupied & pool.keys():
        raise ValueError('A free agent is already on a roster')
    transactions = []
    complete = False
    wave = 1
    minimum = minimum_salary(context.season, context.lineup_rules, run_seed=getattr(context,'run_seed',0))
    cap = salary_cap(context.season, context.lineup_rules, run_seed=getattr(context,'run_seed',0))
    states = dict(context.development)

    rules = roster_rules(context)
    minimum_total, maximum_total = roster_minimum(context), roster_limit(context)
    counts = {owner:Counter(p.position for p in players) for owner,players in rosters.items()}
    missing = {owner:sum(max(0,floor-counts[owner][pos]) for pos,(_,floor) in rules.items())
               for owner in rosters}
    budgets = {owner:cap_payroll(players,context,context.season,owner) for owner,players in rosters.items()}
    potentials, normal_contracts, wave_contracts = {}, {}, {}

    def potential_for(player):
        if player.id not in potentials:
            potentials[player.id] = contract_potential(player,context,states)
        return potentials[player.id]

    def demand(owner, player):
        premium = sum(premiums[owner])
        key = (player.id,wave,premium)
        if key not in wave_contracts:
            if player.id not in normal_contracts:
                normal_contracts[player.id] = veteran_contract(player,context.season,context.lineup_rules,potential_for(player), run_seed=getattr(context,'run_seed',0), context=context)
            wave_contracts[key] = wave_contract(normal_contracts[player.id],context.season,context.lineup_rules,wave,
                premium_basis_points=premium, run_seed=getattr(context,'run_seed',0))
        return wave_contracts[key]

    def reserved(owner, player=None):
        added = int(player is not None)
        filled = int(player is not None and counts[owner][player.position] < rules[player.position][1])
        return minimum * max(missing[owner]-filled, minimum_total-len(rosters[owner])-added, 0)

    def can_sign(owner, player, deal):
        return ((pre_camp or len(rosters[owner]) < maximum_total)
                and budgets[owner] + deal.annual_salary + reserved(owner,player) <= cap)

    def sign(owner, identity):
        player = pool.get(identity)
        if player is None:
            raise ValueError('That free agent is no longer available')
        deal = demand(owner, player)
        if not can_sign(owner,player,deal):
            raise ValueError('Signing must fit roster space, salary cap and required roster minimums')
        if counts[owner][player.position] < rules[player.position][1]:
            missing[owner] -= 1
        counts[owner][player.position] += 1
        budgets[owner] += deal.annual_salary
        rosters[owner].append(replace(player,contract=deal,rookie_offer=None))
        del pool[identity]
        transactions.append({'wave':wave,'team':asdict(TEAM_BY_ID[owner]),
                             'player_id':identity,'name':player.name,'annual_salary':deal.annual_salary})

    def cpu_turns():
        for owner in order[1:]:
            players = rosters[owner]
            if len(players) >= (roster_limit(context)+6 if pre_camp else roster_limit(context)):
                continue
            weakest = {}
            for player in players:
                weakest[player.position] = min(weakest.get(player.position,player.rating),player.rating)
            candidates = []
            for player in pool.values():
                target, floor = rules[player.position]
                count = counts[owner][player.position]
                shortage = count < floor
                baseline = weakest.get(player.position,40)
                if not shortage and count >= target and player.rating <= baseline+3:
                    continue
                deal = demand(owner, player)
                if not can_sign(owner,player,deal):
                    continue
                benefit = (100 if shortage else max(0,player.rating-baseline)) + .1*max(0,potential_for(player)-player.rating)
                score = CPU_GROUP_IMPORTANCE[player.position]*benefit/max(1,deal.annual_salary/1_000_000)**.3
                candidates.append((score,player.rating,player.id))
            if candidates:
                _,_,identity = max(candidates)
                sign(owner,identity)

    for owner, players in rosters.items():
        if not pre_camp and (len(players) > roster_limit(context) or pending_renewals(players,context)):
            raise ValueError('Finalize roster cuts and expired contracts before free agency')
        if not pre_camp and budgets[owner]+reserved(owner)>cap:
            raise ValueError('Clear cap space for required roster minimums before free agency')
    for kind,identity in actions:
        if complete:
            raise ValueError('Free agency has already finished')
        if pre_camp and kind in ('resign','drop'):
            if not identity: raise ValueError('Roster decisions require a player ID')
            if kind == 'resign':
                from .player_contracts import renew_player
                rosters[team_id]=renew_player(rosters[team_id],identity,context.season,context.lineup_rules,context,team_id)
                budgets[team_id]=cap_payroll(rosters[team_id],context,context.season,team_id)
            else:
                from .preseason import release_player
                latest=replace(context,free_agents=tuple(pool.values()))
                latest=replace_lineup_rosters(latest,tuple((o,tuple(ps)) for o,ps in rosters.items()))
                context=release_player(latest,team_id,identity)
                rosters={o:list(ps) for o,ps in context}
                pool={p.id:p for p in context.free_agents}
                counts[team_id]=Counter(p.position for p in rosters[team_id])
                missing[team_id]=sum(max(0,floor-counts[team_id][pos]) for pos,(_,floor) in rules.items())
                budgets[team_id]=cap_payroll(rosters[team_id],context,context.season,team_id)
                states=dict(context.development)
            continue
        if kind == 'finish' and pre_camp and pending_renewals(rosters[team_id],context):
            raise ValueError('Re-sign or release your expired players before finishing free agency')
        if kind == 'sign':
            sign(team_id,identity)
        elif kind not in ('pass','finish') or identity:
            raise ValueError('Invalid free agency action')
        cpu_turns()
        if kind == 'finish':
            # Resolve the league without returning control to the user.
            for remaining_wave in range(wave+1,MAX_WAVES+1):
                wave = remaining_wave
                cpu_turns()
            complete = True
        elif wave == MAX_WAVES:
            if pre_camp and pending_renewals(rosters[team_id],context):
                raise ValueError('Resolve your expired contracts before the final wave ends')
            complete = True
        else:
            wave += 1
    if complete:
        excluded = set(pool) | {p.id for players in rosters.values() for p in players}
        rosters = {owner:fill_roster(players,owner,season,request_seed,excluded,context=context,
                                   identity_suffix='-free-agency') for owner,players in rosters.items()}
        for owner,players in rosters.items():
            validate_roster(players,minimum_total=roster_minimum(context),maximum_total=None if pre_camp else roster_limit(context))
            if not pre_camp and cap_payroll(players,context,context.season,owner)>cap:
                raise ValueError('Final roster exceeds the salary cap')
    context = replace(context, free_agents=tuple(pool[k] for k in sorted(pool)))
    context = replace_lineup_rosters(context,tuple((owner,ranked_players(players)) for owner,players in sorted(rosters.items())))
    if not pre_camp: context = capture_rotation(context)
    available = []
    if not complete:
        for player in pool.values():
            deal = demand(team_id, player)
            available.append({'id':player.id,'name':player.name,'position':player.position,'age':player.age,
                **rating_payload(player,context,states), 'annual_salary':deal.annual_salary,'years':deal.years,
                'affordable':can_sign(team_id,player,deal)})
    premium_payload = {'destination_premium': {
        'strength_basis_points': premiums[team_id][0], 'record_basis_points': premiums[team_id][1],
        'basis_points': sum(premiums[team_id])}} if context.lineup_rules >= 34 else {}
    return {**premium_payload, 'wave':wave,'percent':wave_percent(wave),'complete':complete,
            'actions':[{'kind':kind,'player_id':identity} for kind,identity in actions],
            'order':[asdict(TEAM_BY_ID[owner]) for owner in order],
            'available':sorted(available,key=lambda p:(-p['current_rating'],p['id'])),
            'transactions':transactions}, context
