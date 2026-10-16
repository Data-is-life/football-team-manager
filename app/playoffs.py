from dataclasses import asdict
from functools import lru_cache

from .league import TEAM_BY_ID, ScheduledGame
from .simulation import roster_for, simulate_game
from .player_stats import aggregate_player_stats
from .standings import standings_through_week


ROUND_NAMES = ("Wild Card", "Quarterfinals", "Semifinals", "Championship")


def pair_survivors(teams: list[dict]) -> list[tuple[dict, dict]]:
    """Keep original seeds: highest remaining seed plays lowest."""
    ordered = sorted(teams, key=lambda team: team["seed"])
    if len(ordered) % 2:
        raise ValueError("A playoff round needs an even number of teams")
    return [(ordered[index], ordered[-index - 1]) for index in range(len(ordered) // 2)]


def matchup_payload(home: dict, away: dict, round_number: int) -> dict:
    return {"home": home, "away": away, "neutral_site": round_number == 4}


@lru_cache(maxsize=128)
def postseason_snapshot(season: int, round_number: int) -> dict:
    if round_number < 0 or round_number > 4:
        raise ValueError("Playoff round must be between 0 and 4")
    field = standings_through_week(season, 17)["playoff_race"]
    survivors = list(field)
    rounds = []
    for number in range(1, round_number + 1):
        byes = list(field[:2]) if number == 1 else []
        playing = list(field[2:]) if number == 1 else survivors
        winners = list(byes)
        games = []
        for home, away in pair_survivors(playing):
            opponent = TEAM_BY_ID[away["team"]["id"]]
            game = ScheduledGame(
                week=17 + number, opponent_id=opponent.id,
                opponent=opponent.city, opponent_group=opponent.group,
                venue="Home", reason=ROUND_NAMES[number - 1],
            )
            result = simulate_game(
                home["team"]["id"], game, season,
                allow_ties=False, neutral_site=number == 4,
            )
            winner = home if result["home"]["score"] > result["away"]["score"] else away
            winners.append(winner)
            games.append({
                **matchup_payload(home, away, number),
                "result": result, "winner": winner,
            })
        survivors = sorted(winners, key=lambda team: team["seed"])
        rounds.append({
            "number": number, "name": ROUND_NAMES[number - 1],
            "byes": byes, "games": games,
        })

    upcoming = None
    if round_number < 4:
        number = round_number + 1
        upcoming = {
            "number": number, "name": ROUND_NAMES[number - 1],
            "byes": list(field[:2]) if number == 1 else [],
            "games": [
                matchup_payload(home, away, number)
                for home, away in pair_survivors(list(field[2:]) if number == 1 else survivors)
            ],
        }
    return {
        "field": field, "rounds": rounds, "upcoming": upcoming,
        "survivors": survivors,
        "champion": survivors[0] if round_number == 4 else None,
    }


def playoffs_through_round(team_id: str, season: int, round_number: int) -> dict:
    if team_id not in TEAM_BY_ID:
        raise KeyError(f"Unknown team: {team_id}")
    snapshot = postseason_snapshot(season, round_number)
    qualified = any(row["team"]["id"] == team_id for row in snapshot["field"])
    alive = any(row["team"]["id"] == team_id for row in snapshot["survivors"])
    boxes = []
    for round_ in snapshot["rounds"]:
        for game in round_["games"]:
            for side in ("home", "away"):
                if game[side]["team"]["id"] == team_id:
                    boxes.append(game["result"][side])
    return {
        **snapshot, "team": asdict(TEAM_BY_ID[team_id]),
        "season": season, "completed_round": round_number,
        "next_round": round_number + 1 if round_number < 4 else None,
        "postseason_complete": round_number == 4,
        "qualified": qualified, "eliminated": qualified and not alive,
        "roster_stats": aggregate_player_stats(roster_for(team_id).values(), boxes),
    }
