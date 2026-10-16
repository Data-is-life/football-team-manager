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
let rosterMode = "ratings";
let rosterTotals = null;

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
const leaguePanels = [
  ["#league-results-toggle", "#league-results", "league results"],
  ["#standings-toggle", "#group-standings", "group standings"],
  ["#playoff-race-toggle", "#playoff-race-content", "playoff race"],
].map(([buttonSelector, contentSelector, label]) => ({
  button: document.querySelector(buttonSelector),
  content: document.querySelector(contentSelector),
  label,
}));

function setLeaguePanelExpanded(panel, expanded) {
  panel.content.hidden = !expanded;
  panel.button.setAttribute("aria-expanded", String(expanded));
  panel.button.textContent = `${expanded ? "Hide" : "Show"} ${panel.label}`;
}

for (const panel of leaguePanels) {
  panel.button.addEventListener("click", () => {
    setLeaguePanelExpanded(panel, panel.content.hidden);
  });
}

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

function renderTeamProfile(profile) {
  rosterProfile = profile;
  rosterMode = "ratings";
  rosterCompetition.value = "regular";
  rosterTotals = { regular: profile.roster_stats, playoffs: profile.roster_stats };
  document.querySelector("#offense-rating").textContent = profile.ratings.offense;
  document.querySelector("#defense-rating").textContent = profile.ratings.defense;
  const groups = profile.roster_rules.map((rule) => {
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
    table.innerHTML = '<thead><tr><th scope="col">Depth</th><th scope="col">Player</th><th scope="col">Experience</th><th scope="col">Scouting rating</th></tr></thead>';
    const body = document.createElement("tbody");
    for (const player of players) {
      const row = document.createElement("tr");
      row.className = "roster-player";
      row.dataset.playerId = player.id;
      for (const value of [player.depth, player.name, `${player.experience} yr`, player.rating]) {
        const cell = document.createElement("td");
        cell.textContent = value;
        row.append(cell);
      }
      body.append(row);
    }
    table.append(body);
    wrap.append(table);
    const statsWrap = document.createElement("div");
    statsWrap.className = "table-wrap roster-stats-wrap";
    const untracked = document.createElement("p");
    untracked.className = "roster-note roster-untracked-note";
    untracked.textContent = "Season production isn't tracked for this position yet. Ratings are shown below.";
    group.append(summary, untracked, wrap, statsWrap);
    return group;
  });
  document.querySelector("#roster-groups").replaceChildren(...groups);
  document.querySelector("#roster-title").textContent = `Roster · ${profile.roster.length} players`;
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
  const snapshot = rosterTotals[rosterCompetition.value];
  const competition = rosterCompetition.value === "regular" ? "Regular season" : "Playoffs";
  status.textContent = `${competition} · ${snapshot.games} team game${snapshot.games === 1 ? "" : "s"} recorded.${snapshot.games ? "" : " No completed games in this competition."}`;
  const totals = new Map(snapshot.players.map(player => [player.player_id, player]));
  const decimal = value => value == null ? "—" : value.toFixed(1);
  const percentage = value => value == null ? "—" : `${value.toFixed(1)}%`;
  const column = (category, key, label, format) => ({ category, key, label, format });
  const receiving = [column("receiving", "receptions", "Rec"), column("receiving", "yards", "Rec Yds"),
    column("receiving", "yards_per_reception", "Y/Rec", decimal), column("receiving", "touchdowns", "Rec TD")];
  const columns = {
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
  for (const group of document.querySelectorAll(".roster-group")) {
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
    for (const label of ["Depth", "Player", ...columns[position].map(item => item.label)]) {
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
      const values = [player.depth, player.name, ...columns[position].map(item => {
        const value = entry[item.category][item.key];
        return item.format ? item.format(value) : value;
      })];
      for (const value of values) {
        const cell = document.createElement("td");
        cell.textContent = value;
        row.append(cell);
      }
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

function renderSchedule(data) {
  activeTeamId = data.team.id;
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
  activateView("schedule");
  document.querySelector("#team-group").textContent = data.team.group;
  document.querySelector("#team-name").textContent = data.team.city;
  document.querySelector("#rotation-note").textContent =
    `Season ${data.season} rotation: ${data.rotating_group} · Scores show your team first.`;

  scheduleGrid.replaceChildren();
  for (const game of data.games) {
    const article = document.createElement("article");
    article.className = "game-card";
    article.innerHTML = `
      <span class="week">Week ${game.week}</span>
      <span class="venue ${game.venue.toLowerCase()}">${game.venue === "Home" ? "vs" : "at"}</span>
      <strong>${game.opponent}</strong>
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
  leaguePanels.forEach(panel => setLeaguePanelExpanded(panel, true));
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
    statTable("Receiving", box.receiving, [playerColumn, { key: "receptions", label: "Rec" }, { key: "yards", label: "Yds" }, { key: "yards_per_reception", label: "Y/Rec", format: decimal }, { key: "touchdowns", label: "TD" }]),
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
          <thead><tr><th>#</th><th>Team</th><th>Record</th><th>Diff</th></tr></thead>
          <tbody>
            ${group.teams.map((row) => `
              <tr class="${row.team.id === activeTeamId ? "selected-team" : ""}">
                <td>${row.rank}</td>
                <td><span class="team-cell">${row.team.city}${row.rank === 1 ? '<b class="leader-mark">L</b>' : ""}</span></td>
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
  form.querySelector('button[type="submit"]').textContent = "Start new season";
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
  submit.textContent = "Loading team…";
  select.disabled = true;
  cancelTeamChange.disabled = true;
  errorBox.hidden = true;
  try {
    const teamId = select.value;
    const [scheduleResponse, profileResponse] = await Promise.all([
      fetch(`/api/schedule/${teamId}?season=1`),
      fetch(`/api/team/${teamId}`),
    ]);
    if (!scheduleResponse.ok || !profileResponse.ok) {
      throw new Error("Your team could not be loaded. Please try again.");
    }
    const [schedule, profile] = await Promise.all([
      scheduleResponse.json(), profileResponse.json(),
    ]);
    renderTeamProfile(profile);
    renderSchedule(schedule);
  } catch (error) {
    showError(error.message);
  } finally {
    submit.disabled = false;
    submit.textContent = activeTeamId ? "Start new season" : "Start season";
    select.disabled = false;
    cancelTeamChange.disabled = false;
  }
});

simulateButton.addEventListener("click", async () => {
  if (!activeTeamId || currentWeek >= 17) return;
  simulateButton.disabled = true;
  simulateButton.textContent = "Simulating…";
  errorBox.hidden = true;
  try {
    const nextWeek = currentWeek + 1;
    const response = await fetch(`/api/season/${activeTeamId}/week/${nextWeek}?season=1`);
    if (!response.ok) throw new Error("The week could not be simulated.");
    renderResult(await response.json());
  } catch (error) {
    simulateButton.disabled = false;
    simulateButton.textContent = `Simulate Week ${currentWeek + 1}`;
    showError(error.message);
  }
});

document.querySelector("#away-tab").addEventListener("click", () => selectBoxScore("away"));
document.querySelector("#home-tab").addEventListener("click", () => selectBoxScore("home"));


function playoffGameCard(game) {
  const result = game.result;
  const venue = game.neutral_site ? "Neutral-site championship" : "Higher seed hosts";
  const label = result ? `Final${result.overtime ? " · OT" : ""}` : venue;
  const row = (side) => {
    const entry = game[side];
    const won = result && game.winner.team.id === entry.team.id;
    return `<div class="league-team ${won ? "winner" : ""}"><span>#${entry.seed} ${entry.team.city}</span><strong>${result ? result[side].score : ""}</strong></div>`;
  };
  return `<article class="league-result-card"><span class="control-label">${label}</span>${row("away")}${row("home")}</article>`;
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
  const status = !data.qualified ? "Your team missed the playoffs. Follow the league through the championship."
    : selectedChampion ? "Your team are champions!"
    : data.eliminated ? "Your team has been eliminated. You can still follow the remaining rounds."
    : data.completed_round === 0 && data.field.some(team => team.team.id === activeTeamId && team.bye)
      ? "Your team earned a Wild Card bye. Advance the round to see your quarterfinal opponent."
    : "Your team is still in the title race.";
  document.querySelector("#postseason-status").textContent = status;
  document.querySelector("#season-status").textContent = data.champion
    ? `Season ${data.season} champions: ${data.champion.team.city}.`
    : data.completed_round ? `${data.rounds.at(-1).name} complete. ${status}` : status;
  const banner = document.querySelector("#champion-banner");
  banner.hidden = !champion;
  banner.textContent = champion ? `Season ${data.season} champions: ${champion.team.city} · Seed #${champion.seed}` : "";
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
  const otherGames = latestRound ? latestRound.games.filter(game => game !== selectedGame) : [];
  document.querySelector("#other-playoff-results").hidden = otherGames.length === 0;
  document.querySelector("#playoff-league-games").innerHTML = otherGames.map(playoffGameCard).join("");
  const upcoming = data.upcoming;
  document.querySelector("#postseason-upcoming").innerHTML = upcoming
    ? `<h3>Next: ${upcoming.name}</h3>
       ${upcoming.byes.length ? `<p class="roster-note">Byes: ${upcoming.byes.map(team => `#${team.seed} ${team.team.city}`).join(", ")}</p>` : ""}
       <p class="roster-note">${upcoming.number === 4 ? "Neutral site. No home advantage." : "Reseeded by original seed: highest remaining seed plays lowest. Higher seeds host."}</p>
       <div class="league-results-grid">${upcoming.games.map(playoffGameCard).join("")}</div>`
    : "";
  document.querySelector("#postseason-history").innerHTML = data.rounds.length
    ? data.rounds.map(round => `<h3>${round.name}</h3><div class="league-results-grid">${round.games.map(playoffGameCard).join("")}</div>`).join("")
    : '<p class="roster-note">No playoff rounds completed yet.</p>';
}

async function loadPlayoffRound(number) {
  errorBox.hidden = true;
  playoffsStart.disabled = true;
  playoffSimulate.disabled = true;
  document.querySelector("#change-team-button").disabled = true;
  try {
    const response = await fetch(`/api/playoffs/${activeTeamId}/round/${number}?season=1`);
    if (!response.ok) throw new Error("The playoff round could not be loaded. Please try again.");
    renderPostseason(await response.json());
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

loadTeams();
