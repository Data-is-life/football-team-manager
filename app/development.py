"""Seeded position-specific careers. Longevity is independent of talent and never exposed."""
from dataclasses import dataclass, replace
import hashlib

from .simulation import roster_for, ranked_players
from .league import TEAMS

# Development through, decline from, steep decline from, ordinary loss, steep loss.
CURVES = {
    'QB': (27,34,37,(2,4),(4,6)), 'RB': (23,27,30,(2,4),(4,6)),
    'WR': (25,30,33,(1,2),(4,6)), 'TE': (26,31,34,(1,2),(3,5)),
    'OL': (26,32,35,(1,2),(3,5)), 'DL': (24,29,32,(1,3),(3,5)),
    'LB': (24,28,31,(1,3),(3,5)), 'CB': (24,28,31,(1,3),(3,5)),
    'S': (25,30,33,(1,2),(3,5)),
}


def number(seed, player_id, purpose):
    return int.from_bytes(hashlib.sha256(f'development-v1:{seed}:{player_id}:{purpose}'.encode()).digest()[:8], 'big')


def longevity(seed, player_id, position):
    """No ability/rating argument: a journeyman has the same odds as an elite peer."""
    roll = number(seed, player_id, 'longevity') % 100
    exceptional, well = (4,24) if position == 'QB' else (2,14)
    if roll < exceptional:
        return 3 + number(seed, player_id, 'delay') % 2, True
    if roll < well:
        return 1 + number(seed, player_id, 'delay') % 2, False
    return 0, False


@dataclass(frozen=True)
class DevelopmentState:
    potential: int
    baseline: int
    change: int = 0


@dataclass(frozen=True)
class DevelopmentContext:
    rosters: tuple
    season: int
    run_seed: int
    development: tuple
    lineup_rules: int = 3
    rebuild_team: str | None = None

    def __iter__(self):
        return iter(self.rosters)


def initial_state(player, seed):
    if player.position == 'K':
        return DevelopmentState(player.rating, player.rating)
    develop, decline, *_ = CURVES[player.position]
    maximum = min(18, max(0, 2 * (decline - player.age)))
    minimum = min(6, maximum) if player.age <= develop else 0
    room = minimum + number(seed, player.id, 'potential') % (maximum - minimum + 1)
    return DevelopmentState(min(99, player.rating + room), player.rating)


def with_rosters(context, rosters):
    old = dict(context.development)
    values = {p.id: old.get(p.id) or initial_state(p, context.run_seed) for _, players in rosters for p in players}
    return DevelopmentContext(tuple(rosters), context.season, context.run_seed, tuple(sorted(values.items())), context.lineup_rules, context.rebuild_team)


def rating_view(player, context):
    state = dict(context.development).get(player.id) or initial_state(player, context.run_seed)
    return {'current_rating': player.rating, 'potential_rating': state.potential, 'rating_change': state.change}


def next_player(player, state, seed, season):
    # A drafted rookie's listed age is their age in the upcoming rookie season.
    entry = int(player.id.split('-')[-2]) if player.id.startswith('rookie-') else 1
    if season <= entry:
        return player, replace(state, change=0)
    age = player.age + 1
    if player.position == 'K':
        current = max(1, min(99, state.baseline + number(seed, player.id, f'form:{season}') % 9 - 4))
        return replace(player, age=age, experience=player.experience+1, rating=current), DevelopmentState(current,state.baseline,current-player.rating)
    develop, decline, cliff, loss, hard_loss = CURVES[player.position]
    delay, exceptional = longevity(seed, player.id, player.position)
    decline += delay
    cliff += delay
    draw = number(seed, player.id, f'change:{season}')
    potential = state.potential
    if age <= develop:
        delta = 1 + draw % 4
    elif age < decline:
        delta = int(draw % 3) - 1
    else:
        lo, hi = hard_loss if age >= cliff else loss
        delta = -(lo + draw % (hi-lo+1))
        if exceptional and age < cliff + 4:
            delta = int(delta / 2)
    current = max(1, min(99, min(potential, player.rating + delta)))
    if age >= decline:
        potential = current
    updated = replace(player, age=age, experience=player.experience+1, rating=current)
    return updated, DevelopmentState(potential,state.baseline,current-player.rating)



def advance_context(context, run_seed, season, development_start=1, lineup_rules=None, rebuild_team=None):
    current_rules = getattr(context, 'lineup_rules', 1)
    if rebuild_team is None and current_rules >= 3:
        rebuild_team = context.rebuild_team
    lineup_rules = lineup_rules if lineup_rules is not None else max(3, current_rules)
    if lineup_rules not in (3, 4) or current_rules > lineup_rules:
        raise ValueError('Invalid development rules')
    if not 1 <= development_start <= season <= 999:
        raise ValueError('Invalid development season')
    if current_rules >= 3 and context.rebuild_team != rebuild_team:
        raise ValueError('Rebuild team cannot change during a career')
    if rebuild_team is not None and (lineup_rules != 4 or development_start != 1):
        raise ValueError('Rebuild careers must begin with initial development rules')
    if current_rules < 3:
        if not context and lineup_rules == 4:
            from .lineups import initial_hierarchy, rebuild_lineups
            rosters = rebuild_lineups(run_seed,rebuild_team) if rebuild_team is not None else initial_hierarchy(run_seed)
        else:
            rosters = tuple(context) if context else tuple((team.id, tuple(roster_for(team.id,run_seed).values())) for team in TEAMS)
        rosters = tuple((owner,ranked_players(players)) for owner,players in rosters)
        states = tuple(sorted((p.id,initial_state(p,run_seed)) for _,players in rosters for p in players))
        context = DevelopmentContext(rosters,max(1,development_start-1),run_seed,states,lineup_rules,rebuild_team)
    # Changing a rules label never reshapes an existing roster.
    if context.lineup_rules != lineup_rules:
        context = replace(context, lineup_rules=lineup_rules)
    if context.run_seed != run_seed:
        raise ValueError('Development context belongs to a different run')
    if context.season > season:
        raise ValueError('Development cannot move backwards')
    for year in range(context.season+1, season+1):
        states = dict(context.development)
        rosters, updated_states = [], []
        for owner, players in context:
            updated = []
            for player in players:
                player, state = next_player(player,states[player.id],run_seed,year)
                updated.append(player)
                updated_states.append((player.id,state))
            rosters.append((owner,ranked_players(updated)))
        context = DevelopmentContext(tuple(rosters),year,run_seed,tuple(sorted(updated_states)),lineup_rules,rebuild_team)
    return context
