"""Fixed signed contracts and versioned annual salary/cap schedules."""
from dataclasses import asdict, dataclass, replace
from decimal import Decimal, ROUND_HALF_UP
from functools import lru_cache

MINIMUM_SALARY = 1_000_000
# Annual salary for a 75-current-rated player; game-balance values, not NFL data.
BASE_SALARIES = {'QB':8_000_000,'WR':4_500_000,'TE':3_000_000,'RB':3_000_000,
                 'OL':4_000_000,'K':1_500_000,'DL':4_500_000,'LB':3_500_000,
                 'CB':4_500_000,'S':3_500_000}


# Annual dollars at the $200M base cap, calibrated from 2026 NFL APY/cap
# relationships. These are game rating anchors, not NFL player grades.
MARKET_RATINGS = (40, 60, 70, 75, 80, 90, 99)
MARKET_SALARIES = {
    'QB': (1_000_000, 1_500_000, 7_800_000, 12_000_000, 20_000_000, 34_000_000, 42_000_000),
    'WR': (1_000_000, 1_500_000, 4_225_000, 6_500_000, 10_000_000, 20_000_000, 28_000_000),
    'TE': (1_000_000, 1_500_000, 2_925_000, 4_500_000, 8_000_000, 12_000_000, 14_000_000),
    'RB': (1_000_000, 1_500_000, 2_600_000, 4_000_000, 7_000_000, 12_000_000, 15_000_000),
    'OL': (1_000_000, 1_500_000, 3_575_000, 5_500_000, 8_000_000, 14_000_000, 19_000_000),
    'DL': (1_000_000, 1_500_000, 4_225_000, 6_500_000, 10_000_000, 20_000_000, 30_000_000),
    'LB': (1_000_000, 1_500_000, 2_925_000, 4_500_000, 6_000_000, 11_000_000, 14_000_000),
    'CB': (1_000_000, 1_500_000, 3_900_000, 6_000_000, 9_000_000, 16_000_000, 22_000_000),
    'S': (1_000_000, 1_500_000, 2_925_000, 4_500_000, 6_000_000, 11_000_000, 14_000_000),
    'K': (1_000_000, 1_050_000, 1_170_000, 1_800_000, 2_500_000, 4_000_000, 4_600_000),
}


def market_salary(position, rating, season, rules=21):
    """Versioned market demand, signing-cap scaling and $10k rounding."""
    if rules >= 27:
        # Floor through 60; smoothly accelerating cubic above it. Integer powers
        # and Decimal keep half-rating quotes and replay independent of floats.
        ability = max(Decimal(60), min(Decimal(99), Decimal(str(rating))))
        share = ((ability-40)**3-20**3) / Decimal(59**3-20**3)
        floor = Decimal(minimum_salary(season,rules))
        ceiling = Decimal(MARKET_SALARIES[position][-1]) * salary_cap(season,rules) / SALARY_CAP
        raw = floor + (ceiling-floor)*share
        return max(minimum_salary(season,rules),int((raw/10_000).quantize(Decimal('1'),rounding=ROUND_HALF_UP))*10_000)
    rating = max(MARKET_RATINGS[0], min(MARKET_RATINGS[-1], Decimal(str(rating))))
    amounts = MARKET_SALARIES[position]
    for index, (low, high) in enumerate(zip(MARKET_RATINGS, MARKET_RATINGS[1:])):
        if rating <= high:
            raw = Decimal(amounts[index]) + Decimal(amounts[index+1]-amounts[index]) * (rating-low) / (high-low)
            raw = raw * salary_cap(season,21) / SALARY_CAP
            return max(minimum_salary(season,21), int((raw/10_000).quantize(Decimal('1'),rounding=ROUND_HALF_UP))*10_000)
    raise AssertionError('Unreachable salary anchor')


@dataclass(frozen=True)
class DeadCapCharge:
    owner: str
    player_id: str
    player_name: str
    annual_salary: int
    start_season: int
    end_season: int
    signed_season: int


def record_release(context, owner, player, season):
    """Immutable obligations: unsigned and expired releases owe nothing."""
    if getattr(context,'lineup_rules',1)<23 or player.contract is None:
        return context
    contract=player.contract
    start=max(season,contract.signed_season)
    end=contract.signed_season+contract.years-1
    if end<start:return context
    charge=DeadCapCharge(owner,player.id,player.name,contract.annual_salary,start,end,contract.signed_season)
    existing=context.dead_cap
    if charge in existing:return context
    return replace(context,dead_cap=existing+(charge,))


def payroll_owner(players, context, owner=None):
    if owner is not None:return owner
    ids={p.id for p in players}
    owners=[team for team,roster in context if any(p.id in ids for p in roster)]
    if len(owners)!=1:raise ValueError('Payroll requires an unambiguous team')
    return owners[0]


def dead_cap_total(context, owner, season):
    if getattr(context,'lineup_rules',1)<23:return 0
    return sum(c.annual_salary for c in context.dead_cap if c.owner==owner and c.start_season<=season<=c.end_season)


def cap_payroll(players, context, season=None, owner=None):
    year=context.season if season is None else season
    dead=dead_cap_total(context,payroll_owner(players,context,owner),year) if getattr(context,'lineup_rules',1)>=23 else 0
    return payroll(players)+dead


@dataclass(frozen=True)
class PlayerContract:
    annual_salary: int
    signed_season: int
    years: int
    category: str
    draft_round: int | None = None
    overall_pick: int | None = None


@lru_cache(maxsize=4096, typed=True)
def annual_amount(base, season, quantum):
    """5% from each previously rounded year; integer-only half-up arithmetic."""
    if type(season) is not int or season < 1:
        raise ValueError('Salary schedule season must be a positive integer')
    amount = base
    for _ in range(season-1):
        amount = ((amount * 105 + 50 * quantum) // (100 * quantum)) * quantum
    return amount


def minimum_salary(season, rules=15):
    return annual_amount(MINIMUM_SALARY,season,10_000) if rules >= 17 else MINIMUM_SALARY


def salary_cap(season, rules=16):
    return annual_amount(SALARY_CAP,season,1_000_000) if rules >= 17 else SALARY_CAP


def payroll_floor(season, rules=16):
    if rules < 17: return PAYROLL_FLOOR
    return ((salary_cap(season,rules)*80 + 50_000_000)//100_000_000)*1_000_000


def starting_contract(player, season, rules=15):
    if player.id.startswith('replacement-'):
        signed = int(player.id.split('-')[2])
        return PlayerContract(minimum_salary(signed,rules),signed,1,'replacement')
    if player.id.startswith('rookie-'):
        raise ValueError('Drafted players need their recorded selection to assign salary')
    # Inherited contracts were already signed before the GM arrived. Preserve
    # their original terms; the current market applies only to new agreements.
    return veteran_contract(player,season,min(rules,20))


def salary_demand_rating(player, potential):
    """Keep the exact half-point average; potential is server-derived ability."""
    if type(potential) is not int or not 1<=potential<=99:
        raise ValueError('A valid potential rating is required for salary demands')
    return Decimal(player.rating+potential)/2


def contract_potential(player, context):
    if context is None:
        raise ValueError('Salary demands require the player development context')
    from .development import rating_view
    return rating_view(player,context)['potential_rating']


def veteran_contract(player, season, rules=15, potential=None):
    category, years = ('franchise',5) if player.rating >= 90 else ('low_rated',2) if player.rating < 70 else ('veteran',4) if player.age >= 28 else ('young',3)
    if rules >= 21:
        rating=salary_demand_rating(player,potential) if rules>=26 else player.rating
        salary = market_salary(player.position,rating,season,rules)
    else:
        raw = Decimal(BASE_SALARIES[player.position]) * player.rating ** 2 / 75 ** 2
        salary = max(minimum_salary(season,rules),int((raw / 10_000).quantize(Decimal('1'),rounding=ROUND_HALF_UP))*10_000)
    return PlayerContract(salary,season,years,category)


def rookie_contract(round_number, overall, season, rules=15):
    if not 1 <= round_number <= 6 or not (round_number-1)*30 < overall <= round_number*30:
        raise ValueError('Draft round and overall pick must match the 30-team draft')
    if round_number == 1:
        salary = 5_000_000 if overall==1 else 4_500_000 if overall<=5 else 4_000_000 if overall<=15 else 3_500_000
    else:
        salary = {2:3_000_000,3:2_500_000,4:2_000_000,5:1_500_000,6:1_000_000}[round_number]
    years = 4 if round_number==1 else 3 if round_number<=3 else 2
    if rules >= 17: salary = annual_amount(salary,season,10_000)
    return PlayerContract(salary,season,years,'rookie',round_number,overall)


def signed_rosters(rosters, season, rules=15):
    return tuple((owner,tuple(p if p.contract is not None or p.rookie_offer is not None else replace(p,contract=starting_contract(p,season,rules))
                              for p in players)) for owner,players in rosters)



def inherited_payroll(rosters, owner, seed, season):
    """Career creation only: distribute an actual floor-to-cap signed payroll."""
    from .simulation import ROSTER_RULES, _run_number
    from .retirement import retirement_age
    players=dict(rosters)[owner]
    if any(p.contract is None or p.rookie_offer is not None for p in players):
        raise ValueError('Inherited payroll requires an initially signed roster')
    if any(p.contract.category=='inherited_bad' for p in players):
        return rosters
    def draw(purpose):return _run_number(f'inherited-payroll:{owner}:{purpose}',seed)
    low,high=payroll_floor(season,25),salary_cap(season,25)
    target=low+draw('total')%((high-low)//1_000_000+1)*1_000_000
    weak=[p for p in players if p.rating<70 and p.depth>ROSTER_RULES[p.position][1]]
    groups=([p for p in weak if p.position=='QB'],
            [p for p in weak if p.position in ('WR','TE','RB','OL')],
            [p for p in weak if p.position in ('DL','LB','CB','S')])
    bad={}
    for index,group in enumerate(groups):
        if not group:continue
        # Prefer deals that survive the first offseason, without changing ages
        # or retirement rules to manufacture the financial challenge.
        viable=[p for p in group if retirement_age(p,seed)>=p.age+2]
        selected=min(viable or group,key=lambda p:draw(f'bad:{index}:{p.id}'))
        quote_rating=78+draw(f'price:{selected.id}')%5 if selected.position=='QB' else 82+draw(f'price:{selected.id}')%7
        bad[selected.id]=replace(selected.contract,
            annual_salary=market_salary(selected.position,quote_rating,season),
            years=3+draw(f'term:{selected.id}')%2,category='inherited_bad')
    ordinary=[p for p in players if p.id not in bad]
    minimum=minimum_salary(season,25)
    extra=target-sum(c.annual_salary for c in bad.values())-len(ordinary)*minimum
    if extra<0 or extra%10_000:raise ValueError('Inherited payroll cannot fit its required contracts')
    units=extra//10_000
    weights={p.id:max(1,p.contract.annual_salary-minimum) for p in ordinary}
    total_weight=sum(weights.values())
    portions={identity:units*weight//total_weight for identity,weight in weights.items()}
    remaining=units-sum(portions.values())
    order=sorted(weights,key=lambda identity:(-(units*weights[identity]%total_weight),draw(f'rounding:{identity}')))
    for identity in order[:remaining]:portions[identity]+=1
    updated=tuple(replace(p,contract=bad[p.id] if p.id in bad else replace(p.contract,
                  annual_salary=minimum+portions[p.id]*10_000)) for p in players)
    if payroll(updated)!=target:raise AssertionError('Inherited payroll must match the seeded target')
    return tuple((team,updated if team==owner else roster) for team,roster in rosters)

def ensure_contracts(context, season):
    return replace(context,rosters=signed_rosters(context.rosters,season,getattr(context,"lineup_rules",1)))


def attach_historical_draft_contracts(context, board):
    """Recover exact draft-slot pay from replayed picks when upgrading a save."""
    contracts = {pick['player']['id']:rookie_contract(pick['round'],pick['overall'],board['draft_season'],getattr(context,'lineup_rules',1)) for pick in board['picks']}
    rosters = tuple((owner,tuple(replace(p,contract=contracts[p.id]) if p.contract is None and p.rookie_offer is None and p.id in contracts else p
                                for p in players)) for owner,players in context)
    return ensure_contracts(replace(context,rosters=rosters),board['draft_season'])


def contract_payload(contract, season, rules=15):
    end = contract.signed_season + contract.years - 1
    return {**asdict(contract),**({'fully_guaranteed':True} if rules>=23 else {}),'expires_after_season':end,
            'years_remaining':max(0,min(contract.years,end-season+1)),
            'status':'upcoming' if season<contract.signed_season else 'active' if season<=end else 'expired' if rules>=20 else 'renewal_due'}


def public_player_fields(player, context=()):
    result = asdict(player)
    result.pop('contract')
    result.pop('rookie_offer')
    if getattr(context,'lineup_rules',1) >= 15 and player.contract is not None:
        result['contract'] = contract_payload(player.contract,context.season,getattr(context,'lineup_rules',1))
    if getattr(context,'lineup_rules',1) >= 19 and player.rookie_offer is not None:
        result['contract_offer'] = rookie_offer_payload(player.rookie_offer)
    if getattr(context,'lineup_rules',1) >= 20 and contract_expired(player,context.season):
        potential=contract_potential(player,context) if context.lineup_rules>=26 else None
        offer = veteran_contract(player,context.season,context.lineup_rules,potential)
        result['renewal_offer'] = {'annual_salary':offer.annual_salary,'years':offer.years,
            'starts_season':offer.signed_season,'category':offer.category,
            'annual_change':offer.annual_salary-player.contract.annual_salary}
        if context.lineup_rules>=26:
            result['renewal_offer']['demand_rating']=float(salary_demand_rating(player,potential))
        if context.lineup_rules>=23:
            owner=payroll_owner([player],context)
            amount=cap_payroll(dict(context)[owner],context,owner=owner)
            result['renewal_offer']['affordable']=amount+offer.annual_salary-player.contract.annual_salary<=salary_cap(context.season,context.lineup_rules)
    return result


SALARY_CAP = 200_000_000
PAYROLL_FLOOR = 160_000_000


def contract_terms(player):
    """Cap checks include unsigned rookie holds without pretending they are deals."""
    if player.contract is not None and player.rookie_offer is not None:
        raise ValueError('A player cannot have both a contract and a provisional offer')
    terms = player.contract or player.rookie_offer
    if terms is None:
        raise ValueError('Payroll requires signed or provisional terms for every player')
    return terms


def payroll(players):
    """Count retained signed salaries plus reserved rookie pay toward the cap."""
    return sum(contract_terms(p).annual_salary for p in players)


def rookie_offer_payload(offer):
    return {'annual_salary':offer.annual_salary,'years':offer.years,
            'category':'rookie','draft_round':offer.draft_round,'overall_pick':offer.overall_pick,
            'starts_season':offer.signed_season,'status':'provisional'}


def sign_retained_rookies(context, season):
    """Commit only the survivors after final cap/roster validation."""
    def sign(player):
        if player.rookie_offer is None: return player
        if player.contract is not None or player.rookie_offer.signed_season != season:
            raise ValueError('Rookie signing must match the upcoming playing season')
        offer = player.rookie_offer
        if offer != rookie_contract(offer.draft_round,offer.overall_pick,season,context.lineup_rules):
            raise ValueError('Rookie offer must match its recorded draft slot')
        return replace(player,contract=offer,rookie_offer=None)
    return replace(context,rosters=tuple((owner,tuple(sign(p) for p in players)) for owner,players in context))


def payroll_payload(players, context, season=None, owner=None):
    if getattr(context,'lineup_rules',1) < 16:
        return {}
    season = context.season if season is None else season
    rules = context.lineup_rules
    roster_total=payroll(players)
    dead=dead_cap_total(context,payroll_owner(players,context,owner),season) if rules>=23 else 0
    total, cap, floor = roster_total+dead, salary_cap(season,rules), payroll_floor(season,rules)
    committed = sum(p.contract.annual_salary for p in players if p.contract is not None
                    and (rules < 20 or not contract_expired(p,season)))
    rookie_holds = sum(p.rookie_offer.annual_salary for p in players if p.rookie_offer is not None)
    expired_holds = roster_total-committed-rookie_holds if rules >= 20 else 0
    floor_payroll = committed if rules >= 19 else total
    return {'payroll': {'total':total,'cap':cap,'floor':floor,
            'cap_space':cap-total,'over_cap':max(0,total-cap),
            'below_floor':max(0,floor-floor_payroll),'floor_enforced':False,
            **({'committed':committed,'rookie_holds':rookie_holds} if rules>=19 else {}),
            **({'expired_holds':expired_holds} if rules>=20 else {}),
            **({'dead_cap':dead} if rules>=23 else {}),
            **({'season':season,'minimum_salary':minimum_salary(season,rules)} if rules>=17 else {})}}


def payroll_breakdown(players, context, season=None, owner=None):
    """Current budget detail only; never reprice or modify a contract."""
    if getattr(context,'lineup_rules',1) < 16:
        return {}
    year = context.season if season is None else season
    owner = payroll_owner(players,context,owner)
    categories = {key: [] for key in ('signed','rookie_holds','expired_holds','dead_cap')}
    for player in players:
        terms = contract_terms(player)
        kind = ('rookie_holds' if player.rookie_offer is not None else
                'expired_holds' if context.lineup_rules>=20 and contract_expired(player,year) else 'signed')
        categories[kind].append({'player_id':player.id,'name':player.name,'position':player.position,
                                'amount':terms.annual_salary,
                                'expires_after_season':terms.signed_season+terms.years-1})
    if context.lineup_rules>=23:
        for charge in context.dead_cap:
            if charge.owner==owner and charge.start_season<=year<=charge.end_season:
                categories['dead_cap'].append({'player_id':charge.player_id,'name':charge.player_name,
                    'position':None,'amount':charge.annual_salary,'expires_after_season':charge.end_season})
    groups = [{'kind':key,'total':sum(p['amount'] for p in rows),
               'players':sorted(rows,key=lambda p:(-p['amount'],p['name'],p['player_id']))}
              for key,rows in categories.items()]
    floor_payroll = groups[0]['total'] if context.lineup_rules>=19 else sum(g['total'] for g in groups)
    return {'payroll_breakdown':{'season':year,'floor_payroll':floor_payroll,'categories':groups}}


def cap_ready(players, context, season=None, owner=None):
    return getattr(context,'lineup_rules',1) < 16 or cap_payroll(players,context,season,owner) <= salary_cap(context.season if season is None else season,context.lineup_rules)


def cap_release(players, identity, owner, season, seed, context, excluded):
    """An atomic release/refill preserves position and total minimums at the cap.

    This changes the roster only. Guaranteed-career callers separately record
    the released contract and validate the resulting cap obligations.
    """
    from .retirement import fill_roster
    if not any(p.id == identity for p in players):
        raise ValueError('Player is not on this roster')
    return fill_roster([p for p in players if p.id != identity],owner,season,seed,
                       excluded,context=context)


def release_preview(players, player, owner, season, seed, context):
    """Read-only projection using the same release/refill and cap rules as cuts.

    Replacement identities are deliberately omitted: prior cuts can change their
    generated IDs, but their position and minimum-pay obligations are identical.
    """
    from .career import drop_players
    from .retirement import fill_roster
    from .simulation import roster_minimum
    before = payroll_payload(players,context,season,owner)['payroll']
    charged = record_release(context,owner,player,season)
    schedule = []
    if context.lineup_rules >= 23 and player.contract is not None:
        terms = player.contract
        schedule = [{'season': year, 'amount': terms.annual_salary}
                    for year in range(max(season,terms.signed_season),terms.signed_season+terms.years)]
    preview = {'allowed': True, 'season': season, 'dead_cap_schedule': schedule,
               'new_dead_cap': dead_cap_total(charged,owner,season)-dead_cap_total(context,owner,season),
               'total_obligation': sum(row['amount'] for row in schedule),
               'payroll_before': before['total'], 'cap_space_before': before['cap_space'],
               'cap': before['cap']}
    try:
        if context.lineup_rules >= 23 or not cap_ready(players,context,season,owner):
            remaining = cap_release(players,player.id,owner,season-1,seed,context,(player.id,))
        else:
            remaining = drop_players(players,(player.id,),roster_minimum(context))
            remaining = fill_roster(remaining,owner,season-1,seed,(player.id,),context=context)
        after = payroll_payload(remaining,charged,season,owner)['payroll']
        original_ids = {p.id for p in players}
        replacements = [{'position': p.position, 'annual_salary': p.contract.annual_salary}
                        for p in remaining if p.id not in original_ids]
        preview.update(payroll_after=after['total'],cap_space_after=after['cap_space'],
                       cap_space_change=after['cap_space']-before['cap_space'],
                       replacements=replacements,
                       replacement_cost=sum(p['annual_salary'] for p in replacements))
        if context.lineup_rules >= 23 and after['committed']+after['dead_cap'] > after['cap']:
            raise ValueError('This release cannot fit its guaranteed salary plus required replacement under the cap')
    except ValueError as error:
        preview.update(allowed=False,reason=str(error))
    return preview


def cpu_cap_cuts(players, owner, season, seed, context):
    if getattr(context,'lineup_rules',1)>=23:
        raise ValueError('Guaranteed CPU cuts require their obligation-aware offseason transaction')
    remaining, excluded = list(players), []
    while not cap_ready(remaining,context,season+1):
        # Preserve ability per dollar; the ID tie-break makes replay deterministic.
        eligible = [p for p in remaining if contract_terms(p).annual_salary > minimum_salary(season+1,context.lineup_rules)]
        if not eligible:
            raise ValueError('CPU roster cannot fit under the salary cap')
        player = min(eligible,key=lambda p: (p.rating/contract_terms(p).annual_salary,-contract_terms(p).annual_salary,p.id))
        excluded.append(player.id)
        remaining = cap_release(remaining,player.id,owner,season,seed,context,excluded)
    return remaining



def contract_expired(player, season):
    return player.contract is not None and season >= player.contract.signed_season + player.contract.years


def pending_renewals(players, context):
    return sum(contract_expired(p,context.season) for p in players) if getattr(context,'lineup_rules',1)>=20 else 0


def renew_player(players, identity, season, rules, context=None, owner=None):
    player = next((p for p in players if p.id==identity),None)
    if player is None: raise ValueError('Player is not on this roster')
    if not contract_expired(player,season):
        raise ValueError('Only an expired contract can be re-signed after training camp')
    potential=contract_potential(player,context) if rules>=26 else None
    deal = veteran_contract(player,season,rules,potential)
    updated=[replace(p,contract=deal) if p.id==identity else p for p in players]
    if rules>=23 and context is not None and not cap_ready(updated,context,season,owner):
        raise ValueError('Re-signing would exceed the salary cap. Release unsigned rookies or expired contracts first; signed salaries are fully guaranteed.')
    return updated



# Marginal on-field usage by depth slot. These are roster-planning priorities,
# not the future drive engine's unit ratings.
CPU_SLOT_WEIGHTS = {
    'QB': (.95, .05), 'WR': (.40, .30, .20, .10),
    'RB': (.75, .25), 'TE': (.75, .25),
    'OL': (.17, .17, .17, .17, .17, .10, .05),
    'DL': (.1875, .1875, .1875, .1875, .20, .05),
    'LB': (.25, .25, .25, .20, .05),
    'CB': (.40, .35, .20, .05), 'S': (.50, .40, .10),
    'K': (1.0,),
}
# Keep competing position groups meaningful without valuing a backup QB as
# highly as a contributing wide receiver, corner or lineman.
CPU_GROUP_IMPORTANCE = {
    'QB': .25, 'WR': .23, 'RB': .13, 'TE': .12, 'OL': .27,
    'DL': .34, 'LB': .22, 'CB': .28, 'S': .16, 'K': .08,
}


def cpu_contract_priorities(players, context, year):
    """Deterministic marginal roster value per salary for CPU retention."""
    by_position = {}
    for p in players:
        by_position.setdefault(p.position, []).append(p)
    priorities = {}
    for position, group in by_position.items():
        group.sort(key=lambda p: (-p.rating, p.id))
        weights = CPU_SLOT_WEIGHTS[position]
        for index, player in enumerate(group):
            slot = weights[index] if index < len(weights) else 0.01
            potential = contract_potential(player, context)
            upside = max(0, potential-player.rating)
            ability = max(0, player.rating-50) + .20*upside
            if contract_expired(player,year):
                salary = veteran_contract(player,year,context.lineup_rules,potential).annual_salary
            else:
                salary = contract_terms(player).annual_salary
            # Price discourages costly depth, but does not let minimum-salary
            # backups routinely outrank indispensable starters.
            cost = max(1, salary/1_000_000)**.30
            priorities[player.id] = CPU_GROUP_IMPORTANCE[position]*slot*ability/cost
    return priorities


def smart_cpu_roster_cuts(players, context, year):
    """Cut surplus non-guaranteed depth before creating guaranteed dead cap."""
    from collections import Counter
    from .career import arrange_depth
    from .simulation import roster_limit, roster_minimum, roster_rules, validate_roster
    remaining = list(players)
    minimums = {position: minimum for position, (_, minimum) in roster_rules(context).items()}
    priorities = cpu_contract_priorities(remaining, context, year)
    while len(remaining) > roster_limit(context):
        counts = Counter(p.position for p in remaining)
        eligible = [p for p in remaining if counts[p.position] > minimums[p.position]]
        if not eligible:
            raise ValueError('No legal CPU cut is available')
        # A valid signed deal cannot be undone to free cap space; releasing it
        # incurs the same amount as dead cap. Prefer unsigned/expired surplus.
        cut = min(eligible, key=lambda p:(
            p.contract is not None and not contract_expired(p,year),
            priorities.get(p.id,0), -contract_terms(p).annual_salary, p.id))
        remaining.remove(cut)
    validate_roster(remaining,minimum_total=roster_minimum(context),
                    maximum_total=roster_limit(context))
    return arrange_depth(remaining)


def smart_cpu_offseason(players, owner, season, seed, context):
    """Prioritize valuable expiring players without breaking cap guarantees."""
    year = season+1
    original = tuple(players)
    priorities = cpu_contract_priorities(original,context,year)
    remaining = smart_cpu_roster_cuts(players,context,year)
    retained_ids = {player.id for player in remaining}
    excluded = [player.id for player in original if player.id not in retained_ids]
    for player in original:
        if player.id not in retained_ids:
            context = record_release(context,owner,player,year)

    def release(player):
        nonlocal remaining, context
        excluded.append(player.id)
        remaining = cap_release(remaining,player.id,owner,season,seed,context,excluded)
        context = record_release(context,owner,player,year)

    # Only unsigned/expired holds provide relief; releasing a guaranteed deal
    # merely converts its salary to dead cap and should not be a budget tactic.
    minimum = minimum_salary(year, context.lineup_rules)
    while not cap_ready(remaining,context,year,owner):
        eligible = [p for p in remaining if
                    (p.contract is None or contract_expired(p,year))
                    and contract_terms(p).annual_salary > minimum]
        if not eligible:
            raise ValueError('CPU guaranteed obligations cannot fit under the salary cap')
        release(min(eligible,key=lambda p:(priorities.get(p.id,0),-contract_terms(p).annual_salary,p.id)))

    expiring = sorted((p for p in remaining if contract_expired(p,year)),
                      key=lambda p:(-priorities.get(p.id,0),p.id))
    for target in expiring:
        if not any(p.id == target.id for p in remaining):
            continue
        while True:
            try:
                remaining = renew_player(remaining,target.id,year,context.lineup_rules,context,owner)
                break
            except ValueError:
                # Give a valuable starter first claim on available cap before
                # spending on less useful expiring depth.
                lesser = [p for p in remaining if p.id != target.id
                          and contract_expired(p,year)
                          and priorities.get(p.id,0) < priorities.get(target.id,0)]
                if not lesser:
                    release(target)
                    break
                release(min(lesser,key=lambda p:(priorities.get(p.id,0),p.id)))
    return remaining,context


def guaranteed_cpu_offseason(players, owner, season, seed, context):
    """Honor obligations; only unsigned/expired holds can provide cap relief."""
    if context.lineup_rules >= 28:
        return smart_cpu_offseason(players,owner,season,seed,context)
    from .career import cpu_cuts
    from .simulation import roster_limit,roster_minimum
    from .retirement import fill_roster
    year=season+1
    original=tuple(players)
    remaining=cpu_cuts(players,roster_limit(context),roster_minimum(context))
    retained={p.id for p in remaining}
    for p in original:
        if p.id not in retained:context=record_release(context,owner,p,year)
    excluded=[p.id for p in original if p.id not in retained]
    while not cap_ready(remaining,context,year,owner):
        eligible=[p for p in remaining if (p.contract is None or contract_expired(p,year))
                  and contract_terms(p).annual_salary>minimum_salary(year,context.lineup_rules)]
        if not eligible:raise ValueError('CPU guaranteed obligations cannot fit under the salary cap')
        p=min(eligible,key=lambda p:(p.rating/contract_terms(p).annual_salary,-contract_terms(p).annual_salary,p.id))
        excluded.append(p.id)
        remaining=cap_release(remaining,p.id,owner,season,seed,context,excluded)
    for p in tuple(remaining):
        if not contract_expired(p,year):continue
        try:
            remaining=renew_player(remaining,p.id,year,context.lineup_rules,context,owner)
        except ValueError:
            excluded.append(p.id)
            remaining=fill_roster([v for v in remaining if v.id!=p.id],owner,season,seed,excluded,context=context)
    return remaining,context
