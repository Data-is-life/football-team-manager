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


KICKER_CURVE = (29,37,40,(1,2),(3,4))


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
    rotation_share: float = 0
    potential_change: int = 0
    rookie_revealed: bool = False
    rookie_outcome: str | None = None
    kicker_development: bool = False


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


def initial_state(player, seed, kicker_potential=False):
    if player.position == 'K' and not kicker_potential:
        return DevelopmentState(player.rating, player.rating)
    develop, decline, *_ = (KICKER_CURVE if player.position == 'K' else CURVES[player.position])
    maximum = min(18, max(0, 2 * (decline - player.age)))
    minimum = min(6, maximum) if player.age <= develop else 0
    room = minimum + number(seed, player.id, 'potential') % (maximum - minimum + 1)
    return DevelopmentState(min(99, player.rating + room), player.rating, kicker_development=player.position == 'K' and kicker_potential)


def with_rosters(context, rosters):
    old = dict(context.development)
    values = {p.id: old.get(p.id) or initial_state(p, context.run_seed, context.lineup_rules >= 9) for _, players in rosters for p in players}
    return DevelopmentContext(tuple(rosters), context.season, context.run_seed, tuple(sorted(values.items())), context.lineup_rules, context.rebuild_team)


def rating_view(player, context):
    state = dict(context.development).get(player.id) or initial_state(player, context.run_seed, context.lineup_rules >= 9)
    result = {'current_rating': player.rating, 'potential_rating': state.potential, 'rating_change': state.change}
    if context.lineup_rules >= 7:
        result['potential_change'] = state.potential_change
        if state.rookie_revealed and player.id.startswith('rookie-') and int(player.id.split('-')[-2]) == context.season:
            result['rookie_outcome'] = state.rookie_outcome
    return result


def reveal_rookie(player, state, seed, preseason_growth=False, kicker_potential=False):
    """One entry-season assessment; rules 8 add modest camp growth within potential."""
    if state.rookie_revealed:
        return player, state
    draw = number(seed, player.id, 'rookie-reveal-v2' if preseason_growth else 'rookie-reveal-v1') % 100
    boom, bust = (20, 25) if preseason_growth else (15, 30)
    outcome = 'boom' if draw < boom else 'bust' if draw < bust else 'normal'
    current, potential = player.rating, state.potential
    if outcome == 'boom':
        current = min(99, current + 2 + number(seed, player.id, 'rookie-current-v1') % 5)
        potential = max(current, min(99, potential + 8 + number(seed, player.id, 'rookie-potential-v1') % 8))
    elif outcome == 'bust':
        potential = max(40, potential - 15 - number(seed, player.id, 'rookie-potential-v1') % 11)
        current = max(40, min(potential, current - 3 - number(seed, player.id, 'rookie-current-v1') % 6))
    if preseason_growth and (player.position != 'K' or kicker_potential):
        current = min(99, potential, current + 1 + number(seed, player.id, 'rookie-camp-v1') % 2)
    if player.position == 'K' and not kicker_potential:
        # Preserve the legacy seasonal-form-only model.
        potential = current
    from .attributes import generate_attributes
    updated = replace(player, rating=current, attributes=generate_attributes(player.id, player.position, current, seed)) if current != player.rating else player
    return updated, replace(state, potential=potential, baseline=current if player.position == 'K' else state.baseline,
                            change=current-player.rating, potential_change=potential-state.potential,
                            rookie_revealed=True, rookie_outcome=outcome)


def next_player(player, state, seed, season, rotation_growth=False, rookie_reassessment=False, preseason_growth=False, kicker_potential=False):
    # A drafted rookie's listed age is their age in the upcoming rookie season.
    entry = int(player.id.split('-')[-2]) if player.id.startswith('rookie-') else 1
    previous_potential = state.potential
    initialize_kicker = kicker_potential and player.position == 'K' and not state.kicker_development and season >= entry
    if initialize_kicker:
        # Upgrade only at a real transition, keeping the old form-free anchor.
        fresh = initial_state(replace(player, rating=state.baseline), seed, True)
        state = replace(state, potential=fresh.potential, kicker_development=True)
    if rookie_reassessment and player.id.startswith('rookie-') and season == entry:
        updated, result = reveal_rookie(player, state, seed, preseason_growth, kicker_potential)
        return updated, replace(result, potential_change=result.potential-previous_potential) if initialize_kicker else result

    if season <= entry:
        return player, replace(state, change=0, potential_change=0)
    age = player.age + 1
    if player.position == 'K' and kicker_potential:
        develop, decline, cliff, loss, hard_loss = KICKER_CURVE
        delay, exceptional = longevity(seed, player.id, 'K')
        decline, cliff = decline + delay, cliff + delay
        baseline = state.baseline
        potential = state.potential
        draw = number(seed, player.id, f'change:{season}')
        if age <= develop:
            baseline = min(potential, baseline + 1 + draw % 2)
        elif age >= decline:
            lo, hi = hard_loss if age >= cliff else loss
            delta = -(lo + draw % (hi-lo+1))
            if exceptional and age < cliff + 4:
                delta = int(delta / 2)
            baseline = max(1, baseline + delta)
        # Form never feeds back into the anchor, even after decline collapses
        # displayed potential to current ability.
        current = max(1, min(99, baseline + number(seed, player.id, f'form:{season}') % 9 - 4))
        if age >= decline:
            potential = current
        else:
            current = min(potential, current)
        updated = replace(player, age=age, experience=player.experience+1, rating=current)
        return updated, replace(state, baseline=baseline, potential=potential,
                                change=current-player.rating, potential_change=potential-previous_potential)
    if player.position == 'K':
        current = max(1, min(99, state.baseline + number(seed, player.id, f'form:{season}') % 9 - 4))
        return replace(player, age=age, experience=player.experience+1, rating=current), DevelopmentState(current,state.baseline,current-player.rating, potential_change=current-state.potential if rookie_reassessment else 0, rookie_revealed=state.rookie_revealed, rookie_outcome=state.rookie_outcome)
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
    # The role is captured before the offseason draft/cuts, never inferred from
    # a newly promoted depth chart. This is a role-based estimate, not a snap tally.
    if rotation_growth and player.position not in ('QB','K') and player.age < 25 and state.rotation_share >= .05-1e-9 and age < decline:
        delta += 1
    current = max(1, min(99, min(potential, player.rating + delta)))
    if age >= decline:
        potential = current
    updated = replace(player, age=age, experience=player.experience+1, rating=current)
    return updated, DevelopmentState(potential,state.baseline,current-player.rating, potential_change=potential-state.potential if rookie_reassessment else 0, rookie_revealed=state.rookie_revealed, rookie_outcome=state.rookie_outcome)



def advance_context(context, run_seed, season, development_start=1, lineup_rules=None, rebuild_team=None):
    current_rules = getattr(context, 'lineup_rules', 1)
    if rebuild_team is None and current_rules >= 3:
        rebuild_team = context.rebuild_team
    lineup_rules = lineup_rules if lineup_rules is not None else max(3, current_rules)
    if lineup_rules not in (3, 4, 5, 6, 7, 8, 9) or current_rules > lineup_rules:
        raise ValueError('Invalid development rules')
    if not 1 <= development_start <= season <= 999:
        raise ValueError('Invalid development season')
    if current_rules >= 3 and context.rebuild_team != rebuild_team:
        raise ValueError('Rebuild team cannot change during a career')
    if rebuild_team is not None and (lineup_rules < 4 or development_start != 1):
        raise ValueError('Rebuild careers must begin with initial development rules')
    rotation_growth = current_rules >= 5
    if current_rules < 3:
        if not context and lineup_rules >= 4:
            from .lineups import initial_hierarchy, rebuild_lineups
            rosters = rebuild_lineups(run_seed,rebuild_team,balanced=lineup_rules>=6) if rebuild_team is not None else initial_hierarchy(run_seed)
        else:
            rosters = tuple(context) if context else tuple((team.id, tuple(roster_for(team.id,run_seed).values())) for team in TEAMS)
        rosters = tuple((owner,ranked_players(players)) for owner,players in rosters)
        states = tuple(sorted((p.id,initial_state(p,run_seed,lineup_rules >= 9)) for _,players in rosters for p in players))
        context = DevelopmentContext(rosters,max(1,development_start-1),run_seed,states,lineup_rules,rebuild_team)
        if lineup_rules >= 5 and development_start == 1:
            context = capture_rotation(context)
            rotation_growth = True
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
                player, state = next_player(player,states[player.id],run_seed,year,rotation_growth and player.position not in ('QB','K'), lineup_rules >= 7, lineup_rules >= 8, lineup_rules >= 9)
                updated.append(player)
                updated_states.append((player.id,state))
            rosters.append((owner,ranked_players(updated)))
        context = DevelopmentContext(tuple(rosters),year,run_seed,tuple(sorted(updated_states)),lineup_rules,rebuild_team)
        if lineup_rules >= 5:
            context = capture_rotation(context)
            rotation_growth = True
    return context


def capture_rotation(context):
    from .rotation import season_roles
    shares = {identity:share for _,players in context for identity,share in season_roles(players).items()}
    return replace(context, development=tuple((identity,replace(state,rotation_share=shares[identity]))
                                              for identity,state in context.development))
