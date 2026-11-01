const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {spawn}=require('node:child_process'),{JSDOM}=require('jsdom');
const {finishOffseason}=require('./ui_offseason_helpers.cjs');
const root=path.resolve(__dirname,'..'),base='http://127.0.0.1:8775',key='arcade-league-save';
const html=fs.readFileSync(path.join(root,'app/static/index.html'),'utf8'),script=fs.readFileSync(path.join(root,'app/static/app.js'),'utf8');
const cache=new Map();
async function api(url){if(!cache.has(url))cache.set(url,fetch(base+url).then(async r=>{assert.equal(r.ok,true,url);return r.json()}));return structuredClone(await cache.get(url))}
async function until(check){for(let i=0;i<2000;i++){if(check())return;await new Promise(r=>setTimeout(r,10))}throw new Error('Contract UI state timed out')}
const q=(p,s)=>p.d.querySelector(s),raw=p=>p.w.localStorage.getItem(key),save=p=>JSON.parse(raw(p));
function page(checkpoint){
 const dom=new JSDOM(html,{url:base,runScripts:'outside-only'}),w=dom.window,d=w.document,state={calls:0};
 w.localStorage.setItem(key,JSON.stringify(checkpoint));w.HTMLElement.prototype.scrollIntoView=()=>{};
 w.HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new w.Event('close'))};w.HTMLDialogElement.prototype.showModal=function(){this.open=true};
 w.fetch=(url,init)=>{state.calls++;return fetch(new URL(url,base),init)};
 w.eval(script);return {dom,w,d,state};
}
async function restore(checkpoint){const p=page(checkpoint);await until(()=>/restored|could not/.test(q(p,'#save-status').textContent));assert.match(q(p,'#save-status').textContent,/restored/);return p}
function checkpoint(id,season=1,history=[],priorStandings={}){return {version:12,contracts:true,teamId:id,runSeed:1234,season,week:17,playoffRound:null,lineupRules:1,developmentStart:null,rebuildTeam:null,priorStandings,history,draftChoices:null,dropped:[],career:[]}}
function entry(season,playoffFinish='Missed playoffs',wins=6,losses=11,ties=0){return {season,playoffFinish,wins,losses,ties,championId:'seattle'}}
async function checkGuards(p){
 const before=raw(p),calls=p.state.calls;
 // Handler guards must hold even if controls are forcibly re-enabled.
 for(const id of ['simulate-button','playoffs-start','playoff-simulate','draft-button','auto-draft','next-season','manage-roster','cut-confirm']){
  q(p,'#'+id).disabled=false;q(p,'#'+id).hidden=false;q(p,'#'+id).click();
 }
 await p.w.loadPlayoffRound(0);await p.w.loadDraft();await p.w.loadDraft(null,true);
 assert.equal(p.state.calls,calls,'Fired careers cannot make mutating progress requests');assert.equal(raw(p),before);
 q(p,'#view-gm').click();assert.equal(q(p,'#panel-gm').hidden,false);assert.equal(q(p,'#view-gm').getAttribute('aria-selected'),'true');
 assert.ok(q(p,'#gm-regular').textContent);assert.equal(raw(p),before,'Records remain read-only');
}
async function checks(){
 let p=await restore({...checkpoint('seattle'),week:0});
 assert.match(q(p,'#owner-feedback').textContent,/hired.*four-year/);assert.match(q(p,'#contract-status').textContent,/4 years remaining.*Season 4/);
 const status=p.w.contractStatus;
 assert.equal(status([],1).end,4);assert.equal(status([],1).remaining,4);
 for(const [wins,losses,ties,reward] of [[9,8,0,1],[8,9,0,0],[8,8,1,0],[8,7,2,1]]){
  const c=status([],1,{complete:true,qualified:false,champion:false,wins,losses,ties});assert.equal(c.end,4+reward);assert.equal(c.remaining,3+reward);
 }
 assert.equal(status([],1,{complete:true,qualified:true,champion:false,wins:12,losses:5}).end,6,'Playoffs earn two total, not three');
 assert.equal(status([],1,{complete:true,qualified:true,champion:true,wins:12,losses:5}).end,9,'Championship earns five total, not eight');
 const miss=Array.from({length:4},(_,i)=>entry(i+1,'Missed playoffs',9,8));
 assert.equal(status(miss.slice(0,3),4).fired,false);assert.equal(status(miss,5).reason,'deadline','Winning extensions cannot bypass four-year playoff deadline');
 assert.equal(status([...miss.slice(0,3),entry(4,'Lost in Wild Card')],5).fired,false,'First playoff appearance in year four meets the deadline');
 const long=[entry(1,'Lost in Wild Card'),...Array.from({length:4},(_,i)=>entry(i+2))];
 assert.equal(status(long,6).remaining,1);assert.equal(status([...long,entry(6)],7).reason,'expired');
 assert.equal(status([...long,entry(6,'Missed playoffs',9,8)],7).fired,false,'Winning extension can save an expiring contract');
 p.dom.window.close();
 const final=await api('/api/playoffs/seattle/round/4?run_seed=1234');
 const champion=final.champion.team.id,qual=final.field[0].team.id;
 const regular=await api('/api/season/seattle/week/17?run_seed=1234');
 const ranks=Object.fromEntries(regular.standings.groups.flatMap(g=>g.teams).map(row=>[row.team.id,row.rank]));
 const missed=regular.standings.groups.flatMap(g=>g.teams).find(row=>!final.field.some(f=>f.team.id===row.team.id)).team.id;
 p=await restore(checkpoint(missed));assert.match(q(p,'#owner-feedback').textContent,/disappointed.*monitored closely/);assert.equal(q(p,'#gm-contract').dataset.outcome,'warning');
 const missedRow=regular.standings.groups.flatMap(g=>g.teams).find(row=>row.team.id===missed);
 assert.match(q(p,'#contract-status').textContent,new RegExp(`Season ${missedRow.wins>missedRow.losses?5:4}`));p.dom.window.close();
 p=await restore(checkpoint(qual));assert.match(q(p,'#owner-feedback').textContent,/2-year extension.*upgrade/);assert.match(q(p,'#contract-status').textContent,/Season 6/);p.dom.window.close();
 p=await restore({...checkpoint(champion),playoffRound:3});assert.match(q(p,'#contract-status').textContent,/Season 6/);
 q(p,'#playoff-simulate').click();await until(()=>save(p).playoffRound===4);
 assert.match(q(p,'#owner-feedback').textContent,/championship.*5-year extension/);assert.match(q(p,'#contract-status').textContent,/8 years remaining.*Season 9/);
 const afterTitle=raw(p);p.w.renderGMRecords();p.w.renderGMRecords();assert.equal(raw(p),afterTitle);assert.match(q(p,'#contract-status').textContent,/Season 9/);
 p.dom.window.close();p=await restore(JSON.parse(afterTitle));assert.match(q(p,'#contract-status').textContent,/8 years remaining.*Season 9/);
 await finishOffseason(p,until);q(p,'#next-season').click();await until(()=>save(p).season===2);
 assert.equal(save(p).contracts,true);assert.match(q(p,'#contract-status').textContent,/8 years remaining.*Season 9/);
 q(p,'#simulate-button').click();await until(()=>save(p).week===1);assert.match(q(p,'#contract-status').textContent,/Season 9/);
 const seasonTwo=raw(p);p.dom.window.close();p=await restore(JSON.parse(seasonTwo));assert.match(q(p,'#contract-status').textContent,/Season 9/);p.dom.window.close();
 // Real current-year outcomes paired with prior history exercise both firing paths on restore.
 for(const [year,history,reason] of [[4,miss.slice(0,3),'first four seasons'],[6,long,'not renewed']]){
  const encoded=encodeURIComponent(JSON.stringify(ranks));
  const result=await api(`/api/season/seattle/week/17?season=${year}&run_seed=1234&prior_standings=${encoded}`);
  const nonqual=result.standings.groups.flatMap(g=>g.teams).find(row=>!result.standings.playoff_race.some(f=>f.team.id===row.team.id)&&row.wins<=row.losses).team.id;
  const dead=checkpoint(nonqual,year,history,ranks);p=await restore(dead);
  assert.match(q(p,'#contract-status').textContent,/Fired.*Career over/);assert.match(q(p,'#owner-feedback').textContent,new RegExp(reason));
  assert.equal(q(p,'#simulate-button').disabled,true);for(const action of ['simulate-button','simulate-season','stop-season','playoffs-start','playoff-simulate','draft-button','next-season','manage-roster','starter-editor','auto-starters'])assert.equal(q(p,'#'+action).hidden,true);assert.equal(q(p,'#playoffs-start').hidden,true);assert.equal(q(p,'#next-season').hidden,true);
  await checkGuards(p);assert.equal(raw(p),JSON.stringify(dead));p.dom.window.close();p=await restore(dead);assert.match(q(p,'#contract-status').textContent,/Fired/);p.dom.window.close();
  const legacy={...dead,version:11};delete legacy.contracts;p=await restore(legacy);assert.equal(q(p,'#gm-contract').hidden,true);assert.equal(q(p,'#playoffs-start').hidden,false);p.dom.window.close();
 }
 const fourth=await api(`/api/season/seattle/week/17?season=4&run_seed=1234&prior_standings=${encodeURIComponent(JSON.stringify(ranks))}`);
 p=await restore(checkpoint(fourth.standings.playoff_race[0].team.id,4,miss.slice(0,3),ranks));assert.doesNotMatch(q(p,'#contract-status').textContent,/Fired/);assert.match(q(p,'#owner-feedback').textContent,/2-year extension/);p.dom.window.close();
 const bad={...checkpoint('seattle'),contracts:'yes'};p=page(bad);await until(()=>/could not be read/.test(q(p,'#save-status').textContent));assert.equal(raw(p),JSON.stringify(bad));p.dom.window.close();
 // Starting over after firing clears old history, warnings, contract expiry, and records.
 const dead=checkpoint(missed,4,miss.slice(0,3),ranks);p=await restore(dead);
 q(p,'#change-team-button').click();q(p,'#team-select').value='seattle';q(p,'#team-form').dispatchEvent(new p.w.Event('submit',{bubbles:true,cancelable:true}));
 await until(()=>save(p).season===1&&save(p).week===16);assert.equal(save(p).contracts,true);assert.equal(save(p).version,18);assert.equal(save(p).history.length,0);
 assert.match(q(p,'#owner-feedback').textContent,/hired.*four-year/);assert.match(q(p,'#contract-status').textContent,/4 years remaining.*Season 5/);assert.equal(q(p,'#simulate-button').disabled,false);p.dom.window.close();
 console.log('GM contract checks passed: hiring, highest-only rewards, ties, four-year deadline, later expiry, fourth-year qualification, guard enforcement, records after firing, reload idempotence, draft/cuts/season rollover, legacy exemption, invalid-save preservation, and new-career reset.');
}
(async()=>{const server=spawn(process.env.PYTHON||'python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8775'],{cwd:root,stdio:['ignore','pipe','pipe']});let logs='';server.stdout.on('data',d=>logs+=d);server.stderr.on('data',d=>logs+=d);try{for(let i=0;;i++){if(server.exitCode!==null)throw new Error(logs);try{if((await fetch(base+'/api/teams')).ok)break}catch{}if(i===100)throw new Error(logs);await new Promise(r=>setTimeout(r,100))}await checks()}finally{server.kill()}})().catch(e=>{console.error(e);process.exitCode=1});
