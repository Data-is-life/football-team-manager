"""Derived box-score statistics; these do not change simulation outcomes."""


def per_opportunity(total: int, opportunities: int) -> float | None:
    return total / opportunities if opportunities else None


def passer_rating(completions: int, attempts: int, yards: int,
                  touchdowns: int, interceptions: int) -> float | None:
    """NFL formula: clamp each component to 0..2.375 before scaling."""
    if not attempts:
        return None
    components = (
        (completions / attempts - 0.3) * 5,
        (yards / attempts - 3) * 0.25,
        touchdowns / attempts * 20,
        2.375 - interceptions / attempts * 25,
    )
    return sum(min(2.375, max(0, value)) for value in components) / 6 * 100


def add_efficiency_stats(box: dict) -> None:
    """Keep full precision in the API; the UI formats one decimal place."""
    for row in box["passing"]:
        completion_share = per_opportunity(row["completions"], row["attempts"])
        row["completion_percentage"] = None if completion_share is None else completion_share * 100
        row["yards_per_attempt"] = per_opportunity(row["yards"], row["attempts"])
        row["passer_rating"] = passer_rating(row["completions"], row["attempts"],
                                             row["yards"], row["touchdowns"], row["interceptions"])
    for row in box["rushing"]:
        row["yards_per_carry"] = per_opportunity(row["yards"], row["attempts"])
    for row in box["receiving"]:
        row["yards_per_reception"] = per_opportunity(row["yards"], row["receptions"])
