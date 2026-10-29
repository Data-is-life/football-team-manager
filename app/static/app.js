const form = document.querySelector("#team-form");
const select = document.querySelector("#team-select");
const scheduleSection = document.querySelector("#schedule-section");
const scheduleGrid = document.querySelector("#schedule");
const errorBox = document.querySelector("#error");
const simulateButton = document.querySelector("#simulate-button");
const resultPanel = document.querySelector("#result-panel");
const leagueResultsSection = document.querySelector("#league-results-section");
const standingsSection = document.querySelector("#standings-section");
const playoffSection = document.querySelector("#playoff-section");
const franchiseSetup = document.querySelector("#franchise-setup");
const rosterSection = document.querySelector("#roster-section");
const cancelTeamChange = document.querySelector("#cancel-team-change");
let activeTeamId = null;
let activeRunSeed = 0;
let activeSeason = 1;
let activeLineupRules = 5;
let activeDevelopmentStart = 1;
let activeRebuildTeam = null;
let activePriorStandings = {};
let careerHistory = [];
let regularSnapshot = null;
let activeDraftChoices = null;
let draftState = null;
let activeDropped = [];
let activeCareer = [];
let cutBusy = false;
let advancingSeason = false;
let pendingCut = null;
const rosterManagement = document.querySelector("#roster-management");
const manageRoster = document.querySelector("#manage-roster");
let draftBusy = false;
let draftPendingChoice = null;
const draftButton = document.querySelector("#draft-button");
const draftDialog = document.querySelector("#draft-dialog");
const nextSeasonButton = document.querySelector("#next-season");
let currentWeek = 0;
let latestResult = null;
let completedPlayoffRound = 0;
let playoffState = null;
const playoffsStart = document.querySelector('#playoffs-start');
const playoffSimulate = document.querySelector('#playoff-simulate');
const postseasonSection = document.querySelector('#postseason-section');
const viewTabs = [...document.querySelectorAll(".view-tab")];
const rosterCompetition = document.querySelector("#roster-competition");
let rosterProfile = null;
let rookieSeason = 1;
let rosterMode = "ratings";
let rosterTotals = null;
const rosterDialog = document.querySelector("#team-roster-dialog");
let scoutingRequest = 0;
let scoutingTeamId = null;
let scoutingCity = "";

const SAVE_KEY = "arcade-league-save";
const saveStatus = document.querySelector("#save-status");
const resumeButton = document.querySelector("#resume-save");
let restoring = false;

function rebuildQuery(team = activeRebuildTeam) {
  return team ? `&rebuild_team=${encodeURIComponent(team)}` : "";
}
function rebuildOrigin(context) {
  return context ? context.rebuildTeam : activeRebuildTeam;
}

function saveProgress() {
  if (!activeTeamId || restoring) return;
  const save = { version: 9, teamId: activeTeamId, runSeed: activeRunSeed,
    season: activeSeason, week: currentWeek, lineupRules: activeLineupRules, developmentStart: activeDevelopmentStart, rebuildTeam: activeRebuildTeam,
    priorStandings: activePriorStandings, history: careerHistory,
    draftChoices: activeDraftChoices,
    dropped: activeDropped, career: activeCareer,
    playoffRound: playoffState ? completedPlayoffRound : null };
  try {
    localStorage.setItem(SAVE_KEY, JSON.stringify(save));
    saveStatus.textContent = "Progress saved in this browser.";
    resumeButton.hidden = true;
  } catch {
    saveStatus.textContent = "Progress could not be saved. Browser storage may be unavailable or full. Keep this page open to continue.";
  }
}

function readSave() {
  const raw = localStorage.getItem(SAVE_KEY);
  if (!raw) return null;
  const save = JSON.parse(raw);
  const integer = (value, min, max) => Number.isInteger(value) && value >= min && value <= max;
  if (!save || ![1, 2, 3, 4, 5, 6, 7, 8, 9].includes(save.version) || typeof save.teamId !== "string"
      || ![...select.options].some(option => option.value && option.value === save.teamId)
      || !integer(save.runSeed, 0, 4294967295) || !integer(save.season, 1, 999)
      || !integer(save.week, 0, 17)
      || !(save.playoffRound === null || (save.week === 17 && integer(save.playoffRound, 0, 4)))) {
    throw new Error("Invalid save");
  }
  if (save.version === 1) {
    // PR #31 only created first-season saves. Upgrade without changing its seed or results.
    if (save.season !== 1) throw new Error("Invalid legacy save");
    save.priorStandings = {};
    save.history = [];
  }
  if (save.version < 3) save.draftChoices = null;
  if (!(save.draftChoices === null || (save.week === 17 && save.playoffRound === 4
      && save.season < 999 && Array.isArray(save.draftChoices) && save.draftChoices.length <= 4
      && save.draftChoices.every(id => typeof id === "string" && id.length < 100)
      && new Set(save.draftChoices).size === save.draftChoices.length))) throw new Error("Invalid draft save");
  if (save.version < 4) { save.dropped = []; save.career = []; }
  const ids = values => Array.isArray(values) && values.length <= 42
    && values.every(id => typeof id === "string" && id.length < 100)
    && new Set(values).size === values.length;
  if (!ids(save.dropped) || (save.dropped.length && save.draftChoices?.length !== 4)
      || !Array.isArray(save.career) || save.career.length > 998
      || !save.career.every((step, index) => step && integer(step.season, 1, save.season - 1)
        && (!index || step.season > save.career[index - 1].season)
        && ids(step.manual_picks) && step.manual_picks.length === 4 && ids(step.dropped)
        && validPriorStandings(step.prior_standings ?? {}, step.season))) throw new Error("Invalid roster save");
  if (save.version < 5) save.lineupRules = 1;
  if (![1, 2, 3, 4, 5].includes(save.lineupRules)) throw new Error("Invalid lineup rules");
  if (save.lineupRules < 3) save.developmentStart = null;
  if (save.lineupRules >= 3 && !integer(save.developmentStart, 1, save.season)) throw new Error("Invalid development start");
  if (save.version < 8) save.rebuildTeam = null;
  if (!(save.rebuildTeam === null || (save.rebuildTeam === save.teamId && save.lineupRules >= 4 && save.developmentStart === 1))) throw new Error("Invalid rebuild origin");
  const allowedFinishes = ["Champions", "Missed playoffs", "Lost in Wild Card", "Lost in Quarterfinals", "Lost in Semifinals", "Lost in Championship"];
  const knownTeam = id => [...select.options].some(option => option.value && option.value === id);
  if (!Array.isArray(save.history) || save.history.length !== save.season - 1
      || !save.history.every((entry, index) => entry && entry.season === index + 1
        && [entry.wins, entry.losses, entry.ties].every(value => integer(value, 0, 17))
        && entry.wins + entry.losses + entry.ties === 17
        && knownTeam(entry.championId) && allowedFinishes.includes(entry.playoffFinish))
      || !validPriorStandings(save.priorStandings, save.season)) throw new Error("Invalid career save");
  return save;
}

function validPriorStandings(ranks, season) {
  if (!ranks || typeof ranks !== "object" || Array.isArray(ranks)) return false;
  if (season === 1) return Object.keys(ranks).length === 0;
  if (Object.keys(ranks).length !== 30) return false;
  return [...select.querySelectorAll("optgroup")].every(group => {
    const positions = [...group.children].map(option => ranks[option.value]);
    return positions.every(Number.isInteger) && positions.sort((a, b) => a - b).join(",") === "1,2,3,4,5";
  });
}

function priorStandingsQuery(ranks = activePriorStandings) {
  return Object.keys(ranks).length ? `&prior_standings=${encodeURIComponent(JSON.stringify(ranks))}` : "";
}

function renderSeasonHistory() {
  const section = document.querySelector("#season-history");
  section.hidden = careerHistory.length === 0;
  const rows = careerHistory.map(entry => {
    const row = document.createElement("tr");
    const champion = [...select.options].find(option => option.value === entry.championId)?.textContent;
    for (const value of [entry.season, `${entry.wins}–${entry.losses}${entry.ties ? `–${entry.ties}` : ""}`, entry.playoffFinish, champion]) {
      const cell = document.createElement("td"); cell.textContent = value; row.append(cell);
    }
    return row;
  });
  document.querySelector("#season-history-rows").replaceChildren(...rows);
}

async function resumeProgress() {
  if (restoring) return;
  let save;
  try { save = readSave(); }
  catch {
    saveStatus.textContent = "Saved progress could not be read or uses an unsupported format. Starting a new game will replace it.";
    return;
  }
  if (!save) return;
  restoring = true;
  const submit = form.querySelector('button[type="submit"]');
  submit.disabled = true;
  select.disabled = true;
  resumeButton.disabled = true;
  saveStatus.textContent = "Restoring saved progress…";
  try {
    const requests = [
      `/api/schedule/${save.teamId}?season=${save.season}${priorStandingsQuery(save.priorStandings)}`,
      `/api/team/${save.teamId}?run_seed=${save.runSeed}&lineup_rules=${save.lineupRules}&season=${save.season}&development_start=${save.developmentStart ?? 1}${rebuildQuery(save.rebuildTeam)}`,
    ];
    if (save.week) requests.push(`/api/season/${save.teamId}/week/${save.week}?season=${save.season}&run_seed=${save.runSeed}${priorStandingsQuery(save.priorStandings)}&lineup_rules=${save.lineupRules}&development_start=${save.developmentStart ?? 1}${rebuildQuery(save.rebuildTeam)}`);
    if (save.playoffRound !== null) requests.push(`/api/playoffs/${save.teamId}/round/${save.playoffRound}?season=${save.season}&run_seed=${save.runSeed}${priorStandingsQuery(save.priorStandings)}&lineup_rules=${save.lineupRules}&development_start=${save.developmentStart ?? 1}${rebuildQuery(save.rebuildTeam)}`);
    const payloads = await Promise.all(requests.map(async url => {
      if (save.career.length) {
        if (url.startsWith("/api/team/")) return careerRequest("profile", {}, save);
        if (url.startsWith("/api/season/")) return careerRequest("week", { week: save.week }, save);
        if (url.startsWith("/api/playoffs/")) return careerRequest("playoffs", { round_number: save.playoffRound }, save);
      }
      const response = await fetch(url);
      if (!response.ok) throw new Error("Restore failed");
      return response.json();
    }));
    // Fetch/replay a saved draft before committing any restored UI state.
    const savedDraft = save.draftChoices === null ? null : await fetchDraft(save.draftChoices, save);
    const [schedule, profile, regular, postseason] = payloads;
    if (profile.team.id !== save.teamId || profile.run_seed !== save.runSeed
        || schedule.team.id !== save.teamId || schedule.season !== save.season
        || (regular && (regular.team.id !== save.teamId || regular.week !== save.week || regular.season !== save.season))
        || (postseason && (postseason.team.id !== save.teamId || postseason.completed_round !== save.playoffRound || postseason.season !== save.season))) {
      throw new Error("Restore failed");
    }
    renderTeamProfile(profile, save.season);
    renderSchedule(schedule, save.runSeed, { priorStandings: save.priorStandings, history: save.history, career: save.career, lineupRules: save.lineupRules, developmentStart: save.developmentStart, rebuildTeam: save.rebuildTeam });
    if (regular) renderResult(regular);
    if (postseason) { renderPostseason(postseason); activateView("playoffs"); }
    if (savedDraft) applyDraft(savedDraft);
    select.value = save.teamId;
    saveStatus.textContent = "Saved progress restored. Autosave is on in this browser.";
    resumeButton.hidden = true;
  } catch {
    saveStatus.textContent = "Saved progress could not be loaded. Retry to resume, or start a new game to replace it. Your save has been kept.";
    resumeButton.hidden = false;
  } finally {
    restoring = false;
    submit.disabled = false;
    select.disabled = false;
    resumeButton.disabled = false;
    submit.textContent = activeTeamId ? "Start new career" : "Start season";
  }
}
resumeButton.addEventListener("click", resumeProgress);

async function loadScoutingRoster(teamId, city) {
  const request = ++scoutingRequest;
  const owner = activeTeamId;
  const runSeed = activeRunSeed;
  const season = activeSeason;
  scoutingTeamId = teamId;
  scoutingCity = city;
  document.querySelector("#scout-title").textContent = `${city} roster`;
  const status = document.querySelector("#scout-status");
  status.textContent = "Loading roster…";
  document.querySelector("#scout-retry").hidden = true;
  document.querySelector("#scout-groups").replaceChildren();
  if (!rosterDialog.open) rosterDialog.showModal();
  const isCurrent = () => request === scoutingRequest && rosterDialog.open
    && owner === activeTeamId && runSeed === activeRunSeed && season === activeSeason;
  try {
    let profile;
    if (activeDropped.length && draftState?.complete) {
      profile = (await careerRequest("cuts", { view_team: teamId, manual_picks: activeDraftChoices, dropped: activeDropped })).profile;
    } else if (activeCareer.length) profile = await careerRequest("profile", { view_team: teamId });
    else {
      const response = await fetch(`/api/team/${teamId}?run_seed=${runSeed}&lineup_rules=${activeLineupRules}&season=${activeSeason}&development_start=${activeDevelopmentStart ?? 1}${rebuildQuery()}`);
      if (!response.ok) throw new Error("Roster could not be loaded. Please try again.");
      profile = await response.json();
    }
    if (!isCurrent()) return;
    if (profile.team.id !== teamId || profile.run_seed !== runSeed) throw new Error("Roster could not be loaded. Please try again.");
    if (draftState && !activeDropped.length) {
      const rookies = draftState.picks.filter(pick => pick.team.id === teamId).map(pick => pick.player);
      profile.roster.push(...rookies);
      if (activeLineupRules >= 2) {
        const players = [];
        for (const rule of profile.roster_rules) {
          profile.roster.filter(p => p.position === rule.position)
            .sort((a, b) => b.current_rating - a.current_rating || a.depth - b.depth || a.id.localeCompare(b.id))
            .forEach((p, index) => { p.depth = index + 1; players.push(p); });
        }
        profile.roster = players;
      }
      for (const rule of profile.roster_rules) rule.count = profile.roster.filter(p => p.position === rule.position).length;
    }
    document.querySelector("#scout-groups").replaceChildren(...createRosterGroups(profile, false));
    status.textContent = `${profile.team.group} · ${profile.roster.length} players · Offense ${profile.ratings.offense} · Defense ${profile.ratings.defense} · Ratings out of 99`;
  } catch (error) {
    if (!isCurrent()) return;
    status.textContent = "Roster could not be loaded. Please try again.";
    document.querySelector("#scout-retry").hidden = false;
  }
}

document.querySelector("#group-standings").addEventListener("click", event => {
  const button = event.target.closest(".team-roster-link");
  if (button) loadScoutingRoster(button.dataset.teamId, button.textContent);
});
document.querySelector("#scout-close").addEventListener("click", () => rosterDialog.close());
document.querySelector("#scout-retry").addEventListener("click", () => loadScoutingRoster(scoutingTeamId, scoutingCity));
rosterDialog.addEventListener("close", () => {
  ++scoutingRequest;
  document.querySelector("#scout-groups").replaceChildren();
});

function activateView(id, { focus = false } = {}) {
  for (const tab of viewTabs) {
    const selected = tab.id === `view-${id}`;
    tab.setAttribute("aria-selected", String(selected));
    tab.tabIndex = selected ? 0 : -1;
    document.getElementById(tab.getAttribute("aria-controls")).hidden = !selected;
    if (selected && focus) {
      tab.focus({ preventScroll: true });
      tab.scrollIntoView({ block: "nearest", inline: "nearest" });
    }
  }
}

viewTabs.forEach((tab, index) => {
  tab.addEventListener("click", () => activateView(tab.id.slice(5)));
  tab.addEventListener("keydown", event => {
    let next;
    if (event.key === "ArrowRight") next = (index + 1) % viewTabs.length;
    else if (event.key === "ArrowLeft") next = (index - 1 + viewTabs.length) % viewTabs.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = viewTabs.length - 1;
    else return;
    event.preventDefault();
    activateView(viewTabs[next].id.slice(5), { focus: true });
  });
});
function showError(message) {
  errorBox.textContent = message;
  errorBox.hidden = false;
}

function renderTeamOptions(teams) {
  const grouped = teams.reduce((groups, team) => {
    groups[team.group] ??= [];
    groups[team.group].push(team);
    return groups;
  }, {});
  select.replaceChildren(new Option("Select a city", ""));

  for (const [group, groupTeams] of Object.entries(grouped)) {
    const optgroup = document.createElement("optgroup");
    optgroup.label = group;
    for (const team of groupTeams) {
      optgroup.append(new Option(team.city, team.id));
    }
    select.append(optgroup);
  }
}

function addRookieBadge(cell, player) {
  const match = /^rookie-\d+-(\d+)-\d+$/.exec(player.id);
  if (!match || Number(match[1]) !== rookieSeason) return;
  const badge = document.createElement("span");
  badge.className = "rookie-badge";
  badge.textContent = "R";
  badge.title = "Rookie · most recent draft class";
  badge.setAttribute("aria-label", "Rookie");
  cell.append(document.createTextNode(" "), badge);
}

function createRosterGroups(profile, includeStats = true) {
  return profile.roster_rules.map((rule) => {
    const players = profile.roster.filter(player => player.position === rule.position);
    const group = document.createElement("details");
    group.className = "roster-group";
    group.dataset.position = rule.position;
    group.open = true;
    const summary = document.createElement("summary");
    summary.textContent = `${rule.position} · ${rule.count} players · minimum ${rule.minimum}`;
    const wrap = document.createElement("div");
    wrap.className = "table-wrap roster-rating-wrap";
    const table = document.createElement("table");
    table.className = "roster-table";
    const head = document.createElement("thead");
    const headings = document.createElement("tr");
    for (const label of ["Depth", "Player", "Age", "Current", "Potential"]) {
      const cell = document.createElement("th");
      cell.scope = "col";
      cell.textContent = label;
      headings.append(cell);
    }
    head.append(headings);
    const body = document.createElement("tbody");
    for (const player of players) {
      const row = document.createElement("tr");
      row.className = "roster-player";
      row.classList.toggle("is-starter", player.depth <= rule.minimum);
      row.dataset.starter = String(player.depth <= rule.minimum);
      row.dataset.playerId = player.id;
      for (const value of [`${player.position}${player.depth}`, player.name, player.age, player.current_rating, player.potential_rating]) {
        const cell = document.createElement("td");
        cell.textContent = value;
        row.append(cell);
      }
      addRookieBadge(row.children[1], player);
      const delta = player.rating_change ?? 0;
      if (delta) {
        const trend = document.createElement("span");
        trend.className = `rating-change ${delta > 0 ? "improved" : "declined"}`;
        trend.textContent = ` ${delta > 0 ? "↑ +" : "↓ "}${delta}`;
        trend.title = "Change since last offseason";
        row.children[3].append(trend);
      }
      body.append(row);
    }
    table.append(head, body);
    wrap.append(table);
    const statsWrap = document.createElement("div");
    statsWrap.className = "table-wrap roster-stats-wrap";
    const untracked = document.createElement("p");
    untracked.className = "roster-note roster-untracked-note";
    untracked.textContent = "Season production isn't tracked for this position yet. Ratings are shown below.";
    if (includeStats) group.append(summary, untracked, wrap, statsWrap);
    else group.append(summary, wrap);
    return group;
  });
}

function renderTeamProfile(profile, latestDraftSeason = activeSeason) {
  rookieSeason = latestDraftSeason;
  rosterProfile = profile;
  rosterMode = "ratings";
  rosterCompetition.value = "regular";
  rosterTotals = { regular: profile.roster_stats, playoffs: profile.roster_stats };
  document.querySelector("#offense-rating").textContent = profile.ratings.offense;
  document.querySelector("#defense-rating").textContent = profile.ratings.defense;
  const groups = createRosterGroups(profile);
  document.querySelector("#roster-groups").replaceChildren(...groups);
  document.querySelector("#development-note").textContent = profile.lineup_rules >= 3
    ? "Ratings change once each offseason by position and age. Potential is a possible ceiling; arrows show last offseason’s actual change. Longevity varies by player."
    : "This saved season keeps its original ratings. Position-specific development and aging begin next season.";
  document.querySelector("#roster-title").textContent = `Roster · ${profile.roster.length} players`;
  if (profile.lineup_rules >= 5) document.querySelector("#development-note").textContent += " Under-25 players outside QB/K can earn +1 from a regular rotation role, within potential.";
  rosterSection.hidden = false;
  renderRosterStats();
}

function renderRosterStats() {
  if (!rosterProfile) return;
  const showStats = rosterMode === "stats";
  rosterSection.classList.toggle("stats-view", showStats);
  document.querySelector("#roster-ratings-button").setAttribute("aria-pressed", String(!showStats));
  document.querySelector("#roster-stats-button").setAttribute("aria-pressed", String(showStats));
  document.querySelector("#roster-competition-control").hidden = !showStats;
  const status = document.querySelector("#roster-stats-status");
  status.hidden = !showStats;
  document.querySelector("#roster-stats-note").hidden = !showStats;
  const snapshot = rosterTotals[rosterCompetition.value];
  const competition = rosterCompetition.value === "regular" ? "Regular season" : "Playoffs";
  status.textContent = `${competition} · ${snapshot.games} team game${snapshot.games === 1 ? "" : "s"} recorded.${snapshot.games ? "" : " No completed games in this competition."}`;
  const totals = new Map(snapshot.players.map(player => [player.player_id, player]));
  const decimal = value => value == null ? "—" : value.toFixed(1);
  const percentage = value => value == null ? "—" : `${value.toFixed(1)}%`;
  const column = (category, key, label, format) => ({ category, key, label, format });
  const modern = rosterProfile.lineup_rules >= 5;
  document.querySelector("#roster-stats-note").textContent = modern
    ? "Snaps and defense/line stats are aggregate estimates. Under-25 reserves outside QB/K get development roles. Tackles include sacks; pass snaps include sacks."
    : "Defense and line stats are aggregate estimates. Tackles include sacks; pass snaps include sacks.";
  const receiving = [...(modern ? [column("receiving", "targets", "Targets")] : []), column("receiving", "receptions", "Rec"), column("receiving", "yards", "Rec Yds"),
    column("receiving", "yards_per_reception", "Y/Rec", decimal), column("receiving", "touchdowns", "Rec TD")];
  const defense = [column("defense", "snaps", "Snaps"), column("defense", "tackles", "Tackles"),
    column("defense", "sacks", "Sacks"), column("defense", "interceptions", "INT")];
  const columns = {
    DL: defense, LB: defense, CB: defense, S: defense,
    OL: [column("blocking", "pass_block_snaps", "Pass snaps"),
      column("blocking", "run_block_snaps", "Run snaps"), column("blocking", "sacks_allowed", "Sacks allowed")],
    QB: [column("passing", "completions", "Cmp"), column("passing", "attempts", "Att"),
      column("passing", "completion_percentage", "Cmp%", percentage), column("passing", "yards", "Pass Yds"),
      column("passing", "touchdowns", "TD"), column("passing", "interceptions", "INT"),
      column("passing", "yards_per_attempt", "Y/A", decimal), column("passing", "passer_rating", "Passer rating", decimal)],
    RB: [column("rushing", "attempts", "Carries"), column("rushing", "yards", "Rush Yds"),
      column("rushing", "yards_per_carry", "Y/Carry", decimal), column("rushing", "touchdowns", "Rush TD"), ...receiving],
    WR: receiving, TE: receiving,
    K: [column("kicking", "field_goals_made", "FGM"), column("kicking", "field_goals_attempted", "FGA"),
      column("kicking", "field_goal_percentage", "FG%", percentage),
      column("kicking", "longest_field_goal", "Long FG", value => value == null ? "—" : `${value} yd`),
      column("kicking", "extra_points_made", "XPM"), column("kicking", "extra_points_attempted", "XPA"),
      column("kicking", "kicking_points", "Pts")],
  };
  for (const group of document.querySelectorAll("#roster-groups .roster-group")) {
    const position = group.dataset.position;
    const tracked = Boolean(columns[position]);
    group.querySelector(".roster-rating-wrap").hidden = showStats && tracked;
    group.querySelector(".roster-untracked-note").hidden = !showStats || tracked;
    const wrap = group.querySelector(".roster-stats-wrap");
    wrap.hidden = !showStats || !tracked;
    if (!showStats || !tracked) continue;
    const table = document.createElement("table");
    table.className = "roster-table roster-season-table";
    const caption = document.createElement("caption");
    caption.textContent = `${position} · ${competition}`;
    const head = document.createElement("thead");
    const headings = document.createElement("tr");
    for (const label of ["Depth", "Player", "Age", ...(modern ? ["Snaps"] : []), ...columns[position].map(item => item.label)]) {
      const cell = document.createElement("th");
      cell.scope = "col";
      cell.textContent = label;
      headings.append(cell);
    }
    head.append(headings);
    const body = document.createElement("tbody");
    for (const player of rosterProfile.roster.filter(player => player.position === position)) {
      const row = document.createElement("tr");
      row.className = "roster-season-player";
      row.dataset.playerId = player.id;
      const entry = totals.get(player.id);
      const values = [player.depth, player.name, player.age, ...(modern ? [entry.snaps ?? 0] : []), ...columns[position].map(item => {
        const value = entry[item.category][item.key] ?? (item.key === "targets" ? 0 : null);
        return item.format ? item.format(value) : value;
      })];
      for (const value of values) {
        const cell = document.createElement("td");
        cell.textContent = value;
        row.append(cell);
      }
      addRookieBadge(row.children[1], player);
      body.append(row);
    }
    table.append(caption, head, body);
    wrap.replaceChildren(table);
  }
}

document.querySelector("#roster-ratings-button").addEventListener("click", () => {
  rosterMode = "ratings";
  renderRosterStats();
});
document.querySelector("#roster-stats-button").addEventListener("click", () => {
  rosterMode = "stats";
  renderRosterStats();
});
rosterCompetition.addEventListener("change", renderRosterStats);

function createRunSeed() {
  const candidate = crypto.getRandomValues(new Uint32Array(1))[0] || 1;
  return candidate === activeRunSeed ? (candidate % 4294967295) + 1 : candidate;
}

function renderSchedule(data, runSeed, { priorStandings = {}, history = [], career = [], lineupRules = 5, developmentStart = 1, rebuildTeam = null } = {}) {
  if (rosterDialog.open) rosterDialog.close();
  activeTeamId = data.team.id;
  activeRunSeed = runSeed;
  activeSeason = data.season;
  activeLineupRules = lineupRules;
  activeDevelopmentStart = developmentStart;
  activeRebuildTeam = rebuildTeam;
  document.querySelector("#rebuild-note").hidden = !rebuildTeam || activeSeason !== 1;
  document.querySelector("#rating-method").textContent = lineupRules >= 2
    ? "Team ratings: 80% starters + 20% bench, using current ability. Kickers are separate. Highlighted players are starters."
    : "This saved season keeps its original lineups and ratings. Highest-rated starters and 80%/20% team ratings apply next season.";
  activePriorStandings = priorStandings;
  careerHistory = history;
  regularSnapshot = null;
  activeDraftChoices = null;
  draftState = null;
  activeDropped = [];
  activeCareer = career;
  manageRoster.hidden = true;
  rosterManagement.hidden = true;
  document.querySelector("#cut-confirmation").hidden = true;
  document.querySelector("#cut-error").hidden = true;
  pendingCut = null;
  renderCuts();
  draftPendingChoice = null;
  draftButton.hidden = true;
  draftButton.textContent = "Start rookie draft";
  document.querySelector("#draft-summary").hidden = true;
  document.querySelector("#draft-error").hidden = true;
  document.querySelector("#draft-retry").hidden = true;
  document.querySelector("#draft-board").hidden = true;
  document.querySelector("#draft-prospects").replaceChildren();
  document.querySelector("#draft-picks").replaceChildren();
  document.querySelector("#draft-title").textContent = "Rookie draft";
  document.querySelector("#draft-status").textContent = "";
  document.querySelector("#draft-position").value = "";
  if (draftDialog.open) draftDialog.close();
  nextSeasonButton.hidden = true;
  renderSeasonHistory();
  document.querySelector("#season-display").textContent = activeSeason;
  currentWeek = 0;
  latestResult = null;
  completedPlayoffRound = 0;
  playoffState = null;
  playoffsStart.hidden = true;
  playoffSimulate.hidden = true;
  postseasonSection.hidden = true;
  document.querySelector("#season-status").textContent = "Ready for Week 1.";
  for (const id of ["game", "league", "standings", "race", "playoffs"]) {
    document.querySelector(`#${id}-empty`).hidden = false;
  }
  document.querySelector("#playoffs-empty p").textContent = "Playoffs begin after Week 17.";
  document.querySelector("#postseason-status").textContent = "";
  document.querySelector("#postseason-status").dataset.outcome = "neutral";
  activateView("schedule");
  document.querySelector("#team-group").textContent = data.team.group;
  document.querySelector("#team-name").textContent = data.team.city;
  document.querySelector("#rotation-note").textContent =
    `Season ${data.season} rotation: ${data.rotating_group} · Scores show your team first. Opponent records reflect the latest completed week.`;

  scheduleGrid.replaceChildren();
  for (const game of data.games) {
    const article = document.createElement("article");
    article.className = "game-card";
    article.dataset.opponentId = game.opponent_id;
    article.innerHTML = `
      <span class="week">Week ${game.week}</span>
      <span class="venue ${game.venue.toLowerCase()}">${game.venue === "Home" ? "vs" : "at"}</span>
      <strong>${game.opponent}</strong>
      <span class="opponent-record">Record: 0–0</span>
      <span class="game-final">Not played</span>
      <span class="reason">${game.reason}</span>
    `;
    scheduleGrid.append(article);
  }
  document.querySelector("#season-record").textContent = "0–0";
  simulateButton.textContent = "Simulate Week 1";
  simulateButton.disabled = false;
  resultPanel.hidden = true;
  leagueResultsSection.hidden = true;
  standingsSection.hidden = true;
  playoffSection.hidden = true;
  franchiseSetup.hidden = true;
  scheduleSection.hidden = false;
  document.querySelector("#team-name").focus({ preventScroll: true });
  scheduleSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

function statTable(title, rows, columns) {
  const headings = columns.map((column) => `<th>${column.label}</th>`).join("");
  const body = rows.map((row) => `
    <tr>${columns.map((column) => `<td>${column.format ? column.format(row[column.key]) : row[column.key]}</td>`).join("")}</tr>
  `).join("");
  return `
    <section class="stat-section">
      <h3>${title}</h3>
      <div class="table-wrap"><table><thead><tr>${headings}</tr></thead><tbody>${body}</tbody></table></div>
    </section>
  `;
}

function playerStatsMarkup(box) {
  const playerColumn = { key: "player", label: "Player" };
  const decimal = value => value == null ? "—" : value.toFixed(1);
  const percentage = value => value == null ? "—" : `${value.toFixed(1)}%`;
  return [
    statTable("Passing", box.passing, [playerColumn, { key: "completions", label: "Cmp" }, { key: "attempts", label: "Att" }, { key: "completion_percentage", label: "Cmp%", format: percentage }, { key: "yards", label: "Yds" }, { key: "yards_per_attempt", label: "Y/A", format: decimal }, { key: "touchdowns", label: "TD" }, { key: "interceptions", label: "INT" }, { key: "passer_rating", label: "Passer rating", format: decimal }]),
    statTable("Rushing", box.rushing, [playerColumn, { key: "attempts", label: "Att" }, { key: "yards", label: "Yds" }, { key: "yards_per_carry", label: "Y/Carry", format: decimal }, { key: "touchdowns", label: "TD" }]),
    statTable("Receiving", box.receiving, [playerColumn, ...(box.participation ? [{ key: "targets", label: "Targets" }] : []), { key: "receptions", label: "Rec" }, { key: "yards", label: "Yds" }, { key: "yards_per_reception", label: "Y/Rec", format: decimal }, { key: "touchdowns", label: "TD" }]),
    statTable("Kicking", box.kicking, [playerColumn, { key: "field_goals_made", label: "FGM" }, { key: "field_goals_attempted", label: "FGA" }, { key: "field_goal_percentage", label: "FG%", format: percentage }, { key: "longest_field_goal", label: "Long FG", format: value => value == null ? "—" : `${value} yd` }, { key: "extra_points_made", label: "XPM" }, { key: "extra_points_attempted", label: "XPA" }, { key: "kicking_points", label: "Pts" }]),
  ].join("");
}

function renderPlayerStats(box) {
  document.querySelector("#player-stats").innerHTML = playerStatsMarkup(box);
}

function selectBoxScore(side) {
  const awayTab = document.querySelector("#away-tab");
  const homeTab = document.querySelector("#home-tab");
  awayTab.classList.toggle("active", side === "away");
  homeTab.classList.toggle("active", side === "home");
  awayTab.setAttribute("aria-pressed", String(side === "away"));
  homeTab.setAttribute("aria-pressed", String(side === "home"));
  renderPlayerStats(latestResult[side]);
}

function renderResult(data) {
  regularSnapshot = data;
  rosterTotals.regular = data.roster_stats;
  renderRosterStats();
  latestResult = data.result;
  const { away, home } = latestResult;
  document.querySelector("#away-name").textContent = away.team.city;
  document.querySelector("#away-score").textContent = away.score;
  document.querySelector("#home-name").textContent = home.team.city;
  document.querySelector("#home-score").textContent = home.score;
  document.querySelector("#result-week").textContent = `Week ${data.week} final${latestResult.overtime ? " · OT" : ""}`;
  const badge = document.querySelector("#result-badge");
  badge.textContent = latestResult.outcome === "W" ? "WIN" : latestResult.outcome === "L" ? "LOSS" : "TIE";
  badge.dataset.outcome = latestResult.outcome;

  const record = `${data.record.wins}–${data.record.losses}${data.record.ties ? `–${data.record.ties}` : ""}`;
  document.querySelector("#season-record").textContent = record;
  document.querySelector("#team-comparison").innerHTML = [
    ["Total plays", away.team_stats.total_plays, home.team_stats.total_plays],
    ["Total yards", away.team_stats.total_yards, home.team_stats.total_yards],
    ["Passing", away.team_stats.passing_yards, home.team_stats.passing_yards],
    ["Rushing", away.team_stats.rushing_yards, home.team_stats.rushing_yards],
    ["Turnovers", away.team_stats.turnovers, home.team_stats.turnovers],
    ["Sacks allowed", away.team_stats.sacks_allowed, home.team_stats.sacks_allowed],
    ["Possession", away.team_stats.time_of_possession, home.team_stats.time_of_possession],
  ].map(([label, awayValue, homeValue]) => `
    <div><strong>${awayValue}</strong><span>${label}</span><strong>${homeValue}</strong></div>
  `).join("");

  const awayTab = document.querySelector("#away-tab");
  const homeTab = document.querySelector("#home-tab");
  awayTab.textContent = away.team.city;
  homeTab.textContent = home.team.city;
  selectBoxScore(latestResult.selected_team_id === away.team.id ? "away" : "home");
  resultPanel.hidden = false;

  document.querySelector("#league-results-title").textContent = `League Results — Week ${data.week}`;
  const leagueResults = document.querySelector("#league-results");
  leagueResults.innerHTML = data.league_results.map((game) => {
    const awayWon = game.away_score > game.home_score;
    const homeWon = game.home_score > game.away_score;
    return `
      <article class="league-result-card">
        ${game.overtime ? '<span class="overtime-label">Overtime</span>' : ""}
        <div class="league-team ${awayWon ? "winner" : ""}">
          <span>${game.away.city}</span><strong>${game.away_score}</strong>
        </div>
        <div class="league-team ${homeWon ? "winner" : ""}">
          <span>${game.home.city}</span><strong>${game.home_score}</strong>
        </div>
      </article>
    `;
  }).join("");
  leagueResultsSection.hidden = false;

  document.querySelector("#standings-title").textContent = `Group Standings — Week ${data.week}`;
  document.querySelector("#group-standings").innerHTML = data.standings.groups.map((group) => `
    <article class="standings-card">
      <h4>${group.group}</h4>
      <div class="mini-table-wrap">
        <table class="mini-table">
          <thead><tr><th>#</th><th>Team</th><th>Offense</th><th>Defense</th><th>Record</th><th>Diff</th></tr></thead>
          <tbody>
            ${group.teams.map((row) => `
              <tr class="${row.team.id === activeTeamId ? "selected-team" : ""}">
                <td>${row.rank}</td>
                <td><span class="team-cell"><button class="team-roster-link" type="button" data-team-id="${row.team.id}" aria-label="View ${row.team.city} roster">${row.team.city}</button>${row.rank === 1 ? '<b class="leader-mark">L</b>' : ""}</span></td>
                <td>${row.ratings.offense}</td>
                <td>${row.ratings.defense}</td>
                <td>${row.record}</td>
                <td>${row.point_differential > 0 ? "+" : ""}${row.point_differential}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    </article>
  `).join("");
  standingsSection.hidden = false;

  document.querySelector("#playoff-title").textContent = `Playoff Race — Week ${data.week}`;
  document.querySelector("#playoff-race").innerHTML = data.standings.playoff_race.map((row) => `
    <tr class="${row.team.id === activeTeamId ? "selected-team" : ""}">
      <td><span class="seed">${row.seed}</span></td>
      <td>${row.team.city}${row.bye ? '<span class="bye-pill">Bye</span>' : ""}</td>
      <td>${row.qualification}</td>
      <td>${row.record}</td>
      <td>${row.point_differential > 0 ? "+" : ""}${row.point_differential}</td>
    </tr>
  `).join("");
  document.querySelector("#tiebreaker-note").textContent =
    `Tiebreakers: ${data.standings.tiebreakers.join(" → ")}`;
  playoffSection.hidden = false;

  const opponentRecords = new Map(data.standings.groups.flatMap(group => group.teams)
    .map(row => [row.team.id, `${row.wins}–${row.losses}${row.ties ? `–${row.ties}` : ""}`]));
  for (const card of scheduleGrid.children) {
    card.querySelector(".opponent-record").textContent = `Record: ${opponentRecords.get(card.dataset.opponentId)}`;
  }
  for (const game of data.game_results) {
    const card = scheduleGrid.children[game.week - 1];
    if (!card) continue;
    card.classList.add("completed");
    card.dataset.outcome = game.outcome;
    const final = card.querySelector(".game-final");
    final.textContent = `${game.outcome} · ${game.team_score}–${game.opponent_score}${game.overtime ? " · OT" : ""}`;
    const outcome = game.outcome === "W" ? "Win" : game.outcome === "L" ? "Loss" : "Tie";
    final.setAttribute("aria-label",
      `${outcome}: ${data.team.city} ${game.team_score}, ${game.opponent} ${game.opponent_score}${game.overtime ? ", overtime" : ""}`);
  }

  document.querySelector("#playoff-title").textContent = data.season_complete ? "Final playoff seeds" : `Playoff Race — Week ${data.week}`;
  playoffsStart.hidden = !data.season_complete || playoffState !== null;
  currentWeek = data.week;
  simulateButton.disabled = data.season_complete;
  simulateButton.textContent = data.season_complete ? "Regular season complete" : `Simulate Week ${data.next_week}`;
  for (const id of ["game", "league", "standings", "race"]) {
    document.querySelector(`#${id}-empty`).hidden = true;
  }
  const own = latestResult.selected_team_id === home.team.id ? home : away;
  const opponent = own === home ? away : home;
  document.querySelector("#season-status").textContent =
    `Week ${data.week} final: ${own.team.city} ${own.score}–${opponent.score} ${opponent.team.city}${latestResult.overtime ? " · OT" : ""}.`;
  if (data.season_complete) {
    document.querySelector("#playoffs-empty p").textContent =
      "The playoff field is set. Choose View playoffs above to reveal the bracket.";
  }
}

async function loadTeams() {
  try {
    const response = await fetch("/api/teams");
    if (!response.ok) throw new Error("Teams could not be loaded.");
    const data = await response.json();
    renderTeamOptions(data.teams);
    await resumeProgress();
  } catch (error) {
    select.replaceChildren(new Option("Unavailable", ""));
    showError(error.message);
  }
}

document.querySelector("#change-team-button").addEventListener("click", () => {
  scheduleSection.hidden = true;
  franchiseSetup.hidden = false;
  cancelTeamChange.hidden = false;
  document.querySelector("#new-season-note").hidden = false;
  form.querySelector('button[type="submit"]').textContent = "Start new career";
  errorBox.hidden = true;
  select.focus();
});

cancelTeamChange.addEventListener("click", () => {
  franchiseSetup.hidden = true;
  scheduleSection.hidden = false;
  errorBox.hidden = true;
  document.querySelector("#change-team-button").focus();
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!select.value) return;
  const submit = form.querySelector('button[type="submit"]');
  if (submit.disabled) return;
  submit.disabled = true;
  resumeButton.disabled = true;
  submit.textContent = "Loading team…";
  select.disabled = true;
  cancelTeamChange.disabled = true;
  errorBox.hidden = true;
  try {
    const teamId = select.value;
    const runSeed = createRunSeed();
    const [scheduleResponse, profileResponse] = await Promise.all([
      fetch(`/api/schedule/${teamId}?season=1`),
      fetch(`/api/team/${teamId}?run_seed=${runSeed}&lineup_rules=5&season=1&development_start=1${rebuildQuery(teamId)}`),
    ]);
    if (!scheduleResponse.ok || !profileResponse.ok) {
      throw new Error("Your team could not be loaded. Please try again.");
    }
    const [schedule, profile] = await Promise.all([
      scheduleResponse.json(), profileResponse.json(),
    ]);
    if (profile.run_seed !== runSeed || profile.team.id !== teamId || profile.lineup_rules !== 5 || profile.rebuild_team !== teamId) {
      throw new Error("Your team could not be loaded. Please try again.");
    }
    renderTeamProfile(profile, 1);
    renderSchedule(schedule, runSeed, { rebuildTeam: teamId });
    saveProgress();
  } catch (error) {
    showError(error.message);
  } finally {
    submit.disabled = false;
    submit.textContent = activeTeamId ? "Start new career" : "Start season";
    select.disabled = false;
    cancelTeamChange.disabled = false;
    resumeButton.disabled = false;
  }
});

simulateButton.addEventListener("click", async () => {
  if (!activeTeamId || currentWeek >= 17) return;
  simulateButton.disabled = true;
  simulateButton.textContent = "Simulating…";
  errorBox.hidden = true;
  const teamId = activeTeamId;
  const runSeed = activeRunSeed;
  const season = activeSeason;
  try {
    const nextWeek = currentWeek + 1;
    let data;
    if (activeCareer.length) data = await careerRequest("week", { week: nextWeek });
    else {
      const response = await fetch(`/api/season/${teamId}/week/${nextWeek}?season=${activeSeason}&run_seed=${runSeed}${priorStandingsQuery()}&lineup_rules=${activeLineupRules}&development_start=${activeDevelopmentStart ?? 1}${rebuildQuery()}`);
      if (!response.ok) throw new Error("The week could not be simulated.");
      data = await response.json();
    }
    if (teamId === activeTeamId && runSeed === activeRunSeed && season === activeSeason) {
      renderResult(data);
      saveProgress();
    }
  } catch (error) {
    if (teamId !== activeTeamId || runSeed !== activeRunSeed || season !== activeSeason) return;
    simulateButton.disabled = false;
    simulateButton.textContent = `Simulate Week ${currentWeek + 1}`;
    showError(error.message);
  }
});

document.querySelector("#away-tab").addEventListener("click", () => selectBoxScore("away"));
document.querySelector("#home-tab").addEventListener("click", () => selectBoxScore("home"));


function playoffTeamName(entry) {
  const selected = entry.team.id === activeTeamId;
  return `<span class="playoff-team-name ${selected ? "playoff-team-selected" : ""}" data-team-id="${entry.team.id}">#${entry.seed} ${entry.team.city}${selected ? ' <span class="your-team-badge">Your team</span>' : ""}</span>`;
}

function playoffGameCard(game) {
  const result = game.result;
  const venue = game.neutral_site ? "Neutral-site championship" : "Higher seed hosts";
  const label = result ? `Final${result.overtime ? " · OT" : ""}` : venue;
  const row = (side) => {
    const entry = game[side];
    const won = result && game.winner.team.id === entry.team.id;
    return `<div class="league-team ${won ? "winner" : ""} ${entry.team.id === activeTeamId ? "playoff-team-selected" : ""}">${playoffTeamName(entry)}<strong>${result ? result[side].score : ""}</strong></div>`;
  };
  return `<article class="league-result-card playoff-game-card"><span class="control-label">${label}</span>${row("away")}${row("home")}</article>`;
}

function renderPlayoffBracket(data) {
  const rounds = [
    { name: "Wild Card", games: 6 },
    { name: "Quarterfinals", games: 4 },
    { name: "Semifinals", games: 2 },
    { name: "Championship", games: 1 },
  ];
  document.querySelector("#playoff-bracket").innerHTML = rounds.map((round, index) => {
    const number = index + 1;
    const completed = data.rounds.find(item => item.number === number);
    const upcoming = data.upcoming?.number === number ? data.upcoming : null;
    const known = completed || upcoming;
    const status = completed ? "Complete" : upcoming ? "Up next" : "Awaiting reseeding";
    const byes = number === 1 ? data.field.filter(entry => entry.bye).map(entry =>
      `<article class="league-result-card bracket-bye"><span class="control-label">First-round bye</span>${playoffTeamName(entry)}<p>Advances to Quarterfinals</p></article>`).join("") : "";
    const games = known ? known.games.map(playoffGameCard).join("")
      : Array.from({ length: round.games }, () =>
        '<article class="league-result-card bracket-placeholder"><span class="control-label">Matchup to be determined</span><p>Awaiting previous round</p></article>').join("");
    return `<section class="bracket-round ${completed ? "round-complete" : upcoming ? "round-upcoming" : "round-pending"}" data-round="${number}" aria-labelledby="bracket-round-${number}">
      <header><h3 id="bracket-round-${number}">${round.name}</h3><p class="bracket-round-status">${status}</p></header>
      <div class="bracket-games">${byes}${games}</div>
    </section>`;
  }).join("");
}

function renderPostseason(data) {
  rosterTotals.playoffs = data.roster_stats;
  renderRosterStats();
  playoffState = data;
  completedPlayoffRound = data.completed_round;
  playoffsStart.hidden = true;
  playoffSimulate.hidden = false;
  document.querySelector("#playoffs-empty").hidden = true;
  postseasonSection.hidden = false;
  const champion = data.champion;
  const selectedChampion = champion && champion.team.id === activeTeamId;
  const latestOwn = data.rounds.flatMap(round => round.games.map(game => ({ round, game })))
    .filter(({ game }) => game.home.team.id === activeTeamId || game.away.team.id === activeTeamId).at(-1);
  const won = latestOwn && latestOwn.game.winner.team.id === activeTeamId;
  const ownSide = latestOwn?.game.home.team.id === activeTeamId ? "home" : "away";
  const otherSide = ownSide === "home" ? "away" : "home";
  const score = latestOwn ? `${latestOwn.game.result[ownSide].score}–${latestOwn.game.result[otherSide].score}` : "";
  const status = !data.qualified ? "Your team missed the playoffs. Follow the league through the championship."
    : selectedChampion ? `Congratulations! ${data.team.city} are Season ${data.season} champions!`
    : latestOwn && !won ? `Sorry! ${data.team.city} lost ${score} in the ${latestOwn.round.name} and has been eliminated. You can still follow the remaining rounds.`
    : data.eliminated ? "Sorry! Your team has been eliminated. You can still follow the remaining rounds."
    : won ? `Congratulations! ${data.team.city} won ${score} in the ${latestOwn.round.name}. Your team is still in the title race.`
    : data.completed_round === 0 && data.field.some(team => team.team.id === activeTeamId && team.bye)
      ? "Your team earned a Wild Card bye. Advance the round to see your quarterfinal opponent."
    : "Your team is still in the title race.";
  const statusBox = document.querySelector("#postseason-status");
  statusBox.textContent = status;
  statusBox.dataset.outcome = !data.qualified ? "neutral" : selectedChampion ? "win"
    : data.eliminated ? "loss" : latestOwn ? (won ? "win" : "loss") : "neutral";
  document.querySelector("#season-status").textContent = data.champion
    ? `Season ${data.season} champions: ${data.champion.team.city}.`
    : data.completed_round ? `${data.rounds.at(-1).name} complete. ${status}` : status;
  const banner = document.querySelector("#champion-banner");
  banner.hidden = !champion;
  banner.textContent = champion ? `Season ${data.season} champions: ${champion.team.city} · Seed #${champion.seed}` : "";
  draftButton.hidden = !data.postseason_complete || activeSeason >= 999;
  nextSeasonButton.hidden = !data.postseason_complete;
  nextSeasonButton.disabled = activeSeason >= 999;
  nextSeasonButton.textContent = activeSeason < 999 ? `Continue to Season ${activeSeason + 1}` : "Season limit reached";
  playoffSimulate.disabled = data.postseason_complete;
  playoffSimulate.textContent = data.upcoming ? `Simulate ${data.upcoming.name}` : "Postseason complete";

  const latestRound = data.rounds.at(-1);
  const selectedGame = latestRound?.games.find(game =>
    game.home.team.id === activeTeamId || game.away.team.id === activeTeamId);
  const ownGame = document.querySelector("#your-playoff-game");
  ownGame.hidden = !selectedGame;
  if (selectedGame) {
    const side = selectedGame.home.team.id === activeTeamId ? "home" : "away";
    const won = selectedGame.winner.team.id === activeTeamId;
    ownGame.innerHTML = `<h3>Your ${latestRound.name} game · ${won ? "Win" : "Loss"}</h3>
      ${playoffGameCard(selectedGame)}
      <details><summary>Your player box score</summary><div class="player-stats">${playerStatsMarkup(selectedGame.result[side])}</div></details>`;
  }
  renderPlayoffBracket(data);
}

async function loadPlayoffRound(number) {
  errorBox.hidden = true;
  playoffsStart.disabled = true;
  playoffSimulate.disabled = true;
  document.querySelector("#change-team-button").disabled = true;
  try {
    let data;
    if (activeCareer.length) data = await careerRequest("playoffs", { round_number: number });
    else {
      const response = await fetch(`/api/playoffs/${activeTeamId}/round/${number}?season=${activeSeason}&run_seed=${activeRunSeed}${priorStandingsQuery()}&lineup_rules=${activeLineupRules}&development_start=${activeDevelopmentStart ?? 1}${rebuildQuery()}`);
      if (!response.ok) throw new Error("The playoff round could not be loaded. Please try again.");
      data = await response.json();
    }
    renderPostseason(data);
    saveProgress();
    activateView("playoffs", { focus: true });
  } catch (error) {
    showError(error.message);
    errorBox.scrollIntoView({ behavior: "smooth", block: "center" });
  } finally {
    playoffsStart.disabled = false;
    document.querySelector("#change-team-button").disabled = false;
    playoffSimulate.disabled = playoffState?.postseason_complete ?? false;
  }
}

playoffsStart.addEventListener("click", () => {
  if (currentWeek === 17 && !playoffsStart.disabled) loadPlayoffRound(0);
});
playoffSimulate.addEventListener("click", () => {
  if (playoffState?.next_round && !playoffSimulate.disabled) loadPlayoffRound(completedPlayoffRound + 1);
});

async function careerRequest(action, extra = {}, context = null) {
  const teamId = context?.teamId ?? activeTeamId;
  const ranks = context?.priorStandings ?? activePriorStandings;
  const response = await fetch(`/api/career/${teamId}`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, season: context?.season ?? activeSeason,
      run_seed: context?.runSeed ?? activeRunSeed,
      prior_standings: Object.keys(ranks).length ? ranks : null,
      career: context?.career ?? activeCareer, lineup_rules: context?.lineupRules ?? activeLineupRules, development_start: context?.developmentStart ?? activeDevelopmentStart ?? 1, rebuild_team: rebuildOrigin(context), ...extra }),
  });
  if (!response.ok) {
    let detail;
    try { const data = await response.json(); if (typeof data.detail === "string") detail = data.detail; } catch {}
    throw new Error(detail ?? "Roster progress could not be loaded. Please try again.");
  }
  return response.json();
}

async function fetchDraft(choices, context = null) {
  const teamId = context?.teamId ?? activeTeamId;
  const season = context?.season ?? activeSeason;
  const seed = context?.runSeed ?? activeRunSeed;
  const ranks = context?.priorStandings ?? activePriorStandings;
  const dropped = context?.dropped ?? activeDropped;
  if ((context?.career ?? activeCareer).length || dropped.length) {
    const data = await careerRequest(dropped.length ? "cuts" : "draft", { manual_picks: choices, dropped }, context);
    if (data.team.id !== teamId || data.season !== season || data.run_seed !== seed
        || JSON.stringify(data.manual_picks) !== JSON.stringify(choices)) throw new Error("Draft could not be restored.");
    return data;
  }
  const response = await fetch(`/api/draft/${teamId}`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ season, run_seed: seed, lineup_rules: context?.lineupRules ?? activeLineupRules, development_start: context?.developmentStart ?? activeDevelopmentStart ?? 1, rebuild_team: rebuildOrigin(context),
      prior_standings: Object.keys(ranks).length ? ranks : null, manual_picks: choices }),
  });
  if (!response.ok) throw new Error("The draft could not be loaded. Please try again.");
  const data = await response.json();
  if (data.team.id !== teamId || data.season !== season || data.run_seed !== seed
      || JSON.stringify(data.manual_picks) !== JSON.stringify(choices)) {
    throw new Error("The draft could not be loaded. Please try again.");
  }
  return data;
}

function applyDraft(data) {
  draftState = data;
  activeDraftChoices = data.manual_picks;
  activeDropped = data.dropped ?? [];
  // Extend the finished season's snapshots with zero-production rookies, without
  // losing any existing player totals or attributing last season's stats to rookies.
  const previous = rosterTotals;
  const mode = rosterMode;
  const competition = rosterCompetition.value;
  const collapsed = [...document.querySelectorAll("#roster-groups .roster-group")]
    .filter(group => !group.open).map(group => group.dataset.position);
  renderTeamProfile(data.profile, data.draft_season);
  for (const type of ["regular", "playoffs"]) {
    const old = new Map(previous[type].players.map(player => [player.player_id, player]));
    rosterTotals[type] = { games: previous[type].games,
      players: data.profile.roster_stats.players.map(player => old.get(player.player_id) ?? player) };
  }
  rosterMode = mode;
  rosterCompetition.value = competition;
  renderRosterStats();
  for (const position of collapsed) document.querySelector(`#roster-groups [data-position="${position}"]`).open = false;
  const count = data.profile.roster.length;
  nextSeasonButton.disabled = !data.complete || count > 38;
  nextSeasonButton.textContent = !data.complete ? "Finish rookie draft" : count > 38 ? "Roster limit: 38" : `Continue to Season ${activeSeason + 1}`;
  manageRoster.hidden = !data.complete;
  draftButton.textContent = data.complete ? "Review draft" : "Resume draft";
  const summary = document.querySelector("#draft-summary");
  summary.hidden = false;
  summary.textContent = data.complete
    ? `Draft complete · ${count}/38 players. ${count > 38 ? "Use Manage roster to drop players before the next season." : "Roster ready for next season."}`
    : `Draft in progress · ${activeDraftChoices.length} of 4 picks made · ${count} players.`;
  renderDraft();
  renderCuts();
}

function renderDraft() {
  if (!draftState) return;
  document.querySelector("#draft-title").textContent = `Season ${draftState.draft_season} rookie draft`;
  document.querySelector("#draft-status").textContent = draftState.complete
    ? "All 120 picks are complete. Your four rookies have joined your offseason roster."
    : `Your turn · Round ${draftState.next_round} of 4 · Overall pick ${draftState.next_pick} of 120`;
  const filter = document.querySelector("#draft-position").value;
  const rows = [];
  draftState.available.forEach((player, index) => {
    if (filter && player.position !== filter) return;
    const row = document.createElement("tr");
    row.dataset.prospectId = player.id;
    for (const value of [index + 1, player.name, player.position, player.age, player.current_rating, player.potential_rating]) {
      const cell = document.createElement("td"); cell.textContent = value; row.append(cell);
    }
    const action = document.createElement("td");
    const button = document.createElement("button"); button.type = "button";
    button.textContent = "Draft"; button.dataset.draftId = player.id;
    button.setAttribute("aria-label", `Draft ${player.name}, ${player.position}`);
    button.disabled = draftBusy || draftState.complete;
    action.append(button); row.append(action); rows.push(row);
  });
  document.querySelector("#draft-prospects").replaceChildren(...rows);
  const picks = draftState.picks.map(pick => {
    const item = document.createElement("li");
    item.value = pick.overall;
    item.textContent = `Round ${pick.round} · ${pick.team.city}: ${pick.player.name} · ${pick.player.position} · Current ${pick.player.current_rating} · Potential ${pick.player.potential_rating}`;
    if (pick.team.id === activeTeamId) item.className = "your-draft-pick";
    return item;
  });
  document.querySelector("#draft-picks").replaceChildren(...picks);
  document.querySelector("#draft-available").textContent = `${draftState.available.length} prospects available · Ratings out of 99`;
  document.querySelector("#draft-board").hidden = draftState.complete;
}

async function loadDraft(choice = null) {
  if (draftBusy || advancingSeason || !playoffState?.postseason_complete || activeSeason >= 999) return;
  draftBusy = true;
  draftPendingChoice = choice;
  draftButton.disabled = true;
  document.querySelector("#change-team-button").disabled = true;
  nextSeasonButton.disabled = true;
  document.querySelector("#draft-error").hidden = true;
  document.querySelector("#draft-retry").hidden = true;
  if (!draftDialog.open) draftDialog.showModal();
  if (draftState) renderDraft();
  document.querySelector("#draft-status").textContent = choice ? "Recording your pick and simulating CPU picks…" : "Loading rookie draft…";
  const teamId = activeTeamId, seed = activeRunSeed, season = activeSeason;
  const choices = [...(activeDraftChoices ?? []), ...(choice ? [choice] : [])];
  try {
    const data = await fetchDraft(choices);
    if (teamId !== activeTeamId || seed !== activeRunSeed || season !== activeSeason) return;
    applyDraft(data);
    saveProgress();
    draftPendingChoice = null;
  } catch (error) {
    if (teamId !== activeTeamId || seed !== activeRunSeed || season !== activeSeason) return;
    document.querySelector("#draft-error").textContent = error.message;
    document.querySelector("#draft-error").hidden = false;
    document.querySelector("#draft-retry").hidden = false;
  } finally {
    draftBusy = false;
    draftButton.disabled = false;
    document.querySelector("#change-team-button").disabled = false;
    if (draftState) renderDraft();
    else {
      document.querySelector("#draft-status").textContent = "Draft not started. Your saved season is unchanged.";
      nextSeasonButton.disabled = activeSeason >= 999;
    }
  }
}
draftButton.addEventListener("click", () => {
  if (draftState) { renderDraft(); if (!draftDialog.open) draftDialog.showModal(); }
  else loadDraft();
});
document.querySelector("#draft-close").addEventListener("click", () => draftDialog.close());
document.querySelector("#draft-position").addEventListener("change", renderDraft);
document.querySelector("#draft-retry").addEventListener("click", () => loadDraft(draftPendingChoice));
document.querySelector("#draft-prospects").addEventListener("click", event => {
  const button = event.target.closest("[data-draft-id]");
  if (button && !button.disabled) loadDraft(button.dataset.draftId);
});

function renderCuts() {
  const available = Boolean(draftState?.complete);
  rosterManagement.hidden = !available;
  // Reuse the rating rows so ages, trends, rookies, and starters stay together.
  for (const cell of document.querySelectorAll("#roster-groups .roster-cut-action")) cell.remove();
  if (!available || !rosterProfile) return;
  document.querySelector("#cut-count").textContent = `${rosterProfile.roster.length}/38 players · Keep each position at or above its minimum.`;
  for (const group of document.querySelectorAll("#roster-groups .roster-group")) {
    const rule = rosterProfile.roster_rules.find(rule => rule.position === group.dataset.position);
    const count = rosterProfile.roster.filter(player => player.position === rule.position).length;
    const heading = document.createElement("th");
    heading.className = "roster-cut-action";
    heading.scope = "col";
    heading.textContent = "Action";
    group.querySelector(".roster-rating-wrap thead tr").append(heading);
    for (const row of group.querySelectorAll(".roster-rating-wrap .roster-player")) {
      const player = rosterProfile.roster.find(player => player.id === row.dataset.playerId);
      const cell = document.createElement("td");
      cell.className = "roster-cut-action";
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.dropId = player.id;
      button.textContent = count <= rule.minimum ? "Minimum reached" : "Drop";
      button.disabled = cutBusy || advancingSeason || count <= rule.minimum;
      button.setAttribute("aria-label", `Drop ${player.name}, ${player.position}`);
      if (count <= rule.minimum) button.title = `Keep at least ${rule.minimum} ${player.position} players`;
      cell.append(button);
      row.append(cell);
    }
  }
}
function openCuts() {
  if (!draftState?.complete || cutBusy || advancingSeason) return;
  if (draftDialog.open) draftDialog.close();
  activateView("roster", { focus: true });
  rosterMode = "ratings";
  renderRosterStats();
  renderCuts();
}
manageRoster.addEventListener("click", openCuts);
function cancelCut() {
  const id = pendingCut;
  pendingCut = null;
  document.querySelector("#cut-confirmation").hidden = true;
  document.querySelector("#cut-error").hidden = true;
  const button = [...document.querySelectorAll("#roster-groups [data-drop-id]")].find(button => button.dataset.dropId === id);
  button?.focus();
}
document.querySelector("#cut-cancel").addEventListener("click", cancelCut);
document.querySelector("#roster-groups").addEventListener("click", event => {
  const button = event.target.closest("[data-drop-id]");
  if (!button || button.disabled || cutBusy || advancingSeason || !draftState?.complete) return;
  pendingCut = button.dataset.dropId;
  const player = rosterProfile.roster.find(p => p.id === pendingCut);
  document.querySelector("#cut-error").hidden = true;
  document.querySelector("#cut-confirm-text").textContent = `Drop ${player.name} (${player.position})? This removes the player from your next-season roster.`;
  document.querySelector("#cut-confirmation").hidden = false;
  document.querySelector("#cut-confirm").focus();
});
document.querySelector("#cut-confirm").addEventListener("click", async () => {
  if (!pendingCut || cutBusy || advancingSeason || !draftState?.complete) return;
  cutBusy = true;
  document.querySelector("#cut-confirm").disabled = true;
  document.querySelector("#cut-cancel").disabled = true;
  document.querySelector("#cut-error").hidden = true;
  document.querySelector("#change-team-button").disabled = true;
  nextSeasonButton.disabled = true;
  renderCuts();
  try {
    const data = await careerRequest("cuts", { manual_picks: activeDraftChoices, dropped: [...activeDropped, pendingCut] });
    applyDraft(data);
    saveProgress();
    pendingCut = null;
    document.querySelector("#cut-confirmation").hidden = true;
    document.querySelector("#roster-title").focus();
  } catch (error) {
    document.querySelector("#cut-error").textContent = error.message;
    document.querySelector("#cut-error").hidden = false;
  } finally {
    cutBusy = false;
    document.querySelector("#cut-confirm").disabled = false;
    document.querySelector("#cut-cancel").disabled = false;
    document.querySelector("#change-team-button").disabled = false;
    nextSeasonButton.disabled = rosterProfile.roster.length > 38;
    renderCuts();
  }
});

nextSeasonButton.addEventListener("click", async () => {
  if (advancingSeason || nextSeasonButton.disabled || (activeDraftChoices !== null && (!draftState?.complete || rosterProfile.roster.length > 38)) || cutBusy || draftBusy || !playoffState?.postseason_complete || !regularSnapshot || activeSeason >= 999) return;
  advancingSeason = true;
  nextSeasonButton.disabled = true;
  manageRoster.disabled = true;
  renderCuts();
  draftButton.disabled = true;
  document.querySelector("#change-team-button").disabled = true;
  errorBox.hidden = true;
  const nextSeason = activeSeason + 1;
  const ranks = Object.fromEntries(regularSnapshot.standings.groups.flatMap(group => group.teams)
    .map(row => [row.team.id, row.rank]));
  const lastOwnRound = playoffState.rounds.filter(round => round.games.some(game =>
    game.home.team.id === activeTeamId || game.away.team.id === activeTeamId)).at(-1);
  const summary = { season: activeSeason, ...regularSnapshot.record,
    championId: playoffState.champion.team.id,
    playoffFinish: playoffState.champion.team.id === activeTeamId ? "Champions"
      : !playoffState.qualified ? "Missed playoffs" : `Lost in ${lastOwnRound.name}` };
  try {
    const developmentStart = activeDevelopmentStart ?? nextSeason;
    const lineupRules = Math.max(3, activeLineupRules);
    const career = activeDraftChoices === null ? activeCareer : [...activeCareer, {
      season: activeSeason, prior_standings: Object.keys(activePriorStandings).length ? activePriorStandings : null,
      manual_picks: activeDraftChoices, dropped: activeDropped, lineup_rules: activeLineupRules,
    }];
    const response = await fetch(`/api/schedule/${activeTeamId}?season=${nextSeason}${priorStandingsQuery(ranks)}`);
    if (!response.ok) throw new Error("The next season could not be loaded. Please try again.");
    const schedule = await response.json();
    if (schedule.team.id !== activeTeamId || schedule.season !== nextSeason) {
      throw new Error("The next season could not be loaded. Please try again.");
    }
    const history = [...careerHistory, summary];
    let profile;
    if (career.length) profile = await careerRequest("profile", { season: nextSeason, career, lineup_rules: lineupRules, development_start: developmentStart });
    else {
      const response = await fetch(`/api/team/${activeTeamId}?run_seed=${activeRunSeed}&lineup_rules=${lineupRules}&season=${nextSeason}&development_start=${developmentStart}${rebuildQuery()}`);
      if (!response.ok) throw new Error("The next season could not be loaded. Please try again.");
      profile = await response.json();
    }
    if (profile.team?.id !== activeTeamId || profile.run_seed !== activeRunSeed || profile.lineup_rules !== lineupRules) {
      throw new Error("The next season could not be loaded. Please try again.");
    }
    renderTeamProfile(profile, nextSeason);
    renderSchedule(schedule, activeRunSeed, { priorStandings: ranks, history, career, lineupRules, developmentStart, rebuildTeam: activeRebuildTeam });
    saveProgress();
  } catch (error) {
    showError(error.message);
    nextSeasonButton.disabled = false;
  } finally {
    advancingSeason = false;
    manageRoster.disabled = false;
    renderCuts();
    draftButton.disabled = false;
    document.querySelector("#change-team-button").disabled = false;
  }
});

loadTeams();
