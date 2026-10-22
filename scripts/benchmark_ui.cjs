// DOM construction only: jsdom does not measure browser layout or paint.
const fs = require('node:fs');
const {performance} = require('node:perf_hooks');
const {JSDOM} = require('jsdom');
const data = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const dom = new JSDOM(fs.readFileSync('app/static/index.html', 'utf8'), {
  url: 'http://localhost', runScripts: 'outside-only'
});
const w = dom.window;
w.fetch = async () => ({ok: true, json: async () => data.teams});
w.HTMLElement.prototype.scrollIntoView = () => {};
w.eval(fs.readFileSync('app/static/app.js', 'utf8'));
function measure(operation) {
  for (let i = 0; i < 3; i++) operation();
  const values = [];
  for (let i = 0; i < 20; i++) {
    const start = performance.now(); operation(); values.push(performance.now() - start);
  }
  values.sort((a, b) => a - b);
  return {n: values.length, median_ms: +((values[9] + values[10]) / 2).toFixed(2),
    p95_ms: +values[18].toFixed(2)};
}
(async () => {
  await new Promise(resolve => setImmediate(resolve));
  w.renderTeamProfile(data.profile);
  w.renderSchedule(data.schedule, 1234);
  const schedule = measure(() => w.renderResult(data.week));
  w.document.querySelector('#roster-stats-button').click();
  const stats = measure(() => w.renderResult(data.week));
  const scouting = measure(() => w.createRosterGroups(data.profile, false));
  process.stdout.write(JSON.stringify({schedule_view: schedule, roster_stats_mode: stats,
    scouting_roster: scouting}));
  dom.window.close();
})().catch(error => {console.error(error); process.exitCode = 1;});
