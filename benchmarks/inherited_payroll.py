"""Reproduce initial selected-team payroll bounds and bad-contract counts."""
import json
from pathlib import Path
from statistics import mean,median
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.lineups import lineup_context
from app.player_contracts import payroll


def measure():
    samples=[];bad_amounts=[]
    for seed in range(1,51):
        for owner in ('seattle','miami','dallas','las-vegas'):
            players=dict(lineup_context((),seed,25,rebuild_team=owner))[owner]
            bad=[p for p in players if p.contract.category=='inherited_bad']
            assert len(players)==35 and len(bad)==3
            total=payroll(players)
            assert 160_000_000<=total<=200_000_000
            samples.append(total/1e6)
            bad_amounts.append(sum(p.contract.annual_salary for p in bad)/1e6)
    return dict(method='200 new careers: seeds 1–50, four selected cities, rules 25, Season 1. Actual 35-player signed payroll; three weaker-player 3–4 year deals per career. Existing careers and opponent contracts are not repriced.',
                careers=len(samples),payroll_m=dict(minimum=min(samples),maximum=max(samples),median=median(samples),mean=round(mean(samples),2)),
                three_bad_deals_combined_annual_m=dict(minimum=round(min(bad_amounts),2),maximum=round(max(bad_amounts),2),mean=round(mean(bad_amounts),2)))


if __name__=='__main__':print(json.dumps(measure(),indent=2))
