const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {spawn}=require('node:child_process'),{JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'..'),base='http://127.0.0.1:8772',key='arcade-league-save';
const html=fs.readFileSync(path.join(root,'app/static/index.html'),'utf8'),script=fs.readFileSync(path.join(root,'app/static/app.js'),'utf8');
async function until(check){for(let i=0;i<1500;i++){if(check())return;await new Promise(r=>setTimeout(r,10))}throw new Error('UI state timed out')}
async function json(url,body){const r=await fetch(base+url,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:undefined);assert.equal(r.ok,true,await r.clone().text());return r.json()}
const q=(p,s)=>p.d.querySelector(s),raw=p=>p.w.localStorage.getItem(key),save=p=>JSON.parse(raw(p));
function page(checkpoint){
 const dom=new JSDOM(html,{url:base,runScripts:'outside-only'}),w=dom.window,d=w.document;
 w.localStorage.setItem(key,checkpoint);
 w.HTMLElement.prototype.scrollIntoView=()=>{};
 w.HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new w.Event('close'))};w.HTMLDialogElement.prototype.showModal=function(){this.open=true};
 const state={failCut:false,failProfile:false,cutCalls:0,urls:[]};
 w.fetch=async(url,init)=>{
  state.urls.push(url);
  if(state.failProfile && url.startsWith('/api/career/') && JSON.parse(init.body).action==='profile')return {ok:false,json:async()=>({detail:'Profile load failed'})};
  if(url.startsWith('/api/career/') && JSON.parse(init.body).action==='cuts'){
   state.cutCalls++;if(state.failCut)return {ok:false,json:async()=>({detail:'Simulated cut failure'})};
  }
  return fetch(new URL(url,base),init);
 };
 w.eval(script);return {dom,w,d,state};
}
async function restore(raw){const p=page(raw);await until(()=>/restored|could not/.test(q(p,'#save-status').textContent));assert.match(q(p,'#save-status').textContent,/restored/);return p}
async function checks(){
 const owner='seattle',choices=[];
 for(const position of ['QB','WR','RB','OL']){
  const draft=await json('/api/draft/'+owner,{season:1,run_seed:1234,lineup_rules:4,manual_picks:choices});
  const prospect=draft.available.find(p=>p.position===position);assert.ok(prospect,position);choices.push(prospect.id);
 }
 const checkpoint=JSON.stringify({version:7,teamId:owner,runSeed:1234,lineupRules:4,developmentStart:1,season:1,week:17,playoffRound:4,priorStandings:{},history:[],draftChoices:choices,dropped:[],career:[]});
 let p=await restore(checkpoint);assert.equal(q(p,'#manage-roster').hidden,false);assert.equal(p.d.querySelectorAll('#roster-groups .roster-player').length,42);
 q(p,'#view-roster').click();assert.equal(q(p,'#panel-roster').hidden,false);assert.equal(q(p,'#roster-management').hidden,false);assert.equal(q(p,'#cut-dialog'),null);assert.equal(p.d.querySelectorAll('#roster-groups [data-drop-id]').length,42);assert.match(q(p,'#cut-count').textContent,/42\/38/);
 q(p,`[data-drop-id="${owner}-qb1"]`).click();q(p,'#cut-cancel').click();assert.equal(raw(p),checkpoint);assert.equal(p.d.activeElement.dataset.dropId,`${owner}-qb1`);
 q(p,'#roster-stats-button').click();q(p,'#view-schedule').click();q(p,'#manage-roster').click();assert.equal(q(p,'#panel-roster').hidden,false);assert.equal(q(p,'#roster-ratings-button').getAttribute('aria-pressed'),'true');
 q(p,'#roster-groups [data-position="OL"]').open=false;
 const cuts=[`${owner}-qb1`,`${owner}-qb2`,`${owner}-rb1`,`${owner}-rb2`];
 for(const [index,id] of cuts.entries()){
  q(p,`[data-drop-id="${id}"]`).click();assert.equal(q(p,'#cut-confirmation').hidden,false);
  if(index===0){const old=raw(p);p.state.failCut=true;q(p,'#cut-confirm').click();await until(()=>!q(p,'#cut-error').hidden);assert.equal(raw(p),old);assert.equal(p.d.querySelectorAll('#roster-groups .roster-player').length,42);p.state.failCut=false;}
  const calls=p.state.cutCalls;q(p,'#cut-confirm').click();q(p,'#cut-confirm').click();assert.equal(p.state.cutCalls,calls+1);
  await until(()=>save(p).dropped?.length===index+1);
  assert.equal(p.d.querySelectorAll('#roster-groups .roster-player').length,41-index);assert.match(q(p,'#cut-count').textContent,new RegExp(`${41-index}/38`));assert.equal(q(p,'#panel-roster').hidden,false);
  if(index===0)assert.equal(q(p,'#roster-groups [data-position="OL"]').open,false,'Cuts preserve collapsed groups');
  assert.equal(q(p,`#roster-groups [data-player-id="${id}"]`),null);
  assert.equal(q(p,'#next-season').disabled,index<3);
  if(index===1){
   const qb=p.d.querySelectorAll('#roster-groups [data-position="QB"] .roster-player');assert.equal(qb.length,1);assert.equal(qb[0].querySelector('button').disabled,true);assert.equal(qb[0].querySelector('button').textContent,'Minimum reached');
   const blocked=await fetch(base+'/api/career/'+owner,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'cuts',season:1,run_seed:1234,lineup_rules:4,manual_picks:choices,dropped:[...save(p).dropped,choices[0]]})});assert.equal(blocked.status,422);
  }
  const saved=raw(p);p.dom.window.close();p=await restore(saved);q(p,'#manage-roster').click();assert.equal(p.d.querySelectorAll('#roster-groups [data-drop-id]').length,41-index);
 }
 const retained=[...p.d.querySelectorAll('#roster-groups .roster-player')].map(row=>row.dataset.playerId);
 for(const id of choices)assert.ok(retained.includes(id),'Rookie retained');
 q(p,'#view-standings').click();
 const other=[...p.d.querySelectorAll('.team-roster-link')].find(button=>button.dataset.teamId!==owner);
 other.click();await until(()=>q(p,'#scout-status').textContent.includes('38 players'));
 assert.equal(p.d.querySelectorAll('#scout-groups .roster-player').length,38);assert.equal(p.d.querySelectorAll('#scout-groups [data-drop-id]').length,0,'Other teams remain read-only');q(p,'#scout-close').click();
 const beforeAdvance=raw(p);p.state.failProfile=true;q(p,'#next-season').click();
 assert.equal(q(p,'#manage-roster').disabled,true);assert.ok([...p.d.querySelectorAll('#roster-groups [data-drop-id]')].every(button=>button.disabled),'Inline cuts locked during season advance');assert.equal(q(p,'#draft-button').disabled,true);
 await until(()=>!q(p,'#error').hidden);assert.equal(raw(p),beforeAdvance);assert.equal(q(p,'#season-display').textContent,'1');
 p.state.failProfile=false;q(p,'#next-season').click();await until(()=>save(p).season===2);
 assert.equal(p.d.querySelectorAll('#roster-groups .roster-rating-wrap .rookie-badge').length,4,'All retained rookies keep R in their first season');
 assert.equal(q(p,'#roster-management').hidden,true);assert.equal(p.d.querySelectorAll('#roster-groups [data-drop-id]').length,0,'No cuts during regular season');assert.equal(save(p).lineupRules,4);assert.equal(save(p).career[0].lineup_rules,4);assert.equal(save(p).career.length,1);assert.deepEqual(save(p).career[0].dropped,cuts);assert.equal(save(p).draftChoices,null);assert.deepEqual(save(p).dropped,[]);
 assert.deepEqual([...p.d.querySelectorAll('#roster-groups .roster-player')].map(row=>row.dataset.playerId).sort(),[...retained].sort());
 let saved=raw(p);p.dom.window.close();p=await restore(saved);assert.equal(q(p,'#season-display').textContent,'2');assert.deepEqual([...p.d.querySelectorAll('#roster-groups .roster-player')].map(row=>row.dataset.playerId).sort(),[...retained].sort());
 for(let week=1;week<=17;week++){
  q(p,'#simulate-button').click();await until(()=>save(p).week===week);
  if(week===1){assert.match(q(p,'#player-stats').textContent,/Passing/);const body={action:'week',season:2,run_seed:1234,lineup_rules:4,development_start:1,week:1,prior_standings:save(p).priorStandings,career:save(p).career};const data=await json('/api/career/'+owner,body);const box=data.result.home.team.id===owner?data.result.home:data.result.away;assert.equal(box.passing[0].player_id,choices[0]);assert.equal(box.rushing.length,1);assert.equal(box.rushing[0].player_id,choices[2]);for(const category of ['passing','rushing','receiving','kicking','blocking','defense'])for(const row of box[category])assert.ok(retained.includes(row.player_id));}
  if(week===8){saved=raw(p);p.dom.window.close();p=await restore(saved);assert.equal(q(p,'#simulate-button').textContent,'Simulate Week 9');}
 }
 q(p,'#playoffs-start').click();await until(()=>save(p).playoffRound===0);for(let round=1;round<=4;round++){q(p,'#playoff-simulate').click();await until(()=>save(p).playoffRound===round)}
 // A second offseason must draft from the already modified league, then preserve that career on another rollover.
 q(p,'#draft-button').click();await until(()=>save(p).draftChoices?.length===0);
 for(let turn=1;turn<=4;turn++){q(p,'#draft-prospects [data-draft-id]').click();await until(()=>save(p).draftChoices.length===turn)}
 q(p,'#draft-close').click();q(p,'#manage-roster').click();
 for(let count=1;count<=4;count++){q(p,'#roster-groups [data-drop-id]:not([disabled])').click();q(p,'#cut-confirm').click();await until(()=>save(p).dropped.length===count)}
 q(p,'#next-season').click();await until(()=>save(p).season===3);
 assert.equal(save(p).lineupRules,4);assert.equal(save(p).career.length,2);saved=raw(p);p.dom.window.close();p=await restore(saved);assert.equal(p.d.querySelectorAll('#roster-groups .roster-player').length,38);assert.equal(save(p).career.length,2);
 for(const row of p.d.querySelectorAll('#roster-groups .roster-player')){const entry=Number(row.dataset.playerId.split('-').at(-2));assert.equal(Boolean(row.querySelector('.rookie-badge')),row.dataset.playerId.startsWith('rookie-')&&entry===3);}
 p.dom.window.close();
 console.log('Inline roster-cut UI checks passed: direct Roster controls, Manage roster navigation, no dialog, collapsed groups, in-season cut controls removed, confirmation/cancel/retry, server and UI minimum protection, duplicate clicks, saved cuts, 42 to 38, retained rookie QB/RB in game stats, full next season/playoffs, second draft/cuts, and Season 3 restore.');
}
(async()=>{const server=spawn(process.env.PYTHON||'python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8772'],{cwd:root,stdio:['ignore','pipe','pipe']});let logs='';server.stdout.on('data',d=>logs+=d);server.stderr.on('data',d=>logs+=d);try{for(let i=0;;i++){if(server.exitCode!==null)throw new Error(logs);try{if((await fetch(base+'/api/teams')).ok)break}catch{}if(i===100)throw new Error(logs);await new Promise(r=>setTimeout(r,100))}await checks()}finally{server.kill()}})().catch(e=>{console.error(e);process.exitCode=1});
