from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, replace
from functools import lru_cache
import hashlib
import random

from .league import TEAM_BY_ID, ScheduledGame, Team, generate_league_schedule, generate_schedule
from .stats import add_efficiency_stats
from .kicking import add_kicking_stats
from .player_stats import aggregate_player_stats
from .names import FIRST_NAMES, LAST_NAMES
from .attributes import PlayerAttributes, generate_attributes
from .defense import add_defense_and_blocking


# Position: (initial players, minimum required).
ROSTER_RULES = {
    "QB": (2, 1), "WR": (4, 2), "TE": (2, 1), "RB": (2, 1),
    "OL": (8, 5), "K": (2, 1), "DL": (6, 4), "LB": (5, 3), "CB": (4, 2), "S": (3, 2),
}
POSITIONS = tuple(ROSTER_RULES)
ROSTER_SLOTS = tuple(
    (position, depth)
    for position, (initial, _) in ROSTER_RULES.items()
    for depth in range(1, initial + 1)
)


@dataclass(frozen=True)
class Player:
    id: str
    name: str
    position: str
    rating: int
    depth: int
    experience: int
    age: int
    attributes: PlayerAttributes


@dataclass(frozen=True)
class TeamRatings:
    offense: int
    defense: int


def _stable_number(value: str) -> int:
    return int.from_bytes(hashlib.sha256(value.encode("utf-8")).digest()[:8], "big")


def _run_number(value: str, run_seed: int) -> int:
    return _stable_number(value if run_seed == 0 else f"run:{run_seed}:{value}")


def ranked_players(players):
    """Rank by current ability within position; keep IDs stable and ties deterministic."""
    result = []
    for position in ROSTER_RULES:
        ordered = sorted((p for p in players if p.position == position), key=lambda p: (-p.rating, p.depth, p.id))
        result.extend(replace(player, depth=depth) for depth, player in enumerate(ordered, 1))
    return tuple(result)


def lineup_unit_rating(players, positions):
    starters = [p.rating for p in players if p.position in positions and p.depth <= ROSTER_RULES[p.position][1]]
    bench = [p.rating for p in players if p.position in positions and p.depth > ROSTER_RULES[p.position][1]]
    starter_average = sum(starters) / len(starters)
    bench_average = sum(bench) / len(bench) if bench else starter_average
    return max(1, min(99, round(.8 * starter_average + .2 * bench_average)))


def team_ratings(team_id: str, run_seed: int = 0, roster_context: tuple = ()) -> TeamRatings:
    if team_id not in TEAM_BY_ID:
        raise KeyError(f"Unknown team: {team_id}")
    if getattr(roster_context, 'lineup_rules', 1) >= 2:
        players = dict(roster_context)[team_id]
        return TeamRatings(lineup_unit_rating(players, {"QB", "RB", "WR", "TE", "OL"}),
                           lineup_unit_rating(players, {"DL", "LB", "CB", "S"}))
    if roster_context:
        current = dict(roster_context)[team_id]
        original = _roster_players(team_id, run_seed)
        base = team_ratings(team_id, run_seed)
        def strength(players, positions):
            starters = [p.rating for p in players
                        if p.position in positions and p.depth <= ROSTER_RULES[p.position][1]]
            return sum(starters) / len(starters)
        offense = {"QB", "RB", "WR", "TE", "OL"}
        defense = {"DL", "LB", "CB", "S"}
        return TeamRatings(
            max(1, min(99, round(base.offense + strength(current, offense) - strength(original, offense)))),
            max(1, min(99, round(base.defense + strength(current, defense) - strength(original, defense)))))
    return TeamRatings(
        offense=72 + _run_number(f"{team_id}:offense", run_seed) % 17,
        defense=72 + _run_number(f"{team_id}:defense", run_seed) % 17,
    )


def validate_roster(players: list[Player]) -> None:
    """Enforce position minimums for roster management."""
    if len({player.id for player in players}) != len(players):
        raise ValueError("The roster contains duplicate player IDs")
    counts = Counter(player.position for player in players)
    unknown = set(counts) - set(ROSTER_RULES)
    if unknown:
        raise ValueError(f"Unknown roster position: {', '.join(sorted(unknown))}")
    for position, (_, minimum) in ROSTER_RULES.items():
        if counts[position] < minimum:
            raise ValueError(f"{position} needs at least {minimum} players")


@lru_cache(maxsize=120)
def _roster_players(team_id: str, run_seed: int = 0) -> tuple[Player, ...]:
    if team_id not in TEAM_BY_ID:
        raise KeyError(f"Unknown team: {team_id}")
    used_names: set[str] = set()
    if len(FIRST_NAMES) * len(LAST_NAMES) < len(ROSTER_SLOTS):
        raise ValueError("Name pools need enough combinations for a full roster")
    players = []
    ratings = team_ratings(team_id, run_seed)
    for index, (position, depth) in enumerate(ROSTER_SLOTS):
        slot = f"{position}{depth}"
        offset = 0
        while True:
            number = _run_number(f"{team_id}:{slot}:{offset}", run_seed)
            first = FIRST_NAMES[(number + index) % len(FIRST_NAMES)]
            last = LAST_NAMES[(number // len(FIRST_NAMES) + index * 3) % len(LAST_NAMES)]
            name = f"{first} {last}"
            if name not in used_names:
                break
            offset += 1
        used_names.add(name)
        base_rating = ratings.defense if position in ("DL", "LB", "CB", "S") else ratings.offense
        player_id = f"{team_id}-{slot.lower()}"
        rating = max(50, min(99, base_rating - 8
                            + _run_number(f"{team_id}:{slot}:scouting", run_seed) % 17))
        experience = _run_number(f"{team_id}:{slot}:experience", run_seed) % 13
        players.append(Player(
            id=player_id, name=name, position=position, depth=depth,
            experience=experience,
            age=21 + _run_number(f"{player_id}:entry-age", run_seed) % 4 + experience,
            rating=rating,
            attributes=generate_attributes(player_id, position, rating, run_seed),
        ))
    validate_roster(players)
    return tuple(players)


def roster_for(team_id: str, run_seed: int = 0, roster_context: tuple = ()) -> dict[str, Player]:
    # Return a fresh mapping so callers cannot mutate the cached roster.
    return {f"{player.position}{player.depth}": player for player in (dict(roster_context)[team_id] if roster_context else _roster_players(team_id, run_seed))}


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
    is_home: bool | None,
    rng: random.Random,
    run_seed: int = 0,
    roster_context: tuple = (),
) -> dict[str, object]:
    ratings = team_ratings(team.id, run_seed, roster_context)
    opponent_ratings = team_ratings(opponent.id, run_seed, roster_context)
    expected_points = 22.0 + (ratings.offense - opponent_ratings.defense) * 0.36
    expected_points += 0.0 if is_home is None else (1.6 if is_home else -0.4)

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

    roster = roster_for(team.id, run_seed, roster_context)
    reception_weights = [rng.uniform(0.28, 0.38), rng.uniform(0.20, 0.30), rng.uniform(0.13, 0.21), rng.uniform(0.12, 0.20)]
    receiving_yards = _split_total(passing_yards, reception_weights)
    receptions = _split_total(completions, [weight ** 0.82 for weight in reception_weights])
    receiving_tds = _split_total(passing_tds, reception_weights)

    qb = roster["QB1"]
    rb = roster["RB1"]
    receivers = [roster["WR1"], roster["WR2"], roster["TE1"], rb]

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
            "player_id": qb.id,
            "player": qb.name,
            "position": "QB",
            "completions": completions,
            "completion_rate": completion_rate,
            "attempts": attempts,
            "yards": passing_yards,
            "touchdowns": passing_tds,
            "interceptions": interceptions,
        }],
        "rushing": [{
            "player_id": rb.id,
            "player": rb.name,
            "position": "RB",
            "attempts": carries,
            "yards": rushing_yards,
            "touchdowns": rushing_tds,
        }],
        "receiving": [
            {
                "player": player.name,
                "player_id": player.id,
                "position": player.position,
                "receptions": receptions[index],
                "yards": receiving_yards[index],
                "touchdowns": receiving_tds[index],
            }
            for index, player in enumerate(receivers)
        ],
        "kicking": [{
            "player_id": roster["K1"].id,
            "player": roster["K1"].name,
            "position": "K",
            "field_goals_made": field_goals,
            "field_goals_attempted": field_goals + (1 if rng.random() < 0.24 else 0),
            "extra_points_made": touchdowns,
        }],
        "scoring": {"touchdowns": touchdowns, "field_goals": field_goals},
    }


def resolve_overtime(
    home_box: dict, away_box: dict, rng: random.Random,
    *, allow_ties: bool = True, neutral_site: bool = False, run_seed: int = 0, roster_context: tuple = (),
) -> bool:
    """Resolve a regulation tie with a simplified overtime field goal.

    Most overtime games have a winner; a small fraction remain tied.
    This is a lightweight game model, not a play-by-play NFL rules engine.
    """
    if home_box["score"] != away_box["score"]:
        return False
    if allow_ties and rng.random() < 0.05:
        return True

    home = team_ratings(home_box["team"]["id"], run_seed, roster_context)
    away = team_ratings(away_box["team"]["id"], run_seed, roster_context)
    advantage = home.offense + home.defense - away.offense - away.defense
    home_win_probability = max(0.25, min(0.75, (0.5 if neutral_site else 0.52) + advantage / 100))
    winner = home_box if rng.random() < home_win_probability else away_box
    winner["score"] += 3
    winner["scoring"]["field_goals"] += 1
    winner["kicking"][0]["field_goals_made"] += 1
    winner["kicking"][0]["field_goals_attempted"] += 1
    return True


def pass_share(qb_skill: float, rb_skill: float, deficit: int, experience: int) -> float:
    """Score and relative skill outweigh the modest experience/trust effect."""
    score_effect = max(-0.15, min(0.15, deficit * 0.0075))
    share = 0.55 + (qb_skill - rb_skill) * 0.005 + score_effect + (experience - 6) * 0.004
    return max(0.30, min(0.75, share))


def total_plays(combined_score: int, skill_gap: int, rng: random.Random) -> int:
    center = 65 + (combined_score - 44) * 0.15 + skill_gap * 0.20
    return max(50, min(85, round(rng.gauss(center, 4))))


def possession_weights(carries: int, completions: int, incompletions: int) -> int:
    # Relative clock consumption, normalized to a 60-minute game below.
    return carries * 35 + completions * 28 + incompletions * 8


def apply_usage(box: dict, opponent_box: dict, rng: random.Random, run_seed: int = 0, roster_context: tuple = ()) -> None:
    """Shape aggregate box scores after scoring; this is not a drive engine."""
    roster = roster_for(box["team"]["id"], run_seed, roster_context)
    qb = roster["QB1"]
    backs = [player for player in roster.values() if player.position == "RB"][:2]
    rb1_share = rng.uniform(0.50, 0.90) if len(backs) > 1 else 1.0
    back_weights = [rb1_share, 1 - rb1_share] if len(backs) > 1 else [1.0]
    rb_skill = sum(player.rating * weight for player, weight in zip(backs, back_weights))
    ratings = team_ratings(box["team"]["id"], run_seed, roster_context)
    opponent_ratings = team_ratings(opponent_box["team"]["id"], run_seed, roster_context)
    plays = total_plays(box["score"] + opponent_box["score"],
                        ratings.offense - opponent_ratings.defense, rng)
    attempts = round(plays * pass_share(qb.rating, rb_skill,
                                       opponent_box["score"] - box["score"], qb.experience))
    carries = plays - attempts
    passing = box["passing"][0]
    completions = min(attempts, round(attempts * passing["completion_rate"]))
    passing.update({"attempts": attempts, "completions": completions})
    stats = box["team_stats"]
    stats.update({"total_plays": plays, "pass_attempts": attempts, "rush_attempts": carries})
    rush_attempts = _split_total(carries, back_weights)
    rush_yards = _split_total(stats["rushing_yards"], back_weights)
    rush_tds = _split_total(sum(row["touchdowns"] for row in box["rushing"]), back_weights)
    box["rushing"] = [
        {"player": player.name, "player_id": player.id, "position": "RB", "attempts": rush_attempts[index],
         "yards": rush_yards[index], "touchdowns": rush_tds[index]}
        for index, player in enumerate(backs)
    ]

    receivers = []
    weights = []
    # Share the team's receiving opportunities across every WR, both TEs and RBs.
    for position, group_share in (("WR", 0.60), ("TE", 0.22)):
        group = [player for player in roster.values() if player.position == position]
        raw = [rng.uniform(0.5, 1.5) for _ in group]
        receivers.extend(group)
        weights.extend(group_share * weight / sum(raw) for weight in raw)
    receivers.extend(backs)
    weights.extend(0.18 * weight for weight in back_weights)
    receptions = _split_total(completions, weights)
    eligible = [weight if catches else 0 for weight, catches in zip(weights, receptions)]
    yards = _split_total(stats["passing_yards"], eligible)
    # Allocate each receiving TD only to a player with an unused reception.
    touchdowns = [0] * len(receivers)
    for _ in range(passing["touchdowns"]):
        available = [weight if touchdowns[index] < receptions[index] else 0
                     for index, weight in enumerate(weights)]
        recipient = rng.choices(range(len(receivers)), weights=available)[0]
        touchdowns[recipient] += 1
    box["receiving"] = [
        {"player": player.name, "player_id": player.id, "position": player.position, "yards": yards[index],
         "receptions": receptions[index], "touchdowns": touchdowns[index]}
        for index, player in enumerate(receivers)
    ]


def assign_possession(home_box: dict, away_box: dict) -> None:
    weights = []
    for box in (home_box, away_box):
        stats = box["team_stats"]
        qb = box["passing"][0]
        weights.append(possession_weights(stats["rush_attempts"], qb["completions"],
                                           qb["attempts"] - qb["completions"]))
    seconds = _split_total(3600, weights)
    for box, duration in zip((home_box, away_box), seconds):
        box["team_stats"]["time_of_possession"] = f"{duration // 60}:{duration % 60:02d}"


def simulate_game(
    selected_team_id: str,
    game: ScheduledGame,
    season: int,
    *, allow_ties: bool = True, neutral_site: bool = False, run_seed: int = 0,
    include_defense_and_blocking: bool = True,
    roster_context: tuple = (),
) -> dict[str, object]:
    selected_team = TEAM_BY_ID[selected_team_id]
    opponent = TEAM_BY_ID[game.opponent_id]
    ordered_ids = sorted((selected_team.id, opponent.id))
    seed = _run_number(f"season:{season}:week:{game.week}:{ordered_ids[0]}:{ordered_ids[1]}", run_seed)
    rng = random.Random(seed)

    selected_is_home = game.venue == "Home"
    home_team = selected_team if selected_is_home else opponent
    away_team = opponent if selected_is_home else selected_team
    home_box = _team_box(home_team, away_team, None if neutral_site else True, rng, run_seed, roster_context)
    away_box = _team_box(away_team, home_team, None if neutral_site else False, rng, run_seed, roster_context)
    overtime = resolve_overtime(home_box, away_box, rng, allow_ties=allow_ties, neutral_site=neutral_site, run_seed=run_seed, roster_context=roster_context)
    selected_box = home_box if selected_is_home else away_box
    opponent_box = away_box if selected_is_home else home_box
    # Independent usage stream keeps the existing scoring/overtime draws stable.
    usage_rng = random.Random(_stable_number(f"usage:{seed}"))
    apply_usage(home_box, away_box, usage_rng, run_seed, roster_context)
    apply_usage(away_box, home_box, usage_rng, run_seed, roster_context)
    assign_possession(home_box, away_box)
    add_efficiency_stats(home_box)
    add_efficiency_stats(away_box)
    # Separate stream preserves scores, usage, and playoff outcomes.
    kicking_rng = random.Random(_stable_number(f"kicking:{seed}"))
    add_kicking_stats(home_box, kicking_rng,
                      overtime_winner=overtime and home_box["score"] > away_box["score"])
    add_kicking_stats(away_box, kicking_rng,
                      overtime_winner=overtime and away_box["score"] > home_box["score"])
    if include_defense_and_blocking:
        defense_rng = random.Random(_stable_number(f"defense:{seed}"))
        add_defense_and_blocking(home_box, away_box, roster_for(home_team.id, run_seed, roster_context), defense_rng)
        add_defense_and_blocking(away_box, home_box, roster_for(away_team.id, run_seed, roster_context), defense_rng)
    selected_score = int(selected_box["score"])
    opponent_score = int(opponent_box["score"])
    outcome = "T" if selected_score == opponent_score else ("W" if selected_score > opponent_score else "L")

    return {
        "week": game.week,
        "outcome": outcome,
        "overtime": overtime,
        "selected_team_id": selected_team.id,
        "home": home_box,
        "away": away_box,
    }


def simulate_league_week(season: int, week: int, run_seed: int = 0,
                         *, include_defense_and_blocking: bool = True,
                         prior_standings: tuple[tuple[str, int], ...] = (), roster_context: tuple = ()) -> list[dict[str, object]]:
    if week < 1 or week > 17:
        raise ValueError("Week must be between 1 and 17")
    results: list[dict[str, object]] = []
    for league_game in generate_league_schedule(season=season, standings=dict(prior_standings) or None):
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
        result = simulate_game(league_game.home_id, game, season, run_seed=run_seed,
                               include_defense_and_blocking=include_defense_and_blocking, roster_context=roster_context)
        results.append(result)
    return results


@lru_cache(maxsize=128)
def league_week_scores(season: int, week: int, run_seed: int = 0,
                       prior_standings: tuple[tuple[str, int], ...] = (), roster_context: tuple = ()) -> tuple[tuple[str, str, int, int], ...]:
    """Cache only immutable standings inputs, keyed by the complete run context."""
    return tuple((game["home"]["team"]["id"], game["away"]["team"]["id"],
                  game["home"]["score"], game["away"]["score"])
                 for game in simulate_league_week(season, week, run_seed, include_defense_and_blocking=False,
                                              prior_standings=prior_standings, roster_context=roster_context))


def simulate_through_week(team_id: str, season: int, week: int, run_seed: int = 0,
                          prior_standings: tuple[tuple[str, int], ...] = (), roster_context: tuple = ()) -> dict[str, object]:
    schedule = generate_schedule(team_id=team_id, season=season, standings=dict(prior_standings) or None)
    if week < 1 or week > len(schedule):
        raise ValueError(f"Week must be between 1 and {len(schedule)}")
    results = [simulate_game(team_id, game, season, run_seed=run_seed, roster_context=roster_context) for game in schedule[:week]]
    wins = sum(result["outcome"] == "W" for result in results)
    losses = sum(result["outcome"] == "L" for result in results)
    ties = sum(result["outcome"] == "T" for result in results)
    current = results[-1]
    game_results = []
    for game, result in zip(schedule, results):
        own_side = "home" if game.venue == "Home" else "away"
        other_side = "away" if own_side == "home" else "home"
        game_results.append({
            "week": game.week, "opponent_id": game.opponent_id,
            "opponent": game.opponent, "venue": game.venue,
            "outcome": result["outcome"], "team_score": result[own_side]["score"],
            "opponent_score": result[other_side]["score"], "overtime": result["overtime"],
        })
    other_results = []
    for league_result in simulate_league_week(season, week, run_seed, include_defense_and_blocking=False,
                                              prior_standings=prior_standings, roster_context=roster_context):
        if team_id in (league_result["home"]["team"]["id"], league_result["away"]["team"]["id"]):
            continue
        other_results.append({
            "away": league_result["away"]["team"],
            "away_score": league_result["away"]["score"],
            "home": league_result["home"]["team"],
            "home_score": league_result["home"]["score"],
            "overtime": league_result["overtime"],
        })
    from .standings import standings_through_week

    return {
        "team": asdict(TEAM_BY_ID[team_id]),
        "season": season,
        "run_seed": run_seed,
        "week": week,
        "record": {"wins": wins, "losses": losses, "ties": ties},
        "result": current,
        "game_results": game_results,
        "roster_stats": aggregate_player_stats(roster_for(team_id, run_seed, roster_context).values(),
            (result["home"] if result["home"]["team"]["id"] == team_id else result["away"]
             for result in results)),
        "league_results": other_results,
        "standings": standings_through_week(season, week, run_seed, prior_standings, roster_context),
        "season_complete": week == len(schedule),
        "next_week": None if week == len(schedule) else week + 1,
    }
