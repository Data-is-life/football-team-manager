const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {spawn}=require('node:child_process'),{JSDOM}=require('jsdom');
const {finishOffseason}=require('./ui_offseason_helpers.cjs');
const root=path.resolve(__dirname,'..'),base='http://127.0.0.1:8773',key='arcade-league-save';
async function until(check){for(let i=0;i<2000;i++){if(check())return;await new Promise(r=>setTimeout(r,10))}throw new Error('UI state timed out')}
async function api(url,body){const r=await fetch(base+url,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:undefined);assert.equal(r.ok,true);return r.json()}
const q=(p,s)=>p.d.querySelector(s),save=p=>JSON.parse(p.w.localStorage.getItem(key));
function page(raw){const dom=new JSDOM(fs.readFileSync(path.join(root,'app/static/index.html'),'utf8'),{url:base,runScripts:'outside-only'});const w=dom.window,d=w.document;w.localStorage.setItem(key,raw);w.HTMLElement.prototype.scrollIntoView=()=>{};w.HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new w.Event('close'))};w.HTMLDialogElement.prototype.showModal=function(){this.open=true};w.fetch=(url,init)=>fetch(new URL(url,base),init);w.eval(fs.readFileSync(path.join(root,'app/static/app.js'),'utf8'));return {dom,w,d}}
async function restore(raw){const p=page(raw);await until(()=>/restored|could not/.test(q(p,'#save-status').textContent));assert.match(q(p,'#save-status').textContent,/restored/);return p}
async function checks(){
 // Existing version-5 season remains frozen, then upgrades and ages once.
 const old={version:5,teamId:'seattle',runSeed:1234,season:1,week:17,playoffRound:4,priorStandings:{},history:[],draftChoices:null,dropped:[],career:[],lineupRules:2};
 let p=await restore(JSON.stringify(old));
 await finishOffseason(p,until);
 const before=(await api('/api/career/seattle',{action:'cuts',run_seed:1234,lineup_rules:2,manual_picks:save(p).draftChoices,dropped:save(p).dropped})).profile;
 assert.equal(p.d.querySelectorAll('.rating-change').length,0);
 q(p,'#next-season').click();await until(()=>save(p).season===2);
 assert.equal(save(p).version,13);assert.equal(save(p).lineupRules,3);assert.equal(save(p).developmentStart,2);
 const current=await api('/api/career/seattle',{action:'profile',run_seed:1234,lineup_rules:3,season:2,development_start:2,career:save(p).career});
 const previous=new Map(before.roster.map(p=>[p.id,p]));
 let changed=0;
 for(const player of current.roster){
  assert.equal(player.age,previous.get(player.id).age+(player.id.startsWith('rookie-')?0:1));
  const row=q(p,`#roster-groups [data-player-id="${player.id}"]`);
  assert.equal(row.children[2].textContent,String(player.age));
  const delta=player.current_rating-previous.get(player.id).current_rating;
  assert.equal(delta,player.rating_change);
  if(delta){changed++;assert.match(row.querySelector('.rating-change').textContent,new RegExp(delta>0?'↑ \\+'+delta:'↓ '+delta));}
  else assert.equal(row.querySelector('.rating-change'),null);
  assert.equal(row.children[4].textContent,String(player.potential_rating));
  assert.ok(!Object.keys(player).some(key=>/longevity|baseline|trait/.test(key)));
 }
 assert.ok(changed>0);
 const stats=q(p,'#roster-groups').textContent;
 const raw=p.w.localStorage.getItem(key);p.dom.window.close();p=await restore(raw);assert.equal(q(p,'#roster-groups').textContent,stats);
 q(p,'#simulate-button').click();await until(()=>save(p).week===1);
 const after=await api('/api/career/seattle',{action:'profile',run_seed:1234,lineup_rules:3,season:2,development_start:2,career:save(p).career});assert.deepEqual(current,after,'Playing/retrying a week cannot age players again');
 p.dom.window.close();
 const invalid=await fetch(base+'/api/team/seattle?lineup_rules=3&season=2&development_start=3');assert.equal(invalid.status,422);
 // Version-6 development careers retain their exact old abilities when re-saved.
 const v6={...old,version:6,lineupRules:3,developmentStart:1,week:0,playoffRound:null};
 p=await restore(JSON.stringify(v6));
 const v3=await api('/api/team/seattle?run_seed=1234&lineup_rules=3');
 assert.deepEqual([...p.d.querySelectorAll('#roster-groups .roster-player')].map(row=>row.dataset.playerId),v3.roster.map(player=>player.id));
 for(const player of v3.roster)assert.equal(q(p,`#roster-groups [data-player-id="${player.id}"]`).children[3].textContent,String(player.current_rating));
 q(p,'#simulate-button').click();await until(()=>save(p).week===1);
 assert.equal(save(p).version,13);assert.equal(save(p).lineupRules,3,'Saving an existing career must not adopt initial hierarchy');
 p.dom.window.close();
 // The most recent pre-rotation rebuild save remains on rules 4 after re-saving.
 const v8={...old,version:8,lineupRules:4,developmentStart:1,rebuildTeam:'seattle',week:0,playoffRound:null};
 p=await restore(JSON.stringify(v8));
 const previousRebuild=await api('/api/team/seattle?run_seed=1234&lineup_rules=4&rebuild_team=seattle');
 for(const player of previousRebuild.roster)assert.equal(q(p,`#roster-groups [data-player-id="${player.id}"]`).children[3].textContent,String(player.current_rating));
 q(p,'#simulate-button').click();await until(()=>save(p).week===1);
 assert.equal(save(p).version,13);assert.equal(save(p).lineupRules,4);assert.equal(save(p).rebuildTeam,'seattle');
 assert.equal(q(p,'#player-stats').textContent.includes('Targets'),false,'Legacy receiving layouts remain unchanged');
 p.dom.window.close();
 // The stronger starting balance must not rewrite the latest rules-5 rebuild save.
 const v10={...old,version:10,lineupRules:5,developmentStart:1,rebuildTeam:'seattle',week:0,playoffRound:null};
 p=await restore(JSON.stringify(v10));
 const oldBalance=await api('/api/team/seattle?run_seed=1234&lineup_rules=5&rebuild_team=seattle');
 assert.equal(q(p,'#offense-rating').textContent,String(oldBalance.ratings.offense));assert.ok(oldBalance.ratings.offense<68);
 q(p,'#simulate-button').click();await until(()=>save(p).week===1);
 assert.equal(save(p).version,13);assert.equal(save(p).lineupRules,5);assert.equal(save(p).rebuildTeam,'seattle');
 p.dom.window.close();
 console.log('Development UI checks passed: legacy season unchanged, migration ages once, actual rating arrows, private longevity, seeded profile equality after reload/week, and invalid development start.');
}
(async()=>{const server=spawn(process.env.PYTHON||'python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8773'],{cwd:root,stdio:['ignore','pipe','pipe']});let logs='';server.stdout.on('data',d=>logs+=d);server.stderr.on('data',d=>logs+=d);try{for(let i=0;;i++){if(server.exitCode!==null)throw new Error(logs);try{if((await fetch(base+'/api/teams')).ok)break}catch{}if(i===100)throw new Error(logs);await new Promise(r=>setTimeout(r,100))}await checks()}finally{server.kill()}})().catch(e=>{console.error(e);process.exitCode=1});
