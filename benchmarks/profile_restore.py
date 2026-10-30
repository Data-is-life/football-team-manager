"""Profile application work separately from HTTP and browser rendering."""
import cProfile
import io
import json
import pstats
import sys
import time
from app.main import CareerRequest, career_action


def clear_caches():
    seen = set()
    for name, module in list(sys.modules.items()):
        if name.startswith('app.'):
            for value in vars(module).values():
                if callable(getattr(value, 'cache_clear', None)) and id(value) not in seen:
                    value.cache_clear()
                    seen.add(id(value))


def request(save, action):
    return CareerRequest(action=action, season=save['season'], run_seed=save['runSeed'],
                         lineup_rules=save['lineupRules'], development_start=save['developmentStart'],
                         rebuild_team=save['rebuildTeam'], prior_standings=save['priorStandings'] or None,
                         career=save['career'], week=save['week'] or 1, round_number=save['playoffRound'] or 0,
                         manual_picks=save['draftChoices'] or [], dropped=save['dropped'])


if __name__ == '__main__':
    save=json.load(open(sys.argv[1] if len(sys.argv)>1 else 'benchmarks/year4.json'))
    clear_caches()
    profiler=cProfile.Profile()
    start=time.perf_counter()
    profiler.enable()
    actions = ['profile'] + (['week'] if save['week'] else []) + (['playoffs'] if save['playoffRound'] is not None else []) + (['cuts'] if save['draftChoices'] is not None else [])
    for action in actions:
        step=time.perf_counter(); result=career_action(save['teamId'],request(save,action))
        print(action,round((time.perf_counter()-step)*1000,2),'ms',flush=True)
    profiler.disable()
    print('total',round((time.perf_counter()-start)*1000,2),'ms')
    out=io.StringIO(); pstats.Stats(profiler,stream=out).sort_stats('cumtime').print_stats(28)
    print(out.getvalue())
