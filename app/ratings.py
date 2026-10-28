"""Small, deterministic current/potential view without changing simulation ability."""
import hashlib


def rating_payload(player, roster_context=()) -> dict[str, int]:
    if getattr(roster_context,"lineup_rules",1)==3:
        from .development import rating_view
        return rating_view(player,roster_context)
    current = player.rating
    # Basic shared age bands for now; position-specific development comes later.
    if player.age >= 30:
        headroom = 0
    else:
        maximum = 18 if player.age <= 24 else 2 * (30 - player.age)
        minimum = 6 if player.age <= 24 else 0
        number = int.from_bytes(hashlib.sha256(f'potential:{player.id}'.encode()).digest()[:8], 'big')
        headroom = minimum + number % (maximum - minimum + 1)
    return {'current_rating': current, 'potential_rating': min(99, current + headroom)}
