# Arcade League starter

Python owns the league rules and schedule generation. The browser layer only renders the interface and sends user choices to the API.

## Included

- 30 city-only teams in six groups
- player team selection that gives way to a team home screen
- team offense/defense ratings and a 38-player roster grouped by position, with depth order, minimum counts, and scouting ratings
- common and position-specific player attributes, including QB Clutch Factor, displayed in the roster Ratings view
- Ratings / Season Stats roster views with separate regular-season and playoff totals for every QB, RB, WR, TE, and K
- a dedicated Roster tab and a team-change flow with a keep-current-team option
- 17-game Python schedule generator
- 8 home/away group games
- 5 same-place games based on the prior season
- 4 remaining opponents from a rotating group
- five-season group rotation
- responsive schedule screen
- seven top tabs: Roster, Game Stats, Schedule, Standings, League Results, Playoff Race, and Playoffs
- one-click, week-by-week simulation
- deterministic fictional rosters and team ratings
- final score, team comparison, and player box scores
- player efficiency in regular-season and playoff box scores: NFL passer rating, completion percentage, passing yards/attempt, rushing yards/carry, and receiving yards/reception for all receivers
- kicking box scores with FG made/attempted, FG percentage, longest made FG in yards, extra points made/attempted, and kicking points, including overtime
- simplified overtime: most regulation ties resolve with a winning field goal; a small fraction remain tied
- overtime labels on your result and other league results
- season record that updates after every completed game
- final scores and W/L/T labels on every completed schedule card, with OT markers; your team's score is shown first
- a separate compact League Results section with the other 14 weekly scores
- one coherent league schedule: 15 games per week and no duplicate team appearances
- all six group standings recalculated after every simulated week
- a provisional 14-team playoff field: six group winners plus eight wildcards
- independent show/hide controls for League Results, Group Standings, and Playoff Race; collapsed panels keep updating between weeks, and choosing another team restores them to expanded
- a finalized playoff field after Week 17, with one-round-at-a-time postseason simulation
- original-seed reseeding each round, higher seeds hosting, and a neutral-site championship
- your playoff game and player box score separate from other playoff results
- no playoff ties, elimination/bye status, completed-round history, and a champion
- first-round byes for seeds 1 and 2
- tiebreakers in order: head-to-head, common-opponent record, point differential, points scored, deterministic random draw

Player scouting ratings are deterministic estimates out of 99. Team offense and defense determine scoring; QB/RB scouting ratings and QB experience shape passing volume.

Overtime is a lightweight game mechanic rather than a play-by-play NFL rules implementation. In 5% of regulation ties, overtime also ends tied; otherwise a weighted draw using team ratings and a small home advantage chooses the winning field goal. The field goal is included in the score and kicking statistics. Yardage and possession describe regulation play.

## Navigation

After choosing a team, use the tabs above the content to view one screen at a time. Team identity, ratings, regular-season record, and simulation controls remain above every view. Simulating a week updates all screens while keeping the selected tab, with the latest final score in the shared status line. Game Stats shows the most recent regular-season game; playoff games and box scores appear under Playoffs.

Tabs support Left/Right arrows (including wraparound), Home, and End. The tab bar scrolls horizontally on smaller screens. Views with no results explain when their data becomes available. After Week 17, choose **View playoffs** to load the field; advancing a playoff round opens the Playoffs tab. Switching tabs or canceling a team change preserves progress and collapsed groups. Starting another team resets the screens and returns to Schedule. Refreshing still resets the game.

## Roster

Each team starts with 38 fictional players. Expand or collapse each position group to inspect its players, depth order, and scouting ratings.

Player names are loaded from `app/data/first_names.txt` and `app/data/last_names.txt`, with one name per line. The downloaded Census lists contain 1,219 first names and 5,000 surnames (6,095,000 combinations). See [name data sources and editing instructions](app/data/README.md). The files are bundled locally; no runtime internet access is needed. Names are deterministic and unique within each team's roster; editing the lists can change display names, while stable player IDs, ratings, experience, and production remain unchanged.

Choose **Season Stats** inside Roster to inspect cumulative production, then select **Regular season** or **Playoffs**. QB rows show passing totals and efficiency; RB rows combine rushing and receiving; WR/TE rows show receiving; K rows show FG, extra-point, longest made FG, and kicking-point totals. Backups with no production show zero counts and unavailable rates (`—`). OL and defensive groups continue to show ratings and experience with a note that their production is not tracked.

Only completed games for the selected team count. Byes add no games; playoff totals stop changing after elimination, and teams that miss qualification keep zero playoff totals. The two competitions stay separate. Rates and passer rating are recalculated from cumulative counts, and longest FG is the maximum made distance. Switching roster views, competitions, or top tabs preserves collapsed position groups. Starting another team resets to Ratings and Regular season.

Team profiles return an empty `roster_stats` snapshot; weekly and playoff responses return the respective completed-game snapshot. Each snapshot has `games` (team games recorded) and `players` keyed by stable `player_id`. Box-score rows also include `player_id`, so identical player names cannot merge production. Aggregation rebuilds each snapshot rather than incrementing browser totals, making retries idempotent. Refreshing still resets progress.

| Position | Initial count | Minimum required |
| --- | ---: | ---: |
| QB | 2 | 1 |
| WR | 4 | 2 |
| TE | 2 | 1 |
| RB | 2 | 1 |
| OL | 8 | 5 |
| K | 2 | 1 |
| DL | 6 | 4 |
| LB | 5 | 3 |
| CB | 4 | 2 |
| S | 3 | 2 |
| **Total** | **38** | **22** |

Offense has 18 players (QB, WR, TE, RB, OL), defense has 18 (DL, LB, CB, S), and two kickers complete the roster.

The roster validator enforces these per-position minimums. The team profile API returns the rules and current counts alongside all players. Rosters have stable player IDs and names, and ratings are deterministic; defensive player scouting ratings use the team defense rating as their baseline.

This PR provides roster depth and inspection. Releases, signings, and lineup selection are not yet available. QB1 receives all passing stats and K1 receives kicking stats. RB1/RB2 split rushing production, and receiving production is shared across every WR, both TEs, and both RBs. Team offense and defense still determine scoring; QB/RB skill and QB experience now affect pass volume.

### Player attributes

Every player has **Football IQ, Speed, and Durability**, plus the specialties below. All attributes are integer scouting values from **1 to 99**, with higher values representing stronger ability. The Ratings view shows the applicable columns for each position and an attribute guide. Position groups use the full roster width; wide tables scroll horizontally on small screens.

| Position | Additional attributes |
| --- | --- |
| QB | Accuracy, Arm Strength, Clutch Factor |
| WR / TE | Catching, Strength |
| RB | Strength, Agility |
| OL | Strength, Blocking |
| DL / LB | Strength, Tackling |
| CB / S | Strength, Agility |
| K | Kick Accuracy, Kick Power |

Football IQ describes reads, positioning, and decision-making. Durability describes resistance to injury. Clutch Factor describes composure in high-pressure situations. These are currently scouting information for the future engine: they do not affect scoring, passing volume, injuries, or kicking outcomes in this PR. Existing scouting ratings and QB experience retain their current roles.

Attributes are generated independently per stable player ID and attribute key, with a deterministic offset of −18 to +18 around the existing scouting rating, clamped to 1–99. Players with the same overall rating can have different attribute profiles. These are initial fictional scouting values; the existing overall rating is not recalculated from them. Names, IDs, experience, current ratings, and gameplay results are preserved.

The team API includes an `attributes` object on each roster player, containing only applicable integer values. Each `roster_rules` entry includes the ordered attribute keys, labels, and descriptions for its position. Cached player attributes are immutable; API responses expose independent dictionaries.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

## Play online with Render

The FastAPI app serves both the game interface and API from one web service. The root `render.yaml` configures a free Render service, and `.python-version` selects Python 3.12 for hosting and CI.

After merging the deployment setup:

1. Sign in to [Render](https://dashboard.render.com/).
2. Choose **New → Blueprint**, connect GitHub, and select `Data-is-life/football-team-manager`. If the repository is private, grant Render access to this repository.
3. Use the `main` branch and the root `render.yaml`. Confirm that the web service uses the **Free** instance plan before creating the Blueprint.
4. Wait for the first deploy to become live, then open the service URL shown by Render.

Render builds with `python -m pip install -r requirements.txt` and starts the app with `python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT`. The `/api/teams` route is the health check.

### Try each merged PR

GitHub Actions runs the league tests on pull requests and pushes to `main`. Once you merge a PR and the checks on `main` pass, Render automatically deploys that commit to the same URL. Wait for Render to show the new deploy as live, then refresh the game.

Opening a PR alone does not update the main game URL. This setup does not create separate PR preview services.

### Demo behavior

- The free service sleeps after 15 minutes without traffic; the next visit can take about a minute to wake it.
- No database or account is required. The current team and week live in browser memory, so refreshing the page resets your progress.
- Weekly scores are deterministic for the team and season. Replaying the same season produces the same results.
- After Week 17, choose **View playoffs**, then simulate one round at a time.

See Render's [FastAPI guide](https://render.com/docs/deploy-fastapi), [free-tier limits](https://render.com/docs/free), and [automatic deploy settings](https://render.com/docs/deploys).

## Verify the schedule rules

```bash
python -m unittest discover -s tests -v
```

For UI interaction checks, install Node.js 24+ and the Python requirements above, then run:

```bash
npm ci
npm run test:ui
```

The UI suite starts a local FastAPI server on port 8767 and checks tab/keyboard navigation, empty states, full seasons and playoffs, box-score values, collapse state, failed-request retry, and team reset/cancel using jsdom. Node dependencies are only for development checks; Render still runs the Python app directly. These DOM checks do not verify visual layout.

## Aggregate game usage

### Kicking detail

K1 receives the kicking stats. Every field-goal attempt has a deterministic generated distance in yards, a made/missed flag, and an overtime flag in the API's `field_goal_attempts` list. Long FG is the longest **made** attempt, including a winning overtime FG; it is `null` (`—` in the UI) when no FG was made. FG percentage is also `null`/`—` when there were no attempts, and 0.0% when every attempt missed. Kicking points equal `3 × FGM + XPM`.

The aggregate engine assigns kick outcomes before generating distances. Distances are fictional detail rather than field-position-derived attempts: regulation attempts use a triangular 18–62-yard distribution centered on a 38-yard mode; winning overtime kicks use 18–55 yards with a 35-yard mode. A separate random stream preserves existing scores, usage, and postseason outcomes. Each touchdown still produces one made extra point, so XPM equals XPA; missed extra points and two-point attempts remain for a future engine update.

### Offensive usage

Efficiency statistics are calculated from each player's final box-score totals and displayed to one decimal place. Zero attempts or receptions produce `null` in the API and `—` in the interface. The API retains unrounded values. Passer rating uses the [NFL formula](https://www.profootballhof.com/news/nfl-s-passer-rating), with each of its four components clamped to 0–2.375; its displayed range is 0.0–158.3. These derived statistics do not affect scores or usage.

Scores and team yardage are generated first using the existing model. These final scores then shape the box score; this is not a live drive-by-drive simulation.

- Total offensive plays are bounded to 50–85. The central estimate is `65 + 0.15 × (combined score − 44) + 0.20 × (own offense − opposing defense)`, with random variation.
- Pass share starts at 55%. It changes by 0.5 percentage points per QB-minus-weighted-RB skill point, up to 15 percentage points for score margin, and 0.4 percentage points per QB experience year relative to six years. It is bounded to 30–75%.
- More experienced QBs get a modest trust-based increase in passing volume. Experience is deterministic, from 0–12 years, and appears in the roster. It does not change completion efficiency or turnover probability yet.
- Rush attempts equal total plays minus pass attempts. The existing completion-rate and yardage models remain.
- RB1 receives a random 50–90% share; RB2 receives the rest. Attempts, rushing yards, and rushing TDs use the same underlying share, rounded to whole counts while preserving team totals.
- WRs share 60% of receiving opportunities, TEs 22%, and RBs 18%. Random weights divide each WR/TE group's share across all its players. Both RBs use their rushing share within the RB receiving group.
- Possession uses relative clock weights of 35 per rush, 28 per completion, and 8 per incompletion, then normalizes both sides to 60 minutes. This remains regulation-equivalent possession even in overtime games.
- Total plays here means pass attempts plus rush attempts; sacks are displayed separately rather than added as another play category.

The separate usage random stream preserves existing scores and playoff outcomes for the same season while changing usage statistics.

## Playoff format

After Week 17, the final standings determine the six group winners and eight wildcards. Original seeds remain fixed through the postseason.

- Seeds 1 and 2 receive Wild Card byes.
- The Wild Card round pairs 3–14, 4–13, 5–12, 6–11, 7–10, and 8–9.
- The eight survivors are reseeded for four quarterfinals, then four survivors for two semifinals.
- In each round, the highest remaining seed plays the lowest, and the higher seed hosts.
- The two finalists play at a neutral site without the home advantage.
- Playoff overtime always selects a winner. Scoring uses the same simplified overtime mechanic as the regular season.
- Eliminated teams and teams that miss qualification can still follow every round to the champion.

Regular-season records stay separate from playoff results. Like the regular season, the postseason is deterministic and refreshing resets browser progress.

## Next build slice

Add meaningful pregame management decisions and saved progress. The leaderboard service for the wider arcade can remain separate and be shared by every future game.
