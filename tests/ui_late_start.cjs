const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {spawn}=require('node:child_process'),{JSDOM}=require('jsdom');
const {finishOffseason}=require('./ui_offseason_helpers.cjs');
const root=path.resolve(__dirname,'..'),base='http://127.0.0.1:8779',key='arcade-league-save';
const html=fs.readFileSync(path.join(root,'app/static/index.html'),'utf8'),script=fs.readFileSync(path.join(root,'app/static/app.js'),'utf8');
async function until(check){for(let i=0;i<2000;i++){if(check())return;await new Promise(r=>setTimeout(r,10))}throw new Error('Late-start UI state timed out')}
const q=(p,s)=>p.d.querySelector(s),raw=p=>p.w.localStorage.getItem(key),save=p=>JSON.parse(raw(p));
function page(checkpoint){
 const dom=new JSDOM(html,{url:base,runScripts:'outside-only'}),w=dom.window,d=w.document,state={weeks:[],failStart:false,failCamp:false,campCalls:0};
 if(checkpoint)w.localStorage.setItem(key,JSON.stringify(checkpoint));w.HTMLElement.prototype.scrollIntoView=()=>{};
 w.HTMLDialogElement.prototype.close=function(){this.open=false};w.HTMLDialogElement.prototype.showModal=function(){this.open=true};
 Object.defineProperty(w.crypto,'getRandomValues',{value:a=>{a[0]=5678;return a}});
 w.fetch=async(url,init)=>{
  const body=init?JSON.parse(init.body):null;
  const week=body?.action==='week'?body.week:Number(/\/api\/season\/[^/]+\/week\/(\d+)/.exec(url)?.[1]);
  if(week)state.weeks.push(week);
  if(body?.action==='camp'){state.campCalls++;if(state.failCamp)return {ok:false,json:async()=>({detail:'Camp temporarily unavailable'})};}
  if(state.failStart&&url.startsWith('/api/season/')&&week===16)return {ok:false};
  const response=await fetch(new URL(url,base),init);
  if(!week)return response;
  const data=await response.json();state.lastWeek=data;return {ok:response.ok,json:async()=>data};
 };
 w.eval(script);return {dom,w,d,state};
}
async function restore(checkpoint){const p=page(checkpoint);await until(()=>/restored|could not/.test(q(p,'#save-status').textContent));assert.match(q(p,'#save-status').textContent,/restored/);p.state.weeks=[];return p}
async function start(p){await until(()=>q(p,'#team-select').options.length===31);q(p,'#team-select').value='seattle';q(p,'#team-form').dispatchEvent(new p.w.Event('submit',{cancelable:true}));await until(()=>save(p)?.careerStartWeek===17&&save(p)?.week===16)}
const record=r=>`${r.wins}–${r.losses}–${r.ties}`;
async function checks(){
 let p=page();await start(p);
 assert.equal(save(p).lineupRules,19);
 assert.match(q(p,'#payroll-status').textContent,/Season 1 payroll.*\$200.00M cap/);
 assert.equal(q(p,'#salary-growth-guide').hidden,false);
 assert.equal(p.d.querySelectorAll('#roster-groups .roster-player').length,35);
 const startingResponse=await fetch(base+'/api/team/seattle?run_seed=5678&lineup_rules=19&season=1&development_start=1&rebuild_team=seattle');
 assert.equal(startingResponse.ok,true);const startingProfile=await startingResponse.json();
 const originalPay=new Map(startingProfile.roster.map(player=>[player.id,player.contract.annual_salary]));
 for(const player of startingProfile.roster){
  const cell=q(p,`#roster-groups [data-player-id="${player.id}"] .salary-cell`);
  assert.ok(cell.textContent.startsWith(`$${(player.contract.annual_salary/1000000).toFixed(2)}M/yr`));
  assert.match(cell.title,new RegExp(`${player.contract.years}-year contract`));
 }
 assert.equal(p.d.querySelectorAll('#roster-groups .salary-cell').length,35);
 assert.equal(q(p,'#player-salary-guide').hidden,false);
 const beforeScout=raw(p);q(p,'#view-standings').click();
 const other=[...p.d.querySelectorAll('.team-roster-link')].find(button=>button.dataset.teamId!=='seattle');
 other.click();await until(()=>p.d.querySelectorAll('#scout-groups .salary-cell').length===35);
 assert.equal(raw(p),beforeScout);q(p,'#scout-close').click();q(p,'#view-schedule').click();

 const sizes={QB:2,WR:4,TE:2,RB:2,OL:7,K:1,DL:6,LB:4,CB:4,S:3};
 for(const [position,count]of Object.entries(sizes))assert.equal(p.d.querySelectorAll(`#roster-groups [data-position="${position}"] .roster-player`).length,count);
 assert.match(q(p,'#roster-limit-note').textContent,/Every team starts with 35 players.*roster: 35–38/);assert.match(q(p,'#draft-format').textContent,/roster range is 35–38/);

 assert.equal(save(p).version,29);assert.equal(q(p,'#development-recap-button').hidden,true);assert.equal(q(p,'#development-dialog').open,false);assert.equal(q(p,'#development-recap-rows').children.length,0);assert.equal(save(p).careerStartWeek,17);assert.deepEqual(p.state.weeks,[16]);assert.equal(q(p,'#simulate-button').textContent,'Simulate Week 17');
 assert.equal(p.d.querySelectorAll('#schedule .completed').length,16);assert.equal(q(p,'#gm-regular').textContent,'0–0–0');assert.equal(q(p,'#gm-appearances').textContent,'0');assert.equal(q(p,'#career-start-note').hidden,false);assert.equal(q(p,'#gm-tenure-note').hidden,false);
 assert.match(q(p,'#result-week').textContent,/Before your hiring/);assert.match(q(p,'#owner-feedback').textContent,/four-year contract covering Seasons 2–5/);assert.match(q(p,'#contract-status').textContent,/4 years remaining.*Season 5/);
 q(p,'#welcome-dismiss').click();assert.equal(save(p).welcomeDismissed,true);
 const inherited=save(p),fullRecord=p.state.lastWeek.record;
 assert.equal(fullRecord.wins+fullRecord.losses+fullRecord.ties,16);q(p,'#roster-stats-button').click();assert.match(q(p,'#roster-stats-status').textContent,/16 team games/);
 assert.deepEqual(JSON.parse(JSON.stringify(p.w.managedRecord({record:{wins:8,losses:8,ties:1},game_results:[{week:1,outcome:'W'},{week:17,outcome:'T'}]}))),{wins:0,losses:0,ties:1});
 const status=p.w.contractStatus,intro={season:1,playoffFinish:'Champions',wins:12,losses:5,ties:0};
 assert.equal(status([],1,{complete:true,qualified:true,champion:true,wins:12,losses:5},2).end,5,'Intro achievements do not award contract extensions');
 assert.equal(status([intro],2,null,2).remaining,4);
 for(const [qualified,champion,reward] of [[true,true,5],[true,false,2],[false,false,1]])assert.equal(status([intro],2,{complete:true,qualified,champion,wins:10,losses:7},2).end,5+reward);
 const extended=[intro,{season:2,playoffFinish:'Lost in Wild Card',wins:8,losses:9},...[3,4,5,6,7].map(season=>({season,playoffFinish:'Missed playoffs',wins:6,losses:11}))];
 assert.equal(status(extended,8,null,2).reason,'expired');
 const misses=[2,3,4].map(season=>({season,playoffFinish:'Missed playoffs',wins:9,losses:8,ties:0}));
 assert.equal(status([intro,...misses],5,null,2).fired,false);
 assert.equal(status([intro,...misses,{...misses[0],season:5}],6,null,2).reason,'deadline','Intro playoffs cannot satisfy the full-season deadline');
 assert.equal(status([intro,...misses,{...misses[0],season:5,playoffFinish:'Lost in Wild Card'}],6,null,2).fired,false);
 p.dom.window.close();p=await restore(inherited);assert.equal(q(p,'#gm-regular').textContent,'0–0–0');assert.equal(q(p,'#simulate-button').textContent,'Simulate Week 17');assert.equal(raw(p),JSON.stringify(inherited));
 assert.equal(q(p,'#starter-form'),null);assert.deepEqual(save(p).lineupChanges,[]);
 p.state.weeks=[];q(p,'#simulation-more > summary').click();q(p,'#simulate-season').click();assert.match(q(p,'#season-confirm-message').textContent,/1 regular-season game \(Week 17\)/);assert.equal(p.state.weeks.length,0);q(p,'#season-confirm-start').click();await until(()=>save(p).week===17&&q(p,'#stop-season').hidden);assert.deepEqual(p.state.weeks,[17]);assert.equal(save(p).playoffRound,null);assert.equal(save(p).draftChoices,null);
 const managed=p.w.managedRecord(p.state.lastWeek);assert.equal(managed.wins+managed.losses+managed.ties,1);assert.equal(q(p,'#gm-regular').textContent,record(managed));assert.match(q(p,'#contract-status').textContent,/4 years remaining.*Season 5/);
 // Opponent records update with Week 17, but inherited score results cannot change.
 for(let i=0;i<16;i++){assert.ok(p.d.querySelectorAll('#schedule .game-final')[i].textContent.includes(p.state.lastWeek.game_results[i].team_score+'–'+p.state.lastWeek.game_results[i].opponent_score))}
 const full=p.state.lastWeek.record,completed=save(p);p.dom.window.close();p=await restore(completed);assert.equal(q(p,'#gm-regular').textContent,record(managed));
 q(p,'#playoffs-start').click();await until(()=>save(p).playoffRound===0);for(let round=1;round<=4;round++){q(p,'#playoff-simulate').click();await until(()=>save(p).playoffRound===round)}
 assert.equal(q(p,'#next-season').hidden,true);await finishOffseason(p,until);
 assert.equal(p.d.querySelectorAll('#draft-recap-rows .salary-cell').length,6);
 assert.ok([...p.d.querySelectorAll('#draft-recap-rows .salary-cell')].every(cell=>/Provisional/.test(cell.textContent)));
 const campRookies=[...p.d.querySelectorAll('#roster-groups .roster-player')].filter(row=>row.dataset.playerId.startsWith('rookie-'));
 assert.ok(campRookies.length>0);assert.ok(campRookies.every(row=>/Provisional/.test(row.querySelector('.salary-cell').textContent)));
 assert.ok(campRookies.every(row=>/unsigned until retained past training camp/.test(row.querySelector('.salary-cell').title)));
 assert.match(q(p,'#payroll-status').textContent,/signed.*rookie holds/);
 assert.ok([...p.d.querySelectorAll('#draft-recap-rows .salary-cell')].every(cell=>/\$[0-9.]+M\/yr/.test(cell.textContent)));
 const draftedCount=p.d.querySelectorAll('#roster-groups .roster-player').length;
 assert.ok(draftedCount>=35&&draftedCount<=38);assert.equal(q(p,'#next-season').hidden,false);assert.equal(q(p,'#next-season').disabled,false);
 assert.ok(q(p,'#cut-count').textContent.startsWith(`${draftedCount}/38 players (minimum 35)`));
 assert.match(q(p,'#cut-count').textContent,/No more cuts needed/);
 // Optional cuts can reach 35, then all releases are blocked, even forced clicks.
 while(p.d.querySelectorAll('#roster-groups .roster-player').length>35){
  const before=save(p).dropped.length;
  q(p,'#roster-groups [data-drop-id]:not([disabled])').click();q(p,'#cut-confirm').click();
  await until(()=>save(p).dropped.length===before+1);
 }
 assert.ok([...p.d.querySelectorAll('#roster-groups [data-drop-id]')].every(button=>button.disabled));
 const minimumCheckpoint=raw(p),forced=q(p,'#roster-groups [data-position="WR"] [data-drop-id]');
 forced.disabled=false;forced.click();assert.equal(q(p,'#cut-confirmation').hidden,true);assert.equal(raw(p),minimumCheckpoint);
 p.w.renderCuts();assert.match(q(p,'#cut-count').textContent,/35\/38 players \(minimum 35\)/);
 // UI cap state is server-supplied; test the over-cap minimum-roster controls.
 const minimumSave=save(p);
 const minimumProfile=(await (await fetch(base+'/api/career/seattle',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'cuts',season:1,run_seed:5678,lineup_rules:19,training_camp:true,rebuild_team:'seattle',draft_rounds:6,manual_picks:minimumSave.draftChoices,dropped:minimumSave.dropped})})).json()).profile;
 assert.ok(minimumProfile.payroll.rookie_holds>0);assert.equal(minimumProfile.payroll.total,minimumProfile.payroll.committed+minimumProfile.payroll.rookie_holds);
 assert.equal(minimumProfile.payroll.season,2);assert.equal(minimumProfile.payroll.cap,210000000);assert.equal(minimumProfile.payroll.minimum_salary,1050000);
 p.w.renderTeamProfile({...minimumProfile,payroll:{season:2,minimum_salary:1050000,total:211000000,cap:210000000,floor:168000000,cap_space:-1000000,over_cap:1000000,below_floor:0,floor_enforced:false}});
 p.w.renderCuts();p.w.updateOffseasonActions();
 assert.match(q(p,'#payroll-status').textContent,/\$1.00M over cap/);
 assert.equal(q(p,'#next-season').hidden,true);assert.equal(q(p,'#next-season').disabled,true);
 assert.match(q(p,'#cut-count').textContent,/Clear \$1.00M in cap space/);
 const capRelease=q(p,'#roster-groups [data-position="K"] [data-drop-id]');
 assert.equal(capRelease.disabled,false);capRelease.click();assert.equal(q(p,'#cut-confirmation').hidden,false);
 assert.match(q(p,'#cut-confirm-text').textContent,/weak \$1.05M replacement/);q(p,'#cut-cancel').click();
 assert.equal(raw(p),minimumCheckpoint,'Previewing a cap release does not alter the saved career');
 p.w.renderTeamProfile(minimumProfile);p.w.renderCuts();p.w.updateOffseasonActions();
 assert.equal(q(p,'#next-season').disabled,false);
 const atMinimum=save(p);p.dom.window.close();p=await restore(atMinimum);
 q(p,'#view-roster').click();q(p,'#roster-ratings-button').click();
 assert.ok([...p.d.querySelectorAll('#roster-groups [data-drop-id]')].every(button=>button.disabled));

 const kickerDrop=q(p,'#roster-groups [data-position="K"] [data-drop-id]');
 if(p.d.querySelectorAll('#roster-groups [data-position="K"] .roster-player').length===1)assert.equal(kickerDrop.disabled,true);
 q(p,'#next-season').click();await until(()=>save(p).season===2);
 assert.equal(q(p,'#career-welcome').hidden,true);assert.equal(save(p).welcomeDismissed,true);assert.equal(save(p).week,0);assert.equal(save(p).careerStartWeek,17);assert.deepEqual(save(p).history[0].gmRecord,JSON.parse(JSON.stringify(managed)));
 for(const k of ['wins','losses','ties'])assert.equal(save(p).history[0][k],full[k]);assert.equal(q(p,'#gm-regular').textContent,record(managed));assert.equal(q(p,'#career-start-note').hidden,true);assert.equal(q(p,'#gm-tenure-note').hidden,false);assert.match(q(p,'#owner-feedback').textContent,/first full contract season/);
 assert.match(q(p,'#contract-status').textContent,/4 years remaining.*Season 5/);assert.equal(q(p,'#simulate-button').textContent,'Simulate Week 1');assert.equal(p.d.querySelectorAll('#schedule .completed').length,0);assert.match(q(p,'#season-history-rows').textContent,/\(team /);
 assert.equal(save(p).lineupRules,19);assert.equal(p.d.querySelectorAll('#roster-groups .roster-player').length,35);
 for(const row of p.d.querySelectorAll('#roster-groups .roster-player')){
  if(originalPay.has(row.dataset.playerId))assert.ok(row.querySelector('.salary-cell').textContent.startsWith(`$${(originalPay.get(row.dataset.playerId)/1000000).toFixed(2)}M/yr`),'Development never reprices an existing deal');
 }
 assert.match(q(p,'#payroll-status').textContent,/Season 2 payroll.*\$210.00M cap/);
 assert.ok([...p.d.querySelectorAll('#roster-groups .salary-cell')].every(cell=>!/Provisional/.test(cell.textContent)));
 const yearTwo=save(p);p.dom.window.close();p=await restore(yearTwo);assert.equal(q(p,'#gm-regular').textContent,record(managed));assert.equal(q(p,'#simulate-button').textContent,'Simulate Week 1');
 q(p,'#simulate-button').click();await until(()=>save(p).week===1&&!q(p,'#simulate-button').disabled);const total={...managed};for(const k of ['wins','losses','ties'])total[k]+=p.state.lastWeek.record[k];assert.equal(q(p,'#gm-regular').textContent,record(total));p.dom.window.close();
 // Exercise the second draft and the 39→38 UI boundary.
 const largerCheckpoint={...yearTwo,contracts:false,week:17,playoffRound:4,draftChoices:null,dropped:[]};
 p=await restore(largerCheckpoint);q(p,'#draft-button').click();await until(()=>Array.isArray(save(p).draftChoices));
 q(p,'#auto-draft').click();await until(()=>save(p).draftChoices.length===6);
 assert.equal(q(p,'#training-camp-button').hidden,false);assert.equal(q(p,'#manage-roster').hidden,true);assert.equal(q(p,'#next-season').hidden,true);assert.equal(p.d.querySelectorAll('#roster-groups [data-drop-id]').length,0);
 const beforeCamp=raw(p);p.state.failCamp=true;q(p,'#training-camp-button').click();await until(()=>!q(p,'#error').hidden&&!q(p,'#training-camp-button').disabled);
 assert.equal(raw(p),beforeCamp);assert.match(q(p,'#error').textContent,/temporarily unavailable/);p.state.failCamp=false;
 const campCalls=p.state.campCalls;q(p,'#training-camp-button').click();q(p,'#training-camp-button').click();assert.equal(p.state.campCalls,campCalls+1);
 await until(()=>save(p).trainingCamp===true);assert.equal(q(p,'#training-camp-button').hidden,true);assert.equal(q(p,'#training-camp-status').hidden,false);assert.equal(save(p).season,2);assert.equal(save(p).week,17);
 assert.match(q(p,'#training-camp-status').textContent,/Season 3 development complete/);assert.equal(q(p,'#development-dialog').open,true);q(p,'#development-close').click();
 const campSnapshot=[...p.d.querySelectorAll('#roster-groups .roster-player')].map(row=>[row.dataset.playerId,row.textContent]);
 const campCheckpoint=save(p);p.dom.window.close();p=await restore(campCheckpoint);
 assert.equal(raw(p),JSON.stringify(campCheckpoint));assert.equal(q(p,'#training-camp-status').hidden,false);assert.deepEqual([...p.d.querySelectorAll('#roster-groups .roster-player')].map(row=>[row.dataset.playerId,row.textContent]),campSnapshot);assert.equal(q(p,'#development-dialog').open,false);
 q(p,'#manage-roster').click();
 assert.ok(p.d.querySelectorAll('#roster-groups .roster-player').length>=39);
 while(p.d.querySelectorAll('#roster-groups .roster-player').length>39){
  const count=save(p).dropped.length;q(p,'#roster-groups [data-drop-id]:not([disabled])').click();q(p,'#cut-confirm').click();await until(()=>save(p).dropped.length===count+1);
 }
 assert.match(q(p,'#cut-count').textContent,/39\/38 players.*Drop 1 more player to continue/);assert.equal(q(p,'#next-season').hidden,true);
 const oversized=save(p);p.dom.window.close();p=await restore(oversized);
 assert.equal(p.d.querySelectorAll('#roster-groups .roster-player').length,39);
 const blocked=raw(p);q(p,'#next-season').disabled=false;q(p,'#next-season').click();assert.equal(raw(p),blocked);
 q(p,'#manage-roster').click();const dropCount=save(p).dropped.length;
 q(p,'#roster-groups [data-drop-id]:not([disabled])').click();q(p,'#cut-confirm').click();await until(()=>save(p).dropped.length===dropCount+1);
 assert.match(q(p,'#cut-count').textContent,/38\/38 players.*No more cuts needed/);assert.equal(q(p,'#next-season').hidden,false);assert.equal(q(p,'#next-season').disabled,false);
 const legalMaximum=save(p);p.dom.window.close();p=await restore(legalMaximum);
 q(p,'#next-season').click();await until(()=>save(p).season===3);
 assert.equal(p.d.querySelectorAll('#roster-groups .roster-player').length,38);p.dom.window.close();
 // Rules 12 saves without a started draft adopt the new decision limits on resume.
 const beforeRange={...inherited,version:22,lineupRules:12,welcomeDismissed:true};
 p=await restore(beforeRange);assert.equal(raw(p),JSON.stringify(beforeRange));
 assert.match(q(p,'#roster-limit-note').textContent,/31–38/);
 q(p,'#simulate-button').click();await until(()=>save(p).week===17);
 assert.equal(save(p).lineupRules,13);p.dom.window.close();
 // Existing 31-player careers keep their completed season, then upgrade at rollover.
 const compactLegacy={...inherited,version:21,lineupRules:11,welcomeDismissed:true};
 p=await restore(compactLegacy);assert.equal(save(p).lineupRules,11);
 assert.equal(p.d.querySelectorAll('#roster-groups .roster-player').length,31);
 q(p,'#simulate-button').click();await until(()=>save(p).week===17);
 q(p,'#playoffs-start').click();await until(()=>save(p).playoffRound===0);
 for(let round=1;round<=4;round++){q(p,'#playoff-simulate').click();await until(()=>save(p).playoffRound===round)}
 await finishOffseason(p,until);q(p,'#next-season').click();await until(()=>save(p).season===2);
 assert.equal(save(p).lineupRules,19);assert.equal(save(p).career[0].lineup_rules,11);
 const upgraded=save(p);p.dom.window.close();p=await restore(upgraded);
 assert.equal(save(p).lineupRules,19);q(p,'#simulate-button').click();await until(()=>save(p).week===1&&!q(p,'#simulate-button').disabled);
 const rivals=p.state.lastWeek.standings.groups.flatMap(g=>g.teams).filter(r=>r.team.id!=='seattle');
 assert.equal(rivals.reduce((sum,r)=>sum+r.ratings.offense,0)/rivals.length,75);
 assert.equal(rivals.reduce((sum,r)=>sum+r.ratings.defense,0)/rivals.length,75);p.dom.window.close();
 // Legacy careers keep Week 1 and their original four-year deadline after autosave.
 const old={version:13,contracts:true,lineupChanges:[],teamId:'seattle',runSeed:1234,season:1,week:0,playoffRound:null,lineupRules:6,developmentStart:1,rebuildTeam:'seattle',priorStandings:{},history:[],career:[],draftChoices:null,dropped:[]};
 p=await restore(old);assert.equal(p.d.querySelectorAll('#roster-groups .roster-player').length,38);assert.match(q(p,'#roster-limit-note').textContent,/maximum: 38/);assert.equal(q(p,'#simulate-button').textContent,'Simulate Week 1');assert.match(q(p,'#contract-status').textContent,/Season 4/);assert.equal(q(p,'#career-start-note').hidden,true);
 q(p,'#simulate-button').click();await until(()=>save(p).week===1&&!q(p,'#simulate-button').disabled);assert.equal(save(p).careerStartWeek,1);assert.equal(save(p).version,29);
 const oldSaved=raw(p);p.state.failStart=true;q(p,'#change-team-button').click();q(p,'#team-select').value='seattle';q(p,'#team-form').dispatchEvent(new p.w.Event('submit',{cancelable:true}));await until(()=>!q(p,'#error').hidden);assert.equal(raw(p),oldSaved);assert.equal(save(p).careerStartWeek,1);p.dom.window.close();
 for(const input of [{...inherited,week:0},{...inherited,careerStartWeek:16},{...yearTwo,history:yearTwo.history.map(({gmRecord,...entry})=>entry)}]){
  p=page(input);await until(()=>/could not be read/.test(q(p,'#save-status').textContent));assert.equal(raw(p),JSON.stringify(input));p.dom.window.close();
 }
 // Upgrade a salary-era save without autosaving; unfinished drafts keep their old rules.
 for(const oldRules of [15,16])for(const checkpoint of [inherited,atMinimum]){
  const {trainingCamp,...legacyCheckpoint}=checkpoint;
  const oldSalary={...legacyCheckpoint,version:oldRules===15?25:26,lineupRules:oldRules};
  p=await restore(oldSalary);assert.equal(raw(p),JSON.stringify(oldSalary));
  assert.equal(q(p,'#payroll-status').hidden,oldRules===15&&checkpoint.draftChoices!==null);
  assert.equal(q(p,'#salary-growth-guide').hidden,checkpoint.draftChoices!==null);
  if(checkpoint.draftChoices===null){q(p,'#simulate-button').click();await until(()=>save(p).week===17);assert.equal(save(p).lineupRules,19);}
  p.dom.window.close();
 }
 // A previously signed rules-18 class stays signed during camp and after upgrading at rollover.
 const signedCamp={...atMinimum,version:28,lineupRules:18};
 p=await restore(signedCamp);assert.equal(raw(p),JSON.stringify(signedCamp));
 assert.ok([...p.d.querySelectorAll('#roster-groups .salary-cell')].every(cell=>!/Provisional/.test(cell.textContent)));
 assert.equal(q(p,'#training-camp-status').hidden,false);q(p,'#next-season').click();await until(()=>save(p).season===2);
 assert.equal(save(p).lineupRules,19);assert.equal(save(p).career[0].lineup_rules,18);
 assert.ok([...p.d.querySelectorAll('#roster-groups .salary-cell')].every(cell=>!/Provisional/.test(cell.textContent)));p.dom.window.close();
 console.log('Late-start UI checks passed: inherited 16 games, one managed final game, GM/team record separation, four full contract seasons without intro extensions, reloads, automatic starters, mandatory draft/cuts, full Season 2, archived GM record, legacy rules, failed replacement, and invalid-save preservation.');
}
(async()=>{const server=spawn(process.env.PYTHON||'python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8779'],{cwd:root,stdio:['ignore','pipe','pipe']});let logs='';server.stdout.on('data',d=>logs+=d);server.stderr.on('data',d=>logs+=d);try{for(let i=0;;i++){if(server.exitCode!==null)throw new Error(logs);try{if((await fetch(base+'/api/teams')).ok)break}catch{}if(i===100)throw new Error(logs);await new Promise(r=>setTimeout(r,100))}await checks()}finally{server.kill()}})().catch(e=>{console.error(e);process.exitCode=1});
