const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {spawn,execFileSync}=require('node:child_process'),{JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'..'),base='http://127.0.0.1:8797',key='arcade-league-save';
const checkpointKey='arcade-league-checkpoint';
const fixture=JSON.parse(execFileSync(process.env.PYTHON||'python',['tests/simple_offseason_fixtures.py'],{cwd:root,env:{...process.env,PYTHONPATH:root},encoding:'utf8'}));
const draftRules=Number(process.env.TEST_DRAFT_RULES||42);
const html=fs.readFileSync(path.join(root,'app/static/index.html'),'utf8');
const source=fs.readFileSync(path.join(root,'app/static/app.js'),'utf8');
const script=draftRules<60?require('./historical-save-fixtures.cjs').allowHistoricalFixtures(source):source;
const q=(p,s)=>p.d.querySelector(s),raw=p=>p.w.localStorage.getItem(key),save=p=>JSON.parse(raw(p));
async function until(check){for(let i=0;i<4000;i++){if(check())return;await new Promise(r=>setTimeout(r,10));}throw Error('Simple offseason UI timeout');}
async function page(checkpoint, leagueCheckpoint){
 const dom=new JSDOM(html,{url:base,runScripts:'outside-only'}),w=dom.window,d=w.document,state={calls:[],requests:[],fail:false};
 w.localStorage.setItem(key,JSON.stringify(checkpoint));w.HTMLElement.prototype.scrollIntoView=()=>{};w.scrollTo=()=>{};
 if(leagueCheckpoint)w.localStorage.setItem(checkpointKey,leagueCheckpoint);
 w.HTMLDialogElement.prototype.close=function(){this.open=false};w.HTMLDialogElement.prototype.showModal=function(){this.open=true};
 w.fetch=async(url,init)=>{const b=init&&JSON.parse(init.body);state.requests.push(b?.action??url);if(b)state.calls.push(b);if(state.fail&&b?.action==='own_players')return {ok:false,json:async()=>({detail:'Temporary signing failure'})};const r=await fetch(new URL(url,base),init);if(!r.ok)console.error('API:',b?.action,await r.clone().text());else if(b){const data=await r.clone().json();if(data.profile)state.profile=data.profile;else if(b.action==='profile')state.profile=data;}return r;};
 w.eval(script);const p={dom,w,d,state};await until(()=>/restored|could not/.test(q(p,'#save-status').textContent));assert.match(q(p,'#save-status').textContent,/restored/);return p;
}
function assertDraftNavigation(p, visible){
 for(const selector of ['#draft-button','#roster-draft-return','#view-draft'])assert.equal(q(p,selector).hidden,!visible,selector);
}
async function checks(){
 if(draftRules===44){
  const legacyMarket={...fixture.checkpoint,ownActions:fixture.actions,freeAgency:[]};
  const restored=await page(legacyMarket);
  assert.equal(restored.state.profile.lineup_rules,44,'An opened market keeps its recorded signing rules');
  assert.equal(save(restored).lineupRules,44);assertDraftNavigation(restored,false);restored.dom.window.close();
 }
 const draftCheckpoint={...fixture.checkpoint};delete draftCheckpoint.freeAgency;delete draftCheckpoint.ownActions;
 let p=await page(draftCheckpoint);
 assert.equal(q(p,'#own-signing').hidden,true);assert.equal(q(p,'#next-season').textContent,'Sign your own players');
 q(p,'#next-season').click();await until(()=>!q(p,'#own-signing').hidden&&save(p).ownActions&&q(p,'#roster-groups [data-resign-id]:not([disabled])'));

 assert.equal(q(p,'#own-signing').hidden,false);assert.equal(q(p,'#panel-roster').hidden,false);
 assert.equal(q(p,'#training-camp-button').hidden,true);assert.equal(q(p,'#view-free-agency').hidden,true);assert.equal(q(p,'#view-trades').hidden,true);
 assert.match(q(p,'#own-signing-status').textContent,/decisions remaining/);
 const rookiePick=fixture.own.picks.find(pick=>pick.team.id===fixture.checkpoint.teamId);
 const profileButton=id=>q(p,`#roster-groups [data-player-id="${id}"] .player-profile-button`);
 const profileText=field=>q(p,`#player-overview-${field}`).textContent;
 const salaryRows=()=>[...p.d.querySelectorAll('#player-contract-rows tr')]
  .map(row=>[...row.cells].map(cell=>cell.textContent));
 const profileRequests=p.state.requests.length,profileSave=raw(p);
 profileButton(rookiePick.player.id).click();
 assert.equal(q(p,'#player-overview').open,true);
 assert.equal(profileText('name'),rookiePick.player.name);
 assert.equal(profileText('position'),rookiePick.player.position);
 assert.equal(profileText('age'),String(rookiePick.player.age));
 assert.equal(profileText('current'),String(rookiePick.player.current_rating));
 assert.equal(profileText('potential'),String(rookiePick.player.potential_rating));
 assert.match(profileText('height'),/^\d′ \d{1,2}″$/);
 assert.match(profileText('weight'),/^\d{3} lb$/);
 const profileMeasurements=[profileText('height'),profileText('weight')];
 assert.equal(profileText('draft'),`Round ${rookiePick.round} · #${rookiePick.overall} overall`);
 assert.equal(salaryRows()[0][1],'Provisional');
 assert.equal(p.d.activeElement,q(p,'#player-overview-close'));
 q(p,'#player-overview-close').click();
 assert.equal(q(p,'#player-overview').open,false);
 assert.equal(p.state.requests.length,profileRequests);
 assert.equal(raw(p),profileSave);
 function assertPendingBlocked(){
  assert.equal(q(p,'#next-season').textContent,'Finish own-player signing');
  for(const selector of ['#next-season','#own-signing-finish']){
   const button=q(p,selector);assert.equal(button.disabled,true);
   const calls=p.state.calls.length,checkpoint=raw(p);
   button.click();assert.equal(p.state.calls.length,calls);
   button.disabled=false;button.click();
   assert.equal(p.state.calls.length,calls,'Forced finish sends no premature API request');
   assert.equal(raw(p),checkpoint);button.disabled=true;
  }
 }
 assertPendingBlocked();
 const restoredPending=save(p);p.dom.window.close();p=await page(restoredPending);assertPendingBlocked();
 const initial=raw(p),first=fixture.actions[0];
 q(p,`[data-drop-id="${first.player_id}"]`).click();p.state.fail=true;q(p,'#cut-confirm').click();await until(()=>!q(p,'#cut-error').hidden&&!q(p,'#cut-confirm').disabled);assert.equal(raw(p),initial);p.state.fail=false;q(p,'#cut-cancel').click();
 for(const a of fixture.actions.filter(a=>a.kind!=='finish')){
  const n=save(p).ownActions.length;
  const selector=a.kind==='drop'?'data-drop-id':'data-resign-id';
  q(p,`[${selector}="${a.player_id}"]`).click();
  if(a.kind==='sign'){assert.equal(q(p,'#cut-confirm').textContent,'Confirm signing');assert.match(q(p,'#cut-confirm-text').textContent,/Sign .* for \$/);}
  if(p.state.profile.lineup_rules>=45){
   const pay=p.state.profile.payroll;
   assert.equal(pay.total,pay.committed+pay.dead_cap);assert.equal(pay.rookie_holds,0);assert.equal(pay.expired_holds,0);
   if(a.kind==='sign'){
    const offer=p.state.profile.roster.find(player=>player.id===a.player_id).contract_offer;
    assert.ok(q(p,'#cut-impact').textContent.includes(`Payroll after signing: $${((pay.total+offer.annual_salary)/1e6).toFixed(2)}M`));
    assert.equal(q(p,'#cut-confirm').disabled,pay.total+offer.annual_salary>pay.cap);
   }
  }
  q(p,'#cut-confirm').click();q(p,'#cut-confirm').click();await until(()=>save(p).ownActions.length===n+1);
  assert.equal(save(p).ownActions.at(-1).kind,a.kind);
  const remaining=p.state.profile.roster.filter(player=>player.renewal_offer||player.contract_offer).length;
  for(const selector of ['#next-season','#own-signing-finish'])assert.equal(q(p,selector).disabled,remaining>0);
 }
 const ownSave=save(p);p.dom.window.close();p=await page(ownSave);
 assert.equal(q(p,'#own-signing').hidden,false);assert.equal(q(p,'#own-signing-finish').disabled,false);assert.equal(q(p,'#next-season').disabled,false);assertDraftNavigation(p,true);
 q(p,'#own-signing-finish').click();q(p,'#own-signing-finish').click();await until(()=>save(p).ownActions.at(-1).kind==='finish'&&!q(p,'#panel-free-agency').hidden&&!q(p,'#fa-finish').disabled);
 assert.equal(q(p,'#own-signing').hidden,true);assert.equal(q(p,'#training-camp-button').hidden,true);assertDraftNavigation(p,false);
 assert.equal(q(p,'#fa-pass').hidden,true);assert.equal(q(p,'#fa-review-own').hidden,true);assert.equal(q(p,'#fa-pricing-guide').hidden,true);
 assert.match(q(p,'#fa-status').textContent,/Fixed asking prices/);assert.doesNotMatch(q(p,'#fa-status').textContent,/Wave|undefined/);
 const prices=new Map([...p.d.querySelectorAll('#fa-players tr')].map(r=>[r.querySelector('[data-fa-id]').dataset.faId,r.children[5].textContent]));
 const sign=q(p,'#fa-players button:not([disabled])');assert.ok(sign);const id=sign.dataset.faId;
 const signingRow=[...sign.closest('tr').cells].map(cell=>cell.textContent);
 sign.click();q(p,'#fa-confirm').click();q(p,'#fa-confirm').click();await until(()=>save(p).freeAgency.length===1&&!q(p,'#fa-finish').disabled);
 assert.equal(save(p).freeAgency[0].player_id,id);
 for(const row of p.d.querySelectorAll('#fa-players tr'))assert.equal(row.children[5].textContent,prices.get(row.querySelector('[data-fa-id]').dataset.faId));
 assert.ok(q(p,`#roster-groups [data-player-id="${id}"]`));
 const marketSave=save(p);p.dom.window.close();p=await page(marketSave);
 const recap=q(p,'#fa-log .your-fa-signing');
 assert.ok(recap);
 assert.equal(q(p,'#fa-log-wave').hidden,true);
 assert.deepEqual([...recap.cells].slice(1).map(cell=>cell.textContent),[signingRow[0],signingRow[5]]);
 assert.equal(q(p,'#fa-pass').hidden,true);assert.match(q(p,'#fa-status').textContent,/Fixed asking prices/);assertDraftNavigation(p,false);
 // A different draft order can leave a position short after the initial signing.
 for(let i=0;i<31&&draftRules>=48;i++){
  const profile=p.state.profile;
  const missing=profile.roster_rules.find(rule=>rule.count<rule.minimum);
  if(!missing&&profile.roster.length>=profile.roster_limits.minimum)break;
  const row=[...p.d.querySelectorAll('#fa-players tr')].find(row=>
   (!missing||row.children[1].textContent===missing.position)&&row.querySelector('[data-fa-id]:not([disabled])'));
  assert.ok(row,'An affordable free agent can fill the open slot');
  const count=save(p).freeAgency.length;
  row.querySelector('[data-fa-id]').click();q(p,'#fa-confirm').click();
  await until(()=>save(p).freeAgency.length===count+1&&!q(p,'#fa-finish').disabled);
 }
 q(p,'#fa-finish').click();await until(()=>save(p).freeAgency.at(-1)?.kind==='finish'&&!q(p,'#panel-roster').hidden);
 assertDraftNavigation(p,false);assert.equal(q(p,'#training-camp-button').hidden,true);assert.equal(q(p,'#panel-trades').hidden,true);assert.equal(q(p,'#view-free-agency').hidden,draftRules<48);
 if(!q(p,'#meet-payroll-floor').hidden){q(p,'#meet-payroll-floor').click();q(p,'#floor-confirm').click();await until(()=>q(p,'#meet-payroll-floor').hidden);}
 assert.equal(q(p,'#view-trades').hidden,true);assert.equal(q(p,'#next-season').textContent,'Start season');
 assert.equal(q(p,'#next-season').disabled,false);
 const requestCount=p.state.requests.length;
 q(p,'#next-season').click();await until(()=>save(p).season===2);
 const transition=p.state.requests.slice(requestCount);
 assert.match(transition[0],/\/api\/schedule\/seattle\?season=2&/);
 assert.deepEqual(transition.slice(1),['trades','profile']);
 assert.equal(save(p).lineupRules,draftRules===44?45:draftRules);assert.equal(save(p).career[0].own_actions.at(-1).kind,'finish');assert.equal(save(p).career[0].trade_actions.at(-1).kind,'finish');
 assert.equal(q(p,'#training-camp-button').hidden,true);assert.equal(q(p,'#own-signing').hidden,true);assert.equal(q(p,'#view-trades').hidden,true);
 assert.equal(q(p,'#development-dialog').open,true);assert.ok(q(p,`#roster-groups [data-player-id="${id}"]`));
 const next=save(p),leagueCheckpoint=p.w.localStorage.getItem(checkpointKey);
 const stored=JSON.parse(leagueCheckpoint);
 assert.equal(stored.season,2);assert.equal(stored.teamId,'seattle');assert.ok(stored.token.length>0);
 p.dom.window.close();p=await page(next,leagueCheckpoint);assert.deepEqual(save(p),next);assert.ok(q(p,`#roster-groups [data-player-id="${id}"]`));
 assert.equal(p.state.calls.find(call=>call.action==='profile').checkpoint,stored.token);
 assert.equal(p.w.localStorage.getItem(checkpointKey),leagueCheckpoint);
 q(p,'#view-roster').click();
 profileButton(rookiePick.player.id).click();
 assert.deepEqual([profileText('height'),profileText('weight')],profileMeasurements);
 assert.equal(profileText('draft'),`Round ${rookiePick.round} · #${rookiePick.overall} overall`);
 assert.equal(salaryRows()[0][1],'Current');
 q(p,'#player-overview-close').click();
 const retained=p.state.profile.roster.find(player=>player.contract
  && next.playerContractHistory[0].contracts.some(contract=>contract.playerId===player.id));
 assert.ok(retained);
 const past=next.playerContractHistory[0].contracts.find(contract=>contract.playerId===retained.id);
 q(p,'#roster-stats-button').click();
 q(p,`#roster-groups .roster-season-player[data-player-id="${retained.id}"] .player-profile-button`).click();
 const term=(start,end)=>start===end?String(start):`${start}–${end}`;
 assert.deepEqual(salaryRows()[0],['1','Past',term(past.start,past.end),`$${(past.annualSalary/1e6).toFixed(2)}M`]);
 const deal=retained.contract;
 assert.deepEqual(salaryRows()[1],['2','Current',term(deal.signed_season,deal.expires_after_season),`$${(deal.annual_salary/1e6).toFixed(2)}M`]);
 q(p,'#player-overview-close').click();
 assert.ok(!p.state.calls.some(c=>c.action==='camp'));p.dom.window.close();
 console.log('Simple offseason UI passed: own-player signing and rookies, failure/retry, duplicate guards, fixed-price market with no pass or camp, CPU competition, payroll review, trades, automatic development, saves and Season 2 replay.');
}
(async()=>{const server=spawn(process.env.PYTHON||'python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8797'],{cwd:root,stdio:['ignore','pipe','pipe']});let logs='';server.stdout.on('data',d=>logs+=d);server.stderr.on('data',d=>logs+=d);try{for(let i=0;;i++){if(server.exitCode!==null)throw Error(logs);try{if((await fetch(base+'/api/teams')).ok)break;}catch{}if(i===100)throw Error(logs);await new Promise(r=>setTimeout(r,100));}await checks();}finally{server.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
