"""Seeded aggregate playing-time roles; no substitutions or individual drives yet."""
import math

SLOTS = {'QB':1,'RB':1,'WR':2,'TE':1,'OL':5,'K':1,'DL':4,'LB':3,'CB':2,'S':2}
# Relative backup role before current ability and participation caps are applied.
BACKUP_ROLE = {'RB':.55,'WR':.28,'TE':.30,'OL':.012,'DL':.65,'LB':.35,'CB':.18,'S':.20}


def ability(rating):
    return math.exp((rating-70)/20)


def position_roles(players, position):
    group = sorted((p for p in players if p.position == position),key=lambda p:(p.depth,p.id))
    slots = SLOTS[position]
    if position in ('QB','K'):
        return {p.id:float(i==0) for i,p in enumerate(group)}
    young_count = sum(p.age < 25 and p.depth > slots for p in group)
    youth_floor = min(.05,.25*slots/young_count) if young_count else 0
    floors = [youth_floor if p.age < 25 and p.depth > slots else 0 for p in group]
    weights = [ability(p.rating) * (1 if p.depth <= slots else BACKUP_ROLE[position]) for p in group]
    shares = list(floors)
    remaining = slots-sum(shares)
    eligible = list(range(len(group)))
    while remaining > 1e-10 and eligible:
        total = sum(weights[i] for i in eligible)
        proposed = {i:remaining*weights[i]/total for i in eligible}
        capped = [i for i in eligible if proposed[i] >= 1-shares[i]]
        if capped:
            for i in capped:
                remaining -= 1-shares[i]
                shares[i] = 1
            eligible = [i for i in eligible if i not in capped]
        else:
            for i in eligible:shares[i] += proposed[i]
            break
    return {p.id:share for p,share in zip(group,shares)}


def season_roles(players):
    return {identity:share for position in SLOTS for identity,share in position_roles(players,position).items()}


def position_snaps(players, position, total):
    from .defense import _allocate
    group = sorted((p for p in players if p.position==position),key=lambda p:(p.depth,p.id))
    roles = position_roles(players,position)
    # Role floors survive integer rounding whenever a game has enough plays.
    young_count = sum(p.age<25 and p.depth>SLOTS[position] for p in group)
    youth_floor = min(.05,.25*SLOTS[position]/young_count) if young_count else 0
    floors = [min(total,math.floor(total*youth_floor)) if p.age<25 and p.depth>SLOTS[position]
              and position not in ('QB','K') and total else 0 for p in group]
    count = total*SLOTS[position]
    extra = _allocate(count-sum(floors),[max(0,total*roles[p.id]-floor) for p,floor in zip(group,floors)],
                      [total-floor for floor in floors])
    return {p.id:floor+value for p,floor,value in zip(group,floors,extra)}


def add_participation(box, opponent, roster):
    players = list(roster.values())
    offense = box['team_stats']['total_plays']+box['team_stats']['sacks_allowed']
    defense = opponent['team_stats']['total_plays']+opponent['team_stats']['sacks_allowed']
    kicks = sum(row['field_goals_attempted']+row['extra_points_attempted'] for row in box['kicking'])
    values = {}
    for position in SLOTS:
        total = kicks if position=='K' else defense if position in ('DL','LB','CB','S') else offense
        if position == 'OL':
            pass_work = position_snaps(players,'OL',box['team_stats']['pass_attempts']+box['team_stats']['sacks_allowed'])
            run_work = position_snaps(players,'OL',box['team_stats']['rush_attempts'])
            values.update({identity:count+run_work[identity] for identity,count in pass_work.items()})
        else:
            values.update(position_snaps(players,position,total))
    box['participation'] = [{'player_id':p.id,'snaps':values[p.id]} for p in players]


def receiving_weights(players, position, group_share):
    group = [p for p in players if p.position==position]
    roles = position_roles(players,position)
    weights = [roles[p.id]*ability(p.rating) for p in group]
    total = sum(weights)
    return group,[group_share*weight/total for weight in weights]
