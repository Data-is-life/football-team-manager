"""Aggregate defensive and line production, allocated after game outcomes."""

DEFENSIVE_UNIT = {"DL": 4, "LB": 3, "CB": 2, "S": 2}


def _allocate(total, weights, capacities):
    """Integer weighted shares with a per-player participation limit."""
    counts = [0] * len(weights)
    eligible = [i for i, weight in enumerate(weights) if weight > 0 and capacities[i] > 0]
    if total < 0 or total > sum(capacities[i] for i in eligible):
        raise ValueError("Production exceeds available participation")
    remaining = total
    while remaining:
        weight_sum = sum(weights[i] for i in eligible)
        shares = {i: remaining * weights[i] / weight_sum for i in eligible}
        capped = [i for i in eligible if shares[i] >= capacities[i] - counts[i]]
        if capped:
            for i in capped:
                amount = capacities[i] - counts[i]
                counts[i] += amount
                remaining -= amount
            eligible = [i for i in eligible if i not in capped]
            continue
        for i in eligible:
            amount = int(shares[i])
            counts[i] += amount
            remaining -= amount
        for i in sorted(eligible, key=lambda i: shares[i] - int(shares[i]), reverse=True)[:remaining]:
            counts[i] += 1
        break
    return counts


def _identity(player):
    return {"player_id": player.id, "player": player.name, "position": player.position}


def add_defense_and_blocking(box, opponent, roster, rng):
    """Allocate existing sacks/INTs and estimated tackles; never change scores.

    Five starting linemen receive offensive snaps. Defenders rotate through a
    4-DL/3-LB/2-CB/2-S unit. Tackles assume one credit for each non-scoring
    completion/rush and each sack; sacks are included in tackles. All sacks
    allowed are assigned to a starting lineman. These are aggregate estimates,
    not observed plays, pressures, assists, or pass-protection grades.
    """
    players = list(roster.values())
    linemen = sorted((p for p in players if p.position == "OL"), key=lambda p: p.depth)
    pass_snaps = box["team_stats"]["pass_attempts"] + box["team_stats"]["sacks_allowed"]
    run_snaps = box["team_stats"]["rush_attempts"]
    sacks_allowed = _allocate(box["team_stats"]["sacks_allowed"],
        [(100 - p.rating) * rng.uniform(.75, 1.25) for p in linemen],
        [pass_snaps if p.depth <= 5 else 0 for p in linemen])
    box["blocking"] = [{**_identity(p), "pass_block_snaps": pass_snaps if p.depth <= 5 else 0,
        "run_block_snaps": run_snaps if p.depth <= 5 else 0, "sacks_allowed": sacks_allowed[i]}
        for i, p in enumerate(linemen)]

    defenders = [p for p in players if p.position in DEFENSIVE_UNIT]
    rows = [{**_identity(p), "snaps": 0, "tackles": 0, "sacks": 0, "interceptions": 0}
            for p in defenders]
    opponent_stats = opponent["team_stats"]
    opponent_sacks = opponent_stats["sacks_allowed"]
    snaps = opponent_stats["total_plays"] + opponent_sacks
    for position, count in DEFENSIVE_UNIT.items():
        indexes = [i for i, p in enumerate(defenders) if p.position == position]
        weights = [defenders[i].rating * (1 if defenders[i].depth <= count else .35)
                   * rng.uniform(.8, 1.2) for i in indexes]
        allocated = _allocate(snaps * count, weights, [snaps] * len(indexes))
        for i, value in zip(indexes, allocated):
            rows[i]["snaps"] = value

    def distribute(total, field, position_weights):
        weights = [row["snaps"] * p.rating * position_weights[p.position]
                   * rng.uniform(.75, 1.25) for p, row in zip(defenders, rows)]
        capacities = [row["snaps"] - row["tackles"] - row["interceptions"] for row in rows]
        allocated = _allocate(total, weights, capacities)
        for row, value in zip(rows, allocated):
            row[field] += value
            if field == "sacks":
                row["tackles"] += value

    distribute(opponent_sacks, "sacks", {"DL": 6, "LB": 3, "CB": .5, "S": .5})
    distribute(sum(p["interceptions"] for p in opponent["passing"]), "interceptions",
               {"DL": 0, "LB": 1, "CB": 3, "S": 3})
    tackles = max(0, opponent_stats["rush_attempts"] - sum(p["touchdowns"] for p in opponent["rushing"]))
    tackles += max(0, sum(p["completions"] - p["touchdowns"] for p in opponent["passing"]))
    distribute(tackles, "tackles", {"DL": 2, "LB": 4, "CB": 2, "S": 2})
    box["defense"] = rows
