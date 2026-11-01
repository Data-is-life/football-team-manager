const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {spawn}=require('node:child_process'),{JSDOM}=require('jsdom');
const {finishOffseason}=require('./ui_offseason_helpers.cjs');
const root=path.resolve(__dirname,'..'),base='http://127.0.0.1:8779',key='arcade-league-save';
const html=fs.readFileSync(path.join(root,'app/static/index.html'),'utf8'),script=fs.readFileSync(path.join(root,'app/static/app.js'),'utf8');
async function until(check){for(let i=0;i<2000;i++){if(check())return;await new Promise(r=>setTimeout(r,10))}throw new Error('Late-start UI state timed out')}
const q=(p,s)=>p.d.querySelector(s),raw=p=>p.w.localStorage.getItem(key),save=p=>JSON.parse(raw(p));
function page(checkpoint){
 const dom=new JSDOM(html,{url:base,runScripts:'outside-only'}),w=dom.window,d=w.document,state={weeks:[],failStart:false};
 if(checkpoint)w.localStorage.setItem(key,JSON.stringify(checkpoint));w.HTMLElement.prototype.scrollIntoView=()=>{};
 w.HTMLDialogElement.prototype.close=function(){this.open=false};w.HTMLDialogElement.prototype.showModal=function(){this.open=true};
 Object.defineProperty(w.crypto,'getRandomValues',{value:a=>{a[0]=5678;return a}});
 w.fetch=async(url,init)=>{
  const body=init?JSON.parse(init.body):null;
  const week=body?.action==='week'?body.week:Number(/\/api\/season\/[^/]+\/week\/(\d+)/.exec(url)?.[1]);
  if(week)state.weeks.push(week);
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
 assert.equal(save(p).version,18);assert.equal(q(p,'#development-recap-button').hidden,true);assert.equal(q(p,'#development-dialog').open,false);assert.equal(q(p,'#development-recap-rows').children.length,0);assert.equal(save(p).careerStartWeek,17);assert.deepEqual(p.state.weeks,[16]);assert.equal(q(p,'#simulate-button').textContent,'Simulate Week 17');
 assert.equal(p.d.querySelectorAll('#schedule .completed').length,16);assert.equal(q(p,'#gm-regular').textContent,'0–0–0');assert.equal(q(p,'#gm-appearances').textContent,'0');assert.equal(q(p,'#career-start-note').hidden,false);assert.equal(q(p,'#gm-tenure-note').hidden,false);
 assert.match(q(p,'#result-week').textContent,/Before your hiring/);assert.match(q(p,'#owner-feedback').textContent,/four-year contract covering Seasons 2–5/);assert.match(q(p,'#contract-status').textContent,/4 years remaining.*Season 5/);
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
 // Pick a starter before the only managed regular-season game; inherited games stay unchanged.
 const qb=p.d.querySelectorAll('#starter-fields select[data-starter-position="QB"]')[0];qb.value=qb.options[1].value;
 q(p,'#starter-form').dispatchEvent(new p.w.Event('submit',{cancelable:true}));await until(()=>/saved for/.test(q(p,'#starter-status').textContent));assert.equal(save(p).lineupChanges[0].week,17);
 p.state.weeks=[];q(p,'#simulate-season').click();await until(()=>save(p).week===17&&q(p,'#stop-season').hidden);assert.deepEqual(p.state.weeks,[17]);assert.equal(save(p).playoffRound,null);assert.equal(save(p).draftChoices,null);
 const managed=p.w.managedRecord(p.state.lastWeek);assert.equal(managed.wins+managed.losses+managed.ties,1);assert.equal(q(p,'#gm-regular').textContent,record(managed));assert.match(q(p,'#contract-status').textContent,/4 years remaining.*Season 5/);
 // Opponent records update with Week 17, but inherited score results cannot change.
 for(let i=0;i<16;i++){assert.ok(p.d.querySelectorAll('#schedule .game-final')[i].textContent.includes(p.state.lastWeek.game_results[i].team_score+'–'+p.state.lastWeek.game_results[i].opponent_score))}
 const full=p.state.lastWeek.record,completed=save(p);p.dom.window.close();p=await restore(completed);assert.equal(q(p,'#gm-regular').textContent,record(managed));
 q(p,'#playoffs-start').click();await until(()=>save(p).playoffRound===0);for(let round=1;round<=4;round++){q(p,'#playoff-simulate').click();await until(()=>save(p).playoffRound===round)}
 assert.equal(q(p,'#next-season').hidden,true);await finishOffseason(p,until);q(p,'#next-season').click();await until(()=>save(p).season===2);
 assert.equal(save(p).week,0);assert.equal(save(p).careerStartWeek,17);assert.deepEqual(save(p).history[0].gmRecord,JSON.parse(JSON.stringify(managed)));
 for(const k of ['wins','losses','ties'])assert.equal(save(p).history[0][k],full[k]);assert.equal(q(p,'#gm-regular').textContent,record(managed));assert.equal(q(p,'#career-start-note').hidden,true);assert.equal(q(p,'#gm-tenure-note').hidden,false);assert.match(q(p,'#owner-feedback').textContent,/first full contract season/);
 assert.match(q(p,'#contract-status').textContent,/4 years remaining.*Season 5/);assert.equal(q(p,'#simulate-button').textContent,'Simulate Week 1');assert.equal(p.d.querySelectorAll('#schedule .completed').length,0);assert.match(q(p,'#season-history-rows').textContent,/\(team /);
 const yearTwo=save(p);p.dom.window.close();p=await restore(yearTwo);assert.equal(q(p,'#gm-regular').textContent,record(managed));assert.equal(q(p,'#simulate-button').textContent,'Simulate Week 1');
 q(p,'#simulate-button').click();await until(()=>save(p).week===1&&!q(p,'#simulate-button').disabled);const total={...managed};for(const k of ['wins','losses','ties'])total[k]+=p.state.lastWeek.record[k];assert.equal(q(p,'#gm-regular').textContent,record(total));p.dom.window.close();
 // Legacy careers keep Week 1 and their original four-year deadline after autosave.
 const old={version:13,contracts:true,lineupChanges:[],teamId:'seattle',runSeed:1234,season:1,week:0,playoffRound:null,lineupRules:6,developmentStart:1,rebuildTeam:'seattle',priorStandings:{},history:[],career:[],draftChoices:null,dropped:[]};
 p=await restore(old);assert.equal(q(p,'#simulate-button').textContent,'Simulate Week 1');assert.match(q(p,'#contract-status').textContent,/Season 4/);assert.equal(q(p,'#career-start-note').hidden,true);
 q(p,'#simulate-button').click();await until(()=>save(p).week===1&&!q(p,'#simulate-button').disabled);assert.equal(save(p).careerStartWeek,1);assert.equal(save(p).version,18);
 const oldSaved=raw(p);p.state.failStart=true;q(p,'#change-team-button').click();q(p,'#team-select').value='seattle';q(p,'#team-form').dispatchEvent(new p.w.Event('submit',{cancelable:true}));await until(()=>!q(p,'#error').hidden);assert.equal(raw(p),oldSaved);assert.equal(save(p).careerStartWeek,1);p.dom.window.close();
 for(const input of [{...inherited,week:0},{...inherited,careerStartWeek:16},{...yearTwo,history:yearTwo.history.map(({gmRecord,...entry})=>entry)}]){
  p=page(input);await until(()=>/could not be read/.test(q(p,'#save-status').textContent));assert.equal(raw(p),JSON.stringify(input));p.dom.window.close();
 }
 console.log('Late-start UI checks passed: inherited 16 games, one managed final game, GM/team record separation, four full contract seasons without intro extensions, reloads, manual starters, mandatory draft/cuts, full Season 2, archived GM record, legacy rules, failed replacement, and invalid-save preservation.');
}
(async()=>{const server=spawn(process.env.PYTHON||'python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8779'],{cwd:root,stdio:['ignore','pipe','pipe']});let logs='';server.stdout.on('data',d=>logs+=d);server.stderr.on('data',d=>logs+=d);try{for(let i=0;;i++){if(server.exitCode!==null)throw new Error(logs);try{if((await fetch(base+'/api/teams')).ok)break}catch{}if(i===100)throw new Error(logs);await new Promise(r=>setTimeout(r,100))}await checks()}finally{server.kill()}})().catch(e=>{console.error(e);process.exitCode=1});
