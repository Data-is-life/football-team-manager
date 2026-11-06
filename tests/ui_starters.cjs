const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {spawn}=require('node:child_process'),{JSDOM}=require('jsdom');
const {finishOffseason}=require('./ui_offseason_helpers.cjs');
const root=path.resolve(__dirname,'..'),base='http://127.0.0.1:8778',key='arcade-league-save';
const html=fs.readFileSync(path.join(root,'app/static/index.html'),'utf8'),script=fs.readFileSync(path.join(root,'app/static/app.js'),'utf8');
async function until(check){for(let i=0;i<2000;i++){if(check())return;await new Promise(r=>setTimeout(r,10))}throw new Error('Automatic lineup UI state timed out')}
const q=(p,s)=>p.d.querySelector(s),raw=p=>p.w.localStorage.getItem(key),save=p=>JSON.parse(raw(p));
const checkpoint={version:13,lineupChanges:[],contracts:false,teamId:'seattle',runSeed:1234,season:1,week:0,playoffRound:null,lineupRules:6,developmentStart:1,rebuildTeam:'seattle',priorStandings:{},history:[],career:[],draftChoices:null,dropped:[]};
function page(input,fail=false){
 const dom=new JSDOM(html,{url:base,runScripts:'outside-only'}),w=dom.window,d=w.document,state={requests:[],fail};
 w.localStorage.setItem(key,JSON.stringify(input));w.HTMLElement.prototype.scrollIntoView=()=>{};w.scrollTo=()=>{};
 w.HTMLDialogElement.prototype.close=function(){this.open=false};w.HTMLDialogElement.prototype.showModal=function(){this.open=true};
 w.fetch=async(url,init)=>{
  const body=init?JSON.parse(init.body):null;state.requests.push({url,body});
  if(state.fail&&body?.action==='profile')return {ok:false};
  const response=await fetch(new URL(url,base),init);
  if(body?.action==='week')state.lastWeek=await response.clone().json();
  return response;
 };
 w.eval(script);return {dom,w,d,state};
}
async function restore(input){const p=page(input);await until(()=>/restored|could not/.test(q(p,'#save-status').textContent));assert.match(q(p,'#save-status').textContent,/restored/);return p}
async function api(action,extra={}){const r=await fetch(base+'/api/career/seattle',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,run_seed:1234,lineup_rules:6,rebuild_team:'seattle',...extra})});assert.equal(r.ok,true,await r.clone().text());return r.json()}
function assertBest(p){
 assert.equal(p.d.querySelector('#starter-editor,#starter-form,#auto-starters,#save-starters'),null);
 for(const group of p.d.querySelectorAll('#roster-groups .roster-group')){
  const rows=[...group.querySelectorAll('.roster-player')],starters=rows.filter(r=>r.dataset.starter==='true'),bench=rows.filter(r=>r.dataset.starter!=='true');
  const rating=r=>Number(r.cells[3].firstChild.textContent);
  if(bench.length)assert.ok(Math.min(...starters.map(rating))>=Math.max(...bench.map(rating)),group.dataset.position);
 }
}
async function checks(){
 let p=await restore(checkpoint);assertBest(p);assert.equal(raw(p),JSON.stringify(checkpoint));p.dom.window.close();
 const profile=await api('profile');
 const manual=profile.roster.filter(p=>p.depth<=profile.roster_rules.find(r=>r.position===p.position).minimum).map(p=>p.id);
 const qb=profile.roster.filter(p=>p.position==='QB');manual[manual.indexOf(qb[0].id)]=qb[1].id;
 const past={week:1,starters:manual},active={...checkpoint,week:8,lineupChanges:[past]};
 const before=await api('week',{week:8,lineup_changes:[past]});
 p=await restore(active);assertBest(p);assert.equal(raw(p),JSON.stringify(active),'Restore keeps the checkpoint atomic');
 const migrated=p.state.requests.find(r=>r.body?.action==='profile').body.lineup_changes;
 assert.deepEqual(migrated,[past,{week:9,starters:[]}]);
 const replay=await api('week',{week:8,lineup_changes:migrated});
 for(const field of ['result','record','game_results'])assert.deepEqual(replay[field],before[field],`Past ${field} must remain unchanged`);
 q(p,'#simulate-button').click();await until(()=>save(p).week===9);
 assert.deepEqual(save(p).lineupChanges,migrated);assertBest(p);
 const box=p.state.lastWeek.result.home.team.id==='seattle'?p.state.lastWeek.result.home:p.state.lastWeek.result.away;
 assert.equal(box.passing[0].player_id,qb[0].id,'The next game uses the highest-rated QB');
 const saved=save(p);p.dom.window.close();p=await restore(saved);
 assert.deepEqual(p.state.requests.find(r=>r.body?.action==='profile').body.lineup_changes,migrated,'Reload does not append another reset');p.dom.window.close();
 p=page(active,true);await until(()=>/could not be loaded/.test(q(p,'#save-status').textContent));assert.equal(raw(p),JSON.stringify(active));
 p.state.fail=false;q(p,'#resume-save').click();await until(()=>/restored/.test(q(p,'#save-status').textContent));assertBest(p);assert.equal(raw(p),JSON.stringify(active));p.dom.window.close();
 for(const round of [0,1]){
  const input={...checkpoint,week:17,playoffRound:round,lineupChanges:[past,{week:18,starters:manual}]};
  p=await restore(input);assertBest(p);
  const changes=p.state.requests.find(r=>r.body?.action==='profile').body.lineup_changes;
  assert.deepEqual(changes,round===0?[past,{week:18,starters:[]}]:[past,{week:18,starters:manual},{week:19,starters:[]}]);p.dom.window.close();
 }
 // Completed postseason choices remain historical; the next year is automatic.
 const ended={...checkpoint,week:17,playoffRound:4,lineupChanges:[past]};
 p=await restore(ended);assert.deepEqual(p.state.requests.find(r=>r.body?.action==='profile').body.lineup_changes,[past]);
 await finishOffseason(p,until);q(p,'#next-season').click();await until(()=>save(p).season===2);
 assertBest(p);assert.deepEqual(save(p).lineupChanges,[]);assert.deepEqual(save(p).career[0].lineup_changes,[past]);
 const next=save(p);p.dom.window.close();p=await restore(next);assertBest(p);assert.deepEqual(save(p).career[0].lineup_changes,[past]);p.dom.window.close();
 // New retirement careers flag departures during the season, then retain
 // their earned stats while the active roster moves through draft and cuts.
 const retirementCareer={...checkpoint,runSeed:1,lineupRules:10,week:16};
 p=await restore(retirementCareer);q(p,'#view-roster').click();
 const planned=[...p.d.querySelectorAll('#roster-groups .retirement-badge')].map(b=>b.closest('[data-player-id]').dataset.playerId);
 assert.equal(planned.length,5);
 for(const badge of p.d.querySelectorAll('#roster-groups .retirement-badge')){
  assert.equal(badge.tagName,'DETAILS');assert.equal(badge.open,false);
  const marker=badge.querySelector('summary');assert.equal(marker.textContent,'*');
  assert.equal(marker.title,'Retiring after this season');assert.equal(marker.getAttribute('aria-label'),'Retiring after this season');
  assert.equal(badge.querySelector('.retirement-explanation').textContent,'Retiring after this season');
 }
 const unchanged=raw(p),marker=q(p,'#roster-groups .retirement-badge > summary');
 marker.click();assert.equal(marker.parentElement.open,true);marker.click();assert.equal(marker.parentElement.open,false);
 assert.equal(raw(p),unchanged,'Opening a retirement explanation does not change progress');
 const savedPlan=raw(p);p.dom.window.close();p=await restore(JSON.parse(savedPlan));
 assert.equal(p.d.querySelectorAll('#roster-groups .retirement-badge').length,5);
 q(p,'#simulate-button').click();await until(()=>save(p).week===17);
 q(p,'#playoffs-start').click();await until(()=>save(p).playoffRound===0);
 for(let round=1;round<=4;round++){q(p,'#playoff-simulate').click();await until(()=>save(p).playoffRound===round)}
 assert.equal(q(p,'#retirement-summary').hidden,false);assert.equal(p.d.querySelectorAll('#retirement-list li').length,5);
 for(const id of planned)assert.equal(q(p,`#roster-groups .roster-rating-wrap [data-player-id="${id}"]`).hidden,true);
 q(p,'#view-roster').click();q(p,'#roster-stats-button').click();
 const stats=new Map(planned.map(id=>{const row=q(p,`.roster-season-player[data-player-id="${id}"]`);assert.match(row.cells[1].textContent,/Retired/);return [id,[...row.cells].slice(3).map(cell=>cell.textContent)]}));
 q(p,'#draft-button').click();await until(()=>save(p).draftChoices?.length===0);
 assert.equal(q(p,'#retirement-summary').hidden,false,'Retirement notice remains available during the draft');
 for(let turn=1;turn<save(p).draftRounds;turn++){
  q(p,'#draft-prospects [data-draft-id]:not([disabled])').click();await until(()=>save(p).draftChoices.length===turn);
  assert.equal(q(p,'#retirement-summary').hidden,false);
 }
 const unfinished=save(p);p.dom.window.close();p=await restore(unfinished);
 assert.equal(q(p,'#retirement-summary').hidden,false,'An unfinished draft restores the notice');
 const beforeFinalPick=raw(p),realFetch=p.w.fetch;
 p.w.fetch=(url,init)=>url.startsWith('/api/draft/')?Promise.resolve({ok:false}):realFetch(url,init);
 q(p,'#draft-button').click();q(p,'#draft-prospects [data-draft-id]:not([disabled])').click();await until(()=>!q(p,'#draft-error').hidden);
 assert.equal(raw(p),beforeFinalPick);assert.equal(q(p,'#retirement-summary').hidden,false,'A failed last pick cannot clear the retirement notice');
 p.w.fetch=realFetch;q(p,'#draft-retry').click();await until(()=>save(p).draftChoices.length===save(p).draftRounds);
 assert.equal(q(p,'#retirement-summary').hidden,true,'The successful final pick hides the notice');
 const finishedDraft=save(p);p.dom.window.close();p=await restore(finishedDraft);
 assert.equal(q(p,'#retirement-summary').hidden,true,'A completed draft restores without the retirement notice');
 await finishOffseason(p,until);
 assert.equal(q(p,'#retirement-summary').hidden,true);
 assert.ok(planned.every(id=>!q(p,`.roster-rating-wrap [data-player-id="${id}"]`)));
 const cuts=save(p).dropped.length;
 const drop=p.d.querySelector('#roster-groups [data-drop-id]:not([disabled])');drop.click();q(p,'#cut-confirm').click();await until(()=>save(p).dropped.length===cuts+1);
 assert.equal(p.d.querySelectorAll('#roster-groups .roster-player').length,38);
 assert.ok([...p.d.querySelectorAll('#roster-groups .roster-player')].some(row=>row.dataset.playerId.startsWith('replacement-')));
 q(p,'#roster-stats-button').click();
 for(const [id,values]of stats)assert.deepEqual([...q(p,`.roster-season-player[data-player-id="${id}"]`).cells].slice(3).map(cell=>cell.textContent),values,'Retired players keep their earned stats');
 const afterRetirement=save(p);p.dom.window.close();p=await restore(afterRetirement);
 assert.equal(q(p,'#retirement-summary').hidden,true);assert.equal(p.d.querySelectorAll('#retirement-list li').length,5);assert.ok(planned.every(id=>!q(p,`.roster-rating-wrap [data-player-id="${id}"]`)));
 q(p,'#next-season').click();await until(()=>save(p).season===2);
 assert.ok(planned.every(id=>!q(p,`.roster-rating-wrap [data-player-id="${id}"]`)));assertBest(p);assert.equal(q(p,'#retirement-summary').hidden,true);p.dom.window.close();
 console.log('Automatic starter UI checks passed: controls removed, best-rated starters, legacy regular/playoff migration, historical result parity, failed restore/retry, idempotent reload, draft/cuts/rollover, preserved manual history, retirement labels/removal, archived stats and low-rated replacements.');
}
(async()=>{const server=spawn(process.env.PYTHON||'python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8778'],{cwd:root,stdio:['ignore','pipe','pipe']});let logs='';server.stdout.on('data',d=>logs+=d);server.stderr.on('data',d=>logs+=d);try{for(let i=0;;i++){if(server.exitCode!==null)throw new Error(logs);try{if((await fetch(base+'/api/teams')).ok)break}catch{}if(i===100)throw new Error(logs);await new Promise(r=>setTimeout(r,100))}await checks()}finally{server.kill()}})().catch(e=>{console.error(e);process.exitCode=1});
