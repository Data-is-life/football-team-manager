"""Deterministic versioned offseason drafts, replayed from user choices."""
from dataclasses import asdict, replace
from functools import lru_cache
import random

from .attributes import generate_attributes
from .league import TEAMS, TEAM_BY_ID
from .names import FIRST_NAMES, LAST_NAMES
from .ratings import rating_payload
from .playoffs import postseason_snapshot
from .simulation import Player, ROSTER_RULES, ROSTER_SLOTS, _run_number, roster_for
from .standings import standings_through_week

ROUNDS = 6
CLASS_SIZE = 200


def player_payload(player: Player, roster_context=()) -> dict:
    result = {**asdict(player), **rating_payload(player,roster_context)}
    result['attributes'] = {key: value for key, value in result['attributes'].items() if value is not None}
    return result


@lru_cache(maxsize=32)
def draft_class(season: int, run_seed: int) -> tuple[Player, ...]:
    """Independent of selections/order: every replay has the same permanent rookie IDs."""
    rng = random.Random(_run_number(f'draft-class:{season + 1}', run_seed))
    positions = [ROSTER_SLOTS[i % len(ROSTER_SLOTS)][0] for i in range(CLASS_SIZE)]
    rng.shuffle(positions)
    names = {player.name for team in TEAMS for player in roster_for(team.id, run_seed).values()}
    players = []
    for index, position in enumerate(positions):
        while True:
            name = f'{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}'
            if name not in names:
                names.add(name)
                break
        player_id = f'rookie-{run_seed}-{season + 1}-{index + 1}'
        rating = max(45, min(90, round(rng.gauss(65, 10))))
        players.append(Player(id=player_id, name=name, position=position, rating=rating,
                              depth=0, experience=0, age=rng.randint(21, 24),
                              attributes=generate_attributes(player_id, position, rating, run_seed)))
    return tuple(sorted(players, key=lambda player: (-player.rating, player.id)))


def draft_order(season: int, run_seed: int, prior_standings: tuple = (), roster_context: tuple = ()) -> list[dict]:
    tables = standings_through_week(season, 17, run_seed, prior_standings, roster_context)
    rows = {row['team']['id']: row for group in tables['groups'] for row in group['teams']}
    postseason = postseason_snapshot(season, 4, run_seed, prior_standings, roster_context)
    playoff_ids = {row['team']['id'] for row in postseason['field']}
    # Worst regular-season record first within each finish group. Explicit draft tiebreakers
    # avoid reversing group-winner seeding, which is not an overall league ranking.
    def worst_first(team_id):
        row = rows[team_id]
        return (row['wins'] * 2 + row['ties'], row['point_differential'], row['points_for'],
                _run_number(f'draft-order:{season}:{team_id}', run_seed), team_id)
    groups = [sorted(set(rows) - playoff_ids, key=worst_first)]
    for round_ in postseason['rounds']:
        losers = [game['away']['team']['id'] if game['winner']['team']['id'] == game['home']['team']['id']
                  else game['home']['team']['id'] for game in round_['games']]
        groups.append(sorted(losers, key=worst_first))
    groups.append([postseason['champion']['team']['id']])
    return [{'team': asdict(TEAM_BY_ID[team_id]), 'record': rows[team_id]['record']}
            for group in groups for team_id in group]


def cpu_pick(available, current, additions):
    """Shared quality/need/repeat-position policy for CPU and user auto-picks."""
    position_quality = {position: sum(p.rating for p in current if p.position == position)
                        / sum(p.position == position for p in current) for position in ROSTER_RULES}
    return max(available, key=lambda p: (
        p.rating - .25 * position_quality[p.position] - 12 * additions.get(p.position, 0),
        p.rating, p.id))


def build_draft(team_id: str, season: int, run_seed: int, choices: tuple[str, ...] = (),
                prior_standings: tuple = (), roster_context: tuple = (), return_league: bool = False, auto_pick: bool = False, draft_rounds: int = 4) -> tuple[dict, list[Player]]:
    """Auto-pick up to the user's next turn, or finish after their final pick.

    With auto_pick, fill remaining user turns using the same CPU policy and return
    all resolved user picks, so ordinary manual replay reproduces the whole draft.
    Replaying all choices validates availability at the actual pick, including CPU picks.
    Neither the cached class nor the base rosters is mutated.
    The omitted round count retains legacy four-round API behavior; new UI drafts pass six.
    """
    if team_id not in TEAM_BY_ID or not 1 <= season < 999 or draft_rounds not in (4, ROUNDS) or len(choices) > draft_rounds:
        raise ValueError('Invalid draft context')
    if len(set(choices)) != len(choices):
        raise ValueError('A prospect cannot be selected twice')
    prospects = draft_class(season, run_seed)
    available = {player.id: player for player in prospects}
    if any(choice not in available for choice in choices):
        raise ValueError('Unknown prospect')
    order = draft_order(season, run_seed, prior_standings, roster_context)
    rosters = {team.id: list(roster_for(team.id, run_seed, roster_context).values()) for team in TEAMS}
    additions = {team.id: {} for team in TEAMS}
    picks = []
    resolved_choices = list(choices)
    consumed = 0
    for overall in range(1, draft_rounds * len(order) + 1):
        owner = order[(overall - 1) % len(order)]['team']['id']
        if owner == team_id and consumed < len(choices):
            choice = choices[consumed]
            if choice not in available:
                raise ValueError('That prospect was already drafted before your turn')
            prospect = available[choice]
            consumed += 1
        else:
            if owner == team_id and not auto_pick:
                break
            prospect = cpu_pick(available.values(), rosters[owner], additions[owner])
            if owner == team_id:
                resolved_choices.append(prospect.id)
        del available[prospect.id]
        depth = 1 + max(p.depth for p in rosters[owner] if p.position == prospect.position)
        signed = replace(prospect, depth=depth)
        rosters[owner].append(signed)
        additions[owner][signed.position] = additions[owner].get(signed.position, 0) + 1
        picks.append({'overall': overall, 'round': (overall - 1) // len(order) + 1,
                      'team': asdict(TEAM_BY_ID[owner]), 'player': player_payload(signed,roster_context)})
    complete = len(picks) == draft_rounds * len(order)
    return ({'season': season, 'draft_season': season + 1, 'run_seed': run_seed,
             'team': asdict(TEAM_BY_ID[team_id]), 'rounds': draft_rounds, 'total_picks': draft_rounds * len(order),
             'class_size': CLASS_SIZE, 'order': order, 'picks': picks,
             'available': [player_payload(player,roster_context) for player in prospects if player.id in available],
             'manual_picks': resolved_choices, 'complete': complete,
             'next_pick': None if complete else len(picks) + 1,
             'next_round': None if complete else len(resolved_choices) + 1}, rosters if return_league else rosters[team_id])
