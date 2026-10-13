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
const rosterButton = document.querySelector("#roster-button");
const cancelTeamChange = document.querySelector("#cancel-team-change");
let activeTeamId = null;
let currentWeek = 0;
let latestResult = null;

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
  document.querySelector("#offense-rating").textContent = profile.ratings.offense;
  document.querySelector("#defense-rating").textContent = profile.ratings.defense;
  const rows = profile.roster.map((player) => {
    const row = document.createElement("tr");
    for (const value of [player.position, player.name, player.rating]) {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.append(cell);
    }
    return row;
  });
  document.querySelector("#roster-players").replaceChildren(...rows);
  rosterSection.hidden = false;
  rosterButton.setAttribute("aria-expanded", "true");
  rosterButton.textContent = "Hide roster";
}

function renderSchedule(data) {
  activeTeamId = data.team.id;
  currentWeek = 0;
  latestResult = null;
  document.querySelector("#team-group").textContent = data.team.group;
  document.querySelector("#team-name").textContent = data.team.city;
  document.querySelector("#rotation-note").textContent =
    `Season ${data.season} rotation: ${data.rotating_group}`;

  scheduleGrid.replaceChildren();
  for (const game of data.games) {
    const article = document.createElement("article");
    article.className = "game-card";
    article.innerHTML = `
      <span class="week">Week ${game.week}</span>
      <span class="venue ${game.venue.toLowerCase()}">${game.venue === "Home" ? "vs" : "at"}</span>
      <strong>${game.opponent}</strong>
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
    <tr>${columns.map((column) => `<td>${row[column.key]}</td>`).join("")}</tr>
  `).join("");
  return `
    <section class="stat-section">
      <h3>${title}</h3>
      <div class="table-wrap"><table><thead><tr>${headings}</tr></thead><tbody>${body}</tbody></table></div>
    </section>
  `;
}

function renderPlayerStats(box) {
  const playerColumn = { key: "player", label: "Player" };
  document.querySelector("#player-stats").innerHTML = [
    statTable("Passing", box.passing, [playerColumn, { key: "completions", label: "Cmp" }, { key: "attempts", label: "Att" }, { key: "yards", label: "Yds" }, { key: "touchdowns", label: "TD" }, { key: "interceptions", label: "INT" }]),
    statTable("Rushing", box.rushing, [playerColumn, { key: "attempts", label: "Att" }, { key: "yards", label: "Yds" }, { key: "touchdowns", label: "TD" }]),
    statTable("Receiving", box.receiving, [playerColumn, { key: "receptions", label: "Rec" }, { key: "yards", label: "Yds" }, { key: "touchdowns", label: "TD" }]),
    statTable("Kicking", box.kicking, [playerColumn, { key: "field_goals_made", label: "FGM" }, { key: "field_goals_attempted", label: "FGA" }, { key: "extra_points_made", label: "XP" }]),
  ].join("");
}

function selectBoxScore(side) {
  const awayTab = document.querySelector("#away-tab");
  const homeTab = document.querySelector("#home-tab");
  awayTab.classList.toggle("active", side === "away");
  homeTab.classList.toggle("active", side === "home");
  renderPlayerStats(latestResult[side]);
}

function renderResult(data) {
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

  const completedCard = scheduleGrid.children[data.week - 1];
  if (completedCard) {
    completedCard.classList.add("completed");
    completedCard.dataset.outcome = latestResult.outcome;
  }

  currentWeek = data.week;
  simulateButton.disabled = data.season_complete;
  simulateButton.textContent = data.season_complete ? "Regular season complete" : `Simulate Week ${data.next_week}`;
  resultPanel.scrollIntoView({ behavior: "smooth", block: "start" });
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

rosterButton.addEventListener("click", () => {
  rosterSection.hidden = !rosterSection.hidden;
  rosterButton.setAttribute("aria-expanded", String(!rosterSection.hidden));
  rosterButton.textContent = rosterSection.hidden ? "View roster" : "Hide roster";
});

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

loadTeams();
