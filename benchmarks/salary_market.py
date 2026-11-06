"""Compare inherited payroll with a hypothetical all-market renewal portfolio.

Run: python benchmarks/salary_market.py
This is not actual payroll: signed deals are never repriced all at once.
"""
import json
from pathlib import Path
from statistics import mean, median, pstdev
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.lineups import lineup_context
from app.player_contracts import payroll, veteran_contract


def summary(values):
    return dict(count=len(values),mean_m=round(mean(values)/1e6,2),median_m=round(median(values)/1e6,2),
                standard_deviation_m=round(pstdev(values)/1e6,2),minimum_m=round(min(values)/1e6,2),
                maximum_m=round(max(values)/1e6,2),above_200m=sum(v>200_000_000 for v in values))


def measure():
    inherited,market,managed=[],[],[]
    for seed in range(1,21):
        context=lineup_context((),seed,21,rebuild_team='seattle')
        for owner,players in context:
            if owner=='seattle':
                managed.append(payroll(players))
            else:
                inherited.append(payroll(players))
                market.append(sum(veteran_contract(p,1,21).annual_salary for p in players))
    return dict(method='Seeds 1–20, Seattle managed team; 580 opponent rosters, 35 players each. Season-1 $200M cap. Hypothetical market portfolio quotes every player at current ability simultaneously; it is NOT actual payroll or a forecast. Inherited signed deals remain fixed. Later real renewals are staggered and subject to final cap cuts.',
                inherited_opponents=summary(inherited),hypothetical_market_portfolio=summary(market),
                inherited_managed=summary(managed))


if __name__=='__main__':print(json.dumps(measure(),indent=2))
