from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from functools import lru_cache
import random
import re
from typing import Iterable

import networkx as nx


GROUPS: dict[str, tuple[str, ...]] = {
    "Pacific": ("Seattle", "Las Vegas", "San Francisco", "Los Angeles", "San Diego"),
    "MidWest": ("Dallas", "Houston", "Phoenix", "Denver", "Kansas City"),
    "Frozen North": ("Minneapolis", "Chicago", "Green Bay", "Detroit", "Cleveland"),
    "North Atlantic Coast": ("Boston", "New York", "New Jersey", "Toronto", "Washington DC"),
    "Frozen East": ("Philadelphia", "Pittsburgh", "Cincinnati", "Baltimore", "Nashville"),
    "South Atlantic Coast": ("Miami", "New Orleans", "Atlanta", "Tampa Bay", "Raleigh"),
}


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


@dataclass(frozen=True)
class Team:
    id: str
    city: str
    group: str


@dataclass(frozen=True)
class ScheduledGame:
    week: int
    opponent_id: str
    opponent: str
    opponent_group: str
    venue: str
    reason: str


@dataclass(frozen=True)
class LeagueGame:
    week: int
    away_id: str
    home_id: str
    reason: str


TEAMS: tuple[Team, ...] = tuple(
    Team(id=slugify(city), city=city, group=group)
    for group, cities in GROUPS.items()
    for city in cities
)
TEAM_BY_ID = {team.id: team for team in TEAMS}


def default_standings() -> dict[str, int]:
    """Return placeholder prior-season positions (1-5) for the first season."""
    return {
        slugify(city): position
        for cities in GROUPS.values()
        for position, city in enumerate(cities, start=1)
    }


def _rotation_pairs(season: int) -> list[tuple[str, str]]:
    """Pair all six groups using a five-season round-robin rotation."""
    group_names = list(GROUPS)
    fixed = group_names[0]
    rotating = group_names[1:]
    round_index = (season - 1) % 5

    for _ in range(round_index):
        rotating = [rotating[-1], *rotating[:-1]]

    arranged = [fixed, *rotating]
    return [
        (arranged[index], arranged[-(index + 1)])
        for index in range(len(arranged) // 2)
    ]


def rotating_group(group: str, season: int) -> str:
    for left, right in _rotation_pairs(season):
        if group == left:
            return right
        if group == right:
            return left
    raise KeyError(f"Unknown group: {group}")


def _team_at_position(group: str, position: int, standings: dict[str, int]) -> Team:
    candidates = [
        team for team in TEAMS
        if team.group == group and standings.get(team.id) == position
    ]
    if len(candidates) != 1:
        raise ValueError(f"Group {group!r} must have exactly one team in position {position}")
    return candidates[0]


def validate_standings(standings: dict[str, int]) -> None:
    if set(standings) != set(TEAM_BY_ID):
        raise ValueError("Standings must contain every team exactly once")
    for group, cities in GROUPS.items():
        positions = sorted(standings[slugify(city)] for city in cities)
        if positions != [1, 2, 3, 4, 5]:
            raise ValueError(f"{group} standings must use positions 1 through 5")


def _required_matchups(season: int, standings: dict[str, int]) -> tuple[Counter[tuple[str, str]], dict[tuple[str, str], str]]:
    counts: Counter[tuple[str, str]] = Counter()
    reasons: dict[tuple[str, str], str] = {}

    for group in GROUPS:
        group_teams = [team for team in TEAMS if team.group == group]
        for index, team in enumerate(group_teams):
            for opponent in group_teams[index + 1:]:
                edge = tuple(sorted((team.id, opponent.id)))
                counts[edge] += 2
                reasons[edge] = "Group rematch"

    for index, team in enumerate(TEAMS):
        for opponent in TEAMS[index + 1:]:
            if team.group != opponent.group and standings[team.id] == standings[opponent.id]:
                edge = tuple(sorted((team.id, opponent.id)))
                counts[edge] += 1
                reasons[edge] = "Same-place matchup"

    for left_group, right_group in _rotation_pairs(season):
        left_teams = [team for team in TEAMS if team.group == left_group]
        right_teams = [team for team in TEAMS if team.group == right_group]
        for team in left_teams:
            for opponent in right_teams:
                if standings[team.id] == standings[opponent.id]:
                    continue
                edge = tuple(sorted((team.id, opponent.id)))
                counts[edge] += 1
                reasons[edge] = "Rotating group"

    return counts, reasons


def _orient_schedule(weeks: list[list[tuple[str, str, str]]]) -> list[LeagueGame]:
    graph = nx.MultiGraph()
    graph.add_nodes_from(team.id for team in TEAMS)
    game_by_key: dict[str, tuple[int, str, str, str]] = {}
    orientation: dict[str, tuple[str, str]] = {}
    group_meetings: Counter[tuple[str, str]] = Counter()
    for week, games in enumerate(weeks, start=1):
        for index, (left, right, reason) in enumerate(games):
            key = f"game-{week}-{index}"
            game_by_key[key] = (week, left, right, reason)
            if reason == "Group rematch":
                pair = tuple(sorted((left, right)))
                home_id, away_id = pair if group_meetings[pair] == 0 else (pair[1], pair[0])
                orientation[key] = (home_id, away_id)
                group_meetings[pair] += 1
            else:
                graph.add_edge(left, right, key=key)

    dummy = "__balance__"
    graph.add_node(dummy)
    for team in TEAMS:
        graph.add_edge(dummy, team.id, key=f"dummy-{team.id}")

    for left, right, key in nx.eulerian_circuit(graph, source=dummy, keys=True):
        if key in game_by_key:
            orientation[key] = (left, right)

    schedule: list[LeagueGame] = []
    for key, (week, _, _, reason) in game_by_key.items():
        home_id, away_id = orientation[key]
        schedule.append(LeagueGame(week=week, away_id=away_id, home_id=home_id, reason=reason))
    return sorted(schedule, key=lambda game: (game.week, game.home_id, game.away_id))


@lru_cache(maxsize=32)
def _generate_league_schedule_cached(
    season: int,
    standings_items: tuple[tuple[str, int], ...],
) -> tuple[LeagueGame, ...]:
    standings = dict(standings_items)
    counts, reasons = _required_matchups(season, standings)
    original = counts.copy()

    for attempt in range(250):
        remaining = original.copy()
        weeks: list[list[tuple[str, str, str]]] = []
        for week_index in range(17):
            graph = nx.Graph()
            graph.add_nodes_from(team.id for team in TEAMS)
            rng = random.Random(f"league:{season}:attempt:{attempt}:week:{week_index}")
            for edge, count in remaining.items():
                if count > 0:
                    graph.add_edge(*edge, weight=rng.random())
            matching = nx.max_weight_matching(graph, maxcardinality=True)
            if len(matching) != 15:
                break
            games: list[tuple[str, str, str]] = []
            for left, right in matching:
                edge = tuple(sorted((left, right)))
                remaining[edge] -= 1
                games.append((left, right, reasons[edge]))
            weeks.append(games)

        if len(weeks) == 17 and sum(remaining.values()) == 0:
            return tuple(_orient_schedule(weeks))

    raise RuntimeError("Could not arrange the required matchups into 17 complete weeks")


def generate_league_schedule(
    season: int = 1,
    standings: dict[str, int] | None = None,
) -> list[LeagueGame]:
    if season < 1:
        raise ValueError("Season must be 1 or greater")
    standings = standings or default_standings()
    validate_standings(standings)
    return list(_generate_league_schedule_cached(season, tuple(sorted(standings.items()))))


def generate_schedule(
    team_id: str,
    season: int = 1,
    standings: dict[str, int] | None = None,
    seed: int | None = None,
) -> list[ScheduledGame]:
    """Return one team's view of the coherent 17-week league schedule."""
    del seed  # Retained for compatibility with the original public function.
    if team_id not in TEAM_BY_ID:
        raise KeyError(f"Unknown team: {team_id}")
    games: list[ScheduledGame] = []
    for league_game in generate_league_schedule(season=season, standings=standings):
        if team_id not in (league_game.home_id, league_game.away_id):
            continue
        is_home = league_game.home_id == team_id
        opponent = TEAM_BY_ID[league_game.away_id if is_home else league_game.home_id]
        games.append(ScheduledGame(
            week=league_game.week,
            opponent_id=opponent.id,
            opponent=opponent.city,
            opponent_group=opponent.group,
            venue="Home" if is_home else "Away",
            reason=league_game.reason,
        ))
    return sorted(games, key=lambda game: game.week)


def teams_payload(teams: Iterable[Team] = TEAMS) -> list[dict[str, str]]:
    return [asdict(team) for team in teams]


def schedule_payload(games: Iterable[ScheduledGame]) -> list[dict[str, object]]:
    return [asdict(game) for game in games]
