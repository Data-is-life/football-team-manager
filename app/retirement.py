"""Rules 10: seeded retirements and low-quality offseason roster fillers."""
from collections import Counter
import random
from .simulation import Player, ranked_players, _run_number, roster_rules, roster_fill_target, roster_minimum
from .attributes import generate_attributes
from .names import FIRST_NAMES, LAST_NAMES

FINAL_AGE = {'QB':40,'K':40,'RB':33,'WR':35,'TE':35,'OL':38,'DL':36,'LB':35,'CB':34,'S':33}


def retirement_age(player, seed):
    from .development import longevity
    delay, _ = longevity(seed, player.id, player.position)
    ability = -2 if player.rating < 60 else 2 if player.rating > 80 else 0
    return FINAL_AGE[player.position] + delay + ability


def retiring(player, context):
    return getattr(context,'lineup_rules',1) >= 10 and player.age >= retirement_age(player,context.run_seed)


def retirement_payload(player):
    return dict(id=player.id,name=player.name,position=player.position,age=player.age,current_rating=player.rating)


def fill_roster(players, owner, season, seed, excluded=(), context=(), identity_suffix=""):
    """Fill required positions, then vacancies toward the versioned total target.

    Minimums can require temporary oversizing after an imbalanced draft; normal
    cuts still apply. Excluded IDs prevent released fillers from returning.
    """
    # New leagues still start at 35; later emergency fills target the legal
    # floor, so intentional cuts to 31 never refill the optional bench.
    fill_target=roster_minimum(context) if getattr(context,'lineup_rules',1)>=24 else roster_fill_target(context)
    remaining = list(players)
    ids = {p.id for p in remaining} | set(excluded)
    names = {p.name for p in remaining}
    counts = Counter(p.position for p in remaining)
    for minimum_only in (True, False):
        for position,(target,minimum) in roster_rules(context).items():
            needed = max(0,(minimum if minimum_only else target)-counts[position])
            if not minimum_only: needed = min(needed,max(0,fill_target-len(remaining)))
            for _ in range(needed):
                index = 1
                identity = f'replacement-{seed}-{season+1}-{owner}-{position}{identity_suffix}-{index}'
                while identity in ids:
                    index += 1
                    identity = f'replacement-{seed}-{season+1}-{owner}-{position}{identity_suffix}-{index}'
                rng = random.Random(_run_number(identity,seed))
                name = f'{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}'
                while name in names: name = f'{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}'
                names.add(name)
                rating = rng.randint(40,55)
                player = Player(identity,name,position,rating,counts[position]+1,0,rng.randint(24,28),
                                generate_attributes(identity,position,rating,seed))
                if getattr(context,'lineup_rules',1) >= 15:
                    from dataclasses import replace
                    from .player_contracts import starting_contract
                    player = replace(player,contract=starting_contract(player,season+1,getattr(context,"lineup_rules",1)))
                remaining.append(player);ids.add(identity);counts[position] += 1
    return ranked_players(remaining)
