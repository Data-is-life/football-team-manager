"""Kicking detail for the aggregate engine, after scoring is finalized."""

import random

from .stats import per_opportunity


def add_kicking_stats(box: dict, rng: random.Random, *, overtime_winner: bool = False) -> None:
    """Generate attempt distances around existing outcomes without changing scores.

    Distances are fictional aggregate detail, not derived from field position.
    The simplified overtime engine adds exactly one made FG for the winner.
    """
    for row in box["kicking"]:
        overtime_count = int(overtime_winner)
        made = row["field_goals_made"] - overtime_count
        attempted = row["field_goals_attempted"] - overtime_count
        attempts = [
            {"distance_yards": round(rng.triangular(18, 62, 38)),
             "made": index < made, "overtime": False}
            for index in range(attempted)
        ]
        rng.shuffle(attempts)
        if overtime_winner:
            attempts.append({"distance_yards": round(rng.triangular(18, 55, 35)),
                             "made": True, "overtime": True})
        row["field_goal_attempts"] = attempts
        row["longest_field_goal"] = max(
            (kick["distance_yards"] for kick in attempts if kick["made"]), default=None)
        share = per_opportunity(row["field_goals_made"], row["field_goals_attempted"])
        row["field_goal_percentage"] = None if share is None else share * 100
        # Every TD currently produces a made extra point; misses/2-point tries are not modeled.
        row["extra_points_attempted"] = row["extra_points_made"]
        row["kicking_points"] = 3 * row["field_goals_made"] + row["extra_points_made"]
