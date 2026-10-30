"""Canonical API snapshots for the same checkpoints against two source trees."""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(sys.argv[1]).resolve()))
from app.main import CareerRequest, career_action

result = {}
for name in ('fresh', 'year4', 'year8'):
    save = json.loads((Path(__file__).parent / (name+'.json')).read_text())
    actions = ['profile'] + (['week'] if save['week'] else []) + (['playoffs'] if save['playoffRound'] is not None else []) + (['cuts'] if save['draftChoices'] is not None else [])
    for action in actions:
        request = CareerRequest(action=action, season=save['season'], run_seed=save['runSeed'],
            lineup_rules=save['lineupRules'], development_start=save['developmentStart'],
            rebuild_team=save['rebuildTeam'], prior_standings=save['priorStandings'] or None,
            career=save['career'], week=save['week'] or 1, round_number=save['playoffRound'] or 0,
            manual_picks=save['draftChoices'] or [], dropped=save['dropped'])
        payload = career_action(save['teamId'], request)
        result[name+'/'+action] = hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
print(json.dumps(result,indent=2,sort_keys=True))
