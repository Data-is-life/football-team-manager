const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const {spawn}=require('node:child_process');
const {JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'..'),base='http://127.0.0.1:8771',key='arcade-league-save';
const script=fs.readFileSync(path.join(root,'app/static/app.js'),'utf8');
const html=fs.readFileSync(path.join(root,'app/static/index.html'),'utf8');
async function api(url,init){const response=await fetch(base+url,init);assert.equal(response.ok,true,url);return response.json()}
async function until(check){for(let i=0;i<1500;i++){if(check())return;await new Promise(r=>setTimeout(r,10))}throw new Error('UI state timed out')}
const q=(p,sel)=>p.d.querySelector(sel),raw=p=>p.w.localStorage.getItem(key),save=p=>JSON.parse(raw(p));
function page(checkpoint){
 const dom=new JSDOM(html,{url:base,runScripts:'outside-only'}),w=dom.window,d=w.document;
 w.localStorage.setItem(key,checkpoint);
 w.HTMLElement.prototype.scrollIntoView=()=>{};
 w.HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new w.Event('close'))};
 w.HTMLDialogElement.prototype.showModal=function(){this.open=true};
 Object.defineProperty(w.crypto,'getRandomValues',{value:a=>{a[0]=5678;return a}});
 const state={fail:false,calls:0,last:null,urls:[]};
 w.fetch=async(url,init)=>{
  state.urls.push(url);
  if(url.startsWith('/api/draft/')){
   state.calls++;
   if(state.fail)return {ok:false};
   const result=await api(url,init);state.last=result;
   return {ok:true,json:async()=>result};
  }
  return fetch(new URL(url,base),init);
 };
 w.eval(script);return {dom,w,d,state};
}
async function restore(checkpoint){const p=page(checkpoint);await until(()=>/restored|could not/.test(q(p,'#save-status').textContent));return p}
function oldStats(p){q(p,'#roster-stats-button').click();return new Map([...p.d.querySelectorAll('#roster-groups .roster-season-player')].filter(r=>!r.dataset.playerId.startsWith('rookie-')).map(r=>[r.dataset.playerId,r.textContent]))}
function checkRecap(p, picks) {
 const own=picks.filter(pick=>pick.team.id===save(p).teamId);
 assert.equal(q(p,'#draft-recap').hidden,false);
 assert.equal(q(p,'#draft-recap-empty').hidden,own.length>0);
 assert.equal(q(p,'#draft-recap-table-wrap').hidden,own.length===0);
 assert.deepEqual([...p.d.querySelectorAll('#draft-recap-rows tr')].map(row=>({id:row.dataset.playerId,cells:[...row.cells].map(cell=>cell.textContent)})),
  own.map(pick=>({id:pick.player.id,cells:[pick.round,pick.overall,pick.player.name,pick.player.position,pick.player.current_rating,pick.player.potential_rating].map(String)})));
 assert.match(q(p,'#draft-recap-caption').textContent,/Season 2 · Draft-day ratings/);
 assert.equal(p.d.querySelectorAll('#draft-recap th[scope="col"]').length,6);
 assert.equal(q(p,'#draft-recap-table-wrap').tabIndex,0);
 assert.equal(q(p,'#draft-recap-table-wrap').getAttribute('aria-labelledby'),'draft-recap-title');
 assert.equal(q(p,'#draft-recap').compareDocumentPosition(q(p,'#draft-board'))&p.w.Node.DOCUMENT_POSITION_FOLLOWING,p.w.Node.DOCUMENT_POSITION_FOLLOWING);
}
async function checks(){
 const final=await api('/api/playoffs/seattle/round/4?season=1&run_seed=1234');
 const owner=final.champion.team.id;
 const legacy=JSON.stringify({version:2,teamId:owner,runSeed:1234,season:1,week:17,playoffRound:4,priorStandings:{},history:[]});
 let p=await restore(legacy);assert.match(q(p,'#save-status').textContent,/restored/);
 assert.equal(q(p,'#draft-button').hidden,false);
 assert.equal(q(p,'#next-season').hidden,true);assert.equal(q(p,'#next-season').disabled,true);
 const calls=p.state.urls.length;
 q(p,'#next-season').hidden=false;q(p,'#next-season').disabled=false;q(p,'#next-season').click();
 assert.equal(p.state.urls.length,calls,'Even a forced click cannot bypass the draft');assert.equal(raw(p),legacy);
 const before=oldStats(p);q(p,'#roster-groups [data-position="QB"]').open=false;
 p.state.fail=true;q(p,'#draft-button').click();await until(()=>!q(p,'#draft-error').hidden);
 assert.equal(raw(p),legacy,'Failed start does not erase the saved season');assert.equal(q(p,'#draft-recap').hidden,true);assert.equal(q(p,'#next-season').disabled,true);assert.equal(q(p,'#next-season').hidden,true);
 p.state.fail=false;q(p,'#draft-retry').click();await until(()=>save(p).draftChoices?.length===0);
 assert.equal(p.state.last.class_size,200);assert.equal(p.state.last.order.length,30);
 assert.equal(p.state.last.next_pick,30,'Champion drafts last');
 assert.equal(q(p,'#next-season').disabled,true);
 assert.equal(save(p).draftRounds,6);assert.equal(p.state.last.rounds,6);checkRecap(p,p.state.last.picks);
 let selectedIds=[],previousPicks=[];
 for(let turn=1;turn<=6;turn++){
  q(p,'#roster-groups [data-position="QB"]').open=false;
  const filter=q(p,'#draft-position');filter.value='QB';filter.dispatchEvent(new p.w.Event('change'));
  assert.ok([...p.d.querySelectorAll('#draft-prospects tr')].every(r=>r.children[2].textContent==='QB'));checkRecap(p,p.state.last.picks);
  filter.value='';filter.dispatchEvent(new p.w.Event('change'));
  const buttons=[...p.d.querySelectorAll('[data-draft-id]')];assert.ok(buttons.length>0);
  const id=buttons[0].dataset.draftId;
  const prospect=p.state.last.available[0],cells=q(p,'#draft-prospects tr').children;
  assert.equal(cells.length,7);assert.equal(cells[4].textContent,String(prospect.current_rating));assert.equal(cells[5].textContent,String(prospect.potential_rating));
  assert.equal(q(p,'#draft-prospects tr').querySelectorAll('details').length,0);
  if(turn===1){
   const prior=raw(p);p.state.fail=true;buttons[0].click();await until(()=>!q(p,'#draft-error').hidden);
   assert.equal(raw(p),prior,'Failed pick preserves the checkpoint');checkRecap(p,p.state.last.picks);p.state.fail=false;q(p,'#draft-retry').click();
  }else{const count=p.state.calls;buttons[0].click();buttons[0].click();assert.equal(p.state.calls,count+1,'Double click cannot pick twice')}
  await until(()=>save(p).draftChoices?.length===turn);
  checkRecap(p,p.state.last.picks);
  selectedIds.push(id);assert.deepEqual(save(p).draftChoices,selectedIds);
  assert.deepEqual(p.state.last.picks.slice(0,previousPicks.length),previousPicks);
  previousPicks=structuredClone(p.state.last.picks);
  assert.equal(new Set(previousPicks.map(p=>p.player.id)).size,previousPicks.length);
  assert.equal(p.d.querySelectorAll('#roster-groups .roster-player').length,38+turn);
  assert.equal(q(p,'#roster-groups [data-position="QB"]').open,false);
  assert.deepEqual(oldStats(p),before,'Drafting preserves the completed season stats');
  const signed=[...p.d.querySelectorAll('#roster-groups .roster-player')].filter(row=>row.dataset.playerId.startsWith('rookie-'));
  assert.equal(p.d.querySelectorAll('#roster-groups .roster-rating-wrap .rookie-badge').length,turn);
  assert.equal(p.d.querySelectorAll('#roster-groups .roster-stats-wrap .rookie-badge').length,turn);
  for(const row of signed)assert.equal(row.querySelector('.rookie-badge').getAttribute('aria-label'),'Rookie');
  assert.equal(signed.length,turn);assert.deepEqual(signed.map(r=>r.dataset.playerId).sort(),[...selectedIds].sort());
  // Reload after every turn. Replay must preserve CPU picks, rookie IDs, roster counts, and stats.
  const checkpoint=raw(p),picks=JSON.stringify(previousPicks);p.dom.window.close();p=await restore(checkpoint);
  assert.match(q(p,'#save-status').textContent,/restored/);assert.equal(JSON.stringify(p.state.last.picks),picks);checkRecap(p,p.state.last.picks);
  assert.equal(p.d.querySelectorAll('#roster-groups .roster-player').length,38+turn);
  assert.deepEqual(oldStats(p),before);
  assert.equal(q(p,'#next-season').disabled,true);assert.equal(q(p,'#next-season').hidden,true);if(turn<6)assert.equal(q(p,'#manage-roster').hidden,true);
  q(p,'#draft-button').click();
 }
 assert.equal(p.state.last.complete,true);assert.equal(p.state.last.picks.length,180);assert.equal(p.state.last.available.length,20);
 assert.equal(q(p,'#draft-board').hidden,true);assert.equal(q(p,'#draft-picks').children.length,180);
 assert.equal(p.d.querySelectorAll('.your-draft-pick').length,6);assert.match(q(p,'#draft-summary').textContent,/44\/38 players/);
 const complete=raw(p);q(p,'#draft-close').click();
 const other=p.state.last.picks.find(pick=>pick.team.id!==owner).team.id;
 q(p,`.team-roster-link[data-team-id="${other}"]`).click();await until(()=>q(p,'#scout-status').textContent.includes('44 players'));
 assert.equal(p.d.querySelectorAll('#scout-groups .roster-player').length,44);assert.equal(p.d.querySelectorAll('#scout-groups .rookie-badge').length,6);
 q(p,'#scout-close').click();
 // Cutting a drafted rookie must not remove them from the draft-day recap.
 const completedPicks=structuredClone(p.state.last.picks),signedId=selectedIds[0];
 q(p,'#manage-roster').click();q(p,`#roster-groups [data-drop-id="${signedId}"]`).click();q(p,'#cut-confirm').click();
 await until(()=>save(p).dropped.length===1);assert.equal(q(p,`#roster-groups [data-player-id="${signedId}"]`),null);
 checkRecap(p,completedPicks);const cutCheckpoint=raw(p);p.dom.window.close();p=await restore(cutCheckpoint);
 checkRecap(p,completedPicks);q(p,'#draft-button').click();assert.equal(q(p,'#draft-dialog').open,true);assert.equal(raw(p),cutCheckpoint);
 q(p,'#draft-close').click();
 q(p,'#change-team-button').click();q(p,'#team-select').value='seattle';
 q(p,'#team-form').dispatchEvent(new p.w.Event('submit',{cancelable:true}));await until(()=>save(p).runSeed===5678);
 assert.equal(save(p).draftChoices,null);assert.equal(q(p,'#draft-recap').hidden,true);assert.equal(q(p,'#draft-recap-rows').children.length,0);assert.equal(p.d.querySelectorAll('#roster-groups .rookie-badge').length,0);assert.equal(q(p,'#draft-button').hidden,true);assert.equal(q(p,'#draft-button').textContent,'Start rookie draft');assert.equal(q(p,'#draft-picks').children.length,0);
 assert.equal(p.d.querySelectorAll('#roster-groups .roster-player').length,38);p.dom.window.close();
 const damaged=JSON.parse(complete);damaged.draftChoices[0]='missing-prospect';
 const invalid=JSON.stringify(damaged);p=await restore(invalid);
 assert.match(q(p,'#save-status').textContent,/could not be loaded/);assert.equal(raw(p),invalid);assert.equal(q(p,'#schedule-section').hidden,true);p.dom.window.close();
 // Auto-draft can finish from any user turn, preserves manual choices, and uses ordinary saved IDs.
 for(const manualCount of [0,1,2,3,4,5]){
  p=await restore(legacy);const previousStats=oldStats(p);
  q(p,'#draft-button').click();await until(()=>save(p).draftChoices?.length===0);
  for(let turn=1;turn<=manualCount;turn++){q(p,'#draft-prospects [data-draft-id]').click();await until(()=>save(p).draftChoices.length===turn)}
  const prefix=[...save(p).draftChoices],priorPicks=structuredClone(p.state.last.picks),checkpoint=raw(p);
  if(manualCount===1){
   p.state.fail=true;q(p,'#auto-draft').click();await until(()=>!q(p,'#draft-error').hidden);
   assert.equal(raw(p),checkpoint);assert.equal(q(p,'#next-season').hidden,true);p.state.fail=false;
   q(p,'#draft-retry').click();
  }else{
   const count=p.state.calls;q(p,'#auto-draft').click();q(p,'#auto-draft').click();assert.equal(p.state.calls,count+1,'Auto-draft double click makes one request');
   assert.equal(q(p,'#auto-draft').disabled,true);assert.ok([...p.d.querySelectorAll('#draft-prospects [data-draft-id]')].every(button=>button.disabled));
  }
  await until(()=>save(p).draftChoices.length===6);
  assert.deepEqual(save(p).draftChoices.slice(0,manualCount),prefix);
  assert.deepEqual(p.state.last.picks.slice(0,priorPicks.length),priorPicks);
  assert.equal(p.state.last.picks.length,180);assert.equal(p.state.last.complete,true);checkRecap(p,p.state.last.picks);
  assert.equal(p.d.querySelectorAll('#roster-groups .roster-player').length,44);assert.equal(q(p,'#next-season').disabled,true);
  assert.equal(q(p,'#draft-board').hidden,true);assert.deepEqual(oldStats(p),previousStats);
  const allPicks=structuredClone(p.state.last.picks),saved=raw(p);p.dom.window.close();p=await restore(saved);
  assert.deepEqual(p.state.last.picks,allPicks);checkRecap(p,allPicks);assert.equal(raw(p),saved);p.dom.window.close();
 }
 // Started legacy four-round drafts retain their format, including a saved empty board.
 const post=body=>api(`/api/draft/${owner}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({season:1,run_seed:1234,...body})});
 const oldDraft=await post({auto_draft:true});
 for(const count of [0,2,4]){
  const oldSave={...JSON.parse(legacy),version:15,careerStartWeek:1,lineupChanges:[],contracts:false,
   lineupRules:1,developmentStart:null,rebuildTeam:null,career:[],dropped:[],draftChoices:oldDraft.manual_picks.slice(0,count)};
  const expected=await post({manual_picks:oldSave.draftChoices});
  p=await restore(JSON.stringify(oldSave));checkRecap(p,p.state.last.picks);assert.equal(p.state.last.rounds,4);assert.deepEqual(p.state.last.picks,expected.picks);
  q(p,'#draft-button').click();assert.match(q(p,'#draft-format').textContent,/4 rounds/);
  if(count<4){
   q(p,'#auto-draft').click();await until(()=>save(p).draftChoices.length===4);
   assert.equal(save(p).version,17);assert.equal(save(p).draftRounds,4);
   assert.deepEqual(p.state.last.picks,oldDraft.picks);checkRecap(p,oldDraft.picks);
   const frozen=raw(p);p.dom.window.close();p=await restore(frozen);assert.equal(p.state.last.rounds,4);assert.deepEqual(p.state.last.picks,oldDraft.picks);checkRecap(p,oldDraft.picks);
  }
  assert.equal(p.d.querySelectorAll('#roster-groups .roster-player').length,42);p.dom.window.close();
 }
 for(const rounds of [5,null,undefined]){
  const invalid=JSON.stringify({...JSON.parse(complete),draftRounds:rounds});p=await restore(invalid);
  assert.match(q(p,'#save-status').textContent,/could not be read/);assert.equal(raw(p),invalid);p.dom.window.close();
 }
 // Validate real POST requests and ensure unavailable/duplicate picks never commit.
 const first=await api(`/api/draft/${owner}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({season:1,run_seed:1234})});
 for(const body of [{manual_picks:['missing']},{manual_picks:['x','x']},{manual_picks:['a','b','c','d','e']},{season:999},{run_seed:-1},{prior_standings:{}},{manual_picks:[first.picks[0].player.id]}]){
  const response=await fetch(base+`/api/draft/${owner}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({season:1,run_seed:1234,...body})});
  assert.equal(response.status,422);
 }
 console.log('Draft UI checks passed: all six user turns and 180 picks, CPU replay, permanent IDs, filters/current/potential, failed request/retry, duplicate clicks, reload every round, 44-player own/scouting rosters, preserved stats, regular-season gate, legacy save, new-career reset, invalid API/save data, and own-team draft recap with draft-day ratings, keyboard-scroll region, filters, manual/auto picks, cuts/reloads, legacy drafts and reset.');
}
(async()=>{
 const server=spawn(process.env.PYTHON||'python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8771'],{cwd:root,stdio:['ignore','pipe','pipe']});
 let logs='';server.stdout.on('data',d=>logs+=d);server.stderr.on('data',d=>logs+=d);
 try{
  for(let i=0;;i++){if(server.exitCode!==null)throw new Error(logs);try{if((await fetch(base+'/api/teams')).ok)break}catch{}if(i===100)throw new Error(logs);await new Promise(r=>setTimeout(r,100))}
  await checks();
 }finally{server.kill()}
})().catch(error=>{console.error(error);process.exitCode=1});
