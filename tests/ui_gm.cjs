const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {spawn}=require('node:child_process'),{JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'..'),base='http://127.0.0.1:8774',key='arcade-league-save';
const html=fs.readFileSync(path.join(root,'app/static/index.html'),'utf8'),script=fs.readFileSync(path.join(root,'app/static/app.js'),'utf8');
async function until(check){for(let i=0;i<2000;i++){if(check())return;await new Promise(r=>setTimeout(r,10))}throw new Error('GM UI state timed out')}
async function api(url){const r=await fetch(base+url);assert.equal(r.ok,true,url);return r.json()}
const q=(p,s)=>p.d.querySelector(s),raw=p=>p.w.localStorage.getItem(key);
function page(checkpoint){
 const dom=new JSDOM(html,{url:base,runScripts:'outside-only'}),w=dom.window,d=w.document,state={calls:0};
 w.localStorage.setItem(key,JSON.stringify(checkpoint));w.HTMLElement.prototype.scrollIntoView=()=>{};
 w.HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new w.Event('close'))};w.HTMLDialogElement.prototype.showModal=function(){this.open=true};
 w.fetch=(url,init)=>{state.calls++;return fetch(new URL(url,base),init)};
 w.eval(script);return {dom,w,d,state};
}
async function restore(checkpoint){const p=page(checkpoint);await until(()=>/restored|could not/.test(q(p,'#save-status').textContent));assert.match(q(p,'#save-status').textContent,/restored/);return p}
function legacy(teamId,week=17,playoffRound=4){return {version:1,teamId,runSeed:1234,season:1,week,playoffRound}}
function record(p){return ['regular','appearances','playoffs','championships'].map(id=>q(p,'#gm-'+id).textContent)}
async function checks(){
 const final=await api('/api/playoffs/seattle/round/4?run_seed=1234');
 const teams=(await api('/api/teams')).teams;
 const nonqual=teams.find(t=>!final.field.some(entry=>entry.team.id===t.id)).id;
 const bye=final.field[0].team.id,wildcard=final.field[7].team.id;
 const finalGame=final.rounds.at(-1).games[0],runnerUp=finalGame.winner.team.id===finalGame.home.team.id?finalGame.away.team.id:finalGame.home.team.id;
 for(const [id,round] of [[bye,null],[bye,0],[bye,1],[wildcard,1],[nonqual,4],[runnerUp,4],[final.champion.team.id,4]]){
  let p=await restore(legacy(id,17,round));
  const regular=await api(`/api/season/${id}/week/17?run_seed=1234`);
  const state=round===null?null:await api(`/api/playoffs/${id}/round/${round}?run_seed=1234`);
  let wins=0,losses=0;
  for(const r of state?.rounds??[])for(const game of r.games)if([game.home.team.id,game.away.team.id].includes(id)){if(game.winner.team.id===id)wins++;else losses++;}
  assert.deepEqual(record(p),[`${regular.record.wins}–${regular.record.losses}–${regular.record.ties}`,String(regular.standings.playoff_race.some(entry=>entry.team.id===id)?1:0),`${wins}–${losses}`,String(state?.champion?.team.id===id?1:0)]);
  const calls=p.state.calls,saved=raw(p);q(p,'#view-gm').click();
  assert.equal(q(p,'#panel-gm').hidden,false);assert.equal(q(p,'#view-gm').getAttribute('aria-selected'),'true');assert.equal(p.state.calls,calls);assert.equal(raw(p),saved,'Viewing records must not mutate the save');
  assert.equal(q(p,'#gm-legacy-note').hidden,true);
  const before=record(p);p.dom.window.close();p=await restore(JSON.parse(saved));assert.deepEqual(record(p),before);p.dom.window.close();
 }
 let p=await restore(legacy(bye,8,null));
 const regular=await api(`/api/season/${bye}/week/8?run_seed=1234`);
 assert.deepEqual(record(p),[`${regular.record.wins}–${regular.record.losses}–${regular.record.ties}`,'0','0–0','0']);p.dom.window.close();
 const ranks=Object.fromEntries((await api('/api/season/seattle/week/17?run_seed=1234')).standings.groups.flatMap(g=>g.teams).map(row=>[row.team.id,row.rank]));
 const history=[{season:1,wins:11,losses:6,ties:0,championId:'seattle',playoffFinish:'Champions'},
  {season:2,wins:10,losses:6,ties:1,championId:'miami',playoffFinish:'Lost in Quarterfinals'}];
 const old={version:2,teamId:'seattle',runSeed:1234,season:3,week:0,playoffRound:null,priorStandings:ranks,history};
 p=await restore(old);assert.deepEqual(record(p),['21–12–1','2','3–5 W / 1 L','1']);assert.equal(q(p,'#gm-legacy-note').hidden,false);
 q(p,'#view-gm').click();assert.equal(q(p,'#season-history').closest('#panel-gm'),q(p,'#panel-gm'));
 assert.equal(q(p,'#season-history-rows').children.length,2);assert.match(q(p,'#season-history-rows').textContent,/3–4 W \/ 0 L/);p.dom.window.close();
 const exact={...old,version:10,lineupRules:1,developmentStart:null,rebuildTeam:null,draftChoices:null,dropped:[],career:[],history:history.map((entry,i)=>({...entry,playoffWins:i?0:3,playoffLosses:i?1:0}))};
 p=await restore(exact);assert.deepEqual(record(p),['21–12–1','2','3–1','1']);assert.equal(q(p,'#gm-legacy-note').hidden,true);p.dom.window.close();
 for(const corrupt of [{playoffWins:2,playoffLosses:0},{playoffWins:4},{playoffWins:4,playoffLosses:1}]){
  const bad=structuredClone(exact);bad.history[0]={...history[0],...corrupt};p=page(bad);
  await until(()=>/could not be read/.test(q(p,'#save-status').textContent));assert.equal(raw(p),JSON.stringify(bad));p.dom.window.close();
 }
 console.log('GM Records UI checks passed: current partial/full regular season, qualification before bracket viewing, no wins for byes, round-by-round playoff records, elimination/runner-up/champion, read-only tab and reload, historical W-L-T, legacy win ranges, exact summaries, and invalid summary preservation.');
}
(async()=>{const server=spawn(process.env.PYTHON||'python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8774'],{cwd:root,stdio:['ignore','pipe','pipe']});let logs='';server.stdout.on('data',d=>logs+=d);server.stderr.on('data',d=>logs+=d);try{for(let i=0;;i++){if(server.exitCode!==null)throw new Error(logs);try{if((await fetch(base+'/api/teams')).ok)break}catch{}if(i===100)throw new Error(logs);await new Promise(r=>setTimeout(r,100))}await checks()}finally{server.kill()}})().catch(e=>{console.error(e);process.exitCode=1});
