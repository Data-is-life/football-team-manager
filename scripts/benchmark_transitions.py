"""Compare deterministic career transitions, separately from HTTP and rendering."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def transition_requests(seasons=3):
    from app.main import CareerRequest, career_action

    def call(body):
        return career_action('seattle', CareerRequest(**body))

    requests, history = {}, []
    for season in range(1, seasons+1):
        base = dict(season=season, run_seed=1234, lineup_rules=44,
                    rebuild_team='seattle', draft_rounds=6, career=list(history))
        requests[f'{season}-reload'] = dict(base, action='profile')
        draft = call(dict(base, action='draft', auto_draft=True))
        base['manual_picks'] = draft['manual_picks']
        requests[f'{season}-draft-complete'] = dict(base, action='draft')
        requests[f'{season}-draft-to-own'] = dict(base, action='own_players')
        own = call(requests[f'{season}-draft-to-own'])
        actions = []
        for player in own['profile']['roster']:
            if player.get('renewal_offer'):
                actions.append(dict(kind='drop', player_id=player['id']))
            elif player.get('contract_offer'):
                actions.append(dict(kind='sign', player_id=player['id']))
        actions.append(dict(kind='finish'))
        base['own_actions'] = actions
        requests[f'{season}-own-to-market'] = dict(base, action='free_agency')
        call(requests[f'{season}-own-to-market'])
        base['free_agency'] = [dict(kind='finish')]
        finished = call(dict(base, action='free_agency'))
        plan = finished['payroll_floor_adjustment']
        base['pre_camp_actions'] = [dict(kind='raise', player_id=plan['player_id'])] if plan else []
        base['trade_actions'] = [dict(kind='finish')]
        requests[f'{season}-market-finish'] = dict(base, action='trades')
        assert call(requests[f'{season}-market-finish'])['can_continue']
        history.append({key: value for key, value in base.items() if key in (
            'season', 'manual_picks', 'lineup_rules', 'draft_rounds', 'own_actions',
            'free_agency', 'pre_camp_actions', 'trade_actions')})
        requests[f'{season}-start-season'] = dict(base, season=season+1,
            career=list(history), action='profile', manual_picks=[], own_actions=[],
            free_agency=[], pre_camp_actions=[], trade_actions=[])
    return requests


def digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(raw.encode()).hexdigest()


def benchmark(requests, trials=3):
    from app.main import CareerRequest, career_action
    from benchmarks.profile_restore import clear_caches

    def call(body):
        return career_action('seattle', CareerRequest(**body))

    checks, samples = {}, {}
    for _ in range(trials):
        clear_caches()
        for name, body in requests.items():
            start = time.perf_counter()
            data = call(body)
            samples.setdefault(name, []).append((time.perf_counter()-start)*1000)
            hashed = digest(data)
            if name in checks:
                assert checks[name] == hashed, f'Replay changed: {name}'
            checks[name] = hashed
    cold, warm = [], []
    reload_name = next(reversed([name for name in requests if name.endswith('-reload')]))
    for _ in range(trials):
        clear_caches()
        for output in (cold, warm):
            start = time.perf_counter()
            data = call(requests[reload_name])
            output.append((time.perf_counter()-start)*1000)
            assert digest(data) == checks[reload_name]
    return dict(sha256=checks,
        sequential_ms={key: round(statistics.median(value), 2) for key, value in samples.items()},
        reload=reload_name, reload_cold_ms=round(statistics.median(cold), 2),
        reload_warm_ms=round(statistics.median(warm), 2), trials=trials,
        scope='Python endpoint calls; excludes HTTP, hosting startup and browser rendering.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--seasons', type=int, choices=range(1, 11), default=3)
    parser.add_argument('--trials', type=int, choices=range(1, 11), default=3)
    parser.add_argument('--requests', type=Path, help='Reuse exact request bodies from another revision')
    parser.add_argument('--save-requests', type=Path)
    args = parser.parse_args()
    sys.path[:0] = [str(args.root.resolve()), str(ROOT)]
    requests = (json.loads(args.requests.read_text()) if args.requests
                else transition_requests(args.seasons))
    if args.save_requests:
        args.save_requests.write_text(json.dumps(requests, indent=2)+'\n')
    print(json.dumps(benchmark(requests, args.trials), indent=2))


if __name__ == '__main__':
    main()
