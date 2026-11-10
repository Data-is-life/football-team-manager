"""Reproducible local HTTP + jsdom benchmarks; never contacts a live service."""
import argparse
import json
import math
from pathlib import Path
import statistics
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8768"


def request(path, body=None):
    start = time.perf_counter()
    payload = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(BASE+path,data=payload,
        headers={'Content-Type':'application/json'} if body is not None else {})
    with urllib.request.urlopen(req, timeout=60) as response:
        data = json.load(response)
    return data, (time.perf_counter() - start) * 1000


def summary(values):
    ordered = sorted(values)
    return {"n": len(values), "median_ms": round(statistics.median(values), 2),
            "p95_ms": round(ordered[math.ceil(len(values) * .95) - 1], 2)}


def modern_benchmark(seasons):
    """Current rules, POST endpoints and progressively longer saved careers."""
    history, results = [], []
    def measure(body):
        data, first = request('/api/career/seattle',body)
        warm = []
        for _ in range(3):
            again, elapsed = request('/api/career/seattle',body)
            if again != data:
                raise AssertionError('Repeated benchmark request changed game output')
            warm.append(elapsed)
        return data, {'first_call_ms':round(first,2),'warm':summary(warm)}
    for season in range(1,seasons+1):
        base = dict(season=season,run_seed=1234,lineup_rules=30,development_start=1,
                    rebuild_team='seattle',draft_rounds=6,career=list(history))
        draft, draft_time = measure({**base,'action':'draft','auto_draft':True})
        camp_body = {**base,'action':'camp','training_camp':True,'manual_picks':draft['manual_picks']}
        camp,_ = request('/api/career/seattle',camp_body)
        drops = [p['id'] for p in camp['profile']['roster'] if p.get('contract_offer') or p.get('renewal_offer')]
        actions = [dict(kind='drop',player_id=identity) for identity in drops]
        market_body = {**camp_body,'action':'free_agency','dropped':drops,'roster_actions':actions}
        opened, open_time = measure({**market_body,'free_agency':[]})
        _, wave_time = measure({**market_body,'free_agency':[dict(kind='pass') for _ in range(6)]})
        finish_actions = [dict(kind='finish')]
        finished, finish_time = measure({**market_body,'free_agency':finish_actions})
        if not finished['complete']:
            raise AssertionError('Benchmark offseason did not finish')
        history.append(dict(season=season,lineup_rules=30,draft_rounds=6,
            manual_picks=draft['manual_picks'],dropped=drops,roster_actions=actions,
            free_agency=finish_actions))
        _, replay_time = measure({**base,'action':'profile','season':season+1,'career':list(history)})
        results.append({'completed_seasons':season,'pool_size':len(opened['available']),
            'draft':draft_time,'market_open':open_time,'market_wave7':wave_time,
            'market_finish':finish_time,'next_season_profile':replay_time})
    return {'rules':30,'seed':1234,'timing_scope':'Local HTTP including JSON; first calls may reuse earlier preparation caches; warm calls repeat identical requests.',
            'seasons':results}


def legacy_benchmark(teams, startup):
    schedule, first_schedule = request('/api/schedule/seattle?season=1')
    profile, first_profile = request('/api/team/seattle?run_seed=1234')
    profile_times = [request('/api/team/seattle?run_seed=1234')[1] for _ in range(7)]
    weekly, postseason, season_totals = [], [], []
    fixtures = {'teams':teams,'schedule':schedule,'profile':profile}
    for seed in (1234,5678,9012):
        total = 0
        for week in range(1,18):
            data, elapsed = request(f'/api/season/seattle/week/{week}?run_seed={seed}')
            weekly.append(elapsed); total += elapsed
            if seed==1234 and week==9: fixtures['week'] = data
        season_totals.append(total)
        for number in range(5):
            _, elapsed = request(f'/api/playoffs/seattle/round/{number}?run_seed={seed}')
            postseason.append(elapsed)
    retries = [request('/api/season/seattle/week/17?run_seed=9012')[1] for _ in range(7)]
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)/'fixtures.json'; path.write_text(json.dumps(fixtures))
        ui = json.loads(subprocess.check_output(['node',str(Path(__file__).with_name('benchmark_ui.cjs')),str(path)],cwd=ROOT))
    return {'startup_to_ready_ms':round(startup,2),'first_schedule_ms':round(first_schedule,2),
        'first_profile_ms':round(first_profile,2),'warm_profile':summary(profile_times),
        'fresh_run_weekly':summary(weekly),'regular_season_total':summary(season_totals),
        'playoff_rounds':summary(postseason),'week17_retries':summary(retries),'ui_dom':ui}


def main():
    global ROOT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',nargs='?',type=Path,default=ROOT)
    parser.add_argument('--seasons',type=int,choices=range(1,11),default=3)
    parser.add_argument('--modern-only',action='store_true')
    args = parser.parse_args(); ROOT = args.root.resolve()
    try:
        connection = socket.create_connection(('127.0.0.1',8768),timeout=.2)
    except OSError:
        pass
    else:
        connection.close(); raise RuntimeError('Port 8768 is already occupied')
    started = time.perf_counter()
    server = subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1',
        '--port','8768','--no-access-log'],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for _ in range(200):
            if server.poll() is not None: raise RuntimeError('Benchmark server exited')
            try:
                teams,_ = request('/api/teams'); break
            except OSError: time.sleep(.02)
        else: raise RuntimeError('Benchmark server did not become ready')
        startup = (time.perf_counter()-started)*1000
        report = {} if args.modern_only else legacy_benchmark(teams,startup)
        report['modern'] = modern_benchmark(args.seasons)
        print(json.dumps(report,indent=2))
    finally:
        server.terminate(); server.wait(timeout=10)


if __name__=='__main__':
    main()
