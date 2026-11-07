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


def market_salary(position, rating, season):
    """Interpolate market anchors, scale to the signing cap, round to $10k."""
    rating = max(MARKET_RATINGS[0], min(MARKET_RATINGS[-1], rating))
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


def veteran_contract(player, season, rules=15):
    category, years = ('franchise',5) if player.rating >= 90 else ('low_rated',2) if player.rating < 70 else ('veteran',4) if player.age >= 28 else ('young',3)
    if rules >= 21:
        salary = market_salary(player.position,player.rating,season)
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
        offer = veteran_contract(player,context.season,context.lineup_rules)
        result['renewal_offer'] = {'annual_salary':offer.annual_salary,'years':offer.years,
            'starts_season':offer.signed_season,'category':offer.category,
            'annual_change':offer.annual_salary-player.contract.annual_salary}
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
    deal = veteran_contract(player,season,rules)
    updated=[replace(p,contract=deal) if p.id==identity else p for p in players]
    if rules>=23 and context is not None and not cap_ready(updated,context,season,owner):
        raise ValueError('Re-signing would exceed the salary cap. Release unsigned rookies or expired contracts first; signed salaries are fully guaranteed.')
    return updated



def guaranteed_cpu_offseason(players, owner, season, seed, context):
    """Honor obligations; only unsigned/expired holds can provide cap relief."""
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
