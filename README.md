# Arcade League starter

Python owns the league rules and schedule generation. The browser layer only renders the interface and sends user choices to the API.

## Included

- 30 city-only teams in six groups
- player team selection that gives way to a team home screen
- team offense/defense ratings and a 35-player starting roster grouped by position, with depth order, minimum counts, and scouting ratings
- common and position-specific player attributes, including QB Clutch Factor, displayed in the roster Ratings view
- Ratings / Season Stats roster views with separate regular-season and playoff totals for every QB, RB, WR, TE, and K
- a dedicated Roster tab and a team-change flow with a keep-current-team option
- 17-game Python schedule generator
- 8 home/away group games
- 5 same-place games based on the prior season
- 4 remaining opponents from a rotating group
- five-season group rotation
- responsive schedule screen
- eight top tabs: Roster, Game Stats, Schedule, Standings, League Results, Playoff Race, Playoffs, and GM Records
- one-click, week-by-week simulation
- fresh fictional rosters and team ratings on each start, reproducible within one run
- final score, team comparison, and player box scores
- player efficiency in regular-season and playoff box scores: NFL passer rating, completion percentage, passing yards/attempt, rushing yards/carry, and receiving yards/reception for all receivers
- kicking box scores with FG made/attempted, FG percentage, longest made FG in yards, extra points made/attempted, and kicking points, including overtime
- simplified overtime: most regulation ties resolve with a winning field goal; a small fraction remain tied
- overtime labels on your result and other league results
- season record that updates after every completed game
- final scores and W/L/T labels on every completed schedule card, with OT markers; your team's score is shown first
- opponents' current regular-season records on every schedule card, starting at 0–0 and updating after each simulated week (including ties); completed and upcoming cards both reflect the latest week
- a separate compact League Results section with the other 14 weekly scores
- one coherent league schedule: 15 games per week and no duplicate team appearances
- all six group standings recalculated after every simulated week
- offense and defense ratings out of 99 for every team in Group Standings, matching the current run’s team profiles
- a provisional 14-team playoff field: six group winners plus eight wildcards
- League Results, Group Standings, and Playoff Race each use their own tab and show available content without hide/show buttons
- a finalized playoff field after Week 17, with one-round-at-a-time postseason simulation
- original-seed reseeding each round, higher seeds hosting, and a neutral-site championship
- your playoff game and player box score separate from other playoff results
- a horizontally scrolling playoff bracket with all four rounds, first-round byes, scores, and selected-team highlights
- no playoff ties, elimination/bye status, completed-round history, and a champion
- first-round byes for seeds 1 and 2
- tiebreakers in order: head-to-head, common-opponent record, point differential, points scored, deterministic random draw

Player current ratings are deterministic ability estimates out of 99. Team offense and defense determine scoring; QB/RB scouting ratings and QB experience shape passing volume.

Overtime is a lightweight game mechanic rather than a play-by-play NFL rules implementation. In 5% of regulation ties, overtime also ends tied; otherwise a weighted draw using team ratings and a small home advantage chooses the winning field goal. The field goal is included in the score and kicking statistics. Yardage and possession describe regulation play.

## Navigation

After choosing a team, use the tabs above the content to view one screen at a time. Team identity, ratings, regular-season record, and simulation controls remain above every view. Simulating a week updates all screens while keeping the selected tab, with the latest final score in the shared status line. Game Stats shows the most recent regular-season game; playoff games and box scores appear under Playoffs.

Tabs support Left/Right arrows (including wraparound), Home, and End. The tab bar scrolls horizontally on smaller screens. Views with no results explain when their data becomes available. After Week 17, choose **View playoffs** to load the field; advancing a playoff round opens the Playoffs tab. Switching tabs or canceling a team change preserves progress and collapsed roster groups. Starting another team resets the screens and returns to Schedule. Refreshing resumes the saved game.

## Roster

Click any team name in Group Standings to open its scouting roster in a separate dialog. Inspect players by position, including age, current rating, and potential rating, plus the team's offense and defense ratings. Close the dialog or press Escape to return to Standings. Browsing preserves your managed team, season progress, and roster settings. A failed load can be retried inside the dialog; browsing does not simulate games.

New careers start with 35 fictional players per team (lineup rules 15, save version 25). Existing 38-player careers retain their format, including future seasons and unfinished drafts: starting a new career is required for the smaller format. This avoids deleting retained veterans or draft picks and preserves completed results. Expand or collapse each position group to inspect its players, depth order, and current/potential ratings.

Both Ratings and Season Stats show each player's age in years. Initial ages are 21–36: a deterministic entry age of 21–24 plus the player's existing 0–12 years of experience. Ages stay fixed during a season and are regenerated for each new run. Under current career rules, age and experience increase once per offseason. Development and decline follow the positional curves below; retirement follows the rules described later. Existing saved seasons keep their original rules until their next season transition.

Player names are loaded from `app/data/first_names.txt` and `app/data/last_names.txt`, with one name per line. The downloaded Census lists contain 1,219 first names and 5,000 surnames (6,095,000 combinations). See [name data sources and editing instructions](app/data/README.md). The files are bundled locally; no runtime internet access is needed. Names are reproducible within a run and unique within each team's roster; editing the lists can change display names, while stable player IDs, ratings, experience, and production remain unchanged.

Choose **Season Stats** inside Roster to inspect cumulative production, then select **Regular season** or **Playoffs**. QB rows show passing totals and efficiency; RB rows combine rushing and receiving; WR/TE rows show receiving; K rows show FG, extra-point, longest made FG, and kicking-point totals. Backups with no production show zero counts and unavailable rates (`—`). Defenders show snaps, tackles, sacks, and interceptions. OL shows pass-blocking snaps, run-blocking snaps, and sacks allowed. All positions use Season Stats tables.

Defensive and line production is aggregate detail derived after the game result. Tackles assume one credit per non-scoring completion/rush plus each sack; sacks are included in tackles, and defensive interceptions exactly match the opponent's passing interceptions. This does not yet model assists, pressures, forced fumbles, missed tackles, or individual blocking grades.

Defense rotates through a 4-DL, 3-LB, 2-CB, 2-S unit. Snaps are shared using depth and current ratings, capped at one full game's snaps per player. Tackles/interceptions cannot exceed participation. Under legacy rules 1–4, five starting linemen (OL depths 1–5) receive all pass/run blocking snaps and sacks allowed; reserves remain at zero. Rules 5 use the OL rotation described below and charge sacks within allocated pass-blocking snaps, favoring lower-rated blockers. Defensive and line snaps include sacks, exclude kicking plays, and describe regulation-equivalent offensive activity, like the existing usage model.

New `defense` and `blocking` box-score rows include player IDs and feed the same season aggregation as offensive stats. An independent random stream generates the detail, preserving scores, offensive/kicking production, and playoff outcomes. Detailed attributes are retained internally for compatibility and do not affect the current engine.

Only completed games for the selected team count. Byes add no games; playoff totals stop changing after elimination, and teams that miss qualification keep zero playoff totals. The two competitions stay separate. Rates and passer rating are recalculated from cumulative counts, and longest FG is the maximum made distance. Switching roster views, competitions, or top tabs preserves collapsed position groups. Starting another team resets to Ratings and Regular season.

Team profiles return an empty `roster_stats` snapshot; weekly and playoff responses return the respective completed-game snapshot. Each snapshot has `games` (team games recorded) and `players` keyed by stable `player_id`. Box-score rows also include `player_id`, so identical player names cannot merge production. Aggregation rebuilds each snapshot rather than incrementing browser totals, making retries idempotent. Refreshing restores saved progress.

| Position | Initial count | Minimum required |
| --- | ---: | ---: |
| QB | 2 | 1 |
| WR | 4 | 2 |
| TE | 2 | 1 |
| RB | 2 | 1 |
| OL | 7 | 5 |
| K | 1 | 1 |
| DL | 6 | 4 |
| LB | 4 | 3 |
| CB | 4 | 2 |
| S | 3 | 2 |
| **Total** | **35** | **22** |

Offense has 17 players (QB, WR, TE, RB, OL), defense has 17 (DL, LB, CB, S), and one kicker completes the roster. The 22 position minimums are unchanged, leaving 13 reserves. These are initial targets; legal draft/cut choices can change the position mix. Legacy rules 1–10 keep their original 38-player targets.

The roster validator enforces these per-position minimums. The team profile API returns the rules and current counts alongside all players. Player IDs identify city/position/depth slots. Names and ratings are stable within a run; defensive player current ratings use the team defense rating as their baseline.

QB1 receives all passing stats and K1 receives kicking stats. RBs split rushing production according to the active playing-time rules (a lone RB receives all carries), and receiving production is shared across eligible WRs, TEs, and backs. Team offense/defense determine scoring; current QB/RB ability and QB experience affect passing volume.

### Basic player ratings

The Ratings view uses five columns: **Depth, Player, Age, Current, Potential**. Depth includes the position, such as QB1. Detailed attribute columns, the attribute guide, and the experience column are removed from the UI. Draft prospects and roster-cut management use the same Current/Potential pair.

Current is the ability rating used by roster decisions and simulation. Potential is a possible ceiling rather than a promise of improvement. Current career rules use position-specific growth/decline and hidden, ability-independent longevity, described below. The ceiling is initialized at the draft, reassessed once at rookie-season entry under rules 7, then held fixed during development, and equals current after the player enters decline. Kickers use separate seasonal form. Small arrows beside Current show the actual last-offseason change without adding another column.

Legacy career rules retain the earlier age-band display until upgrading at a season boundary. New careers use development rules immediately.

Player API payloads add `current_rating` and `potential_rating`. The existing `rating`, experience, and generated attribute data remain available for API/save compatibility and existing usage logic; attributes are no longer displayed and still do not affect gameplay. Save version 18 reconstructs the displayed ratings from seeded player state and offseason history.

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
- No database or account is required. Progress autosaves in browser local storage and resumes on refresh.
- Each successful new career gets a fresh random run seed, so weekly results and playoff outcomes can vary between runs. Within one run, every screen and retry uses the same results.
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

The 14 UI suites run with two workers by default, each with an isolated jsdom session and its own local FastAPI port (8767 and 8769–8781). They check tab/keyboard navigation, empty states, full seasons and playoffs, box-score values, roster collapse state, always-expanded league content, failed-request retry, team reset/cancel, save restoration, and multiple-season continuation using jsdom. Node dependencies are only for development checks; Render still runs the Python app directly. These DOM checks do not verify visual layout.

For sequential debugging or a machine with limited resources, use `npm run test:ui -- --workers=1`. Workers can be set from 1 to 4; the default stays at 2 for CI. Run only one full UI command at a time because suites use fixed ports. Each suite still runs all of its scenarios in sequence. The measured longest suite starts first; remaining suites fill the available worker slots. Failures retain their output and fail the overall command; other suites finish so their results remain visible. A five-minute per-suite timeout bounds hangs, and Linux/macOS cancellation terminates each suite's server process group too.

Use `npm run test:ui -- --report=ui-timings.json` for total and per-suite timings with results. `npm run test:runner` checks scheduling, failure propagation, discovery and timeout cleanup; CI runs it before the interaction suites. See [test timing measurements](docs/test-performance.md) for the before/after comparison. All existing interaction scenarios and Python checks remain enabled.

## Randomized runs

Standings reuse a bounded cache of immutable weekly scores keyed by season, week, run seed, prior-season group ranks, and finalized roster context, avoiding repeated simulation of completed weeks. See [performance measurements and benchmark instructions](docs/performance.md) for API/UI timings, startup limits, and correctness checks.

Starting a new career generates a random 32-bit run seed in the browser using `crypto.getRandomValues`. A new start gets a seed different from the current run, including when selecting the same team again. A failed load discards its candidate seed and preserves the active run; canceling a change also preserves it. Own-roster profiles, scouting dialogs, weeks, retries, standings, final tiebreak draws, and playoff rounds share one seed; results agree from either team's perspective. Late weekly responses from a previous run are ignored.

The team-profile, weekly, and playoff APIs accept `run_seed` from 0 through 4294967295 and echo it in the response. Standings/postseason caches include this value. Omitting it uses seed 0, preserving the previous deterministic API results for scripts and tests. Different seeds allow different champions but do not guarantee a different winner on every run.

Each run generates new team offense/defense ratings, names, player ratings, attributes, experience, and ages for all 30 teams. The initial generation inputs remain 72–88, player attributes stay 1–99, and roster counts/minimums remain unchanged. Current team ratings use the starter/bench formula below. Player IDs remain city/position/depth slot IDs; stats reset on each new start, and roster, standings, and score caches include the run seed. The schedule formula stays fixed. Attributes remain scouting information; team ratings and QB/RB skill retain their existing simulation roles. The browser save retains the seed to reproduce the same run after refresh.

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
- Under legacy rules 1–4, RB1 receives a random 50–90% share; RB2 receives the rest. Attempts, rushing yards, and rushing TDs use the same underlying share, rounded to whole counts while preserving team totals.
- WRs share 60% of receiving opportunities, TEs 22%, and RBs 18%. Random weights divide each WR/TE group's share across all its players. Both RBs use their rushing share within the RB receiving group.
- Possession uses relative clock weights of 35 per rush, 28 per completion, and 8 per incompletion, then normalizes both sides to 60 minutes. This remains regulation-equivalent possession even in overtime games.
- Total plays here means pass attempts plus rush attempts; sacks are displayed separately rather than added as another play category.

The separate usage random stream preserves existing scores and playoff outcomes for the same season while changing usage statistics.

## Playoff format

After Week 17, the final standings determine the six group winners and eight wildcards. Original seeds remain fixed through the postseason.

The Playoffs tab shows Wild Card, Quarterfinals, Semifinals, and Championship side by side. Scroll the bracket horizontally on smaller screens, or focus it to scroll with the keyboard. Completed rounds keep their scores and winner markers; the next round shows its actual matchups, while later rounds show placeholders until reseeding. The two Wild Card byes remain visible throughout the postseason. Your team retains its highlight and badge, including after elimination. Your latest-round game and player box score appear below the bracket.

Round arrows show tournament progression, rather than fixed game-to-game paths: opponents are reassigned by original seed after each round. The bracket does not reveal future results or change simulation rules.

- Seeds 1 and 2 receive Wild Card byes.
- The Wild Card round pairs 3–14, 4–13, 5–12, 6–11, 7–10, and 8–9.
- The eight survivors are reseeded for four quarterfinals, then four survivors for two semifinals.
- In each round, the highest remaining seed plays the lowest, and the higher seed hosts.
- The two finalists play at a neutral site without the home advantage.
- Playoff overtime always selects a winner. Scoring uses the same simplified overtime mechanic as the regular season.
- Eliminated teams and teams that miss qualification can still follow every round to the champion.

Regular-season records stay separate from playoff results. Like the regular season, postseason results are reproducible within the same run seed, and refreshing restores saved browser progress.

Your latest playoff outcome appears above the bracket: green congratulations after a win (including the championship), or a red sorry/elimination message after a loss. The loss message remains while you follow later rounds. Byes and missed qualification use neutral status text. Starting another season clears the outcome message.

## Next build slice

Plan the drive engine together, then add meaningful pregame management decisions. The leaderboard service for the wider arcade can remain separate and be shared by every future game.

## Saved progress

Your game autosaves after a successful team selection, next-season transition, simulated week, or playoff round (including revealing the playoff field). Reopening the game restores your team, randomized roster, completed schedule, standings, season stats, and playoff bracket. The next simulation continues from the saved point.

There is one save per browser and site address, using browser local storage; no account or cross-device sync is provided. Clearing site data removes it. Starting another team replaces it only after the new game loads successfully. If saving fails, the game displays a warning and can still be played in the open page. Failed simulations leave the previous save intact. Failed restores keep the save and offer Retry.

Saves store a versioned team/season/run-seed/progress checkpoint; the API reconstructs results deterministically rather than storing rendered HTML. Changing the simulation rules in a future release may require a save migration/version change. Unsupported or damaged saves show a message and are replaced only after a successful new-game start.

## Multiple seasons

After completing all four playoff rounds, complete the rookie draft. Under current rules, start training camp to apply development, then make final cuts to the career roster limits. Then choose **Continue to Season 2** (then Season 3, and so on). The same offseason steps apply whether your team wins, loses, or misses qualification. The API currently supports seasons 1–999; continuation stops at that limit.

Continuing retains your franchise, run seed, and finalized rosters for all 30 teams, including retained rookies and player cuts. Veterans age and gain experience once each offseason; current ability develops or declines by position and age. Attributes remain unchanged; retirements, free agency, and trades are separate future features. The new season has a fresh 17-game schedule, a new group rotation, a 0–0 record, and zero regular-season/playoff stats. Game results use the new season number, so they are not a replay of Season 1.

Same-place opponents use the previous season's actual final group ranks. The browser carries all 30 ranks into schedule, simulation, standings, and postseason requests as the optional JSON `prior_standings` query parameter. The API validates one rank from 1–5 per team/group and canonicalizes the mapping for bounded cache keys. Existing API callers that omit the mapping keep the original placeholder ranks; Season 1 also uses those placeholders. This avoids replaying every past season when restoring a later save.

**Franchise history** inside GM Records lists completed prior seasons: your regular-season record, playoff finish/record, and league champion. It is a summary archive; individual past-season box scores and individual player career totals are not retained. A failed season transition leaves the current game and saved checkpoint intact; retrying cannot append duplicate history. **Choose another team → Start new career** explicitly resets season, history, and seed instead of continuing the franchise.

Save version 10 includes prior ranks, history summaries with exact playoff records for newly completed seasons, draft choices, drops, past offseason decisions, lineup/rating rules, and the season development was enabled. Version 2 and 3 career/draft saves remain supported. Version 1 saves from the saved-progress PR still restore with identical first-season results and upgrade on the next successful save. Refreshing in later seasons restores the correct schedule, standings, season totals, and postseason without mixing seasons.

## Six-round rookie draft

After the league championship (including seasons where your team is eliminated or misses qualification), choose **Start rookie draft**. Drafting opens in the main app’s **Draft** tab, visible only during a playable offseason. **View roster** and **Back to draft** let you compare your team without a dialog or losing your place. **Back to schedule** returns to the normal schedule view. The draft is for the upcoming season and contains 200 rookies and six rounds of 30 picks: 180 total selections. Prospects have unique permanent player IDs, names, positions, ages 21–24, zero experience, current ratings 45–90, and potential ratings. Filter by position to compare prospects.

Non-playoff teams pick first, followed by teams eliminated in the Wild Card, Quarterfinals, Semifinals, and Championship. The champion picks last. Within each finish group, order is worst regular-season record, then lower point differential, fewer points scored, and a deterministic seeded draw. Every round uses the same order, without snaking or pick trades.

CPU teams select automatically up to your next turn. Their score balances prospect quality against current position quality, with a penalty for repeatedly drafting the same position. Your six picks are manual. After your sixth pick the remaining CPU selections complete automatically; all 30 teams receive six rookies. Selections are shown in a scrollable log and your team's picks are highlighted.

Each rookie is added without replacing a player: a full new-career offseason roster can grow from 35 to 41 (38 to 44 for legacy careers), before accounting for retirements. Your Roster includes the rookies, and scouting shows other teams' drafted players. Completed-season stats are preserved; rookies have zero production. Team ratings, depth leaders, and finished-season game outcomes do not change during the draft.

For current careers, start **Training camp** after the draft; development completes before final cuts. Then drop players directly from **Roster → Ratings**. **Manage roster** is a shortcut to this view. Next-season continuation unlocks when the roster is within its career limits, position minimums are satisfied, and any applicable salary-cap check passes. The draft is mandatory before every future season transition, including restored legacy careers. The versioned salary, contract and retirement rules below still apply; trades remain future work.

Draft choices autosave after each successful turn. Save version 16 stores the current draft round count and each past offseason's round count alongside prospect IDs, cuts and prior decisions; the API deterministically replays CPU decisions and validates that each chosen prospect was available at the user's actual pick. Reloads preserve the class, selection history, permanent IDs, and enlarged roster. Failed loads/picks preserve the last checkpoint and offer Retry; duplicate clicks cannot select twice. Versions 1 and 2 restore without a draft, and version 3 restores its saved draft; all upgrade on the next save. Starting a new career clears the draft. Drafts are available through the Season 998 offseason because the next season must fit the API's Season 999 limit.

`POST /api/draft/{team_id}` takes `season`, `run_seed`, optional `prior_standings`, `draft_rounds` (4 or 6, default 4 for legacy clients), and `manual_picks` (up to the declared round count). It returns the selection order, completed picks, remaining prospects, the next user pick, completion state, and the updated managed-team profile. This endpoint is stateless and does not store server-side progress.

## Offseason player cuts and roster carryover

Complete the six-round draft, then open **Roster → Ratings** (or choose **Manage roster** to jump there). Drop controls appear beside each player, together with age, current/potential ratings, rookie badges, and starter highlights. Each position heading shows its player count and minimum, and the roster displays its total against the career roster maximum. Choose Drop, then Confirm drop in the inline confirmation; Cancel leaves the save unchanged. There is no separate roster-management dialog. You can reduce a position to its minimum, but the next cut is disabled and the API rejects it too. For example, QB can go from two to one, but not from one to zero. All ten existing position minimums are preserved. New careers require 35–38 players during the regular season. Rules 11–12 retain their former 31-player maximum while an older draft is being replayed; legacy rules 1–10 retain their 38-player maximum. Rules 10 and later fill post-draft vacancies with weak replacements toward their initial roster targets.

Successful cuts autosave. Failed cuts leave the previous roster/checkpoint intact and can be retried. Once the roster is at or below the career roster limit, Continue to next season unlocks. CPU teams also cut to the career limit, removing the lowest-rated eligible player while protecting every minimum. Cuts are available in the post-draft offseason only; released players are not yet part of free agency and cannot be re-signed in this version.

All retained players are ordered by descending current rating within their position for the next season's depth chart (ties preserve prior depth, then permanent ID). IDs never change when depth changes. QB1 handles passing; RBs share rushing according to the active playing-time rules, or the lone RB receives all carries when only the minimum is retained. WR/TE participation and line/defensive stats use the actual retained roster. Cut players disappear from the next season's profiles and production; finished-game box scores remain historical records. Roster Season Stats shows only currently retained players, so after cuts it is not a complete archive of the finished team's player totals.

Under the current lineup rules, each position starts its highest-current-rated players. Offense/defense ratings are 80% average starter rating plus 20% average bench rating, rounded to the nearest integer. If a unit has no bench, its starter average is used for the full rating. Kickers are excluded from both units and K1 is the highest-rated kicker. This affects scoring, usage, overtime, standings ratings, and postseason; potential is not used. Older saved seasons keep their original rating formula until the next season so completed results and draft availability cannot be rerolled.

Save version 16 stores the managed team's completed draft choices, cuts, and each offseason's schedule context. The server replays those decisions to reconstruct all 30 rosters, rather than accepting arbitrary player attributes from the browser. Bounded caches include the immutable roster context so distinct rosters cannot share scores or standings accidentally. Later drafts start from the modified league; surviving rookies retain their IDs across further seasons and reloads. A failed next-season load preserves the completed offseason save.

`POST /api/career/{team_id}` supports profile, week, playoffs, draft, and cuts actions with the run seed, current season/prior ranks, and completed offseason decisions. Each past offseason must be in increasing year order, precede the current season, include a full draft (six picks, or four for a saved legacy draft) and legal drops, and finish at the versioned roster limit or fewer. Existing seed-only GET APIs remain available for their original deterministic worlds; the UI uses career requests after roster changes.

## Automatic starters and team strength

New careers automatically rank every position by current ability from the first roster load. The same ranking applies after drafts, cuts, and season rollover; ties preserve existing depth, then permanent ID. Roster rows highlight starters. The starter counts are the existing positional minimums: QB 1, WR 2, TE 1, RB 1, OL 5, K 1, DL 4, LB 3, CB 2, S 2. This is automatic selection; manual depth-chart overrides are not part of this slice.

Offense includes QB/WR/TE/RB/OL, defense includes DL/LB/CB/S. Each team's unit rating is `round(0.8 × starter average + 0.2 × bench average)` on current ratings only. An empty bench uses the starter average instead. Ratings, profiles, standings, games, scouting, and postseason share one immutable, versioned lineup context. The old seeded strength values remain only as initial player-generation inputs and for legacy seasons.

Save version 5 records the lineup rules for the active season and for each past offseason. Versions 1–4 restore under their exact old season rules, including in-progress drafts. Continuing into the next season activates highest-rated starters and the 80/20 formula, while past drafts replay under the rules they actually used. New careers use the updated rules immediately. The team header explains the active formula or the pending next-season upgrade. Legacy seed-only APIs default to lineup rules 1; `lineup_rules=2` selects automatic lineups without development; `lineup_rules=3` selects development without initial hierarchy, and `lineup_rules=4` selects initial hierarchy, and `lineup_rules=10` selects current rules in team/week/playoff endpoints and draft/career requests.

## Position-specific development and hidden longevity

Under career rules 3, 4, and 5, development happens once when entering a new season, across all 30 rosters. The upcoming season's age chooses the phase. Veterans gain one year of age and experience. Newly drafted players retain their listed rookie-season age and zero experience on entering their first season; they begin aging at the following transition.

These are deliberately simple game-design curves, not fitted estimates of NFL rating changes:

| Position | Develop through age | Decline from age | Steep decline from age | Annual decline | Annual steep decline |
| --- | ---: | ---: | ---: | --- | --- |
| QB | 27 | 34 | 37 | −2 to −4 | −4 to −6 |
| RB | 23 | 27 | 30 | −2 to −4 | −4 to −6 |
| WR | 25 | 30 | 33 | −1 to −2 | −4 to −6 |
| TE | 26 | 31 | 34 | −1 to −2 | −3 to −5 |
| OL | 26 | 32 | 35 | −1 to −2 | −3 to −5 |
| DL | 24 | 29 | 32 | −1 to −3 | −3 to −5 |
| LB | 24 | 28 | 31 | −1 to −3 | −3 to −5 |
| CB | 24 | 28 | 31 | −1 to −3 | −3 to −5 |
| S | 25 | 30 | 33 | −1 to −2 | −3 to −5 |

Development draws +1 to +4, limited by fixed potential. The prime plateau between development and decline draws −1 to +1, also limited by that ceiling. All current ratings stay within 1–99. Potential is initialized from current ability, position, age, and a seeded player-specific ceiling. Apart from the one-time rookie reassessment below, it does not increase simply because another offseason occurs. Entering the decline phase sets potential to current, and both fall together afterward.

Longevity is hidden in both the UI and player API payloads, reproducibly determined from run seed, permanent player ID, and position. It is independent of ability and potential: a mediocre journeyman can age well, and an elite player can age normally. Some players get a 1–2 year delay; rarer exceptional agers get a 3–4 year delay and initially gentler losses. That protection expires after four years beyond their delayed steep-decline threshold. QBs have more long-career outcomes. No rating bonus or GOAT label is granted by longevity.

Under legacy rules 3–8, kickers have a seeded seasonal form draw of −4 through +4 around a stable underlying baseline, rather than a cumulative random walk. Their potential display equals the current seasonal rating; form is separate from development. Changes between consecutive form draws can therefore exceed four points. Kicker age/experience still advance. Retirement is not modeled in this PR, and no players are automatically removed.

After each transition, depth charts and 80% starter/20% bench team ratings are recalculated. Profile, scouting, stats, CPU draft/cut logic, standings, and games use the resulting current abilities. Green/red inline arrows report actual rating gains/losses since the last offseason. Reloading, retrying a request, or simulating another week cannot age a player or reroll development.

Save version 6 records `developmentStart`. Older save versions preserve their current season and any pending draft, then adopt development at the next season: existing veterans age exactly once, without retroactively aging years previously played under frozen rules. Past offseasons replay under their original lineup rules. GET player/week/playoff APIs and POST draft/career requests accept rules 3 with season/development-start context; older rules 1 and 2 remain reproducible. The hidden state is reconstructed server-side and is not serialized into browser saves or exposed as player fields.

Players from the most recent draft have an **R** badge beside their names in roster ratings, Season Stats, scouting, and roster management. The badge appears when drafted, remains through their rookie season and reloads, and disappears in their second season or when the next draft begins. It follows permanent draft-class IDs, so undrafted initial players with zero experience are not marked.


## Initial starter and backup hierarchy

New careers use lineup rules 10 (save version 20). Every team's initial roster is ranked by current ability, then backups are lowered relative to the weakest starter at that position. Starter counts remain QB 1, WR 2, TE 1, RB 1, OL 5, K 1, DL 4, LB 3, CB 2, and S 2.

If the weakest starter is rated 70 or higher, each backup has a seeded ceiling 8–14 points below that starter. If the weakest starter is below 70, the ceiling is only 1–4 points lower, allowing closer competition on weak units. These are minimum separations: an already weaker backup stays weaker. Initial QB and K backups are also capped at 74. The adjustment never improves or lowers the selected starters, and preserves player identities, names, ages, experience, roster sizes, and position minimums. Backup attributes and potential are initialized from their adjusted ability.

This is a one-time initial-roster rule, not an ongoing limit. Future draft picks, development, aging, and automatic depth-chart changes can produce strong backups or new starters. Existing saved careers keep rules 1–3 and their original rosters, scores, and draft availability; they are not reshaped at their next season transition. Saved rules persist through the current season, draft, cuts and scouting. Future seasons adopt rules 10, while historical offseasons retain their original rules and existing initial rosters are never regenerated. The 80% starter/20% bench team-rating formula is unchanged, so reducing initial bench quality can lower new-career team ratings.


## Rebuild challenge

New careers start the selected city with a manageable rebuild: offense and defense each fall within 68–72 using the existing 80% starter/20% bench formula. Initial starters are 71–73, and reserves are 57–64 after hierarchy caps. Only the selected team is rebuilt. Earlier rules 4/5 rebuilds retain their original, weaker 52–69 starting generation and are not retroactively changed. Player identities, ages, experience, roster sizes, and position minimums are preserved. Other teams keep their normal initial rosters. A short first-season message explains the rebuilding job.

This is a one-time starting condition. Potential is initialized from the rebuilt abilities and existing age/position rules; young players can develop, and draft picks retain their normal ratings. The team is never weakened again during a season transition. Better rosters can earn wins and championships through the normal simulation; losses are not scripted.

Save version 8 stores `rebuildTeam`, the managed city at career creation. Team/week/playoff GET requests and draft/career POST requests carry the matching `rebuild_team` so profiles, scouting, ratings, standings, scores, CPU draft choices, cuts, and future seasons all use the same league. Immutable contexts and cache keys include this origin. Scouting another team never changes the managed team or starts another rebuild. Existing versions 1–7 restore with no rebuild origin and retain their original rosters and outcomes. Starting a new career intentionally creates a new rebuild.


## Rating-based rotations and youth development

New careers use lineup rules 10 and save version 20; playing-time rules are unchanged from rules 5. Existing saves keep their current-season playing-time model and draft estimates, then adopt rules 10 at their next season transition. Past offseasons replay under their saved rules, and existing roster generation is not reapplied.

QB1 handles all passing and K1 all kicking; youth development does not force their backups into games. Starting OL receive nearly all pass/run blocking snaps, with a small reserve role. RB carries favor the stronger starter while keeping a rotation. WR/TE targets combine their current ability with their assigned role; the existing 60% WR / 22% TE / 18% RB receiving mix remains. DL rotate most, LB next, with lighter CB/S rotations. Depth is automatically ranked by current rating as before. Potential does not influence playing time.

These are aggregate estimates rather than play-by-play substitutions. Position snap allocations conserve the configured on-field slots and never give a player more than a full game's snaps. Receiving targets sum to pass attempts, including intercepted throws; catches cannot exceed targets and receiving TDs cannot exceed catches. Rush yards and TDs require a carry. Line and defensive production is assigned within actual allocated participation, including sacks allowed within pass-blocking snaps.

Under-25 reserves outside QB/K normally receive a role floor of 5% of their unit's game snaps. Overstaffed positions share a bounded youth budget (at most 25% of their position's total participation is reserved as floors); integer rounding may reduce tiny roles. Ratings and starter status determine the rest of the allocation. A regular assigned role of at least 5% earns an eligible under-25 player +1 to their next offseason development draw, within their fixed potential and before position-specific decline. This is based on the season's modeled role, not accumulated snap counts, yards, or playoff appearances. QB/K receive no role bonus.

The season's role is captured when entering it and preserved through draft/cut replay. Drafting a replacement cannot remove an incumbent's already assigned development credit. New rookies get no credit for a season before joining the team; they first earn role credit after their rookie season. The next season captures fresh roles after aging and depth-chart changes. Repeat requests, reloads, and playoff games never award extra development. Hidden role state is reconstructed server-side, not trusted from browser saves.

Rules 5 boxes include participation, and Season Stats adds Snaps for all positions. Receiving adds Targets in game and season stats. Older rules retain their original payloads and table layouts. Scores remain outcome-first; this change allocates production after scoring rather than implementing the future drive engine.


## Mandatory offseason draft

After the league championship, **Start rookie draft** is the next step. The next-season button stays hidden until all six user picks and all 180 league picks are complete. A completed draft with more players than its limit shows a disabled **Roster limit: N** button; finish cuts in Roster to enable **Continue to Season N**. Position minimums remain enforced by the cut API.

Closing the draft, reloading midway, or a failed first draft load cannot enable a season skip. The transition handler independently requires a completed draft matching its saved round count, even if button visibility is changed. A failed next-season load preserves the completed draft/cuts and allows retry. At season 999 no draft or transition is offered.

Existing saves still load, including past seasons that skipped drafts. Their next transition must follow the current mandatory draft flow; past results are not replayed under new rules. The save format and simulation rules are unchanged. Players complete each required pick manually; Auto-draft is currently unavailable in the UI.


## Auto-draft (currently disabled in the UI)

The shipped UI hides and disables Auto-draft, and its browser action is guarded so it cannot accidentally skip your picks. Manual drafting, CPU selections, saved picks and retry behavior remain available. The implementation and API are retained for a possible future return, behind `AUTO_DRAFT_ENABLED = false` in `app/static/app.js`; no save-format change is required. Existing auto-drafted selections still replay normally.

When deliberately re-enabled, **Auto-draft remaining picks** fills only your remaining turns using the same current-quality, position-need, and repeat-position penalty as CPU teams. Earlier manual choices and all previous league picks are preserved. You can start with auto-draft or switch after one, two, or three manual picks.

The completed draft still adds six rookies without releasing anyone. Review the roster and make cuts to reach the career roster maximum before continuing. Auto-draft does not automatically cut players or advance the season.

Draft/career POST requests accept a strict boolean `auto_draft` flag. The response's existing `manual_picks` field contains all resolved user selections, including auto-picks; the browser saves those IDs normally. Reloading uses ordinary replay without another automated selection, so no save-format change is needed. Failed requests retain the previous checkpoint and Retry preserves whether the failed action was auto-drafting. Repeated identical requests produce identical picks, and duplicate UI clicks are blocked. Career auto-draft uses the actual retained rosters and original season/rules context; it cannot be requested as a cut, profile, week, or playoff action.


## Regular-season playoff qualification message

As soon as Week 17 finishes, a message above the tabs announces the selected team's final playoff qualification. Qualifiers receive a green congratulations message with their final seed, group-winner/wildcard route, final W–L–T record, and first-round bye when applicable. Teams outside the final field receive a red missed-playoffs message and their final record. The final standings determine the message using the same tiebreakers as the playoff field; earlier weeks do not announce qualification.

The regular-season message remains available while following the playoffs, independently of individual playoff win/loss messages. Reloads reconstruct it from the saved regular-season snapshot. Advancing to the next season or starting another career clears it. This UI change works with existing saves and makes no extra API requests or simulation changes.


## GM Records

The **GM Records** tab follows Playoffs and preserves the order of the existing seven tabs. It shows career regular-season W–L–T, playoff appearances, playoff wins/losses, and championships. Career totals include the current season's completed games. A playoff appearance counts when the final Week 17 field is known, even before revealing the bracket. Only completed playoff games count toward the playoff record; byes do not count as wins, and championships count only when your team wins the final.

The completed-season Franchise history table now lives in GM Records and includes each season's playoff record. Save version 10 stores exact playoff wins/losses when advancing to the next season. The completed season moves from live totals into history once, avoiding double counting. Reloads preserve totals, and starting a new career resets them. Opening the tab makes no requests and changes no saved progress.

Older saves remain supported. Their completed-season summaries store a finishing round but not bye information, so exact playoff wins cannot always be recovered. Those seasons display a bounded range rather than an invented result: for example, an old champion has 3–4 wins and no losses, and a quarterfinal exit has 0–1 wins and one loss. Career totals add those ranges and show an explanatory note when needed. Current seasons and newly completed summaries use exact results; older missing-playoff and Wild Card exits are already exact. No historical simulations are rerun or modified for this page.


## Manageable starting balance

New careers use lineup rules 10 and save version 20. The selected team's initial offense and defense are each within **70 ± 2**. Seeded starter ratings of 71–73 and reserves of 57–64 after the existing hierarchy caps guarantee the target under the current 80% starter/20% bench team-rating formula. QB2/K2 remain clearly weaker than QB1/K1. Ratings vary by player and run; other teams keep their normal rosters.

This replaces the much weaker starting balance for new careers without changing the playing-time model, potential rules, or offseason growth. The balance is applied once: later draft picks and development can raise the team beyond the starting target, while aging can lower it. Existing saves retain their original roster generation, draft availability, and results through future seasons. Start a new career to use the more manageable rebuild.


## GM contracts

New careers start with a four-year GM contract. A persistent contract panel explains the hiring expectations, shows the contract's final season and years remaining, and gives owner feedback. Missing the playoffs triggers a disappointed-owner warning and closer monitoring next season. Failing to reach the playoffs in **all four full contract seasons** ends the career, even if winning-record extensions would leave time on the contract. New late-start careers evaluate Seasons 2–5 and exclude the introductory season; older full-season careers retain their original Seasons 1–4 deadline.

Each evaluated contract season awards **only its highest extension**, added to the contract's end season: championship +5 years; otherwise playoff appearance +2; otherwise a winning record (wins greater than losses, including tie-containing records) +1; otherwise no extension. A .500 record earns nothing. A playoff extension is secured when the Week 17 field is set; winning the championship upgrades that season's award from two to five years, rather than stacking the awards. After the opening playoff requirement is satisfied, contract expiration ends the career.

Firing blocks further weekly/playoff simulation, drafting, cuts, and advancing seasons. Existing results, rosters, standings, scouting, and GM records remain available to view, and a new career can be started. The contract is derived from completed history plus the current season, so repeated renders, retries, and reloads cannot grant duplicate extensions. This is a browser career rule, not authentication or a server-side anti-cheat restriction.

Save version 12 records whether contracts apply. Existing saves from versions 1–11 stay playable without retroactive contracts or firing, and remain exempt after future autosaves and season transitions. Start a new career to use contracts. New careers now include the late-season introduction described below; existing saves retain their original full-season starting point and contract rules.


## Saved-career restoration performance

Restoration now warms a multi-season career's replay once before fetching its dependent weekly and playoff data. Standings reconstruction computes the exact same scores without generating independent player-stat streams for historical league games. Saved progress, roster-context cache isolation, draft replay and all gameplay rules remain unchanged. Existing saves benefit automatically; no new career is needed.

Local repeated benchmarks found empty-cache Season 4 restoration fell from 6.983s to 2.225s, and Season 8 from 11.557s to 3.911s. These are medians of three fresh-server trials per revision; warm restores were broadly similar. Server startup is measured separately, and these figures do not establish a Render cold-start speedup. See [the measurement report](benchmarks/README.md) for raw samples, reproducible checkpoints, API/render timings, limitations and correctness checks.


## Simulate the remaining season

The team header keeps **Simulate Week N** as the primary action. Open **More actions → Simulate Season** for bulk simulation. A modal confirmation shows the exact remaining game count and week range (including the one-game late-season start); Cancel is focused by default, and Cancel/Escape leave progress unchanged. Confirming simulates each remaining regular-season week through Week 17, using the same requests and results as manual weekly play. Every completed week renders normally and autosaves. Progress text shows the active week; **Stop after this week** finishes and saves the in-flight week before stopping. Reloading restores the last saved week and never resumes a batch automatically.

The More actions disclosure and confirmation close when the career changes and disappear outside regular-season play or while a batch runs. Confirmation rechecks the team, seed, season and completed week before starting; a stale or repeated confirmation cannot launch another batch.

Both simulation buttons are blocked while a week/batch is running; career replacement is blocked during a season batch. A failed or mismatched response stops the batch without committing that week; retry continues from the next unplayed week. Browser storage failures retain in-page progress and the existing save warning. Regular-season simulation stops before revealing or simulating playoffs, drafting, cuts, or next-season progression. Qualification/owner messages and GM firing rules still apply. Existing saved careers can use this immediately; no save-format change or new career is needed.


## Automatic starters and historical lineups

The best current-rated players start automatically. Roster highlighting and existing position-specific rotations remain, while manual starter selectors and reset/save buttons are removed. Highest-rated retained players are selected again after development and draft/cuts at each new season.

Saved week-effective manual choices remain available to replay completed games and past offseasons. Loading a career with an active manual preference adds an automatic reset at the next unplayed week/round; it does not overwrite the checkpoint until a successful autosave. Finished postseasons remain historical until the usual automatic new-season selection. The career API retains bounded, immutable lineup-event support for compatibility; UI controls cannot create new manual choices.

## Late-season career introduction

New careers take over **before Week 17**, with exactly one regular-season game remaining. Weeks 1–16 are generated using the same seeded rosters, ratings, schedule and simulation as the final game. They appear as inherited team history in Schedule, Standings and player Season Stats. Game Stats labels Week 16 as before your hiring, and a tenure note explains the starting point. Team ratings remain the existing 68–72 rebuild.

Your GM W–L–T starts at **0–0–0** and counts only Week 17 in the introductory regular season. If the team qualifies, you manage the playoffs and those appearances/results/championships count toward GM records. The inherited team record still determines playoff qualification, draft order and next season's schedule. Archived introductory history shows your managed record alongside the full team record.

Season 1 is an introduction: **no contract year is consumed, no extension is earned, and introductory playoff qualification does not satisfy the full-season contract requirement**. Four full contract seasons cover Seasons 2–5; reach the playoffs at least once during those seasons or be fired at the end of Season 5. The existing highest-reward extension and later expiry rules apply from Season 2 onward. The owner explains this grace period instead of judging you on inherited results.

The final regular-season game, playoffs, mandatory six-round draft and legal cuts keep their usual flow. Each new season defaults to the best current-rated starters. **Season 2 and every later season start at Week 1**, with the existing development and rookie class rules. No ratings, ages or statistics are rerolled on hiring, and drafts cannot be skipped.

Save version 14 stores `careerStartWeek` (17 for new late starts, 1 for older careers), plus the introductory history's one-game `gmRecord`. Versions 1–13 retain their existing progress, GM records and contract deadline after migration and future saves. Starting a new career is required to get the late-season introduction. Failed initialization preserves the previous career and save.


## Rookie booms, busts and potential arrows

Under legacy lineup rules 7, **when a retained drafted player enters Week 1 of their first rookie season**, one seeded assessment applies: **15% boom, 15% bust, 70% unchanged**. The probability is per player and independent of draft round, team or position; each class need not contain exact percentages. Draft cards and the entire draft/cut period retain their original estimates. Reloading, retrying, scouting and playing games never reroll the result. All league teams use the same rules.

For non-kickers, a boom adds **2–6 current** and **8–15 potential**, capped at 99. A bust lowers potential by **15–25** (floor 40), lowers current by **3–8**, and lowers current further if needed to fit the new ceiling. Current never exceeds potential. Thus 75 potential can become 85, and 95 can become 70; a high-current first-rounder can suffer a substantial current-rating drop. The normal 70% keep their draft ratings. Rookies retain their age, experience, identity and rookie badge on entry; normal development begins the following offseason. Attributes are regenerated from reassessed current ability.

Under legacy rules 7–8, kickers also receive one rookie boom/bust assessment, but keep **potential equal to current**, consistent with their existing seasonal-form model. Their reassessed current becomes the permanent form anchor; later seasons fluctuate by at most four points around that anchor. Hidden longevity and the position-specific aging curves are unchanged.

Ratings tables in your roster and read-only scouting show green **↑ +N** or red **↓ −N** potential arrows. Tooltips distinguish changes from draft estimates from later season-to-season changes, and accessible labels state the old and new potential. Zero changes have no arrow. Current-rating arrows remain separate. Rookie arrows last through the rookie season and are replaced by the next offseason's actual changes. Automatic lineups use reassessed current ability; explicit starter preferences remain your choices.

Existing careers preserve their current season and draft under their saved rules, then adopt rules 10 on the next season transition. Only rookies entering their first season at that transition are reassessed; already-playing rookies are never reassessed retroactively. Past offseason steps retain their original rules so old scores, draft order and availability remain reproducible. Save version 20 records current rules 10 and continues reading versions 1–19. Reassessment state is reconstructed server-side from permanent rookie IDs, the run seed and chronological offseason history, rather than trusted player data from the browser. No new career is needed for the next rookie class.


## Six-round drafts and saved-career compatibility

New drafts have **six rounds, 30 picks per round, 180 selections** from the existing 200-player class. Each team adds six rookies; a starting 35-player roster can reach **41 players**, requiring three cuts if nobody retired. A roster already at the 38-player maximum can reach **44 players**, requiring six legal cuts. Position minimums, draft order, prospect generation, rookie booms/busts and auto-pick policy are unchanged. Manual selection and auto-draft both require all six picks before cuts/continuation.

Save version 16 stores `draftRounds` and each completed career step's `draft_rounds`. Versions 1–15 remain readable. A legacy draft already started (including an empty saved choices array) stays at four rounds through cuts and reloads; its next offseason uses six. A career without a started draft uses six immediately. Past four-round drafts retain their original CPU picks, availability, player IDs and resulting rosters. No new career is required.

Draft and career APIs accept `draft_rounds: 4 | 6`; omission defaults to four for compatibility with existing API clients and historical career steps. The UI explicitly sends six for new drafts. Each past step must contain exactly its declared number of picks. Current draft format does not change weekly or playoff results.


## Your draft class recap

The main-app Draft view shows **Your draft class** below the prospect board: round, overall pick, player name, position, current rating and potential together, in selection order. It includes only your team's picks, updates after every manual or automatic selection, and supports six-round drafts and saved four-round drafts. Before your first selection it shows an empty-state prompt.

Use **Review draft** to revisit the recap before training camp starts, including after reloads. Legacy offseasons without a camp stage also allow review after cuts. Ratings are labeled **Draft-day ratings** and remain tied to the original picks, including a rookie you later release. This view does not reveal future rookie outcomes. Starting the next season or a new career clears this offseason's recap; historical draft browsing is outside this change. The league selection log remains available below. No new save fields or API requests are needed.


## Player development recap

After a successful new-season transition, a **Player development** window opens with the season-start roster's current and potential ratings before → after, signed changes, and rookie **Boom**/**Bust** labels. The summary counts current-rating improvements/declines, potential-only changes, unchanged players and rookie outcomes. Only changed players appear by default (including any boom/bust with capped zero changes); **Include unchanged players** shows everyone. If nobody changed, an empty-state message replaces the table.

Reopen **Development recap** from Roster during training camp and preseason, before the first game of its playing season. After the first game is successfully recorded, its button is hidden and an open recap closes; reloading or forced clicks cannot reopen that season’s recap. The next training camp provides its new recap. It compares veterans with the previous season and new rookies with draft-day estimates; kicker changes include seasonal form and, under rules 9, development/aging. Draft additions, later cuts, scouting and starter changes do not replace this season-start snapshot. Reload reconstructs the same recap from the already-fetched season profile, without reopening the window automatically. A later season replaces it; a new career clears it. Initial hiring has no prior-season recap. Saved development seasons without recorded potential changes explicitly show that information as unavailable rather than inventing a change.

This is a read-only presentation change: no extra API calls, save fields, growth rules, boom/bust probabilities or future rookie disclosures. Historical development browsing is outside this change.


## How to Play

All instructions and rules live in the **How to Play** tab. Ratings, development, roster limits/cuts, automatic starters, career timing/contracts, GM records, schedule, draft and playoff guidance are grouped under readable headings. Other screens have no ⓘ controls or hover/focus previews. Current ratings, record, status, owner updates, warnings and errors stay beside their actions.

The guide uses the original live rule elements, with unique IDs, so seed/season-specific guidance and legacy four/six-round drafts remain accurate. Opening it needs no API calls and does not save or change progress. The once-per-career welcome links to How to Play and retains its existing dismissal behavior. Keyboard navigation still covers all nine tabs.

## Actions follow the season phase

Regular-season simulation buttons appear only while games remain. During a full-season simulation, **Stop after this week** replaces both simulation choices; stopping or a failed request restores them at the last completed week. After Week 17, **View playoffs** is the next action. Only the next playoff-round simulation remains visible while the postseason is running, including for eliminated/nonqualifying teams following the league to the draft. It disappears after the championship.

The completed postseason offers **Start/Resume draft**, then **Review draft** and **Manage roster** once the draft is complete. **Continue to Season N** appears only after the roster reaches the career roster limit players; the existing draft summary and roster counts explain required cuts. Starters are selected automatically; no lineup editing actions are shown. A fired career has no simulation/draft/cut/continuation actions, while results, records and starting a new career remain available. Season 999 remains terminal after its postseason.

Visibility derives from the existing restored career state; there are no new save fields or gameplay changes. Existing request guards remain, with playoff actions additionally rejecting attempts to replay an earlier round or start before Week 17.


## League leaders (disabled for now)

League Leaders is hidden from the shipped interface to reduce clutter. Its frontend, dialog, backend aggregation, API and styles remain available for later restoration. To restore the existing entry point in Standings, set `LEAGUE_LEADERS_ENABLED = true` in `app/static/app.js`; startup/phase handling removes its initial hidden attributes. No user setting or new tab is added. The false setting also guards opening/retry handlers, so disabled code makes no leaders requests even if a stale control fires. The dedicated UI suite verifies the default disabled behavior and explicitly opts in to keep the retained functionality covered.

The behavior retained behind the flag is described below.

Open **Standings → League leaders** for the top 10 players in passing yards, rushing yards, receiving yards, sacks and defensive interceptions. Each list shows rank, player/position, city and total. Your players have a highlight and explicit Your team badge; your best positive-total player is shown separately with their league rank if outside the displayed 10. Only positive totals qualify. Equal totals share competition rank (1, 1, 3); stable team/player IDs order tied rows and keep each list to 10 players. Categories without production explain the empty state.

Only completed regular-season games through the current week count. Week 0 shows an empty prompt without requesting stats. Introductory careers include inherited regular-season production, consistent with Season Stats. Playoff games never enter these totals. During the draft/cut period, leaders retain the completed season's original player cohort. New seasons use actual retained league rosters and historical week-effective starter choices. No future games or rookie assessments are revealed.

The read-only dialog loads on demand via the `leaders` action on `POST /api/career/{team_id}`; it adds no leader work or data to weekly simulation/save payloads. A bounded server cache stores compact immutable totals for eight full career/week contexts. Closing or replacing a career ignores late responses; regular-week progress clears stale tables, and failures offer Retry without changing progress. No new tabs, save fields, scoring or development rules are introduced.


## Rookie preseason growth and revised outcomes (legacy rules 8)

New careers and the next season transition of existing careers use **20% boom, 5% bust, 75% normal assessment** for drafted rookies entering their first season. Probabilities are per retained rookie across all teams, not a guarantee of exact class proportions. The seeded outcome is revealed only at the draft/cuts → new-season transition. Draft estimates, ages, experience, identities and rookie badges stay unchanged until then.

After the assessment, non-kicker rookies receive a seeded **+1–2 current-rating training-camp gain**, capped at their assessed potential and 99. A player with less headroom gains only the available amount, possibly zero. Normal assessments leave potential unchanged but can now improve current ability. Booms retain their existing +2–6 assessment gain and +8–15 potential adjustment before camp. Busts retain their existing −3–8 assessment adjustment (or a larger cut to fit the lowered ceiling) and −15–25 potential adjustment before camp; generated busts remain net current-rating declines. Kickers use the new outcome probabilities but keep their existing equal-current/potential seasonal-form anchor, with no extra camp gain; rules 9 extend this with kicker potential as described below.

Current-rating arrows and the development recap show the **combined assessment plus camp delta** from draft-day ratings. Automatic starters are ranked after both changes. This happens once per rookie on entry, never on weekly play, retries, scouting or reload. Normal age/position-based growth resumes at the following offseason; no injury or in-season development mechanics are added.

Past offseasons retain their saved rules (1–7 included). Existing current seasons keep their ratings and original outcomes, then adopt rules 10 at their next rollover; already-entered rookies never receive retroactive camp growth or another reveal. Legacy rules 7 keep the original 15/15/70 outcomes without camp. Save version 18 reads versions 1–17, and no new career is required for the next rookie class.

### Kicker potential (rules 9)

Kickers now have a seeded potential ceiling in draft cards, roster ratings and development recaps. Young kickers gain 1–2 underlying ability per preseason through age 29, capped by potential. Prime ability stays stable; age decline normally begins at 37 and steepens at 40, with the existing hidden longevity exceptions. These are simple game balance curves. Seasonal form still varies by up to ±4 around the underlying ability without accumulating into permanent gains or losses. Current never exceeds potential; declining kickers display potential equal to current.

Rookie kickers now retain boom/bust potential changes and receive the same capped 1–2 preseason growth as other rookies. No ratings change during weekly play. New careers and future season transitions use rules 10/save version 20. Rules 1–8 replay unchanged; existing careers receive kicker ceilings only at their next actual season transition, preserving current-season saves and historical drafts. No extra save state or weekly request is required.

### Roster position after player releases

Offseason Drop confirmation and retry errors appear directly beneath the selected player in Ratings. Cancel returns focus to that player. A successful cut keeps the roster open and places focus on the next remaining player in the same position group, or the previous player for a last-row release. If that position has reached its minimum, its group heading becomes the keyboard destination. The retained row stays at the release location where page bounds allow, with horizontal table offsets and collapsed groups preserved. A delayed response does not switch tabs or move focus back to a hidden roster. No roster rules, saves or API requests change.

Regression checks simulate viewport geometry in jsdom for repeated cuts, last-row releases, minimum-roster focus, cancellation/retry, horizontal offsets and delayed responses after tab changes. They verify DOM/state and scroll calculations; they do not verify native browser layout or mobile rendering.

### Welcome and How to Play

Each successfully created career starts with a brief welcome guide. **Got it** dismisses it for that career; save version 19 stores `welcomeDismissed`, preserves it through reloads and season transitions, and resets it when a new career is successfully created. Versions 1–18 remain readable and skip the welcome guide so existing careers are not interrupted. Storage failures retain the usual visible save warning.

The **How to Play** tab is the sole home for detailed guidance. The gameplay screens keep current state, owner feedback and errors visible while removing the former contextual help buttons. The original live rule elements reside directly in the guide, including legacy-specific text and active draft-round counts.

DOM checks cover welcome persistence/reset, legacy saves, new-season dismissal retention, current help content without duplicate IDs or extra API calls, ninth-tab keyboard navigation, centralized rule placement and all prior UI flows. Native browser/mobile layout is not verified by jsdom.

### Contract details and season-end owner updates

GM Records contains the full contract status, owner feedback and contextual contract rules. The main screen shows a brief owner update only when your team's season finishes: missing the playoffs at the end of the regular season, elimination, or a completed championship. Qualified teams still playing do not get an early season-end update. Introductory seasons remain extension-free. **View GM Records** opens full details; **Dismiss** hides the summary for that season through reloads and later league rounds. The next season can show its own update. Firing remains a persistent, non-dismissible career-over notice with existing action guards intact.

Save version 19 gains an optional `ownerUpdateDismissed` season number (default 0 for existing saves); other career metadata and contract calculations are unchanged. New careers reset it, and season transitions preserve it without repeating old notices. No additional API requests are needed.


## Position- and rating-based retirement (rules 10)

New careers and future season transitions adopt lineup rules 10/save version 20; existing current seasons and in-progress drafts retain their saved rules. New retirement rules first announce departures during that season, then remove them from the active roster after the league postseason, before its draft. Completed scores, box scores, regular/playoff season stats, leaders and historical replay retain the players who actually played. Ratings/scouting show a compact yellow **\*** for players retiring after this season. Hover for its meaning, or focus and activate/tap the marker to expand the explanation; completed-season stats and the roster retirement recap identify retired players.

| Position | Base final playing age |
| --- | ---: |
| QB / K | 40 |
| RB / S | 33 |
| WR / TE / LB | 35 |
| CB | 34 |
| DL | 36 |
| OL | 38 |

Current rating below 60 brings retirement forward two years; above 80 delays it two years. Ratings 60–80 use the base age. The existing seeded hidden longevity trait can delay retirement another 1–4 years, independently of talent. Plans are deterministic from season-start age/current rating and the run seed; ratings do not change during weekly play. These are game-balance rules, informed by active-player longevity examples checked on 2026-11-02, rather than estimated NFL retirement averages.

The GM has six draft picks to address vacancies. CPU/auto-draft picks prioritize positions below their minimum. **After the draft finishes**, remaining minimum shortages receive generated players, then vacancies are filled toward the versioned position targets up to 35 for current careers (31 under rules 11–13, or 38 for legacy rules). Existing surplus picks are not discarded; if filling required minimums leaves more players than the limit, legal cuts remain mandatory. Generated replacements start at **40–55 current**, have potential capped at 60, are not draft rookies, and do not receive rookie boom/bust assessments. Under rules 10–12, legal cuts below the fill target receive another weak replacement; released IDs never reappear. Rules 13 reject any cut below 31; rules 14 reject any cut below the 35-player minimum and leave optional bench places unfilled. Draft quality and roster planning remain the GM's responsibility. CPU teams follow the same roster rules. No free-agency market or signing controls are added.

The ages follow the earlier design review of official NFL player profiles (Rodgers 42, Folk 41, Abdullah 33, Allen 34, Kelce 37, Williams 38, Campbell 40, Davis 37, Jones 33, Smith 37), which illustrate longevity exceptions rather than averages. Retirement runs under rules 10 and later; rules 1–9 payloads and historical draft classes remain reproducible. Save versions 1–25 remain readable.

Official profiles used in the retirement design review: [Rodgers](https://www.nfl.com/players/aaron-rodgers/), [Folk](https://www.nfl.com/players/nick-folk/), [Abdullah](https://www.nfl.com/players/ameer-abdullah/), [Allen](https://www.nfl.com/players/keenan-allen/), [Kelce](https://www.nfl.com/players/travis-kelce/), [Williams](https://www.nfl.com/players/trent-williams/), [Campbell](https://www.nfl.com/players/calais-campbell/), [Davis](https://www.nfl.com/players/demario-davis/), [Jones](https://www.nfl.com/players/jonathan-jones/), [Smith](https://www.nfl.com/players/harrison-smith/).

### Exact cuts remaining

After drafting, the draft summary and roster-management status show the exact number of players still needing to be dropped before continuing: **Drop 6 more players to continue**, **Drop 1 more player to continue**, or **No more cuts needed. Ready for next season.** The count uses the actual roster after retirements, drafting, replacements and saved cuts. It updates after successful drops and reloads; a failed cut leaves it unchanged. The count uses the career’s 31- or 38-player limit; position minimums and season-continuation guards remain enforced.

## Schedule list

The Schedule view uses a chronological, compact list instead of game cards. Each row keeps the week, home/away matchup, scheduling reason, latest opponent record and result (your score first, with overtime when applicable). Rows stack their details on narrow screens. Simulation, restored results and season transitions use the same list.


## Opponent strength (rules 12)

New careers seed the other 29 teams from an approximately normal strength distribution centered at **75**, with a standard deviation near **4** for combined offense/defense. A shared team-strength draw plus a smaller offensive/defensive skew gives teams distinct identities. Each unit's targets are centered and rounded to an exact 75 average; bounded 60–90 targets prevent extreme starting teams. This is a game-balance choice, not an NFL estimate.

These are actual player abilities, not display-only ratings or hidden win bonuses. Ability shifts preserve IDs, names, ages, experience and positional order; attributes are regenerated to match. Uniform shifts retain ability gaps, apart from ability bounds and a possible one-point reserve correction for half-even rounding. Kickers remain separate. The managed rebuilding team is unchanged at 70 ± 2 under the existing creation rules. Current/potential and age development continue normally.

Rules 12 introduced a one-time opponent recalibration for existing compact careers at the next season transition, after normal aging. Rules 14 retain that upgrade for careers that have not yet received it. Only opponents are recalibrated at that one-time upgrade; potential, baseline and development deltas move consistently with ability. Later seasons are not re-centered: draft decisions and development determine their strength. Old 38-player careers keep their legacy format and balance. Existing saves remain readable; new saves use version 24. GM contract rules and playoff qualification are unchanged—this improves the starting gap without guaranteeing success.

`python benchmarks/league_balance.py` compares eight paired seeded careers per version using six-round auto-drafts and lowest-rated legal cuts through Seasons 1–5. The full contract window is Seasons 2–5. `benchmarks/league-balance-results.json` records the sample, including initial opponent means, wins and playoff qualification; it is descriptive rather than a survival forecast.

Seeded check (eight careers per version, four full seasons each):

| Measure | Previous rules 11 | Balanced rules 12 |
| --- | ---: | ---: |
| Initial opponent mean | 80.68 | 75.00 |
| Mean wins per full season | 5.72 | 6.84 |
| Playoff appearances across 32 full seasons | 2 | 7 |
| Careers making playoffs within four full seasons | 2 of 8 | 5 of 8 |

The small sample uses a fixed auto-draft/cut policy, so it demonstrates behavior under that policy rather than estimating every player's chance of keeping the job.

## Previous total roster range (rules 13, retained for replay)

Under rules 13, careers began with **31 players**: 15 offense, 15 defense and one kicker. They must carry **31–38 players** into each regular season, in addition to the existing position minimums (22 required position slots). Draft picks and retirements may temporarily put the offseason roster outside that range. The draft remains mandatory.

After drafting, the GM can retain any legal roster between 31 and 38. Cut status reports the exact number above 38; continuation stays blocked while oversized or below 31. At 31, all Drop controls are disabled, and the API rejects a 31→30 release even when that position has spare players. Position minimums are checked independently. Successful cuts, retries and reloads retain their existing behavior. Payroll and salary caps are separate future PRs.

CPU teams retain legal depth up to 38 and cut the weakest eligible surplus players above the cap. Post-draft replacements fill required positions and bring short rosters toward **31**, not 38, so they do not fill optional bench capacity. The same bounds apply to history replay; an oversized or undersized completed offseason cannot be used to begin a later season.

Save version 23/rules 13 preserve older saves. Rules 12 careers with no draft started adopt the new limits on resume without changing players, completed results, stats or the stored checkpoint until the next action saves. Existing drafts and cuts replay under their recorded rules, then adopt rules 13 at the next season transition; rules 11 careers also upgrade at that transition. Older 38-player-format careers retain legacy behavior. Historical season decisions keep their original rules.

## Starting and minimum roster: 35 players (rules 14)

Every new-career team—including the user’s first season—starts with **35 players**: 17 offense, 17 defense and one kicker, using the position counts in the Roster table above. The regular-season total range is **35–38 players**. Individual position minimums remain unchanged; 35 is a total minimum, not a new set of position minimums.

After the mandatory draft, replacements fill required positions and bring short teams toward **35**, without filling the three optional places up to 38. This applies to CPU teams and the managed team. Retirements can temporarily leave an offseason roster below 35 before drafting finishes. Cuts cannot take a roster below 35 or violate a position minimum; rosters above 38 must be cut before the next season. Drop controls, remaining-cut counts and How to Play show these limits.

New saves use version 24/rules 14. Older current seasons and started drafts keep their original roster sizes and rules. Existing compact careers adopt the new floor at their next season transition: any short team receives deterministic low-rated replacements to reach 35, while legal 35–38-player rosters are retained. Existing player IDs are preserved; expansion replacement IDs have a separate namespace so released players cannot return. The expansion runs once, with potential/development metadata initialized for the new players. Older 38-player-format careers retain legacy behavior and their historical results. Prior sections describing rules 11–13 document their retained replay behavior; the current new-career limits are 35–38.

## Player salaries and signed terms (introduced in rules 15)

Roster Ratings and scouting include a compact **Salary / term** column. The next actual draft pick shows its pay before selection; the pick log and own-team draft recap retain the quoted pay and term after cuts and reloads (signed deals under older rules, provisional offers under rules 19). Unselected prospects have no signed contract: their available-list rank is not their draft slot. Money is stored in integer dollars and displayed in millions. Player contracts are separate from the GM employment contract.

Starting annual pay uses current rating and position: `base at rating 75 × (current / 75)²`, rounded half-up to $10,000 and floored at $1M. These are initial game-balance values, not real NFL salary data:

| Position | Annual base at current rating 75 |
| --- | ---: |
| QB | $8M |
| WR / DL / CB | $4.5M |
| OL | $4M |
| LB / S | $3.5M |
| RB / TE | $3M |
| K | $1.5M |

Starting terms use ordered categories: current 90+ is a franchise player (5 years); current below 70 gets 2 years regardless of age; the remaining players aged 28+ get 4 years, and the younger players get 3. These thresholds are the initial definitions of the discussed categories. Generated roster replacements always receive $1M annually for one year.

| Draft selection | Annual pay | Term |
| --- | ---: | ---: |
| Overall 1 | $5M | 4 years |
| Overall 2–5 | $4.5M | 4 years |
| Overall 6–15 | $4M | 4 years |
| Overall 16–30 | $3.5M | 4 years |
| Round 2 | $3M | 3 years |
| Round 3 | $2.5M | 3 years |
| Round 4 | $2M | 2 years |
| Round 5 | $1.5M | 2 years |
| Round 6 | $1M | 2 years |

Rookie terms begin in the first playing season, not the preceding draft offseason. Salary, signing year and original term remain fixed through development, booms/busts, depth changes and replay. Remaining years decrease with the season number. At term end the UI now shows **Contract expired**. Rules 15–19 retain the last agreed salary and roster place; rules 20 add explicit own-player re-signing after camp, described below. Free agency remains separate work.

Rules 15 preserve the original salary-only behavior. Rules 16 add the cap/floor described below. Rules 17 add annual schedule growth as described below; salary-aware drafting remains future work. The initial fixed pay schedule must remain reproducible when later salary-rule versions are introduced; signed deals must never be repriced by those later changes.

Rules 15 introduced save version 25. Existing compact careers keep their current season/draft rules and adopt salary display at the next season transition. Replay reconstructs original veteran deals and exact historical rookie selection pay, including CPU picks; salary fields are hidden in older-rule payloads. No player-statistics or game-outcome formula changes are introduced. Existing saves remain readable and historical rules are preserved.

Initial-scale sanity check: seeds 1–20 produced 580 opponent-team starting rosters (35 players, Seattle excluded as the managed team). Listed annual salaries averaged $137.99M, ranging from $95.99M to $188.60M. No cap filter or enforcement was applied. This is a starting calibration sample for the following cap PR, not a guarantee about all generated teams.


## Salary cap and payroll floor (rules 16; save version 26)

The team salary cap is **$200M**, with a relevant **$160M (80%) payroll floor**. Roster shows current payroll, cap space or the exact amount over cap, and a below-floor warning. The floor does **not** block play while free agency is unavailable. Rules 16 keep both amounts fixed; rules 17 add annual growth.

Every retained player's full annual salary counts, including upcoming rookies and expired-contract contracts. Unselected prospects and retired/released players do not count. Development, age, potential, and a rules upgrade never reprice an existing deal. The draft is allowed to exceed the cap temporarily; after the draft, roster size **35–38**, all position minimums, and payroll **at or below $200M under rules 16** (the upcoming season’s cap under rules 17) are required before continuing. Both the UI and server-side history replay enforce finalization, so a disabled button is not the sole check. Payrolls exactly at cap pass; a single dollar over fails. There is no payroll-floor top-up or automatic increase to existing contracts.

Releases clear the full annual salary, with no dead money or guarantees at this stage. While over cap, a release that leaves a required position or total-roster vacancy is an atomic release plus a weak **$1M, one-year replacement**. The resulting roster always retains minimums. This also allows rebuilding cap space at the 35-player floor; repeated releases cannot recreate an already dropped replacement ID. At or below cap, ordinary drop protections remain unchanged. CPU teams first trim excess roster size by ability, then clear excess payroll by releasing the lowest current ability per salary dollar, with deterministic tie-breaks and the same replacement/minimum rules. They do not spend up to the floor or select draft prospects based on salary yet.

Rules 16 introduced save version 26. A rules-15 saved career with no active draft gets cap accounting on restoration without changing its roster, ratings, already played games or checkpoint until the next successful save. An existing draft/cut session retains rules 15 until the following season. Other older compact saves adopt rules 16 at the next season transition. Completed legacy offseasons and currently playable inherited/legacy seasons are grandfathered: no retroactive cap cuts, forced salary changes, or blocked restoration. Enforcement starts when finalizing an offseason actually played with rules 16. Historical rules stay on every saved step, preserving deterministic old cuts, CPU decisions and draft slots. The next cap-enabled offseason requires compliance.


## Annual cap and new-contract pay growth (rules 17; save version 27)

New careers increase the cap and new-contract salary schedules **5% each season** from the prior rounded year's amount. The calendar date does not affect a career. All calculations use integer dollars and round half up; no binary floating-point compounding is used.

| Playing season | Cap | Payroll floor | New minimum salary |
| --- | ---: | ---: | ---: |
| 1 | $200M | $160M | $1.00M/year |
| 2 | $210M | $168M | $1.05M/year |
| 3 | $221M | $177M | $1.10M/year |
| 4 | $232M | $186M | $1.16M/year |
| 5 | $244M | $195M | $1.22M/year |

Round each new cap to the nearest **$1M**, then calculate **80% of that rounded cap** and round the floor to the nearest $1M. The floor continues to warn only. Minimum salary and **each rookie pick/round pay bracket independently** increase 5%, rounding to **$10,000 ($0.01M)** each year. For example, a $4.50M rookie bracket becomes $4.73M, and $3.50M becomes $3.68M, in Season 2. The base salaries and contract lengths remain documented above.

**Signed contracts never inflate.** A retained deal can remain below a later season's minimum. Starting salaries stay on their original deal; existing rookies, veterans, one-year replacements, and expired-contract players are not topped up or silently re-signed. Newly generated replacements use the minimum for their actual signing/playing season. Position base salaries for veteran negotiations are not being inflated or added here; free-agency negotiation is separate work.

Drafts following Season 1 sign players for **Season 2**: the #1 pick receives **$5.25M/year for four years**, and a sixth-rounder receives **$1.05M/year for two years**. During draft/cuts, the payroll status, manual/auto picks, previews, replacement pay, CPU decisions, continuation gate and server replay all use the **upcoming playing season's** cap and pay schedule. On rollover, that same cap becomes the active season cap; the draft itself does not consume a contract year. Roster's concise payroll line identifies its budget season. How to Play contains the detailed growth rules.

New careers use rules 17/save version 27. Rules-15/16 saves with no active draft adopt growth accounting on restore, without rewriting the saved checkpoint until a successful action. This changes accounting only: existing contracts, roster, ratings and completed games remain unchanged. The schedule is indexed by career season (a Season 3 upgrade uses a $221M cap), not years since upgrading. An unfinished older draft/cut session retains its original fixed pay/cap decisions, then adopts growth at the next season boundary. Historical rules 15/16 stay attached to completed offseasons, ensuring old pay, releases, replacement IDs and CPU decisions replay exactly. Older pre-salary compact career migrations still reconstruct their original fixed deals before growth is applied to new contracts. Legacy 38-player careers retain their prior rules.


## Draft workspace and mobile controls

Draft is an offseason-only main-app tab, reached through **Start/Resume/Review draft** or the tab itself. The regular-season tab row retains its existing nine views. The active prospect board comes before your draft recap; the optional full-league selections log starts collapsed. You can switch to any normal view while drafting, use **View roster**, and return with **Back to draft** beside the roster controls. Viewing or reopening an already loaded draft does not record another pick or make another draft request.

After a **successful manual pick or auto-draft**, the prospect list resets both scroll axes to the top and receives keyboard focus. Completing the draft focuses the completion heading instead. The current position filter remains selected. If you switched to Roster while a request was running, completion updates the data without changing your tab, focus or page scroll; the list resets when you return to Draft. Failed picks preserve the checkpoint and list position and focus Retry without scrolling; retry uses the original pending player/auto action, preserving duplicate-click protection and successful picks.

The position filter also survives navigation and reload as an optional validated `draftPosition` UI preference in the existing save format. Older saves default to All positions. Filter changes autosave only after a draft exists; a new career or season clears it. Draft IDs, selection order, class, CPU choices, game rules and API requests are unchanged.

At widths up to 640px, each prospect uses a compact labeled layout with a full-width, 48px-minimum Draft button, wrapped player names, and visible rank/position/age/current/potential. The filter and auto-draft controls stack at full width; the position select uses 16px text to avoid focus zoom on mobile. Wider screens retain the comparison table. Both layouts share the same table rows/buttons and explicit table semantics, so there are no duplicate touch/keyboard actions. The prospect region is keyboard focusable, and tab arrow navigation skips the hidden Draft tab outside the offseason. Empty position filters show an explicit message.


## Training camp before final cuts (rules 18; save version 28)

The current offseason has an explicit checkpoint: **season ends → complete draft → start training camp → review development and make final cuts → continue to the next season**. Completing the draft alone does not enable cuts or next-season continuation. The Start training camp action appears only after the draft is complete. Camp opens Roster and the development recap; its status identifies the upcoming playing season. The same 35–38 total, position minimums and upcoming salary-cap constraints still apply to finalization.

Camp develops **the full post-draft league roster before any final cuts**, including veteran aging, positional growth/decline, kicker form, rookie reassessment and preseason gains. The GM can inspect current/potential ratings after those changes before selecting releases. CPU teams also choose their cuts from developed rosters. Capturing final playing-time shares after cuts keeps the next year's rotation-based development tied to the actual retained lineup. Draft-day recap values and picks remain immutable; finished-season scores, stats, playoff results and GM records keep using that completed season's context.

Camp is reconstructed from the immutable pre-camp season/draft state. Retrying, reloading, inspecting another team's camp roster, or releasing additional players yields the same ratings, ages, potential and rookie outcomes. The next-season transition receives that already-developed roster and does **not** apply another development pass. Camp's full development roster remains available in the recap while making cuts; regular-season recaps retain the existing final-roster behavior. The transition no longer reopens the development dialog after it was reviewed in camp. Failed camp requests leave the checkpoint unchanged and may be retried with the same button; duplicate clicks issue one request. Initial retirement removals remain at the draft boundary, and players newly flagged for next year's retirement are not shown as already retired during camp.

The save adds an optional trainingCamp checkpoint to version 28. Older rules-17 careers with **no current cuts** can adopt rules 18 on restore, including an in-progress draft: no picks or pre-camp ratings change. Saves that already made cuts retain their old offseason order and adopt rules 18 at rollover. Older salary-era mid-draft rules remain on their old flow; completed history steps keep their original versions. Legacy 38-player careers retain their old order. Restore reads without overwriting a checkpoint; malformed camp/cut combinations are rejected and preserved for recovery.

POST /api/career/{team_id} adds the camp action. Rules-18 cuts require a started-camp flag, and the camp action requires a completed draft. Server-side career replay always applies camp development before final cuts and validates the finalized roster, so UI button state is not the sole enforcement. The camp flag is cleared when the next season begins; history version 18 reconstructs the completed camp without client-supplied ratings. The pre-cut camp context is cached immutably to avoid rerunning league development for each release.

Rules 18 retained the earlier draft-slot signing policy. Rules 19 below introduce provisional camp offers; rules 20 below add own-player re-signing, while free agency remains separate work. Draft navigation is now hidden once camp starts, as described below. Development recap access ends after the first successfully recorded game of its playing season, as described above.


## Provisional rookies and signing after camp (rules 19; save version 29)

Drafting a rookie reserves that player's rights and the expected slot-based deal, without creating a signed contract. During the draft, training camp and final cuts, Roster/scouting, draft previews, pick logs and the immutable draft recap label those terms **Provisional**. Proposals show a planned first playing season and the full term, with no signed year or remaining-contract countdown. Training, booms/busts and rating changes do not reprice the quoted deal.

**Only rookies retained when continuing past training camp into the next season sign.** Server-side history finalization first checks roster limits, position minimums and the cap, then signs retained rookies for all 30 teams. The signed deal starts in that upcoming playing season, with the full 4/3/2-year term for its original round; camp does not consume a year. Dropped rookies have no signed deal, no dead money and no future charge. The recap still shows the original draft-day proposal, even for a released rookie; it is not a contract ledger. A free-agent pool or signing market for released rookies is not introduced here.

Rookie offers remain **cap holds** during camp: cap usage equals signed annual payroll plus retained rookie holds. Roster shows the signed/hold split when holds exist. This keeps the projected cap limit visible and prevents an unsigned roster from bypassing finalization checks. Releasing a rookie removes their hold; any weak minimum-salary replacement still adds its ordinary existing contract. Unsigned holds do not satisfy the payroll floor, which continues to warn only. Signing retained rookies converts holds to signed payroll without changing total cap usage or cap space. CPU cuts use the same holds and projected cap check. Existing signed contracts, expired-contract players and annual cap/new-pay schedules stay unchanged.

Internally, an unsigned rookie has an immutable offer and **no Player.contract**. The public payload has contract_offer with provisional status, annual pay, term, round, pick and starts_season. Actual signed players use the existing contract payload. Financial terms are reconstructed on the server from recorded draft slots, season and historical rules; save version 29 stores no client-authored salary/offer values. Reloading or retrying draft/camp/cuts cannot activate a proposal. Valid next-season replay signs each retained offer idempotently without repeating development.

New careers use rules 19. Older salary-era saves with **no active draft** adopt the new rules for future classes on restore without rewriting the checkpoint until a successful action. An existing rules-18 draft or camp keeps its already-signed rookie deals and rules until rollover; those deals are never converted into proposals or repriced. Rules-17 drafts with no cuts can still adopt the rules-18 training-camp flow, preserving their signed deals, and later adopt rules 19 at rollover. Completed historical drafts keep their recorded rules and original signings. Legacy 38-player careers remain on their original flow.


## Draft navigation by season phase

Draft navigation is available after the championship and before training camp. Starting camp hides **Back to draft/Open draft**, the **Draft** tab and **Review draft** action. They remain hidden during camp, final cuts and regular-season play, including restored camp saves. Draft navigation becomes available again in the next offseason before camp starts. Phase checks also reject programmatic/forced clicks without fetching or changing the checkpoint. Draft picks, recap data, filters, roster cuts and camp progress remain saved; this is a navigation change with no gameplay or save-format change.


Recap visibility is derived from camp/season/week state without a new saved flag. A failed first-game request leaves recap access available. Hiding the recap does not remove player rating/potential arrows, change development results or alter saved progress. Older saved seasons with games already played follow the same visibility rule; a restored camp still exposes the upcoming season’s recap even though the preceding season has finished.


## Re-signing your players after camp (rules 20; save version 30)

The roster now says **Contract expired**, replacing Renewal due. Once training-camp development finishes, expired players have a **Re-sign** button beside Drop in Roster → Ratings. Review the quoted annual salary, term and first playing season in the inline confirmation; Cancel changes nothing. Confirming replaces only that expired contract, updates payroll immediately and removes that player's renewal action. Active deals and provisional rookies cannot be re-signed. Retired/released players and other teams' players are not eligible.

For rules 20 and earlier, offers use the established position/current-rating formula and current season minimum, after camp development: `position base at 75 × (current / 75)²`, rounded half up to $10,000. Position bases remain the fixed game-balance values documented above; only the new-contract minimum grows annually. Potential does not affect price. These are fixed offers, with the previously agreed terms:

| Current player category | New term |
| --- | ---: |
| Current rating 90+ (franchise) | 5 years |
| Current rating below 70 | 2 years |
| Remaining players age 28+ | 4 years |
| Remaining younger players | 3 years |

Former draft picks and generated replacements use these renewal categories once their original deal expires; a re-signed low-rated filler receives two years rather than another automatic one-year filler deal. The new contract starts in the upcoming playing season with its full term. An active signed salary never changes through aging, inflation, camp or reload. Earlier renewal, term selection, negotiation, desired-length premiums, free-agent markets, signing bonuses and dead money are outside this PR.

**Re-sign or release every retained expired player before continuing to the next season.** The roster status reports the unresolved count alongside cut/cap requirements. Until a decision, an expired player’s previous annual amount remains a temporary **expired-contract cap hold**, shown separately from signed payroll and rookie holds. It is a planning reservation, not a new signed deal, and does not satisfy the payroll floor. Re-signing replaces that hold with the new signed salary; releasing clears it. Re-signing may temporarily put camp payroll above the cap; legal final cuts must restore cap compliance. The same 35–38 roster and position minimums apply. The payroll floor remains a warning while free agency is unavailable. CPU teams re-sign their expired players using the same quotes, then trim their developed roster and clear excess payroll using the existing cap-release/minimum-replacement rules.

Cuts and re-signings are stored as bounded, ordered roster decisions, alongside the existing dropped IDs. Order matters: a renewal changes cap usage, which can affect whether a later cut creates a minimum replacement. Reload, retry and historical replay apply the same sequence from immutable camp results. The server recomputes all prices/terms; no quoted salary is trusted from the browser. Duplicate re-signings, active/provisional/foreign players, invalid phases and inconsistent drop/action histories are rejected. Released players carry no remaining salary charge under the existing simplified contract rules, including a player released after a renewal.

New careers use rules 20. Rules-19 careers can adopt these contract decisions on restore, including camp: existing dropped IDs become ordered drop decisions, while all previous signed deals and rookie holds retain their amounts/terms. The old checkpoint is not overwritten just by reading it. Completed history steps retain their own versions, so old seasons are never retroactively renewed or blocked. Earlier signed draft/camp formats retain their current transaction rules until rollover. Legacy 38-player careers remain on their prior flow. Re-signing controls remain hidden during regular-season play and before camp; historical stats, draft-day recap values and camp development are unchanged.


### NFL-informed veteran market (rules 21)

New veteran agreements use a steeper current-ability curve and positional market values. At the initial $200M cap:

| Position | 75 current | 80 current | 90 current | 99 current |
| --- | ---: | ---: | ---: | ---: |
| QB | $12M | $20M | $34M | $42M |
| WR | $6.5M | $10M | $20M | $28M |
| TE | $4.5M | $8M | $12M | $14M |
| RB | $4M | $7M | $12M | $15M |
| OL | $5.5M | $8M | $14M | $19M |
| DL | $6.5M | $10M | $20M | $30M |
| LB | $4.5M | $6M | $11M | $14M |
| CB | $6M | $9M | $16M | $22M |
| S | $4.5M | $6M | $11M | $14M |
| K | $1.8M | $2.5M | $4M | $4.6M |

Intermediate ratings interpolate linearly; lower-rated depth follows cheaper anchors in `MARKET_SALARIES`. Prices use current ability, not potential, and do not depend on the depth chart. Scale the resulting base amount by **signing-season cap / $200M**, round half up to $10,000, then apply that season's minimum. The term categories remain unchanged. For example, an 80-current TE asks $8M in Season 1 and $8.84M in Season 3 ($221M cap); an 80-current QB asks $20M and $22.1M respectively. A signed deal stays flat for its full term.

Research checked November 6, 2026: the [NFL's 2026 cap is $301.2M](https://operations.nfl.com/calendar-events/nfl-free-agency/nfl-salary-cap). Positional average-per-year benchmarks come from Over The Cap's [QB](https://overthecap.com/position/quarterback), [WR](https://overthecap.com/position/wide-receiver), [TE](https://overthecap.com/position/tight-end), [RB](https://overthecap.com/position/running-back), [LT](https://overthecap.com/position/left-tackle), [C](https://overthecap.com/position/center), [edge](https://overthecap.com/position/edge-rusher), [LB](https://overthecap.com/position/linebacker), [CB](https://overthecap.com/position/cornerback), [S](https://overthecap.com/position/safety), and [K](https://overthecap.com/position/kicker) tables. These are **game-calibrated rating anchors informed by NFL APY/cap proportions**, not real-player rating equivalents or a reproduction of individual NFL contracts. OL blends line roles; DL includes premium pass rushers; LB represents off-ball pay. APY differs from real annual cap hits because NFL contracts have bonus/restructure accounting; this game retains flat annual cap charges and its $200M starting cap.

**Existing contracts remain fixed**, including the deals inherited at career creation. Those use the original initial-pay formula, reflecting an existing roster rather than 35 simultaneous market signings. Only new veteran re-signings use this market. Rookie slots, minimum-pay replacements and their agreed annual growth are unchanged. CPU teams receive the same quotes and must clear the existing final cap/roster checks; expensive stars create real retention choices rather than automatic discounts.

Save format 31 accepts rules 21. Rules-20 checkpoints without a current-camp accepted re-signing adopt the new market on restore, without changing any signed salary, rookie offer, roster or completed history. A camp with an already accepted old-market renewal keeps rules 20 for the rest of that camp so replay cannot reprice the accepted deal; it adopts rules 21 at season rollover. Older history steps keep their original pricing versions. Earlier draft formats retain their existing migration behavior. Reading a save does not overwrite its checkpoint.


### Season notices during the offseason

Season-end and playoff-qualification banners remain visible through the playoffs, then hide after the draft successfully loads (including before your first pick). The completed regular-season simulation notice and non-terminal season-end owner update also hide. They stay hidden while reviewing the draft, browsing rosters, making cuts, attending camp and restoring a saved draft/camp. Failed draft starts preserve the existing notices and saved progress. The next season restores its normal status messages. GM Records retains contract feedback, and historical playoff results remain available; a terminal firing notice is still shown. This is derived from existing draft progress, with no new saved state or gameplay changes.


### Struggling inherited season (rules 22)

New careers start before Week 17 with a **3–13 inherited team record**. Three seeded background win weeks are selected among Weeks 1–16; their locations vary with the city and run seed. The shared scoring path assigns consistent scoring packages before player usage and statistical allocation. Schedule scores, box scores, opponent results, league results, points for/against, head-to-head/group records, standings and draft order therefore derive from the same actual games. Inherited games have no ties. Team/player ratings and salaries are not reduced.

**Week 17 is a normal simulated game**, giving a 3–14 finish after a loss or 4–13 after a win (the existing rare tie outcome remains possible). Only that game counts toward the new GM's record. Other matchups, playoffs and later seasons use the normal engine. Existing careers keep their original inherited results and history versions; this background record is not retroactively applied when restoring them. New careers use rules 22/save format 32; older careers can adopt rules 22 at a later season rollover without rewriting their first season.


### Fully guaranteed contracts and dead cap (rules 23)

Every signed contract is fully guaranteed. A release during camp removes the player from the roster, but **their unchanged annual salary stays on that team's cap in each remaining contract year**, starting with the upcoming playing season. It is not accelerated into one bill and does not inflate. Releasing a player with three remaining years at $8M/year creates $8M of dead cap in each of those years. The charge expires after the original final season. Re-signing and immediately releasing a player owes the new contract's full term.

Unsigned rookies cut before leaving camp create no obligation; removing their provisional hold can free cap space. An expired contract also creates no future dead cap. Retirement removes the retiring rostered player and clears remaining salary without creating a release charge. Dead cap counts toward the cap and available space, separately from active salaries, rookie holds and temporary expired-contract holds; it does not count toward the current active-payroll floor warning.

New guaranteed agreements must fit the current upcoming cap when accepted. Release unsigned rookies or expired contracts first when their holds need clearing; releasing a signed player cannot fund a new deal. Roster/position minimums still apply. An atomic release can add weak minimum-pay replacements to preserve them, including when an expired player occupies the final required slot. A release that would make guaranteed obligations plus a mandatory replacement exceed the cap is rejected without changing the checkpoint. There is no salary refund or offset if a released player later joins another team under this version.

The current payroll line includes the current dead-cap amount. The inline release confirmation previews this cut’s new dead cap for each remaining season, total guaranteed obligation, cap space freed (or consumed), projected cap space and any required minimum-pay replacement cost. Unsigned rookies and expired contracts explicitly show no dead-cap penalty. A release that cannot fit guaranteed obligations plus required replacements is reviewable but cannot be confirmed. Projections come from the same server-side cut/refill and accounting rules as the actual transaction; opening or cancelling a preview never changes the roster or saved career. The collapsible Payroll breakdown in Roster lists signed salaries, unsigned rookie holds, expired-contract holds and active dead-cap charges with player details and exact category totals. It shows the playing season, cap usage/space and floor-eligible payroll without adding another tab. Categories stay collapsed until opened; expanding them never changes career progress.

CPU teams record obligations for their signed roster cuts too. Only unsigned and expired holds can provide cap relief. As a necessary budget safeguard, CPU renewals must fit the cap; otherwise an expired player is released and a minimum replacement fills any mandatory vacancy. More sophisticated age/value/term decision-making remains a separate PR.

Dead obligations are immutable server-derived career state, reconstructed from the existing ordered roster decisions rather than trusted browser salary entries. They survive camp, profile/scouting requests, rollover, retry and reload; expired entries are pruned at season advancement. New careers use rules 23/save 33. Rules-22 checkpoints without any current-camp roster decisions can adopt guarantees immediately without changing signed amounts, inherited games or history. A previously committed camp keeps its original rules until rollover, so past releases cannot acquire retroactive charges. Other legacy seasons retain their versions until the existing rollover upgrade. The total roster minimum remains 35 in this PR; the requested reduction to 31 is a separate change.


### Starting 35, minimum 31, maximum 38 (rules 24)

Every team still begins a new career with **35 players** using the unchanged position counts. The legal regular-season range is now **31–38**, and all position minimums remain mandatory (22 players in total). Draft picks may temporarily exceed 38 until final cuts.

Intentional cuts from 35 down to 31 no longer generate weak fillers merely to restore 35. Emergency replacements after retirement, an expired-player release or a cap transaction fill missing position minimums, then only enough optional vacancies to reach 31. A required-slot replacement can preserve 31; a legal roster never drops below 31 or loses its last required player at a position. Fully guaranteed salary/dead-cap accounting remains unchanged, including the cost of any necessary replacement. Legal 31-player rosters survive camp, reload, season rollover and weekly simulation without automatic expansion. CPU teams use the same 31–38 limits.

New careers use rules 24/save 34. A rules-23 checkpoint with no current-camp decisions may adopt the lower floor immediately without changing its existing 35-player roster, contract amounts, dead cap or completed games. Camps with accepted roster decisions keep their original refill policy until rollover; historical steps retain their original rules. Older 35-minimum saves therefore remain replayable and do not acquire different past replacement players. How to Play and roster/cut status use the active career's limits.


### Inherited payroll and bad contracts (rules 25)

At **new career creation only**, the selected GM team's 35 actual signed contracts total a seeded whole-million amount between the current payroll floor and cap, inclusive: **$160M–$200M in Season 1**. These are real salaries on roster entries, not a displayed total or a balancing cap hold. The existing floor, cap and minimum-pay schedules determine the bounds; the allocator uses $10,000 units and an exact largest-remainder distribution so payroll matches its target without rounding past either bound.

The inherited book includes **three expensive deals for weaker bench players**: a backup QB, another offensive player and a defender. Their 3–4 year deals use higher-ability market benchmarks despite current ratings below 70, reflecting the previous GM's mistakes. Selection prefers players who are not about to retire, without altering ages or retirement mechanics. Other starting salaries are distributed by the original position/current-ability pay weights to complete the target. Ordinary starting contract terms remain intact. Existing guaranteed-contract rules apply to every inherited deal: releases retain the signed annual charge through its end, while retirement clears remaining salary.

Player ratings, potential, names, attributes, starter hierarchy, 3–13 inherited results and 35 starting / 31 minimum / 38 maximum roster rules are unchanged. Opponents' original contract books are unchanged; this assignment applies to the team the user inherits, not a league-wide payroll-floor enforcement change. New renewal offers, rookie slots and minimum replacements retain their existing pricing rules.

New careers use rules 25/save 35. **Restoring an existing career never reprices its inherited roster.** Current saved rules are retained, and a later rollover can adopt rules 25 while its historical origin step preserves the original contract book. Initialization is the only call site for the inherited-payroll allocator; normal development, camp, refill, replay and profile requests preserve signed amounts. How to Play notes the starting payroll and costly inherited deals.


### Current/potential salary demands (rules 26)

New veteran salary offers use **(current rating + potential rating) ÷ 2** in the existing position-specific salary curve, scaled to the signing season's cap and rounded half up to $10,000, subject to that season's minimum. Keep half points: 75 current / 86 potential is priced at **80.5**, not 80 or 81. For a TE at the $200M cap, 75/85 asks $8M and 75/86 asks $8.2M; at the Season-3 $221M cap those become $8.84M and $9.06M. Equal current/potential retains the prior current-only price. Kickers use the same formula.

Use the actual **post-camp displayed potential**, including that transition's development/reassessment, rather than draft-day estimates. The public renewal offer exposes its demand rating, and the inline confirmation shows current, potential and their average. How to Play explains the formula only for careers using it. User and CPU acceptance use the same price as the quote, including the existing guarantee/cap affordability checks. This shared pricing helper is available for future free agency; no free-agent flow is added here.

This changes **salary demand only**. Contract lengths/categories still use current rating and age. Signed annual amounts, inherited contract books (including bad deals), rookie slot pay, minimum replacements and existing dead-cap charges remain fixed. Later development or potential changes cannot reprice a signed deal.

New careers use rules 26/save 36. A rules-25 checkpoint with no accepted current-camp renewal may adopt the new offer formula without changing its roster, signed contracts, cuts or saved checkpoint. If any current-camp re-signing was already accepted, that camp keeps rules 25 through rollover so its agreed salary and any resulting dead cap replay unchanged. All completed history retains its pricing version; older inherited books are not regenerated under new-career salary rules. Reading/restoring never writes a replacement checkpoint by itself.
