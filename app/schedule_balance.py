"""Deterministic venue assignment with bounded search and strict validation."""
from collections import defaultdict
from dataclasses import replace
import math
import random


def balance_venues(games, seed):
    """Keep every matchup/week; flip group rematches together to retain home/away."""
    teams = sorted({g.home_id for g in games}|{g.away_id for g in games})
    index = {team:i for i,team in enumerate(teams)}
    initial = [0]*len(teams)
    groups = defaultdict(list)
    for i,g in enumerate(games):
        initial[index[g.home_id]] |= 1 << (g.week-1)
        key = ('group',*sorted((g.home_id,g.away_id))) if g.reason=='Group rematch' else ('game',i)
        groups[key].append(i)
    variables=[];by_team=[[] for _ in teams]
    for ids in groups.values():
        masks=defaultdict(int)
        for i in ids:
            g=games[i]
            masks[index[g.home_id]] ^= 1 << (g.week-1)
            masks[index[g.away_id]] ^= 1 << (g.week-1)
        variables.append((ids,tuple(masks.items())))
        for team in masks:by_team[team].append(len(variables)-1)
    window_mask = (1 << 15)-1  # Fifteen three-week windows in a 17-week season.
    def penalty(bits):
        home=bits.bit_count();gap=max(8-home,home-9,0)
        runs=((bits & (bits>>1) & (bits>>2)) | (~bits & (~bits>>1) & (~bits>>2))) & window_mask
        return runs.bit_count()+2*gap*gap
    rng=random.Random(seed)
    for _ in range(8):
        bits=initial.copy();flipped=[False]*len(variables)
        costs=[penalty(b) for b in bits];total=sum(costs)
        for step in range(25000):
            if total==0:
                result=list(games)
                for flip,(ids,_) in zip(flipped,variables):
                    if flip:
                        for i in ids:result[i]=replace(games[i],home_id=games[i].away_id,away_id=games[i].home_id)
                return sorted(result,key=lambda g:(g.week,g.home_id,g.away_id))
            bad=[i for i,c in enumerate(costs) if c]
            v=rng.choice(by_team[rng.choice(bad)])
            masks=variables[v][1]
            updated=[(t,bits[t]^mask) for t,mask in masks]
            new=[(t,b,penalty(b)) for t,b in updated]
            delta=sum(c-costs[t] for t,_,c in new)
            temperature=1.25*(1-(step%5000)/5000)+.02
            if delta<=0 or rng.random()<math.exp(-delta/temperature):
                for t,b,c in new:bits[t]=b;costs[t]=c
                total+=delta;flipped[v]=not flipped[v]
    return None
