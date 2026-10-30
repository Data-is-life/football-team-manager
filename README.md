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

Click any team name in Group Standings to open its scouting roster in a separate dialog. Inspect all 38 players by position, including age, current rating, and potential rating, plus the team's offense and defense ratings. Close the dialog or press Escape to return to Standings. Browsing preserves your managed team, season progress, and roster settings. A failed load can be retried inside the dialog; browsing does not simulate games.

Each team starts with 38 fictional players. Expand or collapse each position group to inspect its players, depth order, and current/potential ratings.

Both Ratings and Season Stats show each player's age in years. Initial ages are 21–36: a deterministic entry age of 21–24 plus the player's existing 0–12 years of experience. Ages stay fixed during a season and are regenerated for each new run. Under current career rules, age and experience increase once per offseason. Development and decline follow the positional curves below; retirement remains future work. Existing saved seasons keep their original rules until their next season transition.

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
| OL | 8 | 5 |
| K | 2 | 1 |
| DL | 6 | 4 |
| LB | 5 | 3 |
| CB | 4 | 2 |
| S | 3 | 2 |
| **Total** | **38** | **22** |

Offense has 18 players (QB, WR, TE, RB, OL), defense has 18 (DL, LB, CB, S), and two kickers complete the roster.

The roster validator enforces these per-position minimums. The team profile API returns the rules and current counts alongside all players. Player IDs identify city/position/depth slots. Names and ratings are stable within a run; defensive player current ratings use the team defense rating as their baseline.

QB1 receives all passing stats and K1 receives kicking stats. RBs split rushing production according to the active playing-time rules (a lone RB receives all carries), and receiving production is shared across eligible WRs, TEs, and backs. Team offense/defense determine scoring; current QB/RB ability and QB experience affect passing volume.

### Basic player ratings

The Ratings view uses five columns: **Depth, Player, Age, Current, Potential**. Depth includes the position, such as QB1. Detailed attribute columns, the attribute guide, and the experience column are removed from the UI. Draft prospects and roster-cut management use the same Current/Potential pair.

Current is the ability rating used by roster decisions and simulation. Potential is a possible ceiling rather than a promise of improvement. Current career rules use position-specific growth/decline and hidden, ability-independent longevity, described below. The ceiling is initialized once, held fixed during development, and equals current after the player enters decline. Kickers use separate seasonal form. Small arrows beside Current show the actual last-offseason change without adding another column.

Legacy career rules retain the earlier age-band display until upgrading at a season boundary. New careers use development rules immediately.

Player API payloads add `current_rating` and `potential_rating`. The existing `rating`, experience, and generated attribute data remain available for API/save compatibility and existing usage logic; attributes are no longer displayed and still do not affect gameplay. Save version 14 reconstructs the displayed ratings from seeded player state and offseason history.

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

The UI suites start local FastAPI servers on ports 8767, 8769, 8770, 8771, 8772, 8773, and 8774 and checks tab/keyboard navigation, empty states, full seasons and playoffs, box-score values, roster collapse state, always-expanded league content, failed-request retry, team reset/cancel, save restoration, and multiple-season continuation using jsdom. Node dependencies are only for development checks; Render still runs the Python app directly. These DOM checks do not verify visual layout.

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

After completing all four playoff rounds, complete the rookie draft and trim the roster to at most 38 players. Then choose **Continue to Season 2** (then Season 3, and so on). The same offseason steps apply whether your team wins, loses, or misses qualification. The API currently supports seasons 1–999; continuation stops at that limit.

Continuing retains your franchise, run seed, and finalized rosters for all 30 teams, including retained rookies and player cuts. Veterans age and gain experience once each offseason; current ability develops or declines by position and age. Attributes remain unchanged; retirements, free agency, and trades are separate future features. The new season has a fresh 17-game schedule, a new group rotation, a 0–0 record, and zero regular-season/playoff stats. Game results use the new season number, so they are not a replay of Season 1.

Same-place opponents use the previous season's actual final group ranks. The browser carries all 30 ranks into schedule, simulation, standings, and postseason requests as the optional JSON `prior_standings` query parameter. The API validates one rank from 1–5 per team/group and canonicalizes the mapping for bounded cache keys. Existing API callers that omit the mapping keep the original placeholder ranks; Season 1 also uses those placeholders. This avoids replaying every past season when restoring a later save.

**Franchise history** inside GM Records lists completed prior seasons: your regular-season record, playoff finish/record, and league champion. It is a summary archive; individual past-season box scores and individual player career totals are not retained. A failed season transition leaves the current game and saved checkpoint intact; retrying cannot append duplicate history. **Choose another team → Start new career** explicitly resets season, history, and seed instead of continuing the franchise.

Save version 10 includes prior ranks, history summaries with exact playoff records for newly completed seasons, draft choices, drops, past offseason decisions, lineup/rating rules, and the season development was enabled. Version 2 and 3 career/draft saves remain supported. Version 1 saves from the saved-progress PR still restore with identical first-season results and upgrade on the next successful save. Refreshing in later seasons restores the correct schedule, standings, season totals, and postseason without mixing seasons.

## Four-round rookie draft

After the league championship (including seasons where your team is eliminated or misses qualification), choose **Start rookie draft**. The draft is for the upcoming season and contains 200 rookies and four rounds of 30 picks: 120 total selections. Prospects have unique permanent player IDs, names, positions, ages 21–24, zero experience, current ratings 45–90, and potential ratings. Filter by position to compare prospects.

Non-playoff teams pick first, followed by teams eliminated in the Wild Card, Quarterfinals, Semifinals, and Championship. The champion picks last. Within each finish group, order is worst regular-season record, then lower point differential, fewer points scored, and a deterministic seeded draw. Every round uses the same order, without snaking or pick trades.

CPU teams select automatically up to your next turn. Their score balances prospect quality against current position quality, with a penalty for repeatedly drafting the same position. Your four picks are manual. After your fourth pick the remaining CPU selections complete automatically; all 30 teams receive four rookies. Selections are shown in a scrollable log and your team's picks are highlighted.

Each rookie is added without replacing a player: the offseason roster grows from 38 to 42. Your Roster includes the rookies, and scouting shows other teams' drafted players. Completed-season stats are preserved; rookies have zero production. Team ratings, depth leaders, and finished-season game outcomes do not change during the draft.

After the draft, drop players directly from **Roster → Ratings**. **Manage roster** is a shortcut to this view. Next-season continuation unlocks when the roster is at most 38 and every position minimum is satisfied. The draft is mandatory before every future season transition, including restored legacy careers. Salary caps, contracts, retirement, and trades are later work.

Draft choices autosave after each successful turn. Save version 4 stores up to four prospect IDs for the current draft plus cut and past offseason decisions; the API deterministically replays CPU decisions and validates that each chosen prospect was available at the user's actual pick. Reloads preserve the class, selection history, permanent IDs, and enlarged roster. Failed loads/picks preserve the last checkpoint and offer Retry; duplicate clicks cannot select twice. Versions 1 and 2 restore without a draft, and version 3 restores its saved draft; all upgrade on the next save. Starting a new career clears the draft. Drafts are available through the Season 998 offseason because the next season must fit the API's Season 999 limit.

`POST /api/draft/{team_id}` takes `season`, `run_seed`, optional `prior_standings`, and `manual_picks` (0–4 prospect IDs). It returns the selection order, completed picks, remaining prospects, the next user pick, completion state, and the updated managed-team profile. This endpoint is stateless and does not store server-side progress.

## Offseason player cuts and roster carryover

Complete the four-round draft, then open **Roster → Ratings** (or choose **Manage roster** to jump there). Drop controls appear beside each player, together with age, current/potential ratings, rookie badges, and starter highlights. Each position heading shows its player count and minimum, and the roster displays its total against the 38-player maximum. Choose Drop, then Confirm drop in the inline confirmation; Cancel leaves the save unchanged. There is no separate roster-management dialog. You can reduce a position to its minimum, but the next cut is disabled and the API rejects it too. For example, QB can go from two to one, but not from one to zero. All ten existing position minimums are preserved. The regular-season maximum is 38, not a requirement to fill exactly 38 slots.

Successful cuts autosave. Failed cuts leave the previous roster/checkpoint intact and can be retried. Once the roster is at most 38, Continue to next season unlocks. CPU teams also cut to 38, removing the lowest-rated eligible player while protecting every minimum. Cuts are available in the post-draft offseason only; released players are not yet part of free agency and cannot be re-signed in this version.

All retained players are ordered by descending current rating within their position for the next season's depth chart (ties preserve prior depth, then permanent ID). IDs never change when depth changes. QB1 handles passing; RBs share rushing according to the active playing-time rules, or the lone RB receives all carries when only the minimum is retained. WR/TE participation and line/defensive stats use the actual retained roster. Cut players disappear from the next season's profiles and production; finished-game box scores remain historical records. Roster Season Stats shows only currently retained players, so after cuts it is not a complete archive of the finished team's player totals.

Under the current lineup rules, each position starts its highest-current-rated players. Offense/defense ratings are 80% average starter rating plus 20% average bench rating, rounded to the nearest integer. If a unit has no bench, its starter average is used for the full rating. Kickers are excluded from both units and K1 is the highest-rated kicker. This affects scoring, usage, overtime, standings ratings, and postseason; potential is not used. Older saved seasons keep their original rating formula until the next season so completed results and draft availability cannot be rerolled.

Save version 14 stores the managed team's completed draft choices, cuts, and each offseason's schedule context. The server replays those decisions to reconstruct all 30 rosters, rather than accepting arbitrary player attributes from the browser. Bounded caches include the immutable roster context so distinct rosters cannot share scores or standings accidentally. Later drafts start from the modified league; surviving rookies retain their IDs across further seasons and reloads. A failed next-season load preserves the completed offseason save.

`POST /api/career/{team_id}` supports profile, week, playoffs, draft, and cuts actions with the run seed, current season/prior ranks, and completed offseason decisions. Each past offseason must be in increasing year order, precede the current season, include four valid picks and legal drops, and finish at 38 players or fewer. Existing seed-only GET APIs remain available for their original deterministic worlds; the UI uses career requests after roster changes.

## Automatic starters and team strength

New careers automatically rank every position by current ability from the first roster load. The same ranking applies after drafts, cuts, and season rollover; ties preserve existing depth, then permanent ID. Roster rows highlight starters. The starter counts are the existing positional minimums: QB 1, WR 2, TE 1, RB 1, OL 5, K 1, DL 4, LB 3, CB 2, S 2. This is automatic selection; manual depth-chart overrides are not part of this slice.

Offense includes QB/WR/TE/RB/OL, defense includes DL/LB/CB/S. Each team's unit rating is `round(0.8 × starter average + 0.2 × bench average)` on current ratings only. An empty bench uses the starter average instead. Ratings, profiles, standings, games, scouting, and postseason share one immutable, versioned lineup context. The old seeded strength values remain only as initial player-generation inputs and for legacy seasons.

Save version 5 records the lineup rules for the active season and for each past offseason. Versions 1–4 restore under their exact old season rules, including in-progress drafts. Continuing into the next season activates highest-rated starters and the 80/20 formula, while past drafts replay under the rules they actually used. New careers use the updated rules immediately. The team header explains the active formula or the pending next-season upgrade. Legacy seed-only APIs default to lineup rules 1; `lineup_rules=2` selects automatic lineups without development; `lineup_rules=3` selects development without initial hierarchy, and `lineup_rules=4` selects current rules in team/week/playoff endpoints and draft/career requests.

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

Development draws +1 to +4, limited by fixed potential. The prime plateau between development and decline draws −1 to +1, also limited by that ceiling. All current ratings stay within 1–99. Potential is initialized from current ability, position, age, and a seeded player-specific ceiling; it does not increase simply because another offseason occurs. Entering the decline phase sets potential to current, and both fall together afterward.

Longevity is hidden in both the UI and player API payloads, reproducibly determined from run seed, permanent player ID, and position. It is independent of ability and potential: a mediocre journeyman can age well, and an elite player can age normally. Some players get a 1–2 year delay; rarer exceptional agers get a 3–4 year delay and initially gentler losses. That protection expires after four years beyond their delayed steep-decline threshold. QBs have more long-career outcomes. No rating bonus or GOAT label is granted by longevity.

Kickers have a seeded seasonal form draw of −4 through +4 around a stable underlying baseline, rather than a cumulative random walk. Their potential display equals the current seasonal rating; form is separate from development. Changes between consecutive form draws can therefore exceed four points. Kicker age/experience still advance. Retirement is not modeled in this PR, and no players are automatically removed.

After each transition, depth charts and 80% starter/20% bench team ratings are recalculated. Profile, scouting, stats, CPU draft/cut logic, standings, and games use the resulting current abilities. Green/red inline arrows report actual rating gains/losses since the last offseason. Reloading, retrying a request, or simulating another week cannot age a player or reroll development.

Save version 6 records `developmentStart`. Older save versions preserve their current season and any pending draft, then adopt development at the next season: existing veterans age exactly once, without retroactively aging years previously played under frozen rules. Past offseasons replay under their original lineup rules. GET player/week/playoff APIs and POST draft/career requests accept rules 3 with season/development-start context; older rules 1 and 2 remain reproducible. The hidden state is reconstructed server-side and is not serialized into browser saves or exposed as player fields.

Players from the most recent draft have an **R** badge beside their names in roster ratings, Season Stats, scouting, and roster management. The badge appears when drafted, remains through their rookie season and reloads, and disappears in their second season or when the next draft begins. It follows permanent draft-class IDs, so undrafted initial players with zero experience are not marked.


## Initial starter and backup hierarchy

New careers use lineup rules 6 (save version 14). Every team's initial roster is ranked by current ability, then backups are lowered relative to the weakest starter at that position. Starter counts remain QB 1, WR 2, TE 1, RB 1, OL 5, K 1, DL 4, LB 3, CB 2, and S 2.

If the weakest starter is rated 70 or higher, each backup has a seeded ceiling 8–14 points below that starter. If the weakest starter is below 70, the ceiling is only 1–4 points lower, allowing closer competition on weak units. These are minimum separations: an already weaker backup stays weaker. Initial QB and K backups are also capped at 74. The adjustment never improves or lowers the selected starters, and preserves player identities, names, ages, experience, roster sizes, and position minimums. Backup attributes and potential are initialized from their adjusted ability.

This is a one-time initial-roster rule, not an ongoing limit. Future draft picks, development, aging, and automatic depth-chart changes can produce strong backups or new starters. Existing saved careers keep rules 1–3 and their original rosters, scores, and draft availability; they are not reshaped at their next season transition. Rules 4 persist through drafts, cuts, scouting, and later seasons. The 80% starter/20% bench team-rating formula is unchanged, so reducing initial bench quality can lower new-career team ratings.


## Rebuild challenge

New careers start the selected city with a manageable rebuild: offense and defense each fall within 68–72 using the existing 80% starter/20% bench formula. Initial starters are 71–73, and reserves are 57–64 after hierarchy caps. Only the selected team is rebuilt. Earlier rules 4/5 rebuilds retain their original, weaker 52–69 starting generation and are not retroactively changed. Player identities, ages, experience, roster sizes, and position minimums are preserved. Other teams keep their normal initial rosters. A short first-season message explains the rebuilding job.

This is a one-time starting condition. Potential is initialized from the rebuilt abilities and existing age/position rules; young players can develop, and draft picks retain their normal ratings. The team is never weakened again during a season transition. Better rosters can earn wins and championships through the normal simulation; losses are not scripted.

Save version 8 stores `rebuildTeam`, the managed city at career creation. Team/week/playoff GET requests and draft/career POST requests carry the matching `rebuild_team` so profiles, scouting, ratings, standings, scores, CPU draft choices, cuts, and future seasons all use the same league. Immutable contexts and cache keys include this origin. Scouting another team never changes the managed team or starts another rebuild. Existing versions 1–7 restore with no rebuild origin and retain their original rosters and outcomes. Starting a new career intentionally creates a new rebuild.


## Rating-based rotations and youth development

New careers use lineup rules 6 and save version 14; playing-time rules are unchanged from rules 5. Existing saves keep their current-season playing-time model and remain on their existing rules in later seasons (the earlier rules 1/2 development migration is unchanged). Start a new career for the new rotations.

QB1 handles all passing and K1 all kicking; youth development does not force their backups into games. Starting OL receive nearly all pass/run blocking snaps, with a small reserve role. RB carries favor the stronger starter while keeping a rotation. WR/TE targets combine their current ability with their assigned role; the existing 60% WR / 22% TE / 18% RB receiving mix remains. DL rotate most, LB next, with lighter CB/S rotations. Depth is automatically ranked by current rating as before. Potential does not influence playing time.

These are aggregate estimates rather than play-by-play substitutions. Position snap allocations conserve the configured on-field slots and never give a player more than a full game's snaps. Receiving targets sum to pass attempts, including intercepted throws; catches cannot exceed targets and receiving TDs cannot exceed catches. Rush yards and TDs require a carry. Line and defensive production is assigned within actual allocated participation, including sacks allowed within pass-blocking snaps.

Under-25 reserves outside QB/K normally receive a role floor of 5% of their unit's game snaps. Overstaffed positions share a bounded youth budget (at most 25% of their position's total participation is reserved as floors); integer rounding may reduce tiny roles. Ratings and starter status determine the rest of the allocation. A regular assigned role of at least 5% earns an eligible under-25 player +1 to their next offseason development draw, within their fixed potential and before position-specific decline. This is based on the season's modeled role, not accumulated snap counts, yards, or playoff appearances. QB/K receive no role bonus.

The season's role is captured when entering it and preserved through draft/cut replay. Drafting a replacement cannot remove an incumbent's already assigned development credit. New rookies get no credit for a season before joining the team; they first earn role credit after their rookie season. The next season captures fresh roles after aging and depth-chart changes. Repeat requests, reloads, and playoff games never award extra development. Hidden role state is reconstructed server-side, not trusted from browser saves.

Rules 5 boxes include participation, and Season Stats adds Snaps for all positions. Receiving adds Targets in game and season stats. Older rules retain their original payloads and table layouts. Scores remain outcome-first; this change allocates production after scoring rather than implementing the future drive engine.


## Mandatory offseason draft

After the league championship, **Start rookie draft** is the next step. The next-season button stays hidden until all four user picks and all 120 league picks are complete. A completed draft with more than 38 players shows a disabled **Roster limit: 38** button; finish cuts in Roster to enable **Continue to Season N**. Position minimums remain enforced by the cut API.

Closing the draft, reloading midway, or a failed first draft load cannot enable a season skip. The transition handler independently requires a completed four-pick draft, even if button visibility is changed. A failed next-season load preserves the completed draft/cuts and allows retry. At season 999 no draft or transition is offered.

Existing saves still load, including past seasons that skipped drafts. Their next transition must follow the current mandatory draft flow; past results are not replayed under new rules. The save format and simulation rules are unchanged. Players may make picks manually or use Auto-draft remaining picks; either path completes the required draft.


## Optional auto-draft

Open **Start rookie draft** (or **Resume draft**) and choose **Auto-draft remaining picks**. It fills only your remaining turns using the same current-quality, position-need, and repeat-position penalty as CPU teams. Earlier manual choices and all previous league picks are preserved. You can start with auto-draft or switch after one, two, or three manual picks.

The completed draft still adds four rookies without releasing anyone. Review the roster and make cuts to reach the 38-player maximum before continuing. Auto-draft does not automatically cut players or advance the season.

Draft/career POST requests accept a strict boolean `auto_draft` flag. The response's existing `manual_picks` field contains all resolved user selections, including auto-picks; the browser saves those IDs normally. Reloading uses ordinary replay without another automated selection, so no save-format change is needed. Failed requests retain the previous checkpoint and Retry preserves whether the failed action was auto-drafting. Repeated identical requests produce identical picks, and duplicate UI clicks are blocked. Career auto-draft uses the actual retained rosters and original season/rules context; it cannot be requested as a cut, profile, week, or playoff action.


## Regular-season playoff qualification message

As soon as Week 17 finishes, a message above the tabs announces the selected team's final playoff qualification. Qualifiers receive a green congratulations message with their final seed, group-winner/wildcard route, final W–L–T record, and first-round bye when applicable. Teams outside the final field receive a red missed-playoffs message and their final record. The final standings determine the message using the same tiebreakers as the playoff field; earlier weeks do not announce qualification.

The regular-season message remains available while following the playoffs, independently of individual playoff win/loss messages. Reloads reconstruct it from the saved regular-season snapshot. Advancing to the next season or starting another career clears it. This UI change works with existing saves and makes no extra API requests or simulation changes.


## GM Records

The **GM Records** tab follows Playoffs and preserves the order of the existing seven tabs. It shows career regular-season W–L–T, playoff appearances, playoff wins/losses, and championships. Career totals include the current season's completed games. A playoff appearance counts when the final Week 17 field is known, even before revealing the bracket. Only completed playoff games count toward the playoff record; byes do not count as wins, and championships count only when your team wins the final.

The completed-season Franchise history table now lives in GM Records and includes each season's playoff record. Save version 10 stores exact playoff wins/losses when advancing to the next season. The completed season moves from live totals into history once, avoiding double counting. Reloads preserve totals, and starting a new career resets them. Opening the tab makes no requests and changes no saved progress.

Older saves remain supported. Their completed-season summaries store a finishing round but not bye information, so exact playoff wins cannot always be recovered. Those seasons display a bounded range rather than an invented result: for example, an old champion has 3–4 wins and no losses, and a quarterfinal exit has 0–1 wins and one loss. Career totals add those ranges and show an explanatory note when needed. Current seasons and newly completed summaries use exact results; older missing-playoff and Wild Card exits are already exact. No historical simulations are rerun or modified for this page.


## Manageable starting balance

New careers use lineup rules 6 and save version 14. The selected team's initial offense and defense are each within **70 ± 2**. Seeded starter ratings of 71–73 and reserves of 57–64 after the existing hierarchy caps guarantee the target under the current 80% starter/20% bench team-rating formula. QB2/K2 remain clearly weaker than QB1/K1. Ratings vary by player and run; other teams keep their normal rosters.

This replaces the much weaker starting balance for new careers without changing the four-round draft, playing-time model, potential rules, or offseason growth. The balance is applied once: later draft picks and development can raise the team beyond the starting target, while aging can lower it. Existing saves retain their original roster generation, draft availability, and results through future seasons. Start a new career to use the more manageable rebuild.


## GM contracts

New careers start with a four-year GM contract. A persistent contract panel explains the hiring expectations, shows the contract's final season and years remaining, and gives owner feedback. Missing the playoffs triggers a disappointed-owner warning and closer monitoring next season. Failing to reach the playoffs in **all four full contract seasons** ends the career, even if winning-record extensions would leave time on the contract. New late-start careers evaluate Seasons 2–5 and exclude the introductory season; older full-season careers retain their original Seasons 1–4 deadline.

Each evaluated contract season awards **only its highest extension**, added to the contract's end season: championship +5 years; otherwise playoff appearance +2; otherwise a winning record (wins greater than losses, including tie-containing records) +1; otherwise no extension. A .500 record earns nothing. A playoff extension is secured when the Week 17 field is set; winning the championship upgrades that season's award from two to five years, rather than stacking the awards. After the opening playoff requirement is satisfied, contract expiration ends the career.

Firing blocks further weekly/playoff simulation, drafting, cuts, and advancing seasons. Existing results, rosters, standings, scouting, and GM records remain available to view, and a new career can be started. The contract is derived from completed history plus the current season, so repeated renders, retries, and reloads cannot grant duplicate extensions. This is a browser career rule, not authentication or a server-side anti-cheat restriction.

Save version 12 records whether contracts apply. Existing saves from versions 1–11 stay playable without retroactive contracts or firing, and remain exempt after future autosaves and season transitions. Start a new career to use contracts. New careers now include the late-season introduction described below; existing saves retain their original full-season starting point and contract rules.


## Saved-career restoration performance

Restoration now warms a multi-season career's replay once before fetching its dependent weekly and playoff data. Standings reconstruction computes the exact same scores without generating independent player-stat streams for historical league games. Saved progress, roster-context cache isolation, draft replay and all gameplay rules remain unchanged. Existing saves benefit automatically; no new career is needed.

Local repeated benchmarks found empty-cache Season 4 restoration fell from 6.983s to 2.225s, and Season 8 from 11.557s to 3.911s. These are medians of three fresh-server trials per revision; warm restores were broadly similar. Server startup is measured separately, and these figures do not establish a Render cold-start speedup. See [the measurement report](benchmarks/README.md) for raw samples, reproducible checkpoints, API/render timings, limitations and correctness checks.


## Simulate the remaining season

The team header offers **Simulate remaining season** alongside the existing weekly button. It simulates each remaining regular-season week through Week 17, using the same requests and results as manual weekly play. Every completed week renders normally and autosaves. Progress text shows the active week; **Stop after this week** finishes and saves the in-flight week before stopping. Reloading restores the last saved week and never resumes a batch automatically.

Both simulation buttons are blocked while a week/batch is running; career replacement is blocked during a season batch. A failed or mismatched response stops the batch without committing that week; retry continues from the next unplayed week. Browser storage failures retain in-page progress and the existing save warning. Regular-season simulation stops before revealing or simulating playoffs, drafting, cuts, or next-season progression. Qualification/owner messages and GM firing rules still apply. Existing saved careers can use this immediately; no save-format change or new career is needed.


## Choose your starters

Open **Roster → Choose starters** to select the required players at every position (22 total starter slots). Save the lineup, or use **Auto-select best** to return to the highest current ratings. Duplicate players and incorrect position counts are rejected. Within a position, selected starters are ordered by current rating; reserves continue the existing position-specific rotations. QB1 and K1 get the work, starting OL dominate, and modern team ratings still use 80% starters plus 20% bench.

Choices apply from the next unplayed week, or the next unplayed playoff round. Every completed game's original lineup, score and player production is preserved. A reset is also future-effective; it does not delete earlier decisions. Changes are blocked while a game, season batch or lineup request is running, after elimination/nonqualification, in the completed postseason/draft, and after firing. The editor can be opened in Ratings or Season Stats; saving preserves displayed totals, competition and collapsed position groups. Other teams remain read-only.

Save version 13 stores current-season `lineupChanges` and each past offseason's `lineup_changes` so restoration and historical draft replay use the correct lineups. Existing versions 1–12 adopt empty histories and keep their results until you choose a lineup. Drafts and cuts remain mandatory. Surviving manually chosen starters carry into the next season; released players are replaced with the best remaining players at that position. New careers clear all choices. Player development retains its existing role-based estimate; the final active lineup supplies the participation role for the offseason youth bonus.

The career API accepts bounded, immutable, effective-week starter events. Score caches retain the complete timeline in their context keys, and regular-season/playoff games resolve the correct event for their actual week. No arbitrary player ratings or rosters are accepted from the client. Existing no-choice simulation payloads remain reproducible.


## Late-season career introduction

New careers take over **before Week 17**, with exactly one regular-season game remaining. Weeks 1–16 are generated using the same seeded rosters, ratings, schedule and simulation as the final game. They appear as inherited team history in Schedule, Standings and player Season Stats. Game Stats labels Week 16 as before your hiring, and a tenure note explains the starting point. Team ratings remain the existing 68–72 rebuild.

Your GM W–L–T starts at **0–0–0** and counts only Week 17 in the introductory regular season. If the team qualifies, you manage the playoffs and those appearances/results/championships count toward GM records. The inherited team record still determines playoff qualification, draft order and next season's schedule. Archived introductory history shows your managed record alongside the full team record.

Season 1 is an introduction: **no contract year is consumed, no extension is earned, and introductory playoff qualification does not satisfy the full-season contract requirement**. Four full contract seasons cover Seasons 2–5; reach the playoffs at least once during those seasons or be fired at the end of Season 5. The existing highest-reward extension and later expiry rules apply from Season 2 onward. The owner explains this grace period instead of judging you on inherited results.

The final regular-season game, playoffs, mandatory four-round draft and legal cuts keep their usual flow. Surviving starter preferences carry over. **Season 2 and every later season start at Week 1**, with the existing development and rookie class rules. No ratings, ages or statistics are rerolled on hiring, and drafts cannot be skipped.

Save version 14 stores `careerStartWeek` (17 for new late starts, 1 for older careers), plus the introductory history's one-game `gmRecord`. Versions 1–13 retain their existing progress, GM records and contract deadline after migration and future saves. Starting a new career is required to get the late-season introduction. Failed initialization preserves the previous career and save.
