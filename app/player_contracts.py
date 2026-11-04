"""Fixed player contracts and versioned payroll accounting (no annual inflation yet)."""
from dataclasses import asdict, dataclass, replace
from decimal import Decimal, ROUND_HALF_UP

MINIMUM_SALARY = 1_000_000
# Annual salary for a 75-current-rated player; game-balance values, not NFL data.
BASE_SALARIES = {'QB':8_000_000,'WR':4_500_000,'TE':3_000_000,'RB':3_000_000,
                 'OL':4_000_000,'K':1_500_000,'DL':4_500_000,'LB':3_500_000,
                 'CB':4_500_000,'S':3_500_000}


@dataclass(frozen=True)
class PlayerContract:
    annual_salary: int
    signed_season: int
    years: int
    category: str
    draft_round: int | None = None
    overall_pick: int | None = None


def starting_contract(player, season):
    if player.id.startswith('replacement-'):
        return PlayerContract(MINIMUM_SALARY,int(player.id.split('-')[2]),1,'replacement')
    if player.id.startswith('rookie-'):
        raise ValueError('Drafted players need their recorded selection to assign salary')
    category, years = ('franchise',5) if player.rating >= 90 else ('low_rated',2) if player.rating < 70 else ('veteran',4) if player.age >= 28 else ('young',3)
    raw = Decimal(BASE_SALARIES[player.position]) * player.rating ** 2 / 75 ** 2
    salary = max(MINIMUM_SALARY,int((raw / 10_000).quantize(Decimal('1'),rounding=ROUND_HALF_UP))*10_000)
    return PlayerContract(salary,season,years,category)


def rookie_contract(round_number, overall, season):
    if not 1 <= round_number <= 6 or not (round_number-1)*30 < overall <= round_number*30:
        raise ValueError('Draft round and overall pick must match the 30-team draft')
    if round_number == 1:
        salary = 5_000_000 if overall==1 else 4_500_000 if overall<=5 else 4_000_000 if overall<=15 else 3_500_000
    else:
        salary = {2:3_000_000,3:2_500_000,4:2_000_000,5:1_500_000,6:1_000_000}[round_number]
    years = 4 if round_number==1 else 3 if round_number<=3 else 2
    return PlayerContract(salary,season,years,'rookie',round_number,overall)


def signed_rosters(rosters, season):
    return tuple((owner,tuple(p if p.contract is not None else replace(p,contract=starting_contract(p,season))
                              for p in players)) for owner,players in rosters)


def ensure_contracts(context, season):
    return replace(context,rosters=signed_rosters(context.rosters,season))


def attach_historical_draft_contracts(context, board):
    """Recover exact draft-slot pay from replayed picks when upgrading a save."""
    contracts = {pick['player']['id']:rookie_contract(pick['round'],pick['overall'],board['draft_season']) for pick in board['picks']}
    rosters = tuple((owner,tuple(replace(p,contract=contracts[p.id]) if p.contract is None and p.id in contracts else p
                                for p in players)) for owner,players in context)
    return ensure_contracts(replace(context,rosters=rosters),board['draft_season'])


def contract_payload(contract, season):
    end = contract.signed_season + contract.years - 1
    return {**asdict(contract),'expires_after_season':end,
            'years_remaining':max(0,min(contract.years,end-season+1)),
            'status':'upcoming' if season<contract.signed_season else 'active' if season<=end else 'renewal_due'}


def public_player_fields(player, context=()):
    result = asdict(player)
    result.pop('contract')
    if getattr(context,'lineup_rules',1) >= 15 and player.contract is not None:
        result['contract'] = contract_payload(player.contract,context.season)
    return result


SALARY_CAP = 200_000_000
PAYROLL_FLOOR = 160_000_000


def payroll(players):
    """Count every retained annual salary, including renewal-due contracts."""
    if any(p.contract is None for p in players):
        raise ValueError('Payroll requires a signed contract for every player')
    return sum(p.contract.annual_salary for p in players)


def payroll_payload(players, context):
    if getattr(context,'lineup_rules',1) < 16:
        return {}
    total = payroll(players)
    return {'payroll': {'total':total,'cap':SALARY_CAP,'floor':PAYROLL_FLOOR,
            'cap_space':SALARY_CAP-total,'over_cap':max(0,total-SALARY_CAP),
            'below_floor':max(0,PAYROLL_FLOOR-total),'floor_enforced':False}}


def cap_ready(players, context):
    return getattr(context,'lineup_rules',1) < 16 or payroll(players) <= SALARY_CAP


def cap_release(players, identity, owner, season, seed, context, excluded):
    """An atomic release/refill preserves position and total minimums at the cap.

    Cap cuts can replace mandatory players; there are no dead-money penalties
    before player renewal and free agency are available.
    """
    from .retirement import fill_roster
    if not any(p.id == identity for p in players):
        raise ValueError('Player is not on this roster')
    return fill_roster([p for p in players if p.id != identity],owner,season,seed,
                       excluded,context=context)


def cpu_cap_cuts(players, owner, season, seed, context):
    remaining, excluded = list(players), []
    while not cap_ready(remaining,context):
        # Preserve ability per dollar; the ID tie-break makes replay deterministic.
        eligible = [p for p in remaining if p.contract.annual_salary > MINIMUM_SALARY]
        if not eligible:
            raise ValueError('CPU roster cannot fit under the salary cap')
        player = min(eligible,key=lambda p: (p.rating/p.contract.annual_salary,-p.contract.annual_salary,p.id))
        excluded.append(player.id)
        remaining = cap_release(remaining,player.id,owner,season,seed,context,excluded)
    return remaining
