const form = document.querySelector("#team-form");
const select = document.querySelector("#team-select");
const scheduleSection = document.querySelector("#schedule-section");
const scheduleGrid = document.querySelector("#schedule");
const errorBox = document.querySelector("#error");
const simulateButton = document.querySelector("#simulate-button");
const simulateSeasonButton = document.querySelector("#simulate-season");
const stopSeasonButton = document.querySelector("#stop-season");
const seasonSimulationStatus = document.querySelector("#season-simulation-status");
let weekSimulationBusy = false;
let seasonSimulationActive = false;
let stopSeasonRequested = false;
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
let activeCareerStartWeek = 1;
let activeLineupRules = 7;
let activeDevelopmentStart = 1;
let activeRebuildTeam = null;
let activePriorStandings = {};
let careerHistory = [];
let activeContracts = true;
let regularSnapshot = null;
let activeDraftChoices = null;
let activeDraftRounds = 6;
let draftState = null;
let activeDropped = [];
let activeCareer = [];
let activeLineupChanges = [];
let lineupBusy = false;
let playoffBusy = false;
let cutBusy = false;
let advancingSeason = false;
let pendingCut = null;
const rosterManagement = document.querySelector("#roster-management");
const manageRoster = document.querySelector("#manage-roster");
let draftBusy = false;
let draftPendingChoice = null;
let draftPendingAuto = false;
const draftButton = document.querySelector("#draft-button");
const draftDialog = document.querySelector("#draft-dialog");
const autoDraftButton = document.querySelector("#auto-draft");
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
  const save = { version: 16, draftRounds: activeDraftRounds, careerStartWeek: activeCareerStartWeek, lineupChanges: activeLineupChanges, contracts: activeContracts, teamId: activeTeamId, runSeed: activeRunSeed,
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
  if (!save || ![1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16].includes(save.version) || typeof save.teamId !== "string"
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
  if (save.version < 16) {
    save.draftRounds = save.draftChoices === null ? 6 : 4;
    for (const step of save.career ?? []) step.draft_rounds = 4;
  }
  if (![4, 6].includes(save.draftRounds)) throw new Error("Invalid draft rounds");
  if (!(save.draftChoices === null || (save.week === 17 && save.playoffRound === 4
      && save.season < 999 && Array.isArray(save.draftChoices) && save.draftChoices.length <= save.draftRounds
      && save.draftChoices.every(id => typeof id === "string" && id.length < 100)
      && new Set(save.draftChoices).size === save.draftChoices.length))) throw new Error("Invalid draft save");
  if (save.version < 4) { save.dropped = []; save.career = []; }
  const ids = values => Array.isArray(values) && values.length <= 44
    && values.every(id => typeof id === "string" && id.length < 100)
    && new Set(values).size === values.length;
  if (!ids(save.dropped) || (save.dropped.length && save.draftChoices?.length !== save.draftRounds)
      || !Array.isArray(save.career) || save.career.length > 998
      || !save.career.every((step, index) => step && integer(step.season, 1, save.season - 1)
        && (!index || step.season > save.career[index - 1].season)
        && ids(step.manual_picks) && [4, 6].includes(step.draft_rounds) && step.manual_picks.length === step.draft_rounds && ids(step.dropped)
        && validPriorStandings(step.prior_standings ?? {}, step.season))) throw new Error("Invalid roster save");
  if (save.version < 5) save.lineupRules = 1;
  if (![1, 2, 3, 4, 5, 6, 7].includes(save.lineupRules)) throw new Error("Invalid lineup rules");
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
        && knownTeam(entry.championId) && allowedFinishes.includes(entry.playoffFinish)
        && validPlayoffSummary(entry))
      || !validPriorStandings(save.priorStandings, save.season)) throw new Error("Invalid career save");
  if (save.version < 12) save.contracts = false;
  if (typeof save.contracts !== "boolean") throw new Error("Invalid contract save");
  if (save.version < 13) save.lineupChanges = [];
  const validChanges = changes => Array.isArray(changes) && changes.length <= 21
    && changes.every((entry, i) => entry && integer(entry.week, 1, 21)
      && (!i || entry.week > changes[i-1].week) && Array.isArray(entry.starters)
      && [0, 22].includes(entry.starters.length) && ids(entry.starters));
  if (!validChanges(save.lineupChanges) || save.lineupChanges.some(entry => entry.week > (save.week < 17 ? save.week + 1 : 18 + (save.playoffRound ?? 0)))
      || !save.career.every(step => validChanges(step.lineup_changes ?? []))) throw new Error("Invalid starter save");
  if (save.version < 14) save.careerStartWeek = 1;
  if (![1, 17].includes(save.careerStartWeek) || (save.careerStartWeek === 17 && save.season === 1 && save.week < 16)) throw new Error("Invalid career start");
  const oneGame = record => record && [record.wins, record.losses, record.ties].every(value => integer(value, 0, 1))
    && record.wins + record.losses + record.ties === 1;
  if (!save.history.every(entry => save.careerStartWeek === 17 && entry.season === 1 ? oneGame(entry.gmRecord) : entry.gmRecord === undefined)
      || (save.careerStartWeek === 17 && (save.season === 1 ? save.lineupChanges : save.career.find(step => step.season === 1)?.lineup_changes ?? []).some(entry => entry.week < 17))) throw new Error("Invalid managed history");
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

function legacyPlayoffRecord(entry) {
  const bounds = {
    "Missed playoffs": [0, 0, 0], "Lost in Wild Card": [0, 0, 1],
    "Lost in Quarterfinals": [0, 1, 1], "Lost in Semifinals": [1, 2, 1],
    "Lost in Championship": [2, 3, 1], "Champions": [3, 4, 0],
  };
  const [minimum, maximum, losses] = bounds[entry.playoffFinish];
  return { minimum, maximum, losses };
}

function validPlayoffSummary(entry) {
  if (entry.playoffWins === undefined && entry.playoffLosses === undefined) return true;
  const bounds = legacyPlayoffRecord(entry);
  return Number.isInteger(entry.playoffWins) && entry.playoffWins >= bounds.minimum
    && entry.playoffWins <= bounds.maximum && entry.playoffLosses === bounds.losses;
}

function historicalPlayoffRecord(entry) {
  return entry.playoffWins === undefined ? legacyPlayoffRecord(entry)
    : { minimum: entry.playoffWins, maximum: entry.playoffWins, losses: entry.playoffLosses };
}

function formatPlayoffRecord(record) {
  return record.minimum === record.maximum ? `${record.minimum}–${record.losses}`
    : `${record.minimum}–${record.maximum} W / ${record.losses} L`;
}

function currentPlayoffRecord() {
  let wins = 0, losses = 0;
  for (const round of playoffState?.rounds ?? []) {
    for (const game of round.games) {
      if (game.home.team.id !== activeTeamId && game.away.team.id !== activeTeamId) continue;
      if (game.winner.team.id === activeTeamId) wins++; else losses++;
    }
  }
  return { wins, losses };
}

// Contract state is derived from completed seasons, never incremented by a render or reload.
function contractStatus(history, season, current = null, startSeason = 1) {
  let end = startSeason + 3, appeared = false, reward = 0, last = null;
  const completed = [...history];
  if (current?.complete) completed.push({ season, ...current });
  for (const entry of completed) {
    if (entry.season < startSeason) continue;
    const qualified = entry.qualified ?? entry.playoffFinish !== "Missed playoffs";
    const champion = entry.champion ?? entry.playoffFinish === "Champions";
    appeared ||= qualified;
    reward = champion ? 5 : qualified ? 2 : entry.wins > entry.losses ? 1 : 0;
    // The opening playoff deadline takes priority over extensions earned for winning records.
    if (entry.season >= startSeason + 3 && !appeared) {
      return { end, remaining: 0, fired: true, reason: "deadline", reward: 0, last: entry };
    }
    end += reward;
    last = entry;
    if (end <= entry.season) return { end, remaining: 0, fired: true, reason: "expired", reward, last };
  }
  const consumed = Math.max(startSeason - 1, current?.complete ? season : season - 1);
  return { end, remaining: Math.max(0, end - consumed), fired: false, reward, last };
}

function currentContract() {
  if (!activeContracts) return null;
  const complete = Boolean(regularSnapshot?.season_complete);
  const qualified = complete && regularSnapshot.standings.playoff_race.some(row => row.team.id === activeTeamId);
  return contractStatus(careerHistory, activeSeason, complete ? {
    complete, qualified, champion: playoffState?.champion?.team.id === activeTeamId,
    ...regularSnapshot.record,
  } : null, activeCareerStartWeek === 17 ? 2 : 1);
}

function careerEnded() { return Boolean(currentContract()?.fired); }

function renderContract() {
  const panel = document.querySelector("#gm-contract");
  panel.hidden = !activeContracts;
  if (!activeContracts) return;
  const state = currentContract();
  const intro = activeCareerStartWeek === 17 && activeSeason === 1;
  document.querySelector("#contract-rules").textContent = activeCareerStartWeek === 17
    ? "Season 1 is introductory: it uses no contract year and earns no extension. Reach the playoffs at least once in Seasons 2–5 or lose the job. Each full season earns only the highest reward: championship +5 years; otherwise playoffs +2; otherwise a winning record +1; otherwise no extension. Extensions add to the contract. After the opening deadline, an expired contract ends your career."
    : "Make the playoffs at least once in your first four seasons or lose the job, even if winning records earn extensions. Each season earns only the highest reward: championship +5 years; otherwise playoffs +2; otherwise a winning record +1; otherwise no extension. Extensions add to the contract. After the opening deadline, an expired contract ends your career.";
  const status = document.querySelector("#contract-status");
  const feedback = document.querySelector("#owner-feedback");
  status.textContent = state.fired ? "Fired · Career over"
    : `${intro ? "Introductory season · " : ""}${state.remaining} ${state.remaining === 1 ? "year" : "years"} remaining · Contract through Season ${state.end}${regularSnapshot?.season_complete ? " (after this season)" : ""}`;
  panel.dataset.outcome = state.fired ? "loss" : state.last && !(state.last.qualified ?? state.last.playoffFinish !== "Missed playoffs") ? "warning" : "neutral";
  if (intro) {
    feedback.textContent = "You're hired as General Manager on a four-year contract covering Seasons 2–5! This introductory season uses no contract year and earns no extension. Learn your team in Week 17, then build through your first draft. The owner will evaluate your four full seasons starting next year.";
  } else if (state.fired) {
    feedback.textContent = state.reason === "deadline"
      ? `The owner has fired you: the team failed to make the playoffs in your ${activeCareerStartWeek === 17 ? "first four full contract seasons" : "first four seasons"}. Your career is over. You can review your team and records or start a new career.`
      : "The owner has not renewed your contract. You have been fired and your career is over. You can review your team and records or start a new career.";
    simulateButton.disabled = true;
    simulateButton.textContent = "Career over";
    playoffsStart.hidden = true;
    playoffSimulate.disabled = true;
    playoffSimulate.textContent = "Career over";
    draftButton.hidden = true;
    nextSeasonButton.hidden = true;
    manageRoster.hidden = true;
  } else if (!state.last) {
    feedback.textContent = activeCareerStartWeek === 17
      ? "Your first full contract season begins. The owner expects improvement: reach the playoffs at least once in Seasons 2–5 or be fired. Build a contender to earn more time."
      : "You're hired as General Manager on a four-year contract! The owner expects improvement: reach the playoffs at least once in your first four seasons or be fired. Build a contender to earn more time.";
  } else {
    const qualified = state.last.qualified ?? state.last.playoffFinish !== "Missed playoffs";
    const champion = state.last.champion ?? state.last.playoffFinish === "Champions";
    const reward = state.reward ? ` Your ${champion ? "championship" : qualified ? "playoff appearance" : "winning record"} earned a ${state.reward}-year extension.` : " No contract extension was earned.";
    feedback.textContent = qualified
      ? `The owner is ${champion ? "delighted with the championship!" : "pleased you reached the playoffs."}${reward}`
      : `The owner is disappointed you missed the playoffs in Season ${state.last.season}. You will be monitored closely: do better next year.${reward}`;
    if (regularSnapshot?.season_complete && qualified && !playoffState?.postseason_complete) {
      feedback.textContent += " A championship would upgrade this season's extension to five years total.";
    }
  }
}

function managedRecord(snapshot, season = activeSeason) {
  const result = { wins: 0, losses: 0, ties: 0 };
  if (!snapshot) return result;
  if (activeCareerStartWeek !== 17 || season !== 1) return { ...snapshot.record };
  for (const game of snapshot.game_results) {
    if (game.week < 17) continue;
    result[game.outcome === "W" ? "wins" : game.outcome === "L" ? "losses" : "ties"]++;
  }
  return result;
}

function renderGMRecords() {
  renderContract();
  const current = currentPlayoffRecord();
  const record = { minimum: current.wins, maximum: current.wins, losses: current.losses };
  const regular = managedRecord(regularSnapshot);
  let appearances = regularSnapshot?.season_complete
    && regularSnapshot.standings.playoff_race.some(row => row.team.id === activeTeamId) ? 1 : 0;
  let championships = playoffState?.champion?.team.id === activeTeamId ? 1 : 0;
  for (const entry of careerHistory) {
    for (const key of ["wins", "losses", "ties"]) regular[key] += (entry.gmRecord ?? entry)[key];
    if (entry.playoffFinish !== "Missed playoffs") appearances++;
    if (entry.playoffFinish === "Champions") championships++;
    const past = historicalPlayoffRecord(entry);
    record.minimum += past.minimum; record.maximum += past.maximum; record.losses += past.losses;
  }
  const city = [...select.options].find(option => option.value === activeTeamId)?.textContent ?? "";
  document.querySelector("#gm-tenure-note").hidden = activeCareerStartWeek !== 17;
  document.querySelector("#gm-team").textContent = `${city} · Season ${activeSeason}`;
  document.querySelector("#gm-regular").textContent = `${regular.wins}–${regular.losses}–${regular.ties}`;
  document.querySelector("#gm-appearances").textContent = appearances;
  document.querySelector("#gm-playoffs").textContent = formatPlayoffRecord(record);
  document.querySelector("#gm-championships").textContent = championships;
  document.querySelector("#gm-legacy-note").hidden = record.minimum === record.maximum;
}

function renderSeasonHistory() {
  const section = document.querySelector("#season-history");
  section.hidden = careerHistory.length === 0;
  const rows = careerHistory.map(entry => {
    const row = document.createElement("tr");
    const champion = [...select.options].find(option => option.value === entry.championId)?.textContent;
    const managed = entry.gmRecord ?? entry;
    const record = `${managed.wins}–${managed.losses}${managed.ties ? `–${managed.ties}` : ""}${entry.gmRecord ? ` (team ${entry.wins}–${entry.losses}${entry.ties ? `–${entry.ties}` : ""})` : ""}`;
    for (const value of [entry.season, record, entry.playoffFinish, formatPlayoffRecord(historicalPlayoffRecord(entry)), champion]) {
      const cell = document.createElement("td"); cell.textContent = value; row.append(cell);
    }
    return row;
  });
  document.querySelector("#season-history-rows").replaceChildren(...rows);
}

async function resumeProgress() {
  if (restoring || weekSimulationBusy) return;
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
    // Warm the shared career replay once before dependent endpoints request it.
    // lru_cache does not coalesce simultaneous misses in FastAPI's worker threads.
    const profileRequest = hasLineupContext(save) ? careerRequest("profile", {}, save) : null;
    const payloads = await Promise.all(requests.map(async url => {
      if (profileRequest) {
        if (url.startsWith("/api/team/")) return profileRequest;
        if (url.startsWith("/api/season/")) {
          await profileRequest;
          return careerRequest("week", { week: save.week }, save);
        }
        if (url.startsWith("/api/playoffs/")) {
          await profileRequest;
          return careerRequest("playoffs", { round_number: save.playoffRound }, save);
        }
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
    renderSchedule(schedule, save.runSeed, { priorStandings: save.priorStandings, history: save.history, career: save.career, lineupRules: save.lineupRules, developmentStart: save.developmentStart, rebuildTeam: save.rebuildTeam, contracts: save.contracts, lineupChanges: save.lineupChanges, careerStartWeek: save.careerStartWeek, draftRounds: save.draftRounds });
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
    updateSimulationControls();
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
    } else if (hasLineupContext()) profile = await careerRequest("profile", { view_team: teamId });
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

function addPotentialArrow(cell, player) {
  const delta = player.potential_change ?? 0;
  if (!delta) return;
  const trend = document.createElement("span");
  trend.className = `potential-change ${delta > 0 ? "improved" : "declined"}`;
  trend.textContent = ` ${delta > 0 ? "↑ +" : "↓ "}${delta}`;
  const origin = player.rookie_outcome ? "draft estimate" : "previous season";
  trend.title = `Potential change from ${origin}`;
  trend.setAttribute("aria-label", `Potential ${delta > 0 ? "increased" : "decreased"} by ${Math.abs(delta)}, from ${player.potential_rating-delta} to ${player.potential_rating}`);
  cell.append(trend);
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
      addPotentialArrow(row.children[4], player);
      const delta = player.rating_change ?? 0;
      if (delta) {
        const trend = document.createElement("span");
        trend.className = `rating-change ${delta > 0 ? "improved" : "declined"}`;
        trend.textContent = ` ${delta > 0 ? "↑ +" : "↓ "}${delta}`;
        trend.title = player.rookie_outcome ? "Current rating change from draft estimate" : "Change since last offseason";
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
  if (profile.lineup_rules >= 7) document.querySelector("#development-note").textContent += " At their first season start, rookies have a 15% boom / 15% bust / 70% normal reassessment. Potential arrows show changes from draft estimates or the previous season.";
  rosterSection.hidden = false;
  renderRosterStats();
  renderStarterEditor();
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

function hasLineupContext(context = null) {
  return Boolean((context?.career ?? activeCareer).length || (context?.lineupChanges ?? activeLineupChanges).length);
}

function nextLineupWeek() { return currentWeek < 17 ? currentWeek + 1 : 18 + completedPlayoffRound; }

function canChooseStarters() {
  if (!activeTeamId || !rosterProfile || lineupBusy || playoffBusy || restoring || weekSimulationBusy || advancingSeason || draftBusy || cutBusy || careerEnded()) return false;
  if (currentWeek < 17) return true;
  if (playoffState) return playoffState.qualified && !playoffState.eliminated && !playoffState.postseason_complete;
  return Boolean(regularSnapshot?.standings.playoff_race.some(row => row.team.id === activeTeamId));
}

function updateStarterControls() {
  const disabled = !canChooseStarters();
  for (const control of document.querySelectorAll("#starter-form select, #starter-form button")) control.disabled = disabled;
  document.querySelector("#starter-timing").textContent = careerEnded() ? "Your career has ended. This lineup is read-only."
    : currentWeek === 17 && !canChooseStarters() && !lineupBusy && !playoffBusy && !restoring && !weekSimulationBusy
      ? "No games remain for your team this season. Retained starter choices carry into next season."
    : currentWeek < 17
    ? `Changes apply from Week ${currentWeek + 1}. Completed games stay unchanged.`
    : `Changes apply to your next playoff game. Completed rounds and playoff seeds stay unchanged.`;
}

function renderStarterEditor() {
  if (!rosterProfile) return;
  const fields = document.querySelector("#starter-fields");
  fields.replaceChildren();
  for (const rule of rosterProfile.roster_rules) {
    const fieldset = document.createElement("fieldset");
    const legend = document.createElement("legend"); legend.textContent = `${rule.position} · ${rule.minimum} ${rule.minimum === 1 ? "starter" : "starters"}`;
    fieldset.append(legend);
    const players = rosterProfile.roster.filter(p => p.position === rule.position).sort((a,b) => a.depth-b.depth);
    for (let slot = 0; slot < rule.minimum; slot++) {
      const label = document.createElement("label"); label.textContent = `Starter ${slot + 1}`;
      const choice = document.createElement("select"); choice.dataset.starterPosition = rule.position;
      choice.setAttribute("aria-label", `${rule.position} starter ${slot + 1}`);
      for (const player of players) choice.add(new Option(`${player.name} · Current ${player.current_rating} · Age ${player.age}`, player.id));
      choice.value = players[slot].id;
      label.append(choice); fieldset.append(label);
    }
    fields.append(fieldset);
  }
  updateStarterControls();
}

function carriedStarters() {
  const preferred = activeLineupChanges.at(-1)?.starters ?? [];
  if (!preferred.length || !rosterProfile) return [];
  return rosterProfile.roster_rules.flatMap(rule => {
    const group = rosterProfile.roster.filter(p => p.position === rule.position).sort((a,b) => b.current_rating-a.current_rating || a.depth-b.depth || a.id.localeCompare(b.id));
    const retained = group.filter(p => preferred.includes(p.id)).slice(0,rule.minimum);
    return [...retained, ...group.filter(p => !retained.includes(p)).slice(0,rule.minimum-retained.length)].map(p => p.id);
  });
}

async function saveStarters(starters) {
  if (!canChooseStarters()) return;
  const status = document.querySelector("#starter-status");
  if (new Set(starters).size !== starters.length) {
    status.textContent = "Choose a different player for each starter slot.";
    return;
  }
  const week = nextLineupWeek();
  const changes = [...activeLineupChanges.filter(entry => entry.week < week), { week, starters }];
  lineupBusy = true;
  status.textContent = "Saving starters…";
  updateSimulationControls();
  playoffsStart.disabled = true;
  playoffSimulate.disabled = true;
  try {
    const profile = await careerRequest("profile", { lineup_changes: changes });
    if (profile.team?.id !== activeTeamId || profile.run_seed !== activeRunSeed) throw new Error("Starters could not be saved.");
    const totals = rosterTotals, mode = rosterMode, competition = rosterCompetition.value;
    const collapsed = [...document.querySelectorAll("#roster-groups .roster-group")].filter(group => !group.open).map(group => group.dataset.position);
    activeLineupChanges = changes;
    renderTeamProfile(profile, rookieSeason);
    rosterTotals = totals; rosterMode = mode; rosterCompetition.value = competition;
    renderRosterStats();
    for (const position of collapsed) document.querySelector(`#roster-groups [data-position="${position}"]`).open = false;
    saveProgress();
    status.textContent = starters.length ? `Starters saved for ${week <= 17 ? `Week ${week}` : "your next playoff game"}.` : "Best available starters selected for your next game.";
  } catch (error) {
    status.textContent = `${error.message} Your previous lineup is unchanged. Try again.`;
  } finally {
    lineupBusy = false;
    updateSimulationControls();
    playoffsStart.disabled = false;
    playoffSimulate.disabled = careerEnded() || (playoffState?.postseason_complete ?? false);
  }
}

document.querySelector("#starter-form").addEventListener("submit", event => {
  event.preventDefault();
  saveStarters([...document.querySelectorAll("#starter-fields select")].map(choice => choice.value));
});
document.querySelector("#auto-starters").addEventListener("click", () => saveStarters([]));
document.querySelector("#cancel-starters").addEventListener("click", () => {
  if (lineupBusy) return;
  renderStarterEditor(); document.querySelector("#starter-editor").open = false;
  document.querySelector("#starter-status").textContent = "";
});

function createRunSeed() {
  const candidate = crypto.getRandomValues(new Uint32Array(1))[0] || 1;
  return candidate === activeRunSeed ? (candidate % 4294967295) + 1 : candidate;
}

function renderSchedule(data, runSeed, { priorStandings = {}, history = [], career = [], lineupRules = 7, developmentStart = 1, rebuildTeam = null, contracts = true, lineupChanges = [], careerStartWeek = 1, draftRounds = 6 } = {}) {
  if (rosterDialog.open) rosterDialog.close();
  weekSimulationBusy = false;
  seasonSimulationActive = false;
  stopSeasonRequested = false;
  activeTeamId = data.team.id;
  activeRunSeed = runSeed;
  activeSeason = data.season;
  activeCareerStartWeek = careerStartWeek;
  activeDraftRounds = draftRounds;
  document.querySelector("#career-start-note").hidden = careerStartWeek !== 17 || activeSeason !== 1;
  activeLineupRules = lineupRules;
  activeDevelopmentStart = developmentStart;
  activeRebuildTeam = rebuildTeam;
  document.querySelector("#rebuild-note").hidden = !rebuildTeam || activeSeason !== 1;
  document.querySelector("#rating-method").textContent = lineupRules >= 2
    ? "Team ratings: 80% starters + 20% bench, using current ability. Kickers are separate. Highlighted players are starters."
    : "This saved season keeps its original rating formula. Starter choices affect future games; 80%/20% team ratings apply next season.";
  activePriorStandings = priorStandings;
  careerHistory = history;
  activeContracts = contracts;
  regularSnapshot = null;
  activeDraftChoices = null;
  draftState = null;
  activeDropped = [];
  activeCareer = career;
  activeLineupChanges = lineupChanges;
  document.querySelector("#starter-editor").open = false;
  document.querySelector("#starter-status").textContent = "";
  manageRoster.hidden = true;
  rosterManagement.hidden = true;
  document.querySelector("#cut-confirmation").hidden = true;
  document.querySelector("#cut-error").hidden = true;
  pendingCut = null;
  renderCuts();
  draftPendingChoice = null;
  draftPendingAuto = false;
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
  renderQualification(null);
  renderGMRecords();
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
  simulateButton.disabled = careerEnded();
  resultPanel.hidden = true;
  leagueResultsSection.hidden = true;
  standingsSection.hidden = true;
  playoffSection.hidden = true;
  franchiseSetup.hidden = true;
  scheduleSection.hidden = false;
  document.querySelector("#team-name").focus({ preventScroll: true });
  scheduleSection.scrollIntoView({ behavior: "smooth", block: "start" });
  seasonSimulationStatus.textContent = "";
  seasonSimulationStatus.hidden = true;
  updateSimulationControls();
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

function renderQualification(data) {
  const status = document.querySelector("#qualification-status");
  status.hidden = !data?.season_complete;
  status.textContent = "";
  status.dataset.outcome = "neutral";
  if (status.hidden) return;
  const entry = data.standings.playoff_race.find(row => row.team.id === data.team.id);
  const { wins, losses, ties } = data.record;
  const record = `${wins}–${losses}${ties ? `–${ties}` : ""}`;
  status.dataset.outcome = entry ? "win" : "loss";
  status.textContent = entry
    ? `Congratulations! ${data.team.city} qualified for the Season ${data.season} playoffs as seed #${entry.seed} (${entry.qualification}). Final record: ${record}.${entry.bye ? " You earned a first-round bye." : ""}`
    : `Sorry! ${data.team.city} missed the Season ${data.season} playoffs. Final record: ${record}.`;
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
  document.querySelector("#result-week").textContent = `Week ${data.week} final${activeCareerStartWeek === 17 && activeSeason === 1 && data.week < 17 ? " · Before your hiring" : ""}${latestResult.overtime ? " · OT" : ""}`;
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
  if (activeCareerStartWeek === 17 && activeSeason === 1 && data.week === 16) {
    document.querySelector("#season-status").textContent = "You take over before Week 17. One regular-season game remains before your first offseason.";
  }
  renderQualification(data);
  renderGMRecords();
  updateSimulationControls();
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
  if (lineupBusy || playoffBusy || seasonSimulationActive || restoring) return;
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
  if (lineupBusy || playoffBusy || seasonSimulationActive || restoring || !select.value) return;
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
    const [scheduleResponse, profileResponse, regularResponse] = await Promise.all([
      fetch(`/api/schedule/${teamId}?season=1`),
      fetch(`/api/team/${teamId}?run_seed=${runSeed}&lineup_rules=7&season=1&development_start=1${rebuildQuery(teamId)}`),
      fetch(`/api/season/${teamId}/week/16?run_seed=${runSeed}&lineup_rules=7&season=1&development_start=1${rebuildQuery(teamId)}`),
    ]);
    if (!scheduleResponse.ok || !profileResponse.ok || !regularResponse.ok) {
      throw new Error("Your team could not be loaded. Please try again.");
    }
    const [schedule, profile, regular] = await Promise.all([
      scheduleResponse.json(), profileResponse.json(), regularResponse.json(),
    ]);
    if (profile.run_seed !== runSeed || profile.team.id !== teamId || profile.lineup_rules !== 7 || profile.rebuild_team !== teamId
        || schedule.team?.id !== teamId || schedule.season !== 1 || regular.team?.id !== teamId
        || regular.season !== 1 || regular.week !== 16 || regular.run_seed !== runSeed) {
      throw new Error("Your team could not be loaded. Please try again.");
    }
    renderTeamProfile(profile, 1);
    renderSchedule(schedule, runSeed, { rebuildTeam: teamId, careerStartWeek: 17 });
    renderResult(regular);
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

function updateSimulationControls() {
  const ended = careerEnded();
  const complete = currentWeek >= 17;
  const disabled = lineupBusy || weekSimulationBusy || restoring || !activeTeamId || complete || ended;
  simulateButton.disabled = disabled;
  simulateSeasonButton.disabled = disabled;
  simulateButton.textContent = ended ? "Career over" : complete ? "Regular season complete"
    : weekSimulationBusy ? "Simulating…" : `Simulate Week ${currentWeek + 1}`;
  simulateSeasonButton.textContent = seasonSimulationActive ? `Simulating Week ${Math.min(17, currentWeek + 1)} of 17…` : "Simulate remaining season";
  stopSeasonButton.hidden = !seasonSimulationActive;
  stopSeasonButton.disabled = stopSeasonRequested;
  document.querySelector("#change-team-button").disabled = lineupBusy || seasonSimulationActive;
  updateStarterControls();
}

async function simulateWeeks(wholeSeason = false) {
  if (lineupBusy || weekSimulationBusy || restoring || advancingSeason || careerEnded() || !activeTeamId || currentWeek >= 17
      || form.querySelector('button[type="submit"]').disabled) return;
  weekSimulationBusy = true;
  seasonSimulationActive = wholeSeason;
  stopSeasonRequested = false;
  seasonSimulationStatus.textContent = "";
  seasonSimulationStatus.hidden = !wholeSeason;
  errorBox.hidden = true;
  const teamId = activeTeamId, runSeed = activeRunSeed, season = activeSeason;
  const sameCareer = () => teamId === activeTeamId && runSeed === activeRunSeed && season === activeSeason;
  try {
    do {
      if (!sameCareer() || careerEnded() || stopSeasonRequested || currentWeek >= 17) break;
      const nextWeek = currentWeek + 1;
      updateSimulationControls();
      if (wholeSeason) seasonSimulationStatus.textContent = `Simulating Week ${nextWeek} of 17… Each completed week is saved.`;
      let data;
      if (hasLineupContext()) data = await careerRequest("week", { week: nextWeek });
      else {
        const response = await fetch(`/api/season/${teamId}/week/${nextWeek}?season=${season}&run_seed=${runSeed}${priorStandingsQuery()}&lineup_rules=${activeLineupRules}&development_start=${activeDevelopmentStart ?? 1}${rebuildQuery()}`);
        if (!response.ok) throw new Error("The week could not be simulated.");
        data = await response.json();
      }
      if (!sameCareer()) return;
      if (data.team?.id !== teamId || data.run_seed !== runSeed || data.season !== season || data.week !== nextWeek) {
        throw new Error("The week could not be loaded correctly. Please try again.");
      }
      renderResult(data);
      saveProgress();
    } while (wholeSeason);
    if (wholeSeason && sameCareer()) seasonSimulationStatus.textContent = careerEnded()
      ? "Regular season complete. Your GM career has ended; you can review your results and records."
      : currentWeek === 17 ? "Regular season complete. Review your results, then choose View playoffs to continue."
      : `Stopped after Week ${currentWeek}. Continue one week at a time or simulate the remaining season.`;
  } catch (error) {
    if (!sameCareer()) return;
    if (wholeSeason) seasonSimulationStatus.textContent = `Stopped after Week ${currentWeek}. Your completed weeks are kept. Try again to continue with Week ${currentWeek + 1}.`;
    showError(error.message);
  } finally {
    if (sameCareer()) {
      weekSimulationBusy = false;
      seasonSimulationActive = false;
      stopSeasonRequested = false;
      updateSimulationControls();
    }
  }
}

simulateButton.addEventListener("click", () => simulateWeeks());
simulateSeasonButton.addEventListener("click", () => simulateWeeks(true));
stopSeasonButton.addEventListener("click", () => {
  if (!seasonSimulationActive) return;
  stopSeasonRequested = true;
  stopSeasonButton.disabled = true;
  seasonSimulationStatus.textContent = "Stopping after the current week finishes…";
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

function updateOffseasonActions() {
  const finished = !careerEnded() && Boolean(playoffState?.postseason_complete) && activeSeason < 999;
  const drafted = Boolean(draftState?.complete) && activeDraftChoices?.length === activeDraftRounds;
  const oversized = (rosterProfile?.roster.length ?? 0) > 38;
  draftButton.hidden = !finished;
  nextSeasonButton.hidden = !finished || !drafted;
  nextSeasonButton.disabled = !finished || !drafted || oversized || draftBusy || cutBusy || advancingSeason;
  nextSeasonButton.textContent = !drafted ? "Finish rookie draft" : oversized ? "Roster limit: 38" : `Continue to Season ${activeSeason + 1}`;
}

function renderPostseason(data) {
  rosterTotals.playoffs = data.roster_stats;
  renderRosterStats();
  playoffState = data;
  completedPlayoffRound = data.completed_round;
  renderGMRecords();
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
  updateOffseasonActions();
  updateStarterControls();
  playoffSimulate.disabled = careerEnded() || data.postseason_complete;
  playoffSimulate.textContent = careerEnded() ? "Career over" : data.upcoming ? `Simulate ${data.upcoming.name}` : "Postseason complete";

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
  if (playoffBusy || lineupBusy || careerEnded()) return;
  playoffBusy = true;
  updateStarterControls();
  errorBox.hidden = true;
  playoffsStart.disabled = true;
  playoffSimulate.disabled = true;
  document.querySelector("#change-team-button").disabled = true;
  try {
    let data;
    if (hasLineupContext()) data = await careerRequest("playoffs", { round_number: number });
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
    playoffBusy = false;
    updateStarterControls();
    playoffsStart.disabled = false;
    document.querySelector("#change-team-button").disabled = false;
    playoffSimulate.disabled = careerEnded() || (playoffState?.postseason_complete ?? false);
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
    body: JSON.stringify({ action, draft_rounds: context?.draftRounds ?? activeDraftRounds, season: context?.season ?? activeSeason,
      run_seed: context?.runSeed ?? activeRunSeed,
      prior_standings: Object.keys(ranks).length ? ranks : null,
      career: context?.career ?? activeCareer, lineup_changes: context?.lineupChanges ?? activeLineupChanges, lineup_rules: context?.lineupRules ?? activeLineupRules, development_start: context?.developmentStart ?? activeDevelopmentStart ?? 1, rebuild_team: rebuildOrigin(context), ...extra }),
  });
  if (!response.ok) {
    let detail;
    try { const data = await response.json(); if (typeof data.detail === "string") detail = data.detail; } catch {}
    throw new Error(detail ?? "Roster progress could not be loaded. Please try again.");
  }
  return response.json();
}

function draftChoicesMatch(data, choices, autoDraft, rounds) {
  if (data.rounds !== rounds) return false;
  if (!autoDraft) return JSON.stringify(data.manual_picks) === JSON.stringify(choices);
  return data.complete && Array.isArray(data.manual_picks) && data.manual_picks.length === rounds
    && choices.every((id, index) => data.manual_picks[index] === id);
}

async function fetchDraft(choices, context = null, autoDraft = false) {
  const teamId = context?.teamId ?? activeTeamId;
  const season = context?.season ?? activeSeason;
  const seed = context?.runSeed ?? activeRunSeed;
  const ranks = context?.priorStandings ?? activePriorStandings;
  const dropped = context?.dropped ?? activeDropped;
  if (hasLineupContext(context) || dropped.length) {
    const data = await careerRequest(dropped.length ? "cuts" : "draft", { manual_picks: choices, dropped, auto_draft: autoDraft }, context);
    if (data.team.id !== teamId || data.season !== season || data.run_seed !== seed
        || !draftChoicesMatch(data, choices, autoDraft, context?.draftRounds ?? activeDraftRounds)) throw new Error("Draft could not be restored.");
    return data;
  }
  const response = await fetch(`/api/draft/${teamId}`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ draft_rounds: context?.draftRounds ?? activeDraftRounds, season, run_seed: seed, lineup_rules: context?.lineupRules ?? activeLineupRules, development_start: context?.developmentStart ?? activeDevelopmentStart ?? 1, rebuild_team: rebuildOrigin(context),
      prior_standings: Object.keys(ranks).length ? ranks : null, manual_picks: choices, auto_draft: autoDraft }),
  });
  if (!response.ok) throw new Error("The draft could not be loaded. Please try again.");
  const data = await response.json();
  if (data.team.id !== teamId || data.season !== season || data.run_seed !== seed
      || !draftChoicesMatch(data, choices, autoDraft, context?.draftRounds ?? activeDraftRounds)) {
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
  updateOffseasonActions();
  manageRoster.hidden = careerEnded() || !data.complete;
  draftButton.textContent = data.complete ? "Review draft" : "Resume draft";
  const summary = document.querySelector("#draft-summary");
  summary.hidden = false;
  summary.textContent = data.complete
    ? `Draft complete · ${count}/38 players. ${count > 38 ? "Use Manage roster to drop players before the next season." : "Roster ready for next season."}`
    : `Draft in progress · ${activeDraftChoices.length} of ${activeDraftRounds} picks made · ${count} players.`;
  renderDraft();
  renderCuts();
  renderStarterEditor();
}

function renderDraft() {
  if (!draftState) return;
  autoDraftButton.disabled = draftBusy || draftState.complete;
  document.querySelector("#draft-title").textContent = `Season ${draftState.draft_season} rookie draft`;
  document.querySelector("#draft-status").textContent = draftState.complete
    ? `All ${draftState.total_picks} picks are complete. Your ${draftState.rounds} rookies have joined your offseason roster.`
    : `Your turn · Round ${draftState.next_round} of ${draftState.rounds} · Overall pick ${draftState.next_pick} of ${draftState.total_picks}`;
  document.querySelector("#draft-format").textContent = `${draftState.rounds} rounds · Same order each round · CPU teams balance player quality and position needs. Rookies join your roster without replacing anyone. The regular-season limit is 38.`;
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

async function loadDraft(choice = null, autoDraft = false) {
  if (lineupBusy || careerEnded() || draftBusy || advancingSeason || !playoffState?.postseason_complete || activeSeason >= 999) return;
  if (autoDraft && draftState?.complete) return;
  draftBusy = true;
  draftPendingChoice = choice;
  draftPendingAuto = autoDraft;
  autoDraftButton.disabled = true;
  draftButton.disabled = true;
  document.querySelector("#change-team-button").disabled = true;
  nextSeasonButton.disabled = true;
  document.querySelector("#draft-error").hidden = true;
  document.querySelector("#draft-retry").hidden = true;
  if (!draftDialog.open) draftDialog.showModal();
  if (draftState) renderDraft();
  document.querySelector("#draft-status").textContent = autoDraft ? "Auto-drafting your remaining picks…" : choice ? "Recording your pick and simulating CPU picks…" : "Loading rookie draft…";
  const teamId = activeTeamId, seed = activeRunSeed, season = activeSeason;
  const choices = [...(activeDraftChoices ?? []), ...(choice ? [choice] : [])];
  try {
    const data = await fetchDraft(choices, null, autoDraft);
    if (teamId !== activeTeamId || seed !== activeRunSeed || season !== activeSeason) return;
    applyDraft(data);
    saveProgress();
    draftPendingChoice = null;
    draftPendingAuto = false;
  } catch (error) {
    if (teamId !== activeTeamId || seed !== activeRunSeed || season !== activeSeason) return;
    document.querySelector("#draft-error").textContent = error.message;
    document.querySelector("#draft-error").hidden = false;
    document.querySelector("#draft-retry").hidden = false;
  } finally {
    draftBusy = false;
    draftButton.disabled = false;
    document.querySelector("#change-team-button").disabled = false;
    updateOffseasonActions();
    if (draftState) renderDraft();
    else {
      document.querySelector("#draft-status").textContent = "Draft not started. Your saved season is unchanged.";
    }
  }
}
draftButton.addEventListener("click", () => {
  if (draftState) { renderDraft(); if (!draftDialog.open) draftDialog.showModal(); }
  else loadDraft();
});
document.querySelector("#draft-close").addEventListener("click", () => draftDialog.close());
document.querySelector("#draft-position").addEventListener("change", renderDraft);
document.querySelector("#draft-retry").addEventListener("click", () => loadDraft(draftPendingChoice, draftPendingAuto));
autoDraftButton.addEventListener("click", () => loadDraft(null, true));
document.querySelector("#draft-prospects").addEventListener("click", event => {
  const button = event.target.closest("[data-draft-id]");
  if (button && !button.disabled) loadDraft(button.dataset.draftId);
});

function renderCuts() {
  const available = !careerEnded() && Boolean(draftState?.complete);
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
  if (careerEnded() || !draftState?.complete || cutBusy || advancingSeason) return;
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
  if (careerEnded() || !button || button.disabled || cutBusy || advancingSeason || !draftState?.complete) return;
  pendingCut = button.dataset.dropId;
  const player = rosterProfile.roster.find(p => p.id === pendingCut);
  document.querySelector("#cut-error").hidden = true;
  document.querySelector("#cut-confirm-text").textContent = `Drop ${player.name} (${player.position})? This removes the player from your next-season roster.`;
  document.querySelector("#cut-confirmation").hidden = false;
  document.querySelector("#cut-confirm").focus();
});
document.querySelector("#cut-confirm").addEventListener("click", async () => {
  if (lineupBusy || careerEnded() || !pendingCut || cutBusy || advancingSeason || !draftState?.complete) return;
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
    updateOffseasonActions();
    renderCuts();
  }
});

nextSeasonButton.addEventListener("click", async () => {
  if (lineupBusy || careerEnded() || advancingSeason || nextSeasonButton.disabled || (activeDraftChoices?.length !== activeDraftRounds || !draftState?.complete || rosterProfile.roster.length > 38) || cutBusy || draftBusy || !playoffState?.postseason_complete || !regularSnapshot || activeSeason >= 999) return;
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
    ...(activeCareerStartWeek === 17 && activeSeason === 1 ? { gmRecord: managedRecord(regularSnapshot) } : {}),
    championId: playoffState.champion.team.id,
    playoffWins: currentPlayoffRecord().wins, playoffLosses: currentPlayoffRecord().losses,
    playoffFinish: playoffState.champion.team.id === activeTeamId ? "Champions"
      : !playoffState.qualified ? "Missed playoffs" : `Lost in ${lastOwnRound.name}` };
  try {
    const developmentStart = activeDevelopmentStart ?? nextSeason;
    const lineupRules = 7;
    const carried = carriedStarters();
    const lineupChanges = carried.length ? [{ week: 1, starters: carried }] : [];
    const career = [...activeCareer, {
      season: activeSeason, prior_standings: Object.keys(activePriorStandings).length ? activePriorStandings : null,
      manual_picks: activeDraftChoices, draft_rounds: activeDraftRounds, dropped: activeDropped, lineup_rules: activeLineupRules,
      ...(activeLineupChanges.length ? { lineup_changes: activeLineupChanges } : {}),
    }];
    const response = await fetch(`/api/schedule/${activeTeamId}?season=${nextSeason}${priorStandingsQuery(ranks)}`);
    if (!response.ok) throw new Error("The next season could not be loaded. Please try again.");
    const schedule = await response.json();
    if (schedule.team.id !== activeTeamId || schedule.season !== nextSeason) {
      throw new Error("The next season could not be loaded. Please try again.");
    }
    const history = [...careerHistory, summary];
    const profile = await careerRequest("profile", { season: nextSeason, career, lineup_rules: lineupRules, development_start: developmentStart, lineup_changes: lineupChanges });
    if (profile.team?.id !== activeTeamId || profile.run_seed !== activeRunSeed || profile.lineup_rules !== lineupRules) {
      throw new Error("The next season could not be loaded. Please try again.");
    }
    renderTeamProfile(profile, nextSeason);
    renderSchedule(schedule, activeRunSeed, { priorStandings: ranks, history, career, lineupRules, developmentStart, rebuildTeam: activeRebuildTeam, contracts: activeContracts, lineupChanges, careerStartWeek: activeCareerStartWeek });
    saveProgress();
  } catch (error) {
    showError(error.message);
  } finally {
    advancingSeason = false;
    updateOffseasonActions();
    manageRoster.disabled = false;
    renderCuts();
    draftButton.disabled = false;
    document.querySelector("#change-team-button").disabled = false;
  }
});

loadTeams();
