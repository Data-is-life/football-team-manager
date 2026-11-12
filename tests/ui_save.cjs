const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {spawn} = require('node:child_process');
const {JSDOM} = require('jsdom');
const root = path.resolve(__dirname, '..');
const base = 'http://127.0.0.1:8769';
const key = 'arcade-league-save';
const script = fs.readFileSync(path.join(root,'app/static/app.js'),'utf8');
const html = fs.readFileSync(path.join(root,'app/static/index.html'),'utf8');
const cache = new Map();
async function api(url) {
 if (!cache.has(url)) cache.set(url, fetch(base+url).then(async r=> {
  assert.equal(r.ok,true,url);return r.json();
 }));
 return structuredClone(await cache.get(url));
}
async function until(check) {
 for(let i=0;i<1500;i++) {if(check()) return;await new Promise(r=>setTimeout(r,10));}
 throw new Error('UI state timed out');
}
function page(raw, {fail=false, blocked=false}={}) {
 const dom = new JSDOM(html,{url:base,runScripts:'outside-only'});
 const w=dom.window,d=w.document;
 w.HTMLElement.prototype.scrollIntoView=()=>{};
 w.HTMLDialogElement.prototype.close=function(){this.open=false};
 w.HTMLDialogElement.prototype.showModal=function(){this.open=true};
 Object.defineProperty(w.crypto,'getRandomValues',{value:array=>{array[0]=5678;return array}});
 if(raw!==undefined) w.localStorage.setItem(key,raw);
 if(blocked) w.Storage.prototype.setItem=function(){throw new Error('Quota exceeded')};
 const state={fail};
 w.fetch=async url=> state.fail && url!=='/api/teams' ? {ok:false} : {ok:true,json:()=>api(url)};
 w.eval(script);
 return {dom,w,d,state};
}
const status=p=>p.d.querySelector('#save-status').textContent;
const saved=p=>p.w.localStorage.getItem(key);
async function restored(raw, options) {
 const p=page(raw,options);
 await until(()=>/restored|could not/.test(status(p)));
 return p;
}
function checkpoint(teamId,week,playoffRound=null) {
 return JSON.stringify({version:1,teamId,runSeed:1234,season:1,week,playoffRound});
}
function snapshot(p) {
 const q=sel=>p.d.querySelector(sel).textContent;
 return {roster:q('#roster-groups'),schedule:q('#schedule'),record:q('#season-record'),
  standings:q('#group-standings'),race:q('#playoff-race'),bracket:q('#playoff-bracket'),
  outcome:q('#postseason-status'),qualification:q('#qualification-status'),game:q('#result-panel')};
}
async function checks() {
 const final=await api('/api/playoffs/seattle/round/4?season=1&run_seed=1234');
 const id=final.champion.team.id;
 // Start a fresh game and verify the first successful load creates a save.
 let p=page();
 await until(()=>p.d.querySelector('#team-select').options.length===31);
 p.d.querySelector('#team-select').value=id;
 p.d.querySelector('#team-form').dispatchEvent(new p.w.Event('submit',{cancelable:true}));
 await until(()=>/Progress saved/.test(status(p)));
 assert.match(p.d.querySelector("#owner-feedback").textContent,/hired.*four-year/);
 assert.deepEqual(JSON.parse(saved(p)),{version:41,welcomeDismissed:false,ownerUpdateDismissed:0,draftRounds:6,careerStartWeek:17,lineupChanges:[],contracts:true,teamId:id,runSeed:5678,season:1,week:16,lineupRules:34,developmentStart:1,rebuildTeam:id,priorStandings:{},history:[],draftChoices:null,dropped:[],career:[],playoffRound:null});
 assert.equal(p.d.querySelector('#rebuild-note').hidden,false);
 for(const id of ['offense-rating','defense-rating'])assert.ok(Number(p.d.querySelector('#'+id).textContent)>=68&&Number(p.d.querySelector('#'+id).textContent)<=72);
 // Welcome remains visible on reload until dismissed, then stays dismissed
 // for this career. Reading the current guide or previews is read-only.
 assert.equal(p.d.querySelector('#career-welcome').hidden,false);
 const undismissed=saved(p);p.dom.window.close();p=await restored(undismissed);
 assert.equal(p.d.querySelector('#career-welcome').hidden,false);
 p.d.querySelector('#welcome-help').click();assert.equal(p.d.querySelector('#panel-help').hidden,false);
 assert.equal(p.d.querySelectorAll('#help-topics section').length,12);
 assert.match(p.d.querySelector('#help-topics').textContent,/80% starters/);
 assert.match(p.d.querySelector('#help-topics').textContent,/20% boom/);
 assert.match(p.d.querySelector('#help-topics').textContent,/Seasons 2–5/);
 assert.equal(new Set([...p.d.querySelectorAll('[id]')].map(n=>n.id)).size,p.d.querySelectorAll('[id]').length);
 assert.equal(p.d.querySelector('#view-help').textContent,'How to Play');
 assert.equal(p.d.querySelectorAll('.info-control,.info-body').length,0);
 assert.ok([...p.d.querySelectorAll('#rating-method,#development-note,#contract-rules,#draft-format,#rotation-note,#tiebreaker-note')].every(node=>node.closest('#panel-help')));
 assert.equal(saved(p),undismissed,'Opening help must not change a save');
 p.d.querySelector('#welcome-dismiss').click();assert.equal(p.d.querySelector('#career-welcome').hidden,true);
 assert.equal(JSON.parse(saved(p)).welcomeDismissed,true);
 const first=saved(p);p.dom.window.close();
 p=await restored(first);
 assert.equal(p.d.querySelector('#career-welcome').hidden,true);
 assert.equal(p.d.querySelectorAll('#schedule .completed').length,16);
 assert.equal(p.d.querySelectorAll('.roster-player').length,35);
 p.d.querySelector('#change-team-button').click();p.d.querySelector('#team-select').value=id;
 p.d.querySelector('#team-form').dispatchEvent(new p.w.Event('submit',{cancelable:true}));
 await until(()=>JSON.parse(saved(p)).welcomeDismissed===false);
 assert.equal(p.d.querySelector('#career-welcome').hidden,false,'A new career gets its own guide');p.dom.window.close();
 for(const [week,round] of [[8,null],[17,null],[17,0],[17,1],[17,4]]) {
  const raw=checkpoint(id,week,round);
  p=await restored(raw);
  assert.match(status(p),/restored/);
  assert.equal(p.d.querySelector('#career-welcome').hidden,true,'Existing saves do not replay onboarding');
  assert.equal(saved(p),raw,'Restore must not overwrite the checkpoint');
  assert.equal(p.d.querySelectorAll('#schedule .completed').length,week);assert.equal(p.d.querySelector('#qualification-status').hidden,week<17);
  const before=snapshot(p);
  const again=await restored(saved(p));
  assert.deepEqual(snapshot(again),before,'Reload preserves all rendered results and stats');
  for(const restoredPage of [p,again]){
   const hidden={'simulation-more':week>=17,'simulate-button':week>=17,'simulate-season':week>=17,'stop-season':true,
    'playoffs-start':week<17||round!==null,'playoff-simulate':round===null||round===4,
    'draft-button':round!==4,'next-season':true,'manage-roster':true};
   for(const [action,expected] of Object.entries(hidden))assert.equal(restoredPage.d.querySelector('#'+action).hidden,expected,`Restored ${action} visibility at week ${week}, round ${round}`);
  }
  again.dom.window.close();
  if(week===8) {
   p.state.fail=true;p.d.querySelector('#simulate-button').click();
   await until(()=>!p.d.querySelector('#error').hidden);
   assert.equal(saved(p),raw,'Failed week keeps the last save');
   p.state.fail=false;p.d.querySelector('#simulate-button').click();
   await until(()=>JSON.parse(saved(p)).week===9);
   assert.equal(p.d.querySelectorAll('#schedule .completed').length,9);
  }
  if(round===0) {
   p.state.fail=true;p.d.querySelector('#playoff-simulate').click();
   await until(()=>!p.d.querySelector('#error').hidden);
   assert.equal(saved(p),raw);
   p.state.fail=false;p.d.querySelector('#playoff-simulate').click();
   await until(()=>JSON.parse(saved(p)).playoffRound===1);
  }
  p.dom.window.close();
 }
 // The immediately previous save format remains readable without a new guide.
 const legacy18={...JSON.parse(first),version:18};delete legacy18.welcomeDismissed;
 p=await restored(JSON.stringify(legacy18));assert.equal(p.d.querySelector('#career-welcome').hidden,true);assert.equal(saved(p),JSON.stringify(legacy18));p.dom.window.close();
 const raw=checkpoint(id,8);
 p=await restored(raw,{fail:true});
 assert.equal(saved(p),raw);assert.equal(p.d.querySelector('#schedule-section').hidden,true);
 assert.equal(p.d.querySelector('#resume-save').hidden,false);
 p.state.fail=false;p.d.querySelector('#resume-save').click();
 await until(()=>/restored/.test(status(p)));assert.equal(saved(p),raw);
 // A failed replacement cannot destroy the existing save.
 p.d.querySelector('#change-team-button').click();p.state.fail=true;
 p.d.querySelector('#team-select').value='seattle';
 p.d.querySelector('#team-form').dispatchEvent(new p.w.Event('submit',{cancelable:true}));
 await until(()=>!p.d.querySelector('#error').hidden);
 assert.equal(saved(p),raw);assert.equal(p.d.querySelector('#career-welcome').hidden,true);p.dom.window.close();
 for(const bad of ['{',JSON.stringify({...JSON.parse(first),welcomeDismissed:'yes'}),JSON.stringify({version:2}),checkpoint('missing-team',8),checkpoint(id,5,1),checkpoint(id,18)]) {
  p=await restored(bad);assert.match(status(p),/could not be read/);assert.equal(saved(p),bad);p.dom.window.close();
 }
 p=page(undefined,{blocked:true});await until(()=>p.d.querySelector('#team-select').options.length===31);
 p.d.querySelector('#team-select').value=id;
 p.d.querySelector('#team-form').dispatchEvent(new p.w.Event('submit',{cancelable:true}));
 await until(()=>/could not be saved/.test(status(p)));
 assert.equal(p.d.querySelector('#schedule-section').hidden,false);
 assert.equal(p.d.querySelector('#simulate-button').disabled,false);p.d.querySelector('#welcome-dismiss').click();assert.equal(p.d.querySelector('#career-welcome').hidden,true);assert.match(status(p),/could not be saved/);p.dom.window.close();
 console.log('Save UI checks passed: fresh start, reload at week 0/8/17 and playoff rounds 0/1/4, identical stats/results, resume next week/round, failed request/restore/replacement, corrupt/versioned saves, and storage failure.');
}
(async()=>{
 const server=spawn(process.env.PYTHON||'python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8769'],{cwd:root,stdio:['ignore','pipe','pipe']});
 let logs='';server.stdout.on('data',data=>logs+=data);server.stderr.on('data',data=>logs+=data);
 try {
  for(let i=0;;i++) {
   if(server.exitCode!==null) throw new Error(logs);
   try {if((await fetch(base+'/api/teams')).ok) break;} catch {}
   if(i===100) throw new Error('Server startup timed out: '+logs);
   await new Promise(r=>setTimeout(r,100));
  }
  await checks();
 } finally {server.kill()}
})().catch(error=>{console.error(error);process.exitCode=1});
