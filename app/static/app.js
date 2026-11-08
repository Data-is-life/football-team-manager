const form = document.querySelector("#team-form");
const select = document.querySelector("#team-select");
const scheduleSection = document.querySelector("#schedule-section");
const scheduleList = document.querySelector("#schedule");
const errorBox = document.querySelector("#error");
const simulateButton = document.querySelector("#simulate-button");
const simulateSeasonButton = document.querySelector("#simulate-season");
const simulationMore = document.querySelector("#simulation-more");
const seasonConfirmDialog = document.querySelector("#season-confirm-dialog");
let pendingSeasonSimulation = null;
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
let activeLineupRules = 26;
let activeDevelopmentStart = 1;
let activeRebuildTeam = null;
let activePriorStandings = {};
let careerHistory = [];
let activeContracts = true;
let welcomeDismissed = true;
let ownerUpdateDismissed = 0;
let regularSnapshot = null;
let activeDraftChoices = null;
let activeDraftRounds = 6;
let draftState = null;
let activeTrainingCamp = false;
let campBusy = false;
const campButton = document.querySelector("#training-camp-button");
let activeDropped = [];
let activeRosterActions = [];
let activeCareer = [];
let activeLineupChanges = [];
let playoffBusy = false;
let cutBusy = false;
let advancingSeason = false;
let pendingCut = null;
let pendingRosterKind = "drop";
const rosterManagement = document.querySelector("#roster-management");
const cutConfirmation = document.querySelector("#cut-confirmation");
const manageRoster = document.querySelector("#manage-roster");
let draftBusy = false;
let draftPendingChoice = null;
let draftPendingAuto = false;
const draftButton = document.querySelector("#draft-button");
const draftPanel = document.querySelector("#panel-draft");
let draftScrollPending = false;
// Retained for a future opt-in return; manual drafting is the current UI.
const AUTO_DRAFT_ENABLED = false;
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
let seasonRetirees = [];
let rookieSeason = 1;
let developmentRecap = null;
const developmentDialog = document.querySelector("#development-dialog");
let rosterMode = "ratings";
let rosterTotals = null;
const rosterDialog = document.querySelector("#team-roster-dialog");
// Retained for later: set true to restore the League Leaders launcher in Standings.
const LEAGUE_LEADERS_ENABLED = false;
const leadersDialog = document.querySelector("#leaders-dialog");
const leadersButton = document.querySelector("#league-leaders-button");
leadersButton.hidden = !LEAGUE_LEADERS_ENABLED;
leadersDialog.hidden = !LEAGUE_LEADERS_ENABLED;
let leadersRequest = 0;
let leadersBusy = false;
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
  const save = { version: 36, welcomeDismissed, ownerUpdateDismissed, draftRounds: activeDraftRounds, careerStartWeek: activeCareerStartWeek, lineupChanges: activeLineupChanges, contracts: activeContracts, teamId: activeTeamId, runSeed: activeRunSeed,
    season: activeSeason, week: currentWeek, lineupRules: activeLineupRules, developmentStart: activeDevelopmentStart, rebuildTeam: activeRebuildTeam,
    priorStandings: activePriorStandings, history: careerHistory,
    draftChoices: activeDraftChoices,
    ...(activeTrainingCamp ? { trainingCamp: true } : {}),
    dropped: activeDropped, career: activeCareer,
    ...(activeRosterActions.length ? { rosterActions: activeRosterActions } : {}),
    ...(document.querySelector("#draft-position").value ? { draftPosition: document.querySelector("#draft-position").value } : {}),
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
  if (!save || ![1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36].includes(save.version) || typeof save.teamId !== "string"
      || ![...select.options].some(option => option.value && option.value === save.teamId)
      || !integer(save.runSeed, 0, 4294967295) || !integer(save.season, 1, 999)
      || !integer(save.week, 0, 17)
      || !(save.playoffRound === null || (save.week === 17 && integer(save.playoffRound, 0, 4)))) {
    throw new Error("Invalid save");
  }
  if (save.ownerUpdateDismissed === undefined) save.ownerUpdateDismissed = 0;
  if (!integer(save.ownerUpdateDismissed, 0, save.season)) throw new Error("Invalid owner update state");
  if (save.version < 19) save.welcomeDismissed = true;
  if (typeof save.welcomeDismissed !== "boolean") throw new Error("Invalid welcome state");
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
  if (save.draftPosition !== undefined && ![...document.querySelector("#draft-position").options].some(option => option.value === save.draftPosition)) throw new Error("Invalid draft filter");
  if (save.version < 5) save.lineupRules = 1;
  if (![1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26].includes(save.lineupRules)) throw new Error("Invalid lineup rules");
  if (save.trainingCamp !== undefined && typeof save.trainingCamp !== "boolean") throw new Error("Invalid camp save");
  if (save.trainingCamp && (save.lineupRules < 18 || save.draftChoices?.length !== save.draftRounds || save.week !== 17 || save.playoffRound !== 4)) throw new Error("Invalid camp checkpoint");
  if ([15, 16, 17, 18].includes(save.lineupRules) && save.draftChoices === null) save.lineupRules = 20;
  if (save.lineupRules === 17 && save.dropped.length === 0) save.lineupRules = 18;
  if (save.lineupRules === 19) {
    save.lineupRules = 20;
    save.rosterActions = save.dropped.map(player_id => ({ kind: "drop", player_id }));
  }
  // Inherited deals and completed history retain their original prices. An
  // accepted current-camp renewal must replay under its original market too.
  if (save.lineupRules === 20 && !(save.rosterActions ?? []).some(a => a?.kind === "resign")) save.lineupRules = 21;
  // Never add guarantees retroactively to a current camp's accepted decisions.
  if (save.lineupRules === 22 && !(save.rosterActions ?? []).length) save.lineupRules = 23;
  // Keep accepted camp cuts on their original refill/minimum policy.
  if (save.lineupRules === 23 && !(save.rosterActions ?? []).length) save.lineupRules = 24;
  // Accepted current-camp renewals must replay at the price already agreed.
  if (save.lineupRules === 25 && !(save.rosterActions ?? []).some(a => a?.kind === "resign")) save.lineupRules = 26;
  const validActions = (actions, dropped, rules) => Array.isArray(actions) && actions.length <= 132
    && (!actions.length || rules >= 20) && actions.every(a => a && ["drop", "resign"].includes(a.kind) && typeof a.player_id === "string" && a.player_id.length > 0 && a.player_id.length <= 100)
    && (rules < 20 || JSON.stringify(actions.filter(a => a.kind === "drop").map(a => a.player_id)) === JSON.stringify(dropped));
  save.rosterActions ??= [];
  if (!validActions(save.rosterActions,save.dropped,save.lineupRules) || (save.rosterActions.length && !save.trainingCamp)
      || !save.career.every(step => validActions(step.roster_actions ?? [],step.dropped,step.lineup_rules ?? 1))) throw new Error("Invalid roster decisions");
  if (save.lineupRules >= 18 && save.dropped.length && !save.trainingCamp) throw new Error("Cuts require a camp checkpoint");
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
  // Rules 12→13 change future roster decisions only. Historical seasons and
  // unfinished drafts keep their original rules and release replay.
  if (save.lineupRules === 12 && save.draftChoices === null) save.lineupRules = 13;
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
  document.querySelector("#owner-update").hidden = true;
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
  renderOwnerUpdate(state, intro);
}

function renderOwnerUpdate(state, intro) {
  const update = document.querySelector("#owner-update");
  const qualified = regularSnapshot?.season_complete && regularSnapshot.standings.playoff_race.some(row => row.team.id === activeTeamId);
  const finished = Boolean(regularSnapshot?.season_complete && (!qualified || playoffState?.eliminated || playoffState?.postseason_complete));
  update.hidden = !state.fired && (activeDraftChoices !== null || !finished || ownerUpdateDismissed === activeSeason);
  if (update.hidden) return;
  const champion = playoffState?.champion?.team.id === activeTeamId;
  const reward = state.reward ? ` ${state.reward}-year extension.` : " No extension.";
  document.querySelector("#owner-update-text").textContent = state.fired
    ? "The owner has ended your contract. You have been fired; your career is over. Review GM Records or start a new career."
    : intro ? `Season ${activeSeason} complete. Your introductory season earns no extension; your four full contract seasons begin next year.`
    : `Season ${activeSeason}: ${champion ? "the owner is delighted with your championship!" : qualified ? "the owner is pleased you reached the playoffs." : "the owner is disappointed you missed the playoffs."}${reward} Contract through Season ${state.end}.`;
  update.dataset.outcome = state.fired ? "loss" : intro ? "neutral" : qualified ? "win" : "warning";
  document.querySelector("#owner-update-dismiss").hidden = state.fired;
}

document.querySelector("#owner-update-details").addEventListener("click", () => activateView("gm", { focus: true }));
document.querySelector("#owner-update-dismiss").addEventListener("click", () => {
  if (!activeContracts || careerEnded() || document.querySelector("#owner-update").hidden) return;
  ownerUpdateDismissed = activeSeason;
  document.querySelector("#owner-update").hidden = true;
  document.querySelector('.view-tab[aria-selected="true"]').focus({ preventScroll: true });
  saveProgress();
});

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

function automaticFutureLineups(save) {
  const week = save.week < 17 ? save.week + 1 : 18 + (save.playoffRound ?? 0);
  if (week > 21 || !save.lineupChanges.at(-1)?.starters.length) return save.lineupChanges;
  return [...save.lineupChanges.filter(entry => entry.week < week), { week, starters: [] }];
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
  save.lineupChanges = automaticFutureLineups(save);
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
    ownerUpdateDismissed = save.ownerUpdateDismissed;
    welcomeDismissed = save.welcomeDismissed;
    renderWelcome();
    setDevelopmentRecap(profile, save.season);
    if (regular) renderResult(regular);
    if (postseason) { renderPostseason(postseason); activateView("playoffs"); }
    if (savedDraft) { document.querySelector("#draft-position").value = save.draftPosition ?? ""; applyDraft(savedDraft); }
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
    if (activeTrainingCamp) {
      profile = (await careerRequest("camp", { view_team: teamId, manual_picks: activeDraftChoices, dropped: activeDropped })).profile;
    } else if (activeDropped.length && draftState?.complete) {
      profile = (await careerRequest("cuts", { view_team: teamId, manual_picks: activeDraftChoices, dropped: activeDropped })).profile;
    } else if (hasLineupContext()) profile = await careerRequest("profile", { view_team: teamId });
    else {
      const response = await fetch(`/api/team/${teamId}?run_seed=${runSeed}&lineup_rules=${activeLineupRules}&season=${activeSeason}&development_start=${activeDevelopmentStart ?? 1}${rebuildQuery()}`);
      if (!response.ok) throw new Error("Roster could not be loaded. Please try again.");
      profile = await response.json();
    }
    if (!isCurrent()) return;
    if (profile.team.id !== teamId || profile.run_seed !== runSeed) throw new Error("Roster could not be loaded. Please try again.");
    if (draftState && !activeDropped.length && !activeTrainingCamp) {
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

function clearLeaders() {
  ++leadersRequest;
  leadersBusy = false;
  if (leadersDialog.open) leadersDialog.close();
  document.querySelector("#leaders-lists").replaceChildren();
  document.querySelector("#leaders-status").textContent = "";
  document.querySelector("#leaders-retry").hidden = true;
}

function renderLeaders(data) {
  const sections = data.categories.map(category => {
    const section = document.createElement("section"); section.className = "leaders-category";
    const heading = document.createElement("h3"); heading.id = `leaders-${category.id}`; heading.textContent = category.label; section.append(heading);
    if (category.leaders.length) {
      const wrap = document.createElement("div"); wrap.className = "table-wrap"; wrap.tabIndex = 0;
      wrap.setAttribute("role", "region"); wrap.setAttribute("aria-labelledby", heading.id);
      const table = document.createElement("table"); table.className = "league-leaders-table"; table.setAttribute("aria-labelledby", heading.id);
      const head = document.createElement("thead"), header = document.createElement("tr");
      for (const label of ["Rank", "Player", "Team", "Total"]) {
        const cell = document.createElement("th"); cell.scope = "col"; cell.textContent = label; header.append(cell);
      }
      head.append(header); table.append(head);
      const body = document.createElement("tbody");
      for (const leader of category.leaders) {
        const row = document.createElement("tr"); row.dataset.playerId = leader.player_id;
        if (leader.team.id === activeTeamId) row.className = "leader-own";
        for (const value of [leader.rank, `${leader.player} · ${leader.position}`, leader.team.city, leader.value]) {
          const cell = document.createElement("td"); cell.textContent = value; row.append(cell);
        }
        if (leader.team.id === activeTeamId) {
          const badge = document.createElement("span"); badge.className = "your-team-badge"; badge.textContent = "Your team"; row.cells[2].append(" ", badge);
        }
        body.append(row);
      }
      table.append(body); wrap.append(table); section.append(wrap);
    } else {
      const empty = document.createElement("p"); empty.className = "roster-note"; empty.textContent = `No recorded ${category.label.toLowerCase()} yet.`; section.append(empty);
    }
    const best = category.your_best;
    if (best && !category.leaders.some(row => row.player_id === best.player_id)) {
      const own = document.createElement("p"); own.className = "leaders-your-best leader-own"; own.dataset.playerId = best.player_id;
      own.textContent = `Your best: #${best.rank} · ${best.player} · ${best.position} · ${best.team.city} · ${best.value}`; section.append(own);
    } else if (!best) {
      const empty = document.createElement("p"); empty.className = "roster-note"; empty.textContent = "Your team has no recorded total in this category yet."; section.append(empty);
    }
    return section;
  });
  document.querySelector("#leaders-lists").replaceChildren(...sections);
}

async function loadLeaders() {
  if (!LEAGUE_LEADERS_ENABLED) return;
  if (!activeTeamId || weekSimulationBusy || advancingSeason || restoring || leadersBusy) return;
  leadersBusy = true;
  const request = ++leadersRequest;
  const team = activeTeamId, seed = activeRunSeed, season = activeSeason, week = currentWeek;
  const isCurrent = () => request === leadersRequest && leadersDialog.open && team === activeTeamId
    && seed === activeRunSeed && season === activeSeason && week === currentWeek;
  if (!leadersDialog.open) leadersDialog.showModal();
  document.querySelector("#leaders-lists").replaceChildren();
  document.querySelector("#leaders-retry").hidden = true;
  const status = document.querySelector("#leaders-status");
  if (!week) { leadersBusy = false; status.textContent = `Season ${season} · Regular season · Play Week 1 to see league leaders.`; return; }
  status.textContent = `Loading Season ${season} leaders through Week ${week}…`;
  try {
    const data = await careerRequest("leaders", { week });
    if (!isCurrent()) return;
    if (data.team?.id !== team || data.run_seed !== seed || data.season !== season || data.week !== week
        || !Array.isArray(data.categories) || data.categories.map(item => item.id).join(",") !== "passing,rushing,receiving,sacks,interceptions") throw new Error("Leader response did not match this career.");
    renderLeaders(data);
    status.textContent = `Season ${season} · Regular season through Week ${week}`;
  } catch {
    if (!isCurrent()) return;
    status.textContent = "League leaders could not be loaded. Your progress is unchanged. Try again.";
    document.querySelector("#leaders-retry").hidden = false;
  } finally {
    if (request === leadersRequest) leadersBusy = false;
  }
}

leadersButton.addEventListener("click", loadLeaders);
document.querySelector("#leaders-retry").addEventListener("click", loadLeaders);
document.querySelector("#leaders-close").addEventListener("click", () => leadersDialog.close());
leadersDialog.addEventListener("close", () => { ++leadersRequest; leadersBusy = false; });

function renderWelcome() {
  document.querySelector("#career-welcome").hidden = !activeTeamId || welcomeDismissed;
}
document.querySelector("#welcome-dismiss").addEventListener("click", () => {
  welcomeDismissed = true;
  renderWelcome();
  document.querySelector('.view-tab[aria-selected="true"]').focus({ preventScroll: true });
  saveProgress();
});
document.querySelector("#welcome-help").addEventListener("click", () => activateView("help", { focus: true }));

function renderHelp() {
  document.querySelector("#player-salary-guide").hidden = activeLineupRules < 15;
  document.querySelector("#salary-growth-guide").hidden = activeLineupRules < 17;
  document.querySelector("#training-camp-guide").hidden = activeLineupRules < 18;
  document.querySelector("#rookie-contract-guide").hidden = activeLineupRules < 19;
  document.querySelector("#re-signing-guide").hidden = activeLineupRules < 20;
  document.querySelector("#salary-demand-guide").hidden = activeLineupRules < 26;
  document.querySelector("#roster-limit-note").textContent = `${activeLineupRules >= 14 ? "Every team starts with 35 players. " : ""}${rosterMinimum() ? `Regular-season roster: ${rosterLimitText()} players.` : `Regular-season maximum: ${rosterLimit()} players.`} Offseason draft picks may temporarily increase the roster. Position minimums appear above each group.`;
  document.querySelector("#contract-info").hidden = !activeContracts;
  document.querySelector("#draft-format").textContent = `${activeDraftRounds} rounds · Same order each round · CPU teams balance player quality and position needs. Rookies join your roster without replacing anyone. The regular-season ${rosterMinimum() ? "roster range" : "limit"} is ${rosterLimitText()}.`;
}

function activateView(id, { focus = false } = {}) {
  if (id === "draft" && !draftNavigationAvailable()) return;
  if (id === "help") renderHelp();
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
  if (id === "draft") {
    if (!draftState && !draftBusy) loadDraft();
    else if (draftScrollPending) returnToDraftTop();
  }
}

viewTabs.forEach(tab => {
  tab.addEventListener("click", () => activateView(tab.id.slice(5)));
  tab.addEventListener("keydown", event => {
    const tabs = viewTabs.filter(item => !item.hidden), index = tabs.indexOf(tab);
    let next;
    if (event.key === "ArrowRight") next = (index + 1) % tabs.length;
    else if (event.key === "ArrowLeft") next = (index - 1 + tabs.length) % tabs.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = tabs.length - 1;
    else return;
    event.preventDefault();
    activateView(tabs[next].id.slice(5), { focus: true });
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

function updateRetirementBadge(badge, ended) {
  const label = ended ? "Retired" : "Retiring after this season";
  const summary = document.createElement("summary");
  summary.textContent = ended ? "Retired" : "*";
  summary.title = label;
  summary.setAttribute("aria-label", label);
  const explanation = document.createElement("span");
  explanation.className = "retirement-explanation";
  explanation.textContent = label;
  badge.replaceChildren(summary, explanation);
}

function addRetirementBadge(cell, player) {
  if (!player.retiring_after_season) return;
  const badge = document.createElement("details");
  badge.className = "retirement-badge";
  updateRetirementBadge(badge, playoffState?.postseason_complete && !activeTrainingCamp);
  cell.append(document.createTextNode(" "), badge);
}

function renderRetirements() {
  const section = document.querySelector("#retirement-summary");
  const ended = activeLineupRules >= 10 && playoffState?.postseason_complete;
  section.hidden = !ended || !seasonRetirees.length || Boolean(draftState?.complete);
  const list = document.querySelector("#retirement-list");
  list.replaceChildren();
  for (const player of seasonRetirees) {
    const item = document.createElement("li");
    item.textContent = `${player.name} · ${player.position} · Age ${player.age} · Current ${player.current_rating}`;
    list.append(item);
  }
  const retiredIds = new Set(ended ? seasonRetirees.map(p => p.id) : []);
  for (const row of document.querySelectorAll("#roster-groups .roster-rating-wrap .roster-player")) row.hidden = retiredIds.has(row.dataset.playerId);
  for (const badge of document.querySelectorAll("#roster-groups .retirement-badge")) updateRetirementBadge(badge, ended && !activeTrainingCamp);
  const count = rosterProfile?.roster.filter(p => !retiredIds.has(p.id)).length ?? 0;
  if (rosterProfile) document.querySelector("#roster-title").textContent = `Roster · ${count} players`;
  for (const group of document.querySelectorAll("#roster-groups .roster-group")) {
    const rule = rosterProfile.roster_rules.find(r => r.position === group.dataset.position);
    const remaining = rosterProfile.roster.filter(p => p.position === rule.position && !retiredIds.has(p.id)).length;
    group.querySelector("summary").textContent = `${rule.position} · ${remaining} players · minimum ${rule.minimum}`;
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

function salaryLabel(contract) {
  if (contract.status === "provisional") return `$${(contract.annual_salary / 1000000).toFixed(2)}M/yr · ${contract.years} ${contract.years === 1 ? "yr" : "yrs"} · Provisional`;
  const term = ["renewal_due", "expired"].includes(contract.status) ? "Contract expired"
    : `${contract.years_remaining} ${contract.years_remaining === 1 ? "yr" : "yrs"}${contract.status === "active" ? " left" : ""}`;
  return `$${(contract.annual_salary / 1000000).toFixed(2)}M/yr · ${term}`;
}

function addSalaryCell(row, contract) {
  const cell = document.createElement("td");
  cell.className = "salary-cell";
  cell.textContent = contract ? salaryLabel(contract) : "—";
  if (contract) cell.title = contract.status === "provisional" ? `Expected ${contract.years}-year deal starting Season ${contract.starts_season}; unsigned until retained past training camp` : `${contract.years}-year contract · Season ${contract.signed_season} through ${contract.expires_after_season}`;
  row.append(cell);
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
    for (const label of ["Depth", "Player", "Age", "Current", "Potential", ...(profile.lineup_rules >= 15 ? ["Salary / term"] : [])]) {
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
      if (profile.lineup_rules >= 15) addSalaryCell(row, player.contract ?? player.contract_offer);
      addRookieBadge(row.children[1], player);
      addRetirementBadge(row.children[1], player);
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

function clearDevelopmentRecap() {
  developmentRecap = null;
  if (developmentDialog.open) developmentDialog.close();
  document.querySelector("#development-recap-button").hidden = true;
  document.querySelector("#development-recap-rows").replaceChildren();
  document.querySelector("#development-recap-summary").textContent = "";
  document.querySelector("#development-show-unchanged").checked = false;
}

function developmentRecapAvailable() {
  if (!developmentRecap) return false;
  return activeTrainingCamp ? developmentRecap.season === activeSeason + 1
    : developmentRecap.season === activeSeason && currentWeek === 0;
}

function updateDevelopmentRecapVisibility() {
  const available = developmentRecapAvailable();
  document.querySelector("#development-recap-button").hidden = !available;
  if (!available && developmentDialog.open) developmentDialog.close();
}

function setDevelopmentRecap(profile, season) {
  if (season < 2 || profile.lineup_rules < 3) return;
  // Capture the season-start profile before draft additions/cuts or scouting.
  // Restore already fetches this same profile before replaying the current draft.
  developmentRecap = { season, players: profile.roster.map(player => ({ ...player })) };
  renderDevelopmentRecap();
  updateDevelopmentRecapVisibility();
}

function renderDevelopmentRecap() {
  if (!developmentRecap) return;
  const players = developmentRecap.players;
  const improved = players.filter(p => p.rating_change > 0).length;
  const declined = players.filter(p => p.rating_change < 0).length;
  const booms = players.filter(p => p.rookie_outcome === "boom").length;
  const busts = players.filter(p => p.rookie_outcome === "bust").length;
  const changed = p => Boolean(p.rating_change || p.potential_change);
  const unchanged = players.filter(p => !changed(p)).length;
  const potentialOnly = players.filter(p => !p.rating_change && p.potential_change).length;
  const knownPotential = players.every(p => Number.isFinite(p.potential_change));
  document.querySelector("#development-recap-title").textContent = `Season ${developmentRecap.season} player development`;
  document.querySelector("#development-recap-summary").textContent =
    `${improved} improved · ${declined} declined in current rating · ${potentialOnly} potential-only changes · ${unchanged} ${knownPotential ? "unchanged in both ratings" : "with no recorded change"}. Rookies: ${booms} boom · ${busts} bust.`;
  document.querySelector("#development-recap-legacy").hidden = knownPotential;
  const showUnchanged = document.querySelector("#development-show-unchanged").checked;
  const rows = players.filter(p => showUnchanged || changed(p) || ["boom", "bust"].includes(p.rookie_outcome)).map(player => {
    const row = document.createElement("tr"); row.dataset.playerId = player.id;
    const current = player.rating_change ?? 0, potential = player.potential_change;
    const outcome = player.rookie_outcome === "boom" ? "Boom" : player.rookie_outcome === "bust" ? "Bust"
      : current > 0 ? "Improved" : current < 0 ? "Declined" : potential > 0 ? "Potential increased"
      : potential < 0 ? "Potential decreased" : player.rookie_outcome === "normal" ? "Rookie · Unchanged" : "Unchanged";
    for (const value of [player.name, player.position, outcome]) {
      const cell = document.createElement("td"); cell.textContent = value; row.append(cell);
    }
    for (const [value, delta] of [[player.current_rating, current], [player.potential_rating, potential]]) {
      const cell = document.createElement("td");
      cell.textContent = Number.isFinite(delta)
        ? `${value - delta} → ${value} (${delta > 0 ? "+" : ""}${delta})` : `${value} (change unavailable)`;
      if (delta) cell.className = delta > 0 ? "development-improved" : "development-declined";
      row.append(cell);
    }
    return row;
  });
  document.querySelector("#development-recap-rows").replaceChildren(...rows);
  document.querySelector("#development-recap-empty").hidden = rows.length > 0;
  document.querySelector("#development-recap-scroll").hidden = rows.length === 0;
}

document.querySelector("#development-recap-button").addEventListener("click", () => {
  if (developmentRecapAvailable() && !developmentDialog.open) developmentDialog.showModal();
});
document.querySelector("#development-close").addEventListener("click", () => developmentDialog.close());
document.querySelector("#development-show-unchanged").addEventListener("change", renderDevelopmentRecap);

function renderTeamProfile(profile, latestDraftSeason = activeSeason) {
  rookieSeason = latestDraftSeason;
  rosterProfile = profile;
  renderPayroll();
  rosterMode = "ratings";
  rosterCompetition.value = "regular";
  rosterTotals = { regular: profile.roster_stats, playoffs: profile.roster_stats };
  document.querySelector("#offense-rating").textContent = profile.ratings.offense;
  document.querySelector("#defense-rating").textContent = profile.ratings.defense;
  // Keep the shared inline confirmation alive when replacing roster rows.
  rosterManagement.append(cutConfirmation);
  const groups = createRosterGroups(profile);
  document.querySelector("#roster-groups").replaceChildren(...groups);
  document.querySelector("#development-note").textContent = profile.lineup_rules >= 3
    ? "Ratings change once each offseason by position and age. Potential is a possible ceiling; arrows show last offseason’s actual change. Longevity varies by player."
    : "This saved season keeps its original ratings. Position-specific development and aging begin next season.";
  document.querySelector("#roster-title").textContent = `Roster · ${profile.roster.length} players`;
  if (profile.lineup_rules >= 5) document.querySelector("#development-note").textContent += " Under-25 players outside QB/K can earn +1 from a regular rotation role, within potential.";
  if (profile.lineup_rules >= 10) document.querySelector("#development-note").textContent += " Retirement plans use position, age, current rating and hidden longevity. Retiring players leave after the postseason. After the draft, unfilled roster spots receive low-rated replacements.";
  if (profile.lineup_rules >= 9) document.querySelector("#development-note").textContent += " Rookies have a 20% boom / 5% bust / 75% normal preseason reassessment and up to 1–2 current rating growth within potential. Young kickers develop toward potential; seasonal form varies by up to 4 around underlying ability. Older kickers decline. Ratings stay fixed during weekly play.";
  else if (profile.lineup_rules >= 8) document.querySelector("#development-note").textContent += " At their first preseason, rookies have a 20% boom / 5% bust / 75% normal reassessment. Non-kickers then gain up to 1–2 current rating within potential; kickers keep their seasonal-form model. Ratings stay fixed during weekly play. Arrows include the combined preseason change.";
  else if (profile.lineup_rules >= 7) document.querySelector("#development-note").textContent += " At their first season start, rookies have a 15% boom / 15% bust / 70% normal reassessment. Potential arrows show changes from draft estimates or the previous season.";
  rosterSection.hidden = false;
  renderRosterStats();
  renderRetirements();

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
    const retired = seasonRetirees.filter(p => !rosterProfile.roster.some(current => current.id === p.id));
    for (const player of [...rosterProfile.roster,...retired].filter(player => player.position === position)) {
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
      addRetirementBadge(row.children[1], player);
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

function draftNavigationAvailable() {
  return Boolean(activeTeamId) && !careerEnded() && Boolean(playoffState?.postseason_complete)
    && activeSeason < 999 && !activeTrainingCamp;
}

function updatePhaseActions() {
  leadersButton.hidden = !LEAGUE_LEADERS_ENABLED;
  leadersButton.disabled = !LEAGUE_LEADERS_ENABLED || !activeTeamId || weekSimulationBusy || advancingSeason || restoring;
  const draftingStarted = activeDraftChoices !== null;
  document.querySelector("#season-status").hidden = draftingStarted;
  if (draftingStarted) {
    renderQualification(null);
    seasonSimulationStatus.hidden = true;
    if (!careerEnded()) document.querySelector("#owner-update").hidden = true;
  }
  const live = Boolean(activeTeamId) && !careerEnded();
  const regular = live && currentWeek < 17;
  simulateButton.hidden = !regular || seasonSimulationActive;
  simulateSeasonButton.hidden = !regular || seasonSimulationActive;
  simulationMore.hidden = !regular || seasonSimulationActive;
  if (simulationMore.hidden) {
    simulationMore.open = false;
    closeSeasonConfirmation(false);
  }
  stopSeasonButton.hidden = !regular || !seasonSimulationActive;
  playoffsStart.hidden = !live || currentWeek !== 17 || playoffState !== null;
  playoffSimulate.hidden = !live || !playoffState || playoffState.postseason_complete;
  const offseason = live && Boolean(playoffState?.postseason_complete) && activeSeason < 999;
  const drafted = Boolean(draftState?.complete) && activeDraftChoices?.length === activeDraftRounds;
  const draftAvailable = draftNavigationAvailable();
  draftButton.hidden = !draftAvailable;
  document.querySelector("#view-draft").hidden = !draftAvailable;
  document.querySelector("#roster-draft-return").hidden = !draftAvailable;
  document.querySelector("#roster-draft-return").textContent = draftState ? "Back to draft" : "Open draft";
  const campRequired = activeLineupRules >= 18 && !activeTrainingCamp;
  campButton.hidden = !offseason || !drafted || !campRequired;
  campButton.disabled = campBusy || draftBusy || cutBusy || advancingSeason;
  manageRoster.hidden = !offseason || !drafted || campRequired;
  nextSeasonButton.hidden = !offseason || !drafted || campRequired || !rosterReady();
  document.querySelector("#training-camp-status").hidden = !activeTrainingCamp;
  document.querySelector("#training-camp-status").textContent = activeTrainingCamp ? `Training camp · Season ${activeSeason + 1} development complete. Finalize your roster before continuing.` : "";
}

function createRunSeed() {
  const candidate = crypto.getRandomValues(new Uint32Array(1))[0] || 1;
  return candidate === activeRunSeed ? (candidate % 4294967295) + 1 : candidate;
}

function renderSchedule(data, runSeed, { priorStandings = {}, history = [], career = [], lineupRules = 26, developmentStart = 1, rebuildTeam = null, contracts = true, lineupChanges = [], careerStartWeek = 1, draftRounds = 6 } = {}) {
  closeSeasonConfirmation(false);
  simulationMore.open = false;
  clearLeaders();
  if (rosterDialog.open) rosterDialog.close();
  weekSimulationBusy = false;
  seasonSimulationActive = false;
  stopSeasonRequested = false;
  activeTeamId = data.team.id;
  activeRunSeed = runSeed;
  activeSeason = data.season;
  clearDevelopmentRecap();
  activeCareerStartWeek = careerStartWeek;
  activeDraftRounds = draftRounds;
  document.querySelector("#career-start-note").hidden = careerStartWeek !== 17 || activeSeason !== 1;
  activeLineupRules = lineupRules;
  seasonRetirees = lineupRules >= 10 ? rosterProfile.roster.filter(p => p.retiring_after_season) : [];
  activeDevelopmentStart = developmentStart;
  activeRebuildTeam = rebuildTeam;
  document.querySelector("#rebuild-note").hidden = !rebuildTeam || activeSeason !== 1;
  document.querySelector("#rating-method").textContent = lineupRules >= 2
    ? "Team ratings: 80% starters + 20% bench, using current ability. Kickers are separate. Highlighted players are starters."
    : "This saved season keeps its original rating formula. Automatic starters and 80%/20% team ratings apply next season.";
  activePriorStandings = priorStandings;
  careerHistory = history;
  activeContracts = contracts;
  renderHelp();
  regularSnapshot = null;
  activeDraftChoices = null;
  draftState = null;
  activeTrainingCamp = false;
  activeDropped = [];
  activeRosterActions = [];
  activeCareer = career;
  activeLineupChanges = lineupChanges;
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
  document.querySelector("#draft-recap").hidden = true;
  document.querySelector("#draft-recap-rows").replaceChildren();
  document.querySelector("#draft-recap-caption").textContent = "";
  document.querySelector("#draft-title").textContent = "Rookie draft";
  document.querySelector("#draft-status").textContent = "";
  document.querySelector("#draft-position").value = "";
  draftScrollPending = false;
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
  renderRetirements();
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

  scheduleList.replaceChildren();
  for (const game of data.games) {
    const row = document.createElement("li");
    row.className = "schedule-row";
    row.dataset.opponentId = game.opponent_id;
    row.innerHTML = `
      <span class="week">Week ${game.week}</span>
      <span class="schedule-matchup">
        <span class="venue ${game.venue.toLowerCase()}" title="${game.venue}">${game.venue === "Home" ? "vs" : "at"}</span>
        <strong>${game.opponent}</strong>
        <span class="reason">${game.reason}</span>
      </span>
      <span class="opponent-record">Record: 0–0</span>
      <span class="game-final">Not played</span>
    `;
    scheduleList.append(row);
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
  status.hidden = !data?.season_complete || activeDraftChoices !== null;
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
  clearLeaders();
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
  for (const row of scheduleList.children) {
    row.querySelector(".opponent-record").textContent = `Record: ${opponentRecords.get(row.dataset.opponentId)}`;
  }
  for (const game of data.game_results) {
    const row = scheduleList.children[game.week - 1];
    if (!row) continue;
    row.classList.add("completed");
    row.dataset.outcome = game.outcome;
    const final = row.querySelector(".game-final");
    final.textContent = `${game.outcome} · ${game.team_score}–${game.opponent_score}${game.overtime ? " · OT" : ""}`;
    const outcome = game.outcome === "W" ? "Win" : game.outcome === "L" ? "Loss" : "Tie";
    final.setAttribute("aria-label",
      `${outcome}: ${data.team.city} ${game.team_score}, ${game.opponent} ${game.opponent_score}${game.overtime ? ", overtime" : ""}`);
  }

  document.querySelector("#playoff-title").textContent = data.season_complete ? "Final playoff seeds" : `Playoff Race — Week ${data.week}`;
  playoffsStart.hidden = !data.season_complete || playoffState !== null;
  currentWeek = data.week;
  updateDevelopmentRecapVisibility();
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
  if (playoffBusy || seasonSimulationActive || restoring) return;
  closeSeasonConfirmation(false);
  simulationMore.open = false;
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
  if (playoffBusy || seasonSimulationActive || restoring || !select.value) return;
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
      fetch(`/api/team/${teamId}?run_seed=${runSeed}&lineup_rules=26&season=1&development_start=1${rebuildQuery(teamId)}`),
      fetch(`/api/season/${teamId}/week/16?run_seed=${runSeed}&lineup_rules=26&season=1&development_start=1${rebuildQuery(teamId)}`),
    ]);
    if (!scheduleResponse.ok || !profileResponse.ok || !regularResponse.ok) {
      throw new Error("Your team could not be loaded. Please try again.");
    }
    const [schedule, profile, regular] = await Promise.all([
      scheduleResponse.json(), profileResponse.json(), regularResponse.json(),
    ]);
    if (profile.run_seed !== runSeed || profile.team.id !== teamId || profile.lineup_rules !== 26 || profile.rebuild_team !== teamId
        || schedule.team?.id !== teamId || schedule.season !== 1 || regular.team?.id !== teamId
        || regular.season !== 1 || regular.week !== 16 || regular.run_seed !== runSeed) {
      throw new Error("Your team could not be loaded. Please try again.");
    }
    renderTeamProfile(profile, 1);
    renderSchedule(schedule, runSeed, { rebuildTeam: teamId, careerStartWeek: 17 });
    renderResult(regular);
    ownerUpdateDismissed = 0;
    welcomeDismissed = false;
    renderWelcome();
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
  const disabled = weekSimulationBusy || restoring || !activeTeamId || complete || ended;
  simulateButton.disabled = disabled;
  simulateSeasonButton.disabled = disabled;
  simulateButton.textContent = ended ? "Career over" : complete ? "Regular season complete"
    : weekSimulationBusy ? "Simulating…" : `Simulate Week ${currentWeek + 1}`;
  simulateSeasonButton.textContent = "Simulate Season";
  stopSeasonButton.hidden = !seasonSimulationActive;
  stopSeasonButton.disabled = stopSeasonRequested;
  document.querySelector("#change-team-button").disabled = seasonSimulationActive;
  updatePhaseActions();
}

function canSimulate() {
  return !weekSimulationBusy && !restoring && !advancingSeason && !careerEnded() && activeTeamId && currentWeek < 17
    && !form.querySelector('button[type="submit"]').disabled;
}

function closeSeasonConfirmation(returnFocus = true) {
  pendingSeasonSimulation = null;
  if (!seasonConfirmDialog.open) return;
  seasonConfirmDialog.close();
  if (returnFocus && !simulationMore.hidden) simulationMore.querySelector("summary").focus({ preventScroll: true });
}

function openSeasonConfirmation() {
  if (!canSimulate() || seasonConfirmDialog.open || !franchiseSetup.hidden) return;
  const count = 17 - currentWeek;
  pendingSeasonSimulation = { teamId: activeTeamId, runSeed: activeRunSeed, season: activeSeason, week: currentWeek };
  document.querySelector("#season-confirm-message").textContent =
    `This will simulate ${count} regular-season ${count === 1 ? "game" : "games"} (${count === 1 ? "Week 17" : `Weeks ${currentWeek + 1}–17`}). Each completed week is saved. Playoffs and the draft wait for you.`;
  document.querySelector("#season-confirm-start").textContent = `Simulate ${count} ${count === 1 ? "game" : "games"}`;
  simulationMore.open = false;
  seasonConfirmDialog.showModal();
  document.querySelector("#season-confirm-cancel").focus({ preventScroll: true });
}

async function simulateWeeks(wholeSeason = false) {
  if (!canSimulate() || seasonConfirmDialog.open) return;
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
simulateSeasonButton.addEventListener("click", openSeasonConfirmation);
document.querySelector("#season-confirm-cancel").addEventListener("click", () => closeSeasonConfirmation());
seasonConfirmDialog.addEventListener("cancel", event => {
  event.preventDefault();
  closeSeasonConfirmation();
});
seasonConfirmDialog.addEventListener("close", () => {
  if (!seasonConfirmDialog.open) pendingSeasonSimulation = null;
});
document.querySelector("#season-confirm-start").addEventListener("click", () => {
  const pending = pendingSeasonSimulation;
  if (!seasonConfirmDialog.open || !pending) return;
  const current = pending.teamId === activeTeamId && pending.runSeed === activeRunSeed
    && pending.season === activeSeason && pending.week === currentWeek;
  const ready = current && canSimulate() && franchiseSetup.hidden;
  closeSeasonConfirmation(false);
  if (ready) {
    simulateWeeks(true);
    if (!stopSeasonButton.hidden) stopSeasonButton.focus({ preventScroll: true });
  }
});
stopSeasonButton.addEventListener("click", () => {
  if (!seasonSimulationActive || currentWeek >= 17 || careerEnded()) return;
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

function rosterLimit() {
  return activeLineupRules >= 13 ? 38 : activeLineupRules >= 11 ? 31 : 38;
}

function rosterMinimum() {
  return activeLineupRules >= 24 ? 31 : activeLineupRules >= 14 ? 35 : activeLineupRules >= 13 ? 31 : 0;
}

function replacementPay() {
  return `$${((rosterProfile?.payroll?.minimum_salary ?? 1000000) / 1000000).toFixed(2)}M`;
}

function capOverage() {
  return rosterProfile?.payroll?.over_cap ?? 0;
}

function renderPayroll() {
  const status = document.querySelector("#payroll-status"), pay = rosterProfile?.payroll;
  status.hidden = !pay;
  if (!pay) { status.textContent = ""; return; }
  const money = amount => `$${(amount / 1000000).toFixed(2)}M`;
  status.textContent = `${pay.season ? `Season ${pay.season} payroll` : "Payroll"} ${money(pay.total)} / ${money(pay.cap)} cap${pay.rookie_holds || pay.expired_holds ? ` (${money(pay.committed)} signed${pay.rookie_holds ? ` + ${money(pay.rookie_holds)} rookie holds` : ""}${pay.expired_holds ? ` + ${money(pay.expired_holds)} expired holds` : ""})` : ""}${pay.dead_cap ? ` · ${money(pay.dead_cap)} dead cap` : ""} · ${pay.over_cap ? `${money(pay.over_cap)} over cap; clear space before next season` : `${money(pay.cap_space)} available`}${pay.below_floor ? ` · ${money(pay.below_floor)} below payroll floor (warning only)` : ""}`;
}

function pendingRenewals() {
  return activeLineupRules >= 20 && activeTrainingCamp ? rosterProfile?.roster.filter(p => p.renewal_offer).length ?? 0 : 0;
}

function rosterReady() {
  const count = rosterProfile?.roster.length ?? 0;
  return count >= rosterMinimum() && count <= rosterLimit() && !capOverage() && !pendingRenewals();
}

function rosterLimitText() {
  return rosterMinimum() ? `${rosterMinimum()}–${rosterLimit()}` : String(rosterLimit());
}

function rosterCutStatus(count) {
  if (activeLineupRules >= 18 && !activeTrainingCamp) return "Start training camp before final cuts and next season.";
  if (count < rosterMinimum()) return `Need ${rosterMinimum() - count} more players to continue.`;
  const remaining = Math.max(0, count - rosterLimit());
  if (pendingRenewals()) return `${remaining ? `Drop ${remaining} more players. ` : ""}${capOverage() ? `Clear $${(capOverage()/1000000).toFixed(2)}M in cap space. ` : ""}Re-sign or release ${pendingRenewals()} ${pendingRenewals() === 1 ? "player" : "players"} with expired contracts.`;
  if (capOverage()) return `${remaining ? `Drop ${remaining} more players and clear` : "Clear"} $${(capOverage() / 1000000).toFixed(2)}M in cap space to continue.`;
  return remaining ? `Drop ${remaining} more ${remaining === 1 ? "player" : "players"} to continue.`
    : "No more cuts needed. Ready for next season.";
}

function updateOffseasonActions() {
  const finished = !careerEnded() && Boolean(playoffState?.postseason_complete) && activeSeason < 999;
  const drafted = Boolean(draftState?.complete) && activeDraftChoices?.length === activeDraftRounds;
  const invalidRoster = !rosterReady() || (activeLineupRules >= 18 && !activeTrainingCamp);
  updatePhaseActions();
  nextSeasonButton.disabled = !finished || !drafted || invalidRoster || draftBusy || cutBusy || campBusy || advancingSeason;
  nextSeasonButton.textContent = !drafted ? "Finish rookie draft" : invalidRoster ? rosterCutStatus(rosterProfile.roster.length) : `Continue to Season ${activeSeason + 1}`;
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
  updatePhaseActions();
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
  renderRetirements();
}

async function loadPlayoffRound(number) {
  if (playoffBusy || weekSimulationBusy || restoring || careerEnded() || currentWeek !== 17
      || number !== (playoffState ? completedPlayoffRound + 1 : 0) || playoffState?.postseason_complete) return;
  playoffBusy = true;
  updatePhaseActions();
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
    updatePhaseActions();
    playoffsStart.disabled = false;
    document.querySelector("#change-team-button").disabled = false;
    playoffSimulate.disabled = careerEnded() || (playoffState?.postseason_complete ?? false);
  }
}

playoffsStart.addEventListener("click", () => {
  if (currentWeek === 17 && !playoffState && !playoffsStart.hidden && !playoffsStart.disabled) loadPlayoffRound(0);
});
playoffSimulate.addEventListener("click", () => {
  if (playoffState?.next_round && !playoffSimulate.hidden && !playoffSimulate.disabled) loadPlayoffRound(completedPlayoffRound + 1);
});

async function careerRequest(action, extra = {}, context = null) {
  const teamId = context?.teamId ?? activeTeamId;
  const ranks = context?.priorStandings ?? activePriorStandings;
  const response = await fetch(`/api/career/${teamId}`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, roster_actions: context?.rosterActions ?? activeRosterActions, training_camp: context?.trainingCamp ?? activeTrainingCamp, draft_rounds: context?.draftRounds ?? activeDraftRounds, season: context?.season ?? activeSeason,
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
  const camp = context?.trainingCamp ?? activeTrainingCamp;
  if (camp) {
    const data = await careerRequest("camp", { manual_picks: choices, dropped }, context);
    if (data.team.id !== teamId || data.season !== season || data.run_seed !== seed || !data.training_camp || !draftChoicesMatch(data, choices, false, context?.draftRounds ?? activeDraftRounds)) throw new Error("Training camp could not be restored.");
    return data;
  }
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
  activeTrainingCamp = data.training_camp === true;
  activeDraftChoices = data.manual_picks;
  activeDropped = data.dropped ?? [];
  activeRosterActions = data.roster_actions ?? [];
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
      players: [...data.profile.roster_stats.players.map(player => old.get(player.player_id) ?? player),
        ...seasonRetirees.filter(p => !data.profile.roster.some(current => current.id === p.id)).map(p => old.get(p.id)).filter(Boolean)] };
  }
  rosterMode = mode;
  rosterCompetition.value = competition;
  renderRosterStats();
  for (const position of collapsed) document.querySelector(`#roster-groups [data-position="${position}"]`).open = false;
  const count = data.profile.roster.length;
  updateOffseasonActions();
  draftButton.textContent = data.complete ? "Review draft" : "Resume draft";
  const summary = document.querySelector("#draft-summary");
  summary.hidden = false;
  summary.textContent = data.complete
    ? `Draft complete · ${count}/${rosterLimit()} players. ${rosterCutStatus(count)}`
    : `Draft in progress · ${activeDraftChoices.length} of ${activeDraftRounds} picks made · ${count} players.`;
  if (data.retirements) summary.textContent += ` ${data.retirements.length} retired; ${(data.replacements ?? []).length} low-rated replacements added after the draft.`;
  renderDraft();
  renderCuts();
  renderRetirements();
  if (activeTrainingCamp && data.development_roster) setDevelopmentRecap({ lineup_rules: activeLineupRules, roster: data.development_roster }, data.development_season);

}

function renderDraftRecap() {
  // Use the immutable selection log, not the retained roster: cuts must not
  // erase picks or replace their draft-day estimates with later ratings.
  const ownPicks = draftState.picks.filter(pick => pick.team.id === activeTeamId);
  const paid = activeLineupRules >= 15;
  const head = document.querySelector("#draft-recap-table-wrap thead tr");
  head.replaceChildren(...["Round", "Pick", "Player", "Position", "Current", "Potential", ...(paid ? ["Salary / term"] : [])].map(label => {
    const th = document.createElement("th"); th.scope = "col"; th.textContent = label; return th;
  }));
  const rows = ownPicks.map(pick => {
    const row = document.createElement("tr");
    row.dataset.playerId = pick.player.id;
    for (const value of [pick.round, pick.overall, pick.player.name, pick.player.position,
      pick.player.current_rating, pick.player.potential_rating]) {
      const cell = document.createElement("td"); cell.textContent = value; row.append(cell);
    }
    if (paid) addSalaryCell(row, pick.player.contract ?? pick.player.contract_offer);
    return row;
  });
  document.querySelector("#draft-recap-rows").replaceChildren(...rows);
  document.querySelector("#draft-recap-caption").textContent = `Season ${draftState.draft_season} · Draft-day ratings`;
  document.querySelector("#draft-recap-empty").hidden = ownPicks.length > 0;
  document.querySelector("#draft-recap-table-wrap").hidden = ownPicks.length === 0;
  document.querySelector("#draft-recap").hidden = false;
}

function renderDraft() {
  if (!draftState) return;
  renderDraftRecap();
  autoDraftButton.hidden = !AUTO_DRAFT_ENABLED;
  autoDraftButton.disabled = !AUTO_DRAFT_ENABLED || draftBusy || draftState.complete;
  document.querySelector("#draft-position").disabled = draftBusy;
  draftPanel.setAttribute("aria-busy", String(draftBusy));
  document.querySelector("#draft-title").textContent = `Season ${draftState.draft_season} rookie draft`;
  document.querySelector("#draft-status").textContent = draftState.complete
    ? `All ${draftState.total_picks} picks are complete. Your ${draftState.rounds} rookies have joined your offseason roster.`
    : `Your turn · Round ${draftState.next_round} of ${draftState.rounds} · Overall pick ${draftState.next_pick} of ${draftState.total_picks}`;
  document.querySelector("#draft-format").textContent = `${draftState.rounds} rounds · Same order each round · CPU teams balance player quality and position needs. Rookies join your roster without replacing anyone. The regular-season ${rosterMinimum() ? "roster range" : "limit"} is ${rosterLimitText()}.`;
  if (draftState.next_contract) document.querySelector("#draft-status").textContent += ` · ${salaryLabel(draftState.next_contract)}`;
  const filter = document.querySelector("#draft-position").value;
  const rows = [];
  draftState.available.forEach((player, index) => {
    if (filter && player.position !== filter) return;
    const row = document.createElement("tr");
    row.dataset.prospectId = player.id;
    row.setAttribute("role", "row");
    const labels = ["Rank", "Player", "Position", "Age", "Current", "Potential"];
    [index + 1, player.name, player.position, player.age, player.current_rating, player.potential_rating].forEach((value, column) => {
      const cell = document.createElement("td"); cell.textContent = value;
      cell.dataset.label = labels[column]; cell.setAttribute("role", "cell"); row.append(cell);
    });
    const action = document.createElement("td"); action.setAttribute("role", "cell");
    const button = document.createElement("button"); button.type = "button";
    button.textContent = "Draft"; button.dataset.draftId = player.id;
    button.setAttribute("aria-label", `Draft ${player.name}, ${player.position}`);
    button.disabled = draftBusy || draftState.complete;
    action.append(button); row.append(action); rows.push(row);
  });
  document.querySelector("#draft-prospects").replaceChildren(...rows);
  document.querySelector("#draft-no-matches").hidden = rows.length > 0;
  const picks = draftState.picks.map(pick => {
    const item = document.createElement("li");
    item.value = pick.overall;
    item.textContent = `Round ${pick.round} · ${pick.team.city}: ${pick.player.name} · ${pick.player.position} · Current ${pick.player.current_rating} · Potential ${pick.player.potential_rating}${pick.player.contract || pick.player.contract_offer ? ` · ${salaryLabel(pick.player.contract ?? pick.player.contract_offer)}` : ""}`;
    if (pick.team.id === activeTeamId) item.className = "your-draft-pick";
    return item;
  });
  document.querySelector("#draft-picks").replaceChildren(...picks);
  document.querySelector("#draft-available").textContent = `${rows.length} shown · ${draftState.available.length} prospects available · Ratings out of 99`;
  document.querySelector("#draft-board").hidden = draftState.complete;
}

async function loadDraft(choice = null, autoDraft = false) {
  if (autoDraft && !AUTO_DRAFT_ENABLED) return;
  if (careerEnded() || draftBusy || campBusy || activeTrainingCamp || advancingSeason || !playoffState?.postseason_complete || activeSeason >= 999) return;
  if (autoDraft && draftState?.complete) return;
  const list = document.querySelector("#draft-prospect-list");
  const previousScroll = { top: list.scrollTop, left: list.scrollLeft };
  let committedPick = false;
  draftBusy = true;
  draftPanel.setAttribute("aria-busy", "true");
  document.querySelector("#draft-position").disabled = true;
  draftPendingChoice = choice;
  draftPendingAuto = autoDraft;
  autoDraftButton.disabled = true;
  draftButton.disabled = true;
  document.querySelector("#change-team-button").disabled = true;
  nextSeasonButton.disabled = true;
  document.querySelector("#draft-error").hidden = true;
  document.querySelector("#draft-retry").hidden = true;
  activateView("draft");
  if (draftState) renderDraft();
  document.querySelector("#draft-status").textContent = autoDraft ? "Auto-drafting your remaining picks…" : choice ? "Recording your pick and simulating CPU picks…" : "Loading rookie draft…";
  const teamId = activeTeamId, seed = activeRunSeed, season = activeSeason;
  const choices = [...(activeDraftChoices ?? []), ...(choice ? [choice] : [])];
  try {
    const data = await fetchDraft(choices, null, autoDraft);
    if (teamId !== activeTeamId || seed !== activeRunSeed || season !== activeSeason) return;
    applyDraft(data);
    saveProgress();
    committedPick = Boolean(choice || autoDraft);
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
    draftPanel.setAttribute("aria-busy", "false");
    document.querySelector("#draft-position").disabled = false;
    if (committedPick) {
      draftScrollPending = true;
      if (!draftPanel.hidden) returnToDraftTop();
    } else {
      list.scrollTop = previousScroll.top; list.scrollLeft = previousScroll.left;
      if (!draftPanel.hidden && !document.querySelector("#draft-retry").hidden) document.querySelector("#draft-retry").focus({ preventScroll: true });
    }
  }
}

function returnToDraftTop() {
  draftScrollPending = false;
  const list = document.querySelector("#draft-prospect-list");
  list.scrollTop = 0; list.scrollLeft = 0;
  const target = draftState?.complete ? document.querySelector("#draft-title") : list;
  target.focus({ preventScroll: true });
  target.scrollIntoView({ block: "start", behavior: "auto" });
}

draftButton.addEventListener("click", () => {
  if (draftButton.hidden || draftButton.disabled || !draftNavigationAvailable()) return;
  if (draftState) { renderDraft(); activateView("draft", { focus: true }); }
  else loadDraft();
});
document.querySelector("#draft-close").addEventListener("click", () => activateView("schedule", { focus: true }));
document.querySelector("#draft-roster").addEventListener("click", () => activateView("roster", { focus: true }));
document.querySelector("#roster-draft-return").addEventListener("click", () => activateView("draft", { focus: true }));
document.querySelector("#draft-position").addEventListener("change", () => {
  renderDraft();
  document.querySelector("#draft-prospect-list").scrollTop = 0;
  if (draftState && !draftBusy) saveProgress();
});
document.querySelector("#draft-retry").addEventListener("click", () => loadDraft(draftPendingChoice, draftPendingAuto));
autoDraftButton.addEventListener("click", () => loadDraft(null, true));
document.querySelector("#draft-prospects").addEventListener("click", event => {
  const button = event.target.closest("[data-draft-id]");
  if (button && !button.disabled) loadDraft(button.dataset.draftId);
});

function captureCutPlace(id, removing = false) {
  const row = [...document.querySelectorAll("#roster-groups .roster-player")]
    .find(row => row.dataset.playerId === id);
  if (!row) return null;
  const group = row.closest(".roster-group");
  const peers = [...group.querySelectorAll(".roster-player")];
  const index = peers.indexOf(row);
  const neighbor = removing ? peers[index + 1] ?? peers[index - 1] : row;
  return {
    id: neighbor?.dataset.playerId,
    visible: !document.querySelector("#panel-roster").hidden && rosterMode === "ratings" && group.open,
    // The next player takes the released player's place; the previous player
    // stays where it was when cutting the last row of a position.
    top: (removing && peers[index + 1] ? row : neighbor ?? row).getBoundingClientRect().top,
    x: window.scrollX,
    horizontal: [...document.querySelectorAll("#roster-groups .roster-group")]
      .map(group => [group.dataset.position, group.querySelector(".roster-rating-wrap").scrollLeft]),
  };
}

function restoreCutPlace(place) {
  if (!place) return;
  for (const [position, left] of place.horizontal) {
    document.querySelector(`#roster-groups [data-position="${position}"] .roster-rating-wrap`).scrollLeft = left;
  }
  if (!place.visible || document.querySelector("#panel-roster").hidden) return;
  const row = [...document.querySelectorAll("#roster-groups .roster-player")]
    .find(row => row.dataset.playerId === place.id);
  if (!row) return;
  const button = row.querySelector("[data-drop-id]");
  // A position at its minimum has only disabled Drop buttons. Its summary is
  // the nearby keyboard destination rather than the top of the whole roster.
  const target = button && !button.disabled ? button : row.closest(".roster-group").querySelector("summary");
  target.focus({ preventScroll: true });
  window.scrollTo({ left: place.x, top: window.scrollY + row.getBoundingClientRect().top - place.top, behavior: "instant" });
}

function renderCuts() {
  // Park the same controls before removing/rebuilding their surrounding row.
  rosterManagement.append(cutConfirmation);
  for (const row of document.querySelectorAll("#roster-groups .cut-confirmation-row")) row.remove();
  const available = !careerEnded() && Boolean(draftState?.complete) && (activeLineupRules < 18 || activeTrainingCamp);
  rosterManagement.hidden = !available;
  // Reuse the rating rows so ages, trends, rookies, and starters stay together.
  for (const cell of document.querySelectorAll("#roster-groups .roster-cut-action")) cell.remove();
  if (!available || !rosterProfile) return;
  document.querySelector("#cut-count").textContent = `${rosterProfile.roster.length}/${rosterLimit()} players${rosterMinimum() ? ` (minimum ${rosterMinimum()})` : ""} · ${rosterCutStatus(rosterProfile.roster.length)}`;
  const atRosterMinimum = rosterProfile.roster.length <= rosterMinimum();
  const capCut = capOverage() > 0;
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
      const canReplace = capCut || (activeLineupRules >= 23 && Boolean(player.renewal_offer));
      button.textContent = canReplace ? "Drop" : count <= rule.minimum ? "Minimum reached" : atRosterMinimum ? "Roster minimum reached" : "Drop";
      button.disabled = cutBusy || advancingSeason || (!canReplace && (count <= rule.minimum || atRosterMinimum));
      button.setAttribute("aria-label", `Drop ${player.name}, ${player.position}`);
      if (canReplace) button.title = `Any vacancy receives a weak ${replacementPay()} replacement to preserve minimums`;
      else if (count <= rule.minimum) button.title = `Keep at least ${rule.minimum} ${player.position} players`;
      else if (atRosterMinimum) button.title = `Keep at least ${rosterMinimum()} players on the roster`;
      if (player.renewal_offer) {
        const resign = document.createElement("button"); resign.type = "button";
        resign.className = "secondary-button"; resign.dataset.resignId = player.id;
        resign.textContent = "Re-sign"; resign.disabled = cutBusy || advancingSeason || player.renewal_offer.affordable === false;
        if (player.renewal_offer.affordable === false) resign.title = "Not enough cap space. Release unsigned rookies or expired contracts first; signed salaries remain guaranteed.";
        resign.setAttribute("aria-label", `Re-sign ${player.name}, ${player.position}`);
        cell.append(resign, document.createTextNode(" "));
      }
      cell.append(button);
      row.append(cell);
    }
  }
  if (pendingCut && !cutConfirmation.hidden) {
    const selected = [...document.querySelectorAll("#roster-groups .roster-player")]
      .find(row => row.dataset.playerId === pendingCut);
    if (selected) {
      const row = document.createElement("tr");
      row.className = "cut-confirmation-row";
      const cell = document.createElement("td");
      cell.colSpan = selected.children.length;
      cell.append(cutConfirmation);
      row.append(cell);
      selected.after(row);
    }
  }
}
function openCuts() {
  if (careerEnded() || !draftState?.complete || cutBusy || advancingSeason || (activeLineupRules >= 18 && !activeTrainingCamp)) return;
  draftScrollPending = false;
  activateView("roster", { focus: true });
  rosterMode = "ratings";
  renderRosterStats();
  renderCuts();
}
manageRoster.addEventListener("click", openCuts);
function cancelCut() {
  const place = captureCutPlace(pendingCut);
  pendingCut = null;
  document.querySelector("#cut-confirmation").hidden = true;
  document.querySelector("#cut-error").hidden = true;
  renderCuts();
  restoreCutPlace(place);
}
document.querySelector("#cut-cancel").addEventListener("click", cancelCut);
document.querySelector("#roster-groups").addEventListener("click", event => {
  const button = event.target.closest("[data-drop-id], [data-resign-id]");
  if (careerEnded() || !button || button.disabled || cutBusy || advancingSeason || !draftState?.complete || (activeLineupRules >= 18 && !activeTrainingCamp) || (!button.dataset.resignId && rosterProfile.roster.length <= rosterMinimum() && !capOverage() && activeLineupRules < 23)) return;
  pendingRosterKind = button.dataset.resignId ? "resign" : "drop";
  pendingCut = button.dataset.resignId ?? button.dataset.dropId;
  const player = rosterProfile.roster.find(p => p.id === pendingCut);
  document.querySelector("#cut-error").hidden = true;
  if (pendingRosterKind === "resign" && !player.renewal_offer) { pendingCut = null; return; }
  document.querySelector("#cut-confirm").textContent = pendingRosterKind === "resign" ? "Confirm re-sign" : "Confirm drop";
  document.querySelector("#cut-confirm-text").textContent = pendingRosterKind === "resign" ? `Re-sign ${player.name} (${player.position}) for $${(player.renewal_offer.annual_salary/1000000).toFixed(2)}M/year, ${player.renewal_offer.years} years, starting Season ${player.renewal_offer.starts_season}? ${player.renewal_offer.demand_rating !== undefined ? `Priced from ${player.current_rating} current / ${player.potential_rating} potential (average ${player.renewal_offer.demand_rating}). ` : ""}Final payroll must fit the cap before continuing.` : `Drop ${player.name} (${player.position})? This removes the player from your next-season roster.${activeLineupRules >= 23 && player.contract?.years_remaining > 0 ? ` Remaining signed salary stays on the cap through Season ${player.contract.expires_after_season}.` : ""}${capOverage() || activeLineupRules >= 23 ? ` Any vacancy receives a weak ${replacementPay()} replacement to preserve minimums.` : ""}`;
  cutConfirmation.hidden = false;
  renderCuts();
  // Confirmation is now beside the chosen player, not above the whole roster.
  document.querySelector("#cut-confirm").focus({ preventScroll: true });
  const bottom = cutConfirmation.getBoundingClientRect().bottom;
  if (bottom > window.innerHeight) window.scrollTo({ left: window.scrollX,
    top: window.scrollY + bottom - window.innerHeight + 16, behavior: "instant" });
});
document.querySelector("#cut-confirm").addEventListener("click", async () => {
  if (careerEnded() || !pendingCut || cutBusy || advancingSeason || !draftState?.complete || (activeLineupRules >= 18 && !activeTrainingCamp) || (pendingRosterKind === "drop" && rosterProfile.roster.length <= rosterMinimum() && !capOverage() && activeLineupRules < 23)) return;
  cutBusy = true;
  document.querySelector("#cut-confirm").disabled = true;
  document.querySelector("#cut-cancel").disabled = true;
  document.querySelector("#cut-error").hidden = true;
  document.querySelector("#change-team-button").disabled = true;
  nextSeasonButton.disabled = true;
  renderCuts();
  let place;
  try {
    const kind = pendingRosterKind;
    const data = await careerRequest(kind === "resign" ? "resign" : "cuts", {
      manual_picks: activeDraftChoices,
      dropped: kind === "drop" ? [...activeDropped, pendingCut] : activeDropped,
      ...(activeLineupRules >= 20 ? { roster_actions: [...activeRosterActions, {kind,player_id:pendingCut}] } : {}),
    });
    place = captureCutPlace(pendingCut, kind === "drop");
    pendingCut = null;
    cutConfirmation.hidden = true;
    applyDraft(data);
    saveProgress();
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
    if (place) restoreCutPlace(place);
    else if (pendingCut && !document.querySelector("#panel-roster").hidden) document.querySelector("#cut-confirm").focus({ preventScroll: true });
  }
});

campButton.addEventListener("click", async () => {
  if (campButton.hidden || campButton.disabled || campBusy || draftBusy || cutBusy || advancingSeason || careerEnded() || !draftState?.complete || activeTrainingCamp) return;
  campBusy = true;
  updateOffseasonActions();
  document.querySelector("#change-team-button").disabled = true;
  errorBox.hidden = true;
  try {
    const data = await careerRequest("camp", { manual_picks: activeDraftChoices, dropped: [] });
    if (data.team?.id !== activeTeamId || data.run_seed !== activeRunSeed || data.season !== activeSeason || !data.training_camp || data.development_season !== activeSeason+1 || !draftChoicesMatch(data, activeDraftChoices, false, activeDraftRounds)) throw new Error("Training camp could not be loaded. Please try again.");
    applyDraft(data);
    saveProgress();
    activateView("roster", { focus: true });
    if (developmentRecap) developmentDialog.showModal();
  } catch (error) { showError(error.message); }
  finally {
    campBusy = false;
    document.querySelector("#change-team-button").disabled = false;
    updateOffseasonActions();
    renderCuts();
  }
});

nextSeasonButton.addEventListener("click", async () => {
  if (careerEnded() || advancingSeason || nextSeasonButton.disabled || (activeDraftChoices?.length !== activeDraftRounds || !draftState?.complete || !rosterReady() || (activeLineupRules >= 18 && !activeTrainingCamp)) || cutBusy || draftBusy || campBusy || !playoffState?.postseason_complete || !regularSnapshot || activeSeason >= 999) return;
  advancingSeason = true;
  nextSeasonButton.disabled = true;
  manageRoster.disabled = true;
  renderCuts();
  draftButton.disabled = true;
  document.querySelector("#change-team-button").disabled = true;
  errorBox.hidden = true;
  const hadCamp = activeTrainingCamp;
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
    const lineupRules = activeLineupRules >= 11 ? 26 : 10;
    // Re-rank the new roster after development and draft/cuts. Prior-season
    // overrides remain only in career history, where completed games need them.
    const lineupChanges = [];
    const career = [...activeCareer, {
      season: activeSeason, prior_standings: Object.keys(activePriorStandings).length ? activePriorStandings : null,
      manual_picks: activeDraftChoices, draft_rounds: activeDraftRounds, dropped: activeDropped, lineup_rules: activeLineupRules,
      ...(activeRosterActions.length ? { roster_actions: activeRosterActions } : {}),
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
    renderWelcome();
    setDevelopmentRecap(profile, nextSeason);
    saveProgress();
    if (developmentRecap && !hadCamp) developmentDialog.showModal();
  } catch (error) {
    showError(error.message);
  } finally {
    advancingSeason = false;
    updatePhaseActions();
    updateOffseasonActions();
    manageRoster.disabled = false;
    renderCuts();
    draftButton.disabled = false;
    document.querySelector("#change-team-button").disabled = false;
  }
});

loadTeams();
