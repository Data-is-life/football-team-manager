const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {spawn} = require('node:child_process');
const {JSDOM} = require('jsdom');
const {finishOffseason}=require('./ui_offseason_helpers.cjs');
const root=path.resolve(__dirname,'..'),base='http://127.0.0.1:8770',key='arcade-league-save';
const script=fs.readFileSync(path.join(root,'app/static/app.js'),'utf8');
const html=fs.readFileSync(path.join(root,'app/static/index.html'),'utf8');
const cache=new Map();
async function api(url) {
 if(!cache.has(url)) cache.set(url,fetch(base+url).then(async r=>{assert.equal(r.ok,true,url);return r.json()}));
 return structuredClone(await cache.get(url));
}
async function until(check) {
 for(let i=0;i<1500;i++){if(check())return;await new Promise(r=>setTimeout(r,10))}
 throw new Error('UI state timed out');
}
function page(raw) {
 const dom=new JSDOM(html,{url:base,runScripts:'outside-only'}),w=dom.window,d=w.document;
 w.localStorage.setItem(key,raw);
 w.HTMLElement.prototype.scrollIntoView=()=>{};
 w.HTMLDialogElement.prototype.close=function(){this.open=false};
 w.HTMLDialogElement.prototype.showModal=function(){this.open=true};
 Object.defineProperty(w.crypto,'getRandomValues',{value:a=>{a[0]=5678;return a}});
 const state={failNext:false,delayNext:null,urls:[]};
 w.fetch=async (url,init)=> {
  state.urls.push(url);
  if(state.failNext && url.startsWith('/api/schedule/') && url.includes('season=2'))return {ok:false};
  if(state.delayNext && url.startsWith('/api/schedule/') && url.includes('season=2'))await state.delayNext;
  if(init)return fetch(new URL(url,base),init);
  return {ok:true,json:()=>api(url)};
 };
 w.eval(script);
 return {dom,w,d,state};
}
const rawSave=p=>p.w.localStorage.getItem(key);
const save=p=>JSON.parse(rawSave(p));
const q=(p,sel)=>p.d.querySelector(sel);
async function restore(raw) {
 const p=page(raw);await until(()=>/restored|could not/.test(q(p,'#save-status').textContent));
 assert.match(q(p,'#save-status').textContent,/restored/);return p;
}
function legacy(id,round=4) {return JSON.stringify({version:1,teamId:id,runSeed:1234,season:1,week:17,playoffRound:round})}
const ranksOf=data=>Object.fromEntries(data.standings.groups.flatMap(g=>g.teams).map(r=>[r.team.id,r.rank]));
function statsSnapshot(p){q(p,'#roster-stats-button').click();return q(p,'#roster-groups').textContent}
async function checks() {
 const final=await api('/api/playoffs/seattle/round/4?season=1&run_seed=1234');
 const id=final.champion.team.id;
 let p=await restore(legacy(id,3));
 assert.equal(q(p,'#next-season').hidden,true,'Cannot skip an unfinished postseason');p.dom.window.close();
 p=await restore(legacy(id));
 assert.equal(q(p,'#next-season').hidden,true);await finishOffseason(p,until);assert.equal(q(p,'#next-season').hidden,false);
 const roster=[...p.d.querySelectorAll('.roster-player')].map(row=>[row.dataset.playerId,row.children[1].textContent]).sort();
 const regular=await api(`/api/season/${id}/week/17?season=1&run_seed=1234`);
 const ranks=ranksOf(regular),old=rawSave(p);
 // Failed and duplicate transition requests cannot partially advance or overwrite the save.
 p.state.failNext=true;q(p,'#next-season').click();
 await until(()=>!q(p,'#error').hidden);
 assert.equal(rawSave(p),old);assert.equal(q(p,'#season-display').textContent,'1');
 p.state.failNext=false;
 let release;p.state.delayNext=new Promise(resolve=>release=resolve);
 const count=p.state.urls.length;q(p,'#next-season').click();q(p,'#next-season').click();
 assert.equal(p.state.urls.length,count+1);assert.equal(q(p,'#change-team-button').disabled,true);
 release();await until(()=>save(p).season===2);
 assert.equal(q(p,'#season-display').textContent,'2');
 assert.deepEqual([...p.d.querySelectorAll('.roster-player')].map(row=>[row.dataset.playerId,row.children[1].textContent]).sort(),roster,'Player IDs and names survive offseason aging');
 assert.equal(save(p).runSeed,1234);assert.deepEqual(save(p).priorStandings,ranks);
 assert.equal(save(p).version,14);assert.equal(save(p).contracts,false);assert.equal(q(p,"#gm-contract").hidden,true);assert.equal(save(p).week,0);assert.equal(save(p).playoffRound,null);
 assert.equal(q(p,'#qualification-status').hidden,true);assert.equal(q(p,'#qualification-status').textContent,'');
 assert.equal(q(p,'#season-record').textContent,'0–0');assert.equal(q(p,'#next-season').hidden,true);
 assert.equal(q(p,'#postseason-section').hidden,true);
 assert.equal(q(p,'#season-history').hidden,false);
 assert.equal(q(p,'#gm-regular').textContent,`${regular.record.wins}–${regular.record.losses}–${regular.record.ties}`);assert.equal(q(p,'#gm-championships').textContent,'1');assert.equal(q(p,'#gm-playoffs').textContent,`${save(p).history[0].playoffWins}–0`);
 assert.equal(save(p).history.length,1);assert.equal(save(p).history[0].playoffFinish,'Champions');
 assert.deepEqual(save(p).history[0],{season:1,...regular.record,championId:id,playoffFinish:'Champions',playoffWins:final.rounds.reduce((sum,round)=>sum+round.games.filter(game=>game.winner.team.id===id).length,0),playoffLosses:0});
 assert.equal(q(p,'#season-history-rows').children.length,1);
 assert.match(q(p,'#season-history-rows').textContent,/Champions/);
 q(p,'#roster-stats-button').click();assert.match(q(p,'#roster-stats-status').textContent,/0 team games/);
 q(p,'#roster-competition').value='playoffs';q(p,'#roster-competition').dispatchEvent(new p.w.Event('change'));
 assert.match(q(p,'#roster-stats-status').textContent,/0 team games/);
 let raw=rawSave(p);p.dom.window.close();p=await restore(raw);
 assert.equal(q(p,'#season-display').textContent,'2');assert.deepEqual(save(p).priorStandings,ranks);
 const expectedSchedule=await api(`/api/schedule/${id}?season=2&prior_standings=${encodeURIComponent(JSON.stringify(ranks))}`);
 assert.deepEqual([...p.d.querySelectorAll('#schedule .game-card')].map(c=>c.dataset.opponentId),expectedSchedule.games.map(g=>g.opponent_id));
 const history=save(p).history;
 for(let week=1;week<=17;week++) {
  q(p,'#simulate-button').click();await until(()=>save(p).week===week);
  assert.equal(save(p).season,2);assert.deepEqual(save(p).history,history);
  if(week===8) {
   const stats=statsSnapshot(p),raw=rawSave(p);p.dom.window.close();p=await restore(raw);
   assert.equal(statsSnapshot(p),stats);assert.equal(q(p,'#simulate-button').textContent,'Simulate Week 9');
  }
 }
 assert.equal(q(p,'#next-season').hidden,true);
 const expected=await (await fetch(base+'/api/career/'+id,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'week',season:2,week:17,run_seed:1234,lineup_rules:3,development_start:2,prior_standings:ranks,career:save(p).career})})).json();
 const rec=expected.record;assert.equal(q(p,'#season-record').textContent,`${rec.wins}–${rec.losses}${rec.ties?`–${rec.ties}`:''}`);
 q(p,'#playoffs-start').click();await until(()=>save(p).playoffRound===0);
 for(let round=1;round<=4;round++) {
  q(p,'#playoff-simulate').click();await until(()=>save(p).playoffRound===round);
 }
 raw=rawSave(p);const playoffText=q(p,'#playoff-bracket').textContent;p.dom.window.close();p=await restore(raw);
 assert.equal(q(p,'#playoff-bracket').textContent,playoffText);
 assert.equal(q(p,'#next-season').hidden,true);await finishOffseason(p,until);assert.equal(q(p,'#next-season').textContent,'Continue to Season 3');
 q(p,'#next-season').click();await until(()=>save(p).season===3);
 assert.deepEqual(save(p).priorStandings,ranksOf(expected));
 assert.equal(save(p).history.length,2);assert.deepEqual(save(p).history[0],history[0]);
 assert.equal(save(p).history[1].season,2);assert.equal(save(p).week,0);
 raw=rawSave(p);p.dom.window.close();p=await restore(raw);assert.equal(q(p,'#season-history-rows').children.length,2);
 // Explicitly starting another franchise starts a new career and resets history/context.
 q(p,'#change-team-button').click();q(p,'#team-select').value='seattle';
 q(p,'#team-form').dispatchEvent(new p.w.Event('submit',{cancelable:true}));
 await until(()=>save(p).runSeed===5678);
 assert.equal(save(p).season,1);assert.deepEqual(save(p).history,[]);assert.deepEqual(save(p).priorStandings,{});
 assert.equal(q(p,'#season-history').hidden,true);assert.equal(q(p,'#gm-regular').textContent,'0–0–0');assert.equal(q(p,'#gm-appearances').textContent,'0');assert.equal(q(p,'#gm-playoffs').textContent,'0–0');assert.equal(q(p,'#gm-championships').textContent,'0');assert.equal(q(p,'#gm-legacy-note').hidden,true);p.dom.window.close();
 // Non-qualifiers and eliminated teams can continue once the league championship is complete.
 const teams=(await api('/api/teams')).teams;
 const nonqual=teams.find(t=>!final.field.some(f=>f.team.id===t.id)).id;
 const game=final.rounds[0].games[0];const loser=game.winner.team.id===game.home.team.id?game.away.team.id:game.home.team.id;
 for(const [other,finish] of [[nonqual,'Missed playoffs'],[loser,'Lost in Wild Card']]) {
  p=await restore(legacy(other));assert.equal(q(p,'#next-season').hidden,true);await finishOffseason(p,until);q(p,'#next-season').click();await until(()=>save(p).season===2);
  assert.equal(save(p).history[0].playoffFinish,finish);p.dom.window.close();
 }
 // All three API routes reject malformed ranking context; object key order is irrelevant.
 for(const route of [`/api/schedule/${id}`,`/api/season/${id}/week/1`,`/api/playoffs/${id}/round/0`]) {
  assert.equal((await fetch(base+route+'?season=2&prior_standings=%7B%7D')).status,422);
  assert.equal((await fetch(base+route+'?season=2&prior_standings='+ 'x'.repeat(2001))).status,422);
 }
 // A damaged career checkpoint is left intact instead of silently losing history or schedule context.
 const damaged=JSON.parse(raw);damaged.history=[];
 p=page(JSON.stringify(damaged));await until(()=>/could not be read/.test(q(p,'#save-status').textContent));
 assert.equal(rawSave(p),JSON.stringify(damaged));assert.equal(q(p,'#schedule-section').hidden,true);p.dom.window.close();
 console.log('Multiple-season UI checks passed: championship gating; retained roster/seed; season 2 full regular season/playoffs and season 3 transition; prior ranks; history/stats reset; reloads; legacy saves; failed/duplicate transition; missed playoffs/elimination; new career reset; API context validation.');
}
(async()=>{
 const server=spawn(process.env.PYTHON||'python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8770'],{cwd:root,stdio:['ignore','pipe','pipe']});
 let logs='';server.stdout.on('data',d=>logs+=d);server.stderr.on('data',d=>logs+=d);
 try {
  for(let i=0;;i++) {
   if(server.exitCode!==null)throw new Error(logs);
   try{if((await fetch(base+'/api/teams')).ok)break}catch{}
   if(i===100)throw new Error(logs);await new Promise(r=>setTimeout(r,100));
  }
  await checks();
 }finally{server.kill()}
})().catch(error=>{console.error(error);process.exitCode=1});
