const {test} = require('node:test');
const assert = require('node:assert/strict');
const {mkdtempSync,writeFileSync,readFileSync,existsSync,rmSync} = require('node:fs');
const {tmpdir} = require('node:os');
const path = require('node:path');
const {runSuites, discoverSuites} = require('../scripts/run-ui-tests.cjs');

function fixtures(t, sources) {
  const dir = mkdtempSync(path.join(tmpdir(),'league-runner-'));
  t.after(() => rmSync(dir,{recursive:true,force:true}));
  return sources.map((source,i) => {const p=path.join(dir,`${i}.cjs`);writeFileSync(p,source);return p;});
}

test('bounded workers overlap suites, retain output and run every file exactly once', async t => {
  const dir=mkdtempSync(path.join(tmpdir(),'league-overlap-'));
  t.after(()=>rmSync(dir,{recursive:true,force:true}));
  const events=path.join(dir,'events');
  const files=fixtures(t,Array.from({length:5},()=>`const fs=require('node:fs');console.log('started');fs.appendFileSync(${JSON.stringify(events)},'start\\n');setTimeout(()=>{fs.appendFileSync(${JSON.stringify(events)},'end\\n');console.log('finished')},150)`));
  const completed=[];
  const result=await runSuites(files,{workers:2,onResult:r=>completed.push(r.suite)});
  assert.equal(result.passed,true);assert.deepEqual([...completed].sort(),[...files].sort());
  for(const suite of result.suites) assert.match(suite.output,/started\nfinished/);
  let active=0,maximum=0;
  for(const event of readFileSync(events,'utf8').trim().split('\n')){
    active+=event==='start'?1:-1;maximum=Math.max(maximum,active);assert.ok(active>=0&&active<=2);
  }
  assert.equal(maximum,2);assert.equal(active,0);
});

test('failure remains failure and does not skip remaining checks',async t=>{
  const files=fixtures(t,[`console.error('deliberate failure');process.exitCode=7`,`console.log('still checked')`]);
  const result=await runSuites(files,{workers:1});
  assert.equal(result.passed,false);assert.equal(result.suites.length,2);
  assert.equal(result.suites[0].code,7);assert.match(result.suites[0].output,/deliberate failure/);
  assert.equal(result.suites[1].passed,true);
});

test('hung suite is terminated and reported as a timeout',async t=>{
  const files=fixtures(t,[`setInterval(()=>{},1000)`]);
  const result=await runSuites(files,{workers:1,timeoutMs:200});
  assert.equal(result.passed,false);assert.equal(result.suites[0].timedOut,true);
});

test('invalid concurrency is rejected before starting suites',async()=>{
  for(const workers of [0,5,1.5,NaN])await assert.rejects(runSuites([],{workers}),/Workers/);
});

test('discovery includes interaction suites but excludes helpers and runner self-tests',()=>{
  const files=discoverSuites(path.resolve(__dirname,'..'));
  assert.ok(files.includes('tests/ui_tabs.cjs'));assert.equal(files.length,14);
  assert.ok(!files.some(file=>file.includes('helpers')||file.includes('.test.')));
});

test('timeout also stops the suite API-server process group', {skip:process.platform==='win32'}, async t=>{
  const dir=mkdtempSync(path.join(tmpdir(),'league-child-'));
  t.after(()=>rmSync(dir,{recursive:true,force:true}));
  const marker=path.join(dir,'orphan');
  const child=`setTimeout(()=>require('node:fs').writeFileSync(${JSON.stringify(marker)},'still running'),600)`;
  const files=fixtures(t,[`require('node:child_process').spawn(process.execPath,['-e',${JSON.stringify(child)}]);console.log('child started');setInterval(()=>{},1000)`]);
  const result=await runSuites(files,{workers:1,timeoutMs:300});
  assert.match(result.suites[0].output,/child started/);assert.equal(result.suites[0].timedOut,true);
  await new Promise(resolve=>setTimeout(resolve,700));assert.equal(existsSync(marker),false);
});
