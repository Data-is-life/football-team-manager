"""Fixed depth-slot contributions; absent players never redistribute weight."""

# Basis points make every position sum to exactly 100%, without rounding
# intermediate position ratings. Group averages expand into equal slot weights.
POSITION_SLOT_WEIGHTS = {
    'QB': (9500, 500),
    'WR': (4000, 3000, 2000, 1000),
    'RB': (7500, 2500),
    'TE': (7500, 2500),
    'OL': (1700, 1700, 1700, 1700, 1700, 1000, 500),
    'DL': (1875, 1875, 1875, 1875, 2000, 500),
    'LB': (2500, 2500, 2500, 2000, 500),
    'CB': (3750, 3750, 2000, 500),
    'S': (3750, 3750, 2500),
    'K': (10000,),
}
OFFENSE_WEIGHTS = {'QB':120, 'WR':90, 'RB':90, 'TE':80, 'OL':120}
DEFENSE_POSITIONS = ('CB', 'DL', 'LB', 'S')


def position_rating_points(players):
    """Return rating × 10,000, selecting best current ability in each slot."""
    groups = {position: [] for position in POSITION_SLOT_WEIGHTS}
    for player in players:
        groups[player.position].append(player)
    result = {}
    for position, weights in POSITION_SLOT_WEIGHTS.items():
        ordered = sorted(groups[position], key=lambda p: (-p.rating, p.depth, p.id))
        result[position] = sum(p.rating*weight for p, weight in zip(ordered, weights))
    return result


def position_ratings(players):
    return {position: points/10_000 for position, points in position_rating_points(players).items()}


def weighted_unit_ratings(players):
    """Keep integer arithmetic until the final O/D division; K stays separate."""
    points = position_rating_points(players)
    offense = sum(points[pos]*weight for pos, weight in OFFENSE_WEIGHTS.items()) / 5_000_000
    defense = sum(points[pos] for pos in DEFENSE_POSITIONS) / 40_000
    return offense, defense
