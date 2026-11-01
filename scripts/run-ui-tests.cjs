// Each suite owns a distinct API port and an isolated jsdom/localStorage session.
const {spawn} = require('node:child_process');
const {readdirSync, writeFileSync} = require('node:fs');
const path = require('node:path');
const {performance} = require('node:perf_hooks');

function stop(child) {
  try {
    if (process.platform === 'win32') child.kill('SIGKILL');
    else process.kill(-child.pid, 'SIGKILL'); // Include the suite's uvicorn child.
  } catch (error) { if (error.code !== 'ESRCH') throw error; }
}

async function runSuites(files, {workers = 2, timeoutMs = 300000, onResult = () => {}} = {}) {
  if (!Number.isInteger(workers) || workers < 1 || workers > 4) throw new Error('Workers must be an integer from 1 to 4');
  const started = performance.now(), active = new Set(), results = [];
  let cursor = 0, interrupted = false;
  const cancel = () => { interrupted = true; for (const child of active) stop(child); };
  process.once('SIGINT', cancel); process.once('SIGTERM', cancel);
  try {
    async function worker() {
      while (!interrupted && cursor < files.length) {
        const file = files[cursor++], start = performance.now();
        const result = await new Promise(resolve => {
          const child = spawn(process.execPath, [file], {detached: process.platform !== 'win32', stdio: ['ignore', 'pipe', 'pipe']});
          active.add(child);
          let output = '', timedOut = false, spawnError;
          child.stdout.on('data', data => { output += data; });
          child.stderr.on('data', data => { output += data; });
          const timer = setTimeout(() => { timedOut = true; stop(child); }, timeoutMs);
          child.on('error', error => { spawnError = error.message; });
          child.on('close', (code, signal) => {
            clearTimeout(timer); active.delete(child);
            resolve({suite: file, seconds: Number(((performance.now()-start)/1000).toFixed(3)),
              passed: code === 0 && !timedOut && !spawnError, code, signal, timedOut, output, ...(spawnError ? {error: spawnError} : {})});
          });
        });
        results.push(result); onResult(result);
      }
    }
    await Promise.all(Array.from({length: Math.min(workers, files.length)}, worker));
    return {workers, totalSeconds: Number(((performance.now()-started)/1000).toFixed(3)), interrupted,
      passed: !interrupted && results.length === files.length && results.every(r => r.passed), suites: results};
  } finally {
    process.removeListener('SIGINT', cancel); process.removeListener('SIGTERM', cancel);
    for (const child of active) stop(child);
  }
}

function discoverSuites(root) {
  return readdirSync(path.join(root, 'tests')).filter(file => /^ui_[a-z_]+\.cjs$/.test(file) && !file.endsWith('_helpers.cjs'))
    // Start the measured longest suite first so it does not become a tail job.
    .sort((a, b) => a === b ? 0 : a === 'ui_tabs.cjs' ? -1 : b === 'ui_tabs.cjs' ? 1 : a.localeCompare(b))
    .map(file => `tests/${file}`);
}

async function main() {
  let workers = 2, report;
  for (const arg of process.argv.slice(2)) {
    if (arg.startsWith('--workers=')) workers = Number(arg.slice(10));
    else if (arg.startsWith('--report=')) report = arg.slice(9);
    else throw new Error(`Unknown argument: ${arg}`);
  }
  const root = path.resolve(__dirname, '..');
  process.chdir(root);
  const files = discoverSuites(root);
  if (!files.length) throw new Error('No UI suites found');
  const result = await runSuites(files, {workers, onResult: r => {
    process.stdout.write(`\n${r.passed ? 'PASS' : 'FAIL'} ${r.suite} (${r.seconds}s)${r.timedOut ? ' — timed out' : ''}\n${r.output}`);
  }});
  if (report) writeFileSync(report, JSON.stringify(result, null, 2) + '\n');
  console.log(`\n${result.suites.filter(r => r.passed).length}/${files.length} UI suites passed in ${result.totalSeconds}s (${workers} workers)`);
  if (!result.passed) process.exitCode = 1;
}

module.exports = {runSuites, discoverSuites};
if (require.main === module) main().catch(error => { console.error(error); process.exitCode = 1; });
