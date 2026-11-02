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
 console.log('Automatic starter UI checks passed: controls removed, best-rated starters, legacy regular/playoff migration, historical result parity, failed restore/retry, idempotent reload, draft/cuts/rollover, and preserved manual history.');
}
(async()=>{const server=spawn(process.env.PYTHON||'python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8778'],{cwd:root,stdio:['ignore','pipe','pipe']});let logs='';server.stdout.on('data',d=>logs+=d);server.stderr.on('data',d=>logs+=d);try{for(let i=0;;i++){if(server.exitCode!==null)throw new Error(logs);try{if((await fetch(base+'/api/teams')).ok)break}catch{}if(i===100)throw new Error(logs);await new Promise(r=>setTimeout(r,100))}await checks()}finally{server.kill()}})().catch(e=>{console.error(e);process.exitCode=1});
