from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import random

from .league import TEAM_BY_ID, ScheduledGame, Team, generate_league_schedule, generate_schedule


FIRST_NAMES = (
    "Andre", "Caleb", "Darius", "Eli", "Isaiah", "Jalen", "Jonah", "Kai",
    "Malik", "Marcus", "Micah", "Miles", "Noah", "Roman", "Theo", "Xavier",
)
LAST_NAMES = (
    "Bennett", "Brooks", "Carter", "Coleman", "Davis", "Foster", "Grant", "Hayes",
    "Jackson", "Lewis", "Mitchell", "Reed", "Robinson", "Turner", "Walker", "Young",
)
POSITIONS = ("QB", "RB", "WR1", "WR2", "TE", "K")


@dataclass(frozen=True)
class Player:
    id: str
    name: str
    position: str
    rating: int


@dataclass(frozen=True)
class TeamRatings:
    offense: int
    defense: int


def _stable_number(value: str) -> int:
    return int.from_bytes(hashlib.sha256(value.encode("utf-8")).digest()[:8], "big")


def team_ratings(team_id: str) -> TeamRatings:
    if team_id not in TEAM_BY_ID:
        raise KeyError(f"Unknown team: {team_id}")
    return TeamRatings(
        offense=72 + _stable_number(f"{team_id}:offense") % 17,
        defense=72 + _stable_number(f"{team_id}:defense") % 17,
    )


def roster_for(team_id: str) -> dict[str, Player]:
    if team_id not in TEAM_BY_ID:
        raise KeyError(f"Unknown team: {team_id}")
    roster: dict[str, Player] = {}
    used_names: set[str] = set()
    for index, position in enumerate(POSITIONS):
        offset = 0
        while True:
            number = _stable_number(f"{team_id}:{position}:{offset}")
            first = FIRST_NAMES[(number + index) % len(FIRST_NAMES)]
            last = LAST_NAMES[(number // len(FIRST_NAMES) + index * 3) % len(LAST_NAMES)]
            name = f"{first} {last}"
            if name not in used_names:
                break
            offset += 1
        used_names.add(name)
        roster[position] = Player(
            id=f"{team_id}-{position.lower()}",
            name=name,
            position=position,
            rating=max(50, min(99, team_ratings(team_id).offense - 8
                               + _stable_number(f"{team_id}:{position}:scouting") % 17)),
        )
    return roster


def _split_total(total: int, weights: list[float]) -> list[int]:
    raw = [total * weight / sum(weights) for weight in weights]
    values = [int(value) for value in raw]
    for index in sorted(range(len(raw)), key=lambda item: raw[item] - values[item], reverse=True):
        if sum(values) == total:
            break
        values[index] += 1
    return values


def _allocate_touchdowns(total: int, rng: random.Random) -> tuple[int, int]:
    if total == 0:
        return 0, 0
    passing = sum(rng.random() < 0.66 for _ in range(total))
    return passing, total - passing


def _team_box(
    team: Team,
    opponent: Team,
    is_home: bool,
    rng: random.Random,
) -> dict[str, object]:
    ratings = team_ratings(team.id)
    opponent_ratings = team_ratings(opponent.id)
    expected_points = 22.0 + (ratings.offense - opponent_ratings.defense) * 0.36
    expected_points += 1.6 if is_home else -0.4

    touchdowns = max(0, min(6, round(rng.gauss(expected_points / 8.2, 1.15))))
    field_goals = max(0, min(4, round(rng.gauss(1.65, 0.85))))
    score = touchdowns * 7 + field_goals * 3
    if score == 0 and rng.random() < 0.82:
        field_goals = 1
        score = 3

    passing_tds, rushing_tds = _allocate_touchdowns(touchdowns, rng)
    interceptions = max(0, min(4, round(rng.gauss(1.05 - (ratings.offense - 72) / 40, 0.8))))
    attempts = rng.randint(27, 43)
    completion_rate = min(0.76, max(0.49, 0.61 + (ratings.offense - 80) / 110 + rng.gauss(0, 0.035)))
    completions = min(attempts, round(attempts * completion_rate))
    passing_yards = max(105, round(rng.gauss(225 + (ratings.offense - opponent_ratings.defense) * 3.0, 48)))
    carries = rng.randint(21, 34)
    rushing_yards = max(42, round(rng.gauss(112 + (ratings.offense - opponent_ratings.defense) * 1.8, 32)))
    sacks_allowed = max(0, min(7, round(rng.gauss(2.3 + (opponent_ratings.defense - ratings.offense) / 12, 1.2))))

    roster = roster_for(team.id)
    reception_weights = [rng.uniform(0.28, 0.38), rng.uniform(0.20, 0.30), rng.uniform(0.13, 0.21), rng.uniform(0.12, 0.20)]
    receiving_yards = _split_total(passing_yards, reception_weights)
    receptions = _split_total(completions, [weight ** 0.82 for weight in reception_weights])
    receiving_tds = _split_total(passing_tds, reception_weights)

    qb = roster["QB"]
    rb = roster["RB"]
    receivers = [roster["WR1"], roster["WR2"], roster["TE"], rb]

    return {
        "team": {"id": team.id, "city": team.city},
        "score": score,
        "team_stats": {
            "total_yards": passing_yards + rushing_yards,
            "passing_yards": passing_yards,
            "rushing_yards": rushing_yards,
            "turnovers": interceptions,
            "sacks_allowed": sacks_allowed,
            "time_of_possession": "00:00",
        },
        "passing": [{
            "player": qb.name,
            "position": "QB",
            "completions": completions,
            "attempts": attempts,
            "yards": passing_yards,
            "touchdowns": passing_tds,
            "interceptions": interceptions,
        }],
        "rushing": [{
            "player": rb.name,
            "position": "RB",
            "attempts": carries,
            "yards": rushing_yards,
            "touchdowns": rushing_tds,
        }],
        "receiving": [
            {
                "player": player.name,
                "position": player.position.replace("1", "").replace("2", ""),
                "receptions": receptions[index],
                "yards": receiving_yards[index],
                "touchdowns": receiving_tds[index],
            }
            for index, player in enumerate(receivers)
        ],
        "kicking": [{
            "player": roster["K"].name,
            "position": "K",
            "field_goals_made": field_goals,
            "field_goals_attempted": field_goals + (1 if rng.random() < 0.24 else 0),
            "extra_points_made": touchdowns,
        }],
        "scoring": {"touchdowns": touchdowns, "field_goals": field_goals},
    }


def simulate_game(
    selected_team_id: str,
    game: ScheduledGame,
    season: int,
) -> dict[str, object]:
    selected_team = TEAM_BY_ID[selected_team_id]
    opponent = TEAM_BY_ID[game.opponent_id]
    ordered_ids = sorted((selected_team.id, opponent.id))
    seed = _stable_number(f"season:{season}:week:{game.week}:{ordered_ids[0]}:{ordered_ids[1]}")
    rng = random.Random(seed)

    selected_is_home = game.venue == "Home"
    home_team = selected_team if selected_is_home else opponent
    away_team = opponent if selected_is_home else selected_team
    home_box = _team_box(home_team, away_team, True, rng)
    away_box = _team_box(away_team, home_team, False, rng)
    selected_box = home_box if selected_is_home else away_box
    opponent_box = away_box if selected_is_home else home_box
    selected_possession_seconds = rng.randint(27 * 60, 33 * 60)
    opponent_possession_seconds = 60 * 60 - selected_possession_seconds
    selected_box["team_stats"]["time_of_possession"] = (
        f"{selected_possession_seconds // 60}:{selected_possession_seconds % 60:02d}"
    )
    opponent_box["team_stats"]["time_of_possession"] = (
        f"{opponent_possession_seconds // 60}:{opponent_possession_seconds % 60:02d}"
    )
    selected_score = int(selected_box["score"])
    opponent_score = int(opponent_box["score"])
    outcome = "T" if selected_score == opponent_score else ("W" if selected_score > opponent_score else "L")

    return {
        "week": game.week,
        "outcome": outcome,
        "selected_team_id": selected_team.id,
        "home": home_box,
        "away": away_box,
    }


def simulate_league_week(season: int, week: int) -> list[dict[str, object]]:
    if week < 1 or week > 17:
        raise ValueError("Week must be between 1 and 17")
    results: list[dict[str, object]] = []
    for league_game in generate_league_schedule(season=season):
        if league_game.week != week:
            continue
        away = TEAM_BY_ID[league_game.away_id]
        game = ScheduledGame(
            week=week,
            opponent_id=away.id,
            opponent=away.city,
            opponent_group=away.group,
            venue="Home",
            reason=league_game.reason,
        )
        result = simulate_game(league_game.home_id, game, season)
        results.append(result)
    return results


def simulate_through_week(team_id: str, season: int, week: int) -> dict[str, object]:
    schedule = generate_schedule(team_id=team_id, season=season)
    if week < 1 or week > len(schedule):
        raise ValueError(f"Week must be between 1 and {len(schedule)}")
    results = [simulate_game(team_id, game, season) for game in schedule[:week]]
    wins = sum(result["outcome"] == "W" for result in results)
    losses = sum(result["outcome"] == "L" for result in results)
    ties = sum(result["outcome"] == "T" for result in results)
    current = results[-1]
    other_results = []
    for league_result in simulate_league_week(season, week):
        if team_id in (league_result["home"]["team"]["id"], league_result["away"]["team"]["id"]):
            continue
        other_results.append({
            "away": league_result["away"]["team"],
            "away_score": league_result["away"]["score"],
            "home": league_result["home"]["team"],
            "home_score": league_result["home"]["score"],
        })
    from .standings import standings_through_week

    return {
        "team": asdict(TEAM_BY_ID[team_id]),
        "season": season,
        "week": week,
        "record": {"wins": wins, "losses": losses, "ties": ties},
        "result": current,
        "league_results": other_results,
        "standings": standings_through_week(season, week),
        "season_complete": week == len(schedule),
        "next_week": None if week == len(schedule) else week + 1,
    }
