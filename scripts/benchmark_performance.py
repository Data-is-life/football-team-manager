"""Run a reproducible local HTTP + jsdom benchmark; no live service changes."""
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

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8768"


def request(path):
    start = time.perf_counter()
    with urllib.request.urlopen(BASE + path, timeout=30) as response:
        data = json.load(response)
    return data, (time.perf_counter() - start) * 1000


def summary(values):
    ordered = sorted(values)
    return {"n": len(values), "median_ms": round(statistics.median(values), 2),
            "p95_ms": round(ordered[math.ceil(len(values) * .95) - 1], 2)}


def main():
    try:
        connection = socket.create_connection(("127.0.0.1", 8768), timeout=.2)
    except OSError:
        pass
    else:
        connection.close()
        raise RuntimeError("Port 8768 is already occupied")
    started = time.perf_counter()
    server = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app",
        "--host", "127.0.0.1", "--port", "8768", "--no-access-log"], cwd=ROOT,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(200):
            if server.poll() is not None:
                raise RuntimeError("Benchmark server exited (is port 8768 occupied?)")
            try:
                teams, _ = request("/api/teams")
                break
            except OSError:
                time.sleep(.02)
        else:
            raise RuntimeError("Benchmark server did not become ready")
        startup = (time.perf_counter() - started) * 1000
        schedule, first_schedule = request("/api/schedule/seattle?season=1")
        profile, first_profile = request("/api/team/seattle?run_seed=1234")
        profile_times = [request("/api/team/seattle?run_seed=1234")[1] for _ in range(7)]
        weekly, postseason, season_totals = [], [], []
        fixtures = {"teams": teams, "schedule": schedule, "profile": profile}
        for seed in (1234, 5678, 9012):
            total = 0
            for week in range(1, 18):
                data, elapsed = request(f"/api/season/seattle/week/{week}?run_seed={seed}")
                weekly.append(elapsed)
                total += elapsed
                if seed == 1234 and week == 9:
                    fixtures["week"] = data
            season_totals.append(total)
            for number in range(5):
                _, elapsed = request(f"/api/playoffs/seattle/round/{number}?run_seed={seed}")
                postseason.append(elapsed)
        retries = [request("/api/season/seattle/week/17?run_seed=9012")[1] for _ in range(7)]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixtures.json"
            path.write_text(json.dumps(fixtures))
            ui = json.loads(subprocess.check_output(["node", str(Path(__file__).with_name("benchmark_ui.cjs")), str(path)], cwd=ROOT))
        print(json.dumps({"startup_to_ready_ms": round(startup, 2),
            "first_schedule_ms": round(first_schedule, 2), "first_profile_ms": round(first_profile, 2),
            "warm_profile": summary(profile_times), "fresh_run_weekly": summary(weekly),
            "regular_season_total": summary(season_totals), "playoff_rounds": summary(postseason),
            "week17_retries": summary(retries), "ui_dom": ui}, indent=2))
    finally:
        server.terminate()
        server.wait(timeout=10)


if __name__ == "__main__":
    main()
