"""Cumulative player production from completed team box scores."""

from .stats import add_efficiency_stats, per_opportunity


COUNT_FIELDS = {
    "defense": ("snaps", "tackles", "sacks", "interceptions"),
    "blocking": ("pass_block_snaps", "run_block_snaps", "sacks_allowed"),
    "passing": ("completions", "attempts", "yards", "touchdowns", "interceptions"),
    "rushing": ("attempts", "yards", "touchdowns"),
    "receiving": ("receptions", "yards", "touchdowns"),
    "kicking": ("field_goals_made", "field_goals_attempted", "extra_points_made",
                "extra_points_attempted", "kicking_points"),
}
POSITION_CATEGORIES = {
    "DL": ("defense",), "LB": ("defense",), "CB": ("defense",), "S": ("defense",),
    "OL": ("blocking",),
    "QB": ("passing",), "RB": ("rushing", "receiving"),
    "WR": ("receiving",), "TE": ("receiving",), "K": ("kicking",),
}


def aggregate_player_stats(players, boxes) -> dict:
    """Rebuild a snapshot from totals, never average per-game rate statistics."""
    totals = {}
    for player in players:
        entry = {"player_id": player.id, "position": player.position}
        for category in POSITION_CATEGORIES.get(player.position, ()):
            entry[category] = {field: 0 for field in COUNT_FIELDS[category]}
            if category == "kicking":
                entry[category]["longest_field_goal"] = None
        totals[player.id] = entry

    boxes = tuple(boxes)
    modern = any('participation' in box for box in boxes)
    if modern:
        for entry in totals.values():
            entry['snaps'] = 0
            if 'receiving' in entry:entry['receiving']['targets'] = 0
    games = 0
    for box in boxes:
        games += 1
        for row in box.get('participation',[]):
            totals[row['player_id']]['snaps'] += row['snaps']
        for category, fields in COUNT_FIELDS.items():
            for row in box.get(category, []):
                target = totals[row["player_id"]][category]
                if category == 'receiving' and 'targets' in row:
                    target['targets'] += row['targets']
                for field in fields:
                    target[field] += row[field]
                if category == "kicking" and row["longest_field_goal"] is not None:
                    previous = target["longest_field_goal"]
                    target["longest_field_goal"] = max(previous or 0, row["longest_field_goal"])

    add_efficiency_stats({
        category: [row[category] for row in totals.values() if category in row]
        for category in ("passing", "rushing", "receiving")
    })
    for entry in totals.values():
        if "kicking" in entry:
            row = entry["kicking"]
            share = per_opportunity(row["field_goals_made"], row["field_goals_attempted"])
            row["field_goal_percentage"] = None if share is None else share * 100
    return {"games": games, "players": list(totals.values())}
