const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {spawn}=require('node:child_process'),{JSDOM}=require('jsdom');
const {finishOffseason}=require('./ui_offseason_helpers.cjs');
const root=path.resolve(__dirname,'..'),base='http://127.0.0.1:8778',key='arcade-league-save';
const html=fs.readFileSync(path.join(root,'app/static/index.html'),'utf8'),script=fs.readFileSync(path.join(root,'app/static/app.js'),'utf8');
async function until(check){for(let i=0;i<2000;i++){if(check())return;await new Promise(r=>setTimeout(r,10))}throw new Error('Starter UI state timed out')}
const q=(p,s)=>p.d.querySelector(s),raw=p=>p.w.localStorage.getItem(key),save=p=>JSON.parse(raw(p));
const checkpoint={version:12,contracts:false,teamId:'seattle',runSeed:1234,season:1,week:0,playoffRound:null,lineupRules:6,developmentStart:1,rebuildTeam:'seattle',priorStandings:{},history:[],career:[],draftChoices:null,dropped:[]};
function page(input){
 const dom=new JSDOM(html,{url:base,runScripts:'outside-only'}),w=dom.window,d=w.document,state={requests:[],fail:false,hold:false,holdWeek:false};
 w.localStorage.setItem(key,JSON.stringify(input));w.HTMLElement.prototype.scrollIntoView=()=>{};
 w.HTMLDialogElement.prototype.close=function(){this.open=false};w.HTMLDialogElement.prototype.showModal=function(){this.open=true};
 w.fetch=async(url,init)=>{
  const body=init?JSON.parse(init.body):null;state.requests.push({url,body});
  if(body?.action==='profile'&&body.lineup_changes?.length){
   if(state.hold)await new Promise(resolve=>state.release=resolve);
   if(state.fail)return {ok:false,json:async()=>({detail:'Injected lineup failure'})};
  }
  if(state.holdPlayoff&&body?.action==='playoffs')await new Promise(resolve=>state.releasePlayoff=resolve);
  if(state.holdWeek&&(body?.action==='week'||url.startsWith('/api/season/')))await new Promise(resolve=>state.releaseWeek=resolve);
  return fetch(new URL(url,base),init);
 };
 w.eval(script);return {dom,w,d,state};
}
async function restore(input){const p=page(input);await until(()=>/restored|could not/.test(q(p,'#save-status').textContent));assert.match(q(p,'#save-status').textContent,/restored/);return p}
const position=(p,pos)=>[...p.d.querySelectorAll(`#roster-groups [data-position="${pos}"] .roster-player`)];
const starter=(p,pos)=>position(p,pos).filter(row=>row.dataset.starter==='true').map(row=>row.dataset.playerId);
function choose(p,pos,id,slot=0){p.d.querySelectorAll(`#starter-fields select[data-starter-position="${pos}"]`)[slot].value=id}
async function commit(p){q(p,'#starter-form').dispatchEvent(new p.w.Event('submit',{cancelable:true}));await until(()=>/saved for|best available|unchanged|different player/i.test(q(p,'#starter-status').textContent)&&!q(p,'#save-starters').disabled)}
async function checks(){
 let p=await restore(checkpoint);q(p,'#view-roster').click();q(p,'#starter-editor').open=true;
 assert.equal(p.d.querySelectorAll('#starter-fields select').length,22);assert.equal(q(p,'#save-starters').disabled,false);
 const original=starter(p,'QB')[0],reserve=position(p,'QB').find(row=>row.dataset.starter==='false').dataset.playerId;
 const wr=p.d.querySelectorAll('#starter-fields select[data-starter-position="WR"]');wr[1].value=wr[0].value;
 const untouched=raw(p),count=p.state.requests.length;await commit(p);assert.match(q(p,'#starter-status').textContent,/different player/);assert.equal(raw(p),untouched);assert.equal(p.state.requests.length,count);
 q(p,'#cancel-starters').click();assert.equal(q(p,'#starter-editor').open,false);q(p,'#starter-editor').open=true;
 choose(p,'QB',reserve);const beforeRating=Number(q(p,'#offense-rating').textContent);p.state.fail=true;await commit(p);
 assert.equal(raw(p),untouched);assert.deepEqual(starter(p,'QB'),[original]);assert.match(q(p,'#starter-status').textContent,/unchanged/);
 p.state.fail=false;p.state.hold=true;q(p,'#starter-form').dispatchEvent(new p.w.Event('submit',{cancelable:true}));await until(()=>Boolean(p.state.release));
 assert.equal(q(p,'#simulate-button').disabled,true);assert.equal(q(p,'#simulate-season').disabled,true);assert.equal(q(p,'#change-team-button').disabled,true);
 const calls=p.state.requests.length;q(p,'#save-starters').disabled=false;q(p,'#starter-form').dispatchEvent(new p.w.Event('submit',{cancelable:true}));q(p,'#simulate-button').disabled=false;q(p,'#simulate-button').click();assert.equal(p.state.requests.length,calls);
 p.state.hold=false;p.state.release();await until(()=>/saved for/.test(q(p,'#starter-status').textContent)&&!q(p,'#save-starters').disabled);
 assert.equal(save(p).version,16);assert.equal(save(p).lineupChanges[0].week,1);assert.equal(save(p).lineupChanges[0].starters.length,22);assert.deepEqual(starter(p,'QB'),[reserve]);assert.ok(Number(q(p,'#offense-rating').textContent)<=beforeRating);
 const selected=raw(p);p.dom.window.close();p=await restore(JSON.parse(selected));assert.deepEqual(starter(p,'QB'),[reserve]);assert.equal(raw(p),selected);
 q(p,'#simulate-button').click();await until(()=>save(p).week===1&&!q(p,'#simulate-button').disabled);
 const weekOne=raw(p),box=q(p,'#player-stats').textContent,record=q(p,'#season-record').textContent;
 const other=[...p.d.querySelectorAll('.team-roster-link')].find(button=>button.dataset.teamId!=='seattle');other.click();await until(()=>/38 players/.test(q(p,'#scout-status').textContent));
 assert.equal(q(p,'#team-roster-dialog').querySelector('#starter-editor'),null);assert.equal(raw(p),weekOne);q(p,'#scout-close').click();
 choose(p,'QB',original);await commit(p);assert.equal(save(p).lineupChanges.length,2);assert.equal(save(p).lineupChanges[1].week,2);assert.equal(q(p,'#player-stats').textContent,box);assert.equal(q(p,'#season-record').textContent,record);
 const changed=raw(p);p.dom.window.close();p=await restore(JSON.parse(changed));assert.equal(q(p,'#player-stats').textContent,box);assert.equal(q(p,'#season-record').textContent,record);
 // Auto reset is another future-effective event, not deletion of historical decisions.
 q(p,'#auto-starters').click();await until(()=>/Best available/.test(q(p,'#starter-status').textContent));assert.equal(save(p).lineupChanges.length,2);assert.deepEqual(save(p).lineupChanges[1].starters,[]);assert.deepEqual(starter(p,'QB'),[original]);
 p.state.holdWeek=true;q(p,'#simulate-button').click();await until(()=>Boolean(p.state.releaseWeek));assert.equal(q(p,'#save-starters').disabled,true);p.state.releaseWeek();p.state.holdWeek=false;await until(()=>save(p).week===2&&!q(p,'#simulate-button').disabled);p.dom.window.close();
 // Complete the manual-lineup season and real draft/cuts; retained manual choices carry to season two.
 p=await restore(JSON.parse(selected));q(p,'#simulate-season').click();await until(()=>save(p).week===17&&q(p,'#stop-season').hidden);
 assert.equal(q(p,'#save-starters').disabled,true,'Eliminated/nonqualified teams cannot edit offseason lineups');
 q(p,'#playoffs-start').click();await until(()=>save(p).playoffRound===0);
 for(let round=1;round<=4;round++){q(p,'#playoff-simulate').click();await until(()=>save(p).playoffRound===round)}
 assert.equal(q(p,'#save-starters').disabled,true);await finishOffseason(p,until);
 const preferred=save(p).lineupChanges.at(-1).starters,retained=new Set([...p.d.querySelectorAll('#roster-groups .roster-player')].map(r=>r.dataset.playerId));
 const oldEvents=save(p).lineupChanges;q(p,'#next-season').click();await until(()=>save(p).season===2);
 assert.deepEqual(save(p).career[0].lineup_changes,oldEvents);assert.equal(save(p).lineupChanges[0].week,1);
 for(const id of preferred.filter(id=>retained.has(id)))assert.ok(save(p).lineupChanges[0].starters.includes(id));
 const yearTwo=raw(p),depths=[...p.d.querySelectorAll('#roster-groups .is-starter')].map(r=>r.dataset.playerId);p.dom.window.close();p=await restore(JSON.parse(yearTwo));assert.deepEqual([...p.d.querySelectorAll('#roster-groups .is-starter')].map(r=>r.dataset.playerId),depths);
 q(p,'#change-team-button').click();q(p,'#team-select').value='seattle';q(p,'#team-form').dispatchEvent(new p.w.Event('submit',{cancelable:true}));await until(()=>save(p).season===1&&save(p).week===16);
 assert.deepEqual(save(p).lineupChanges,[]);assert.equal(save(p).career.length,0);p.dom.window.close();
 // A qualified team can choose its playoff starter without reseeding or replaying completed rounds.
 const bracket=await (await fetch(base+'/api/playoffs/seattle/round/0?run_seed=1234')).json();const wildcard=bracket.field.find(team=>!team.bye).team.id;
 p=await restore({version:1,teamId:wildcard,runSeed:1234,season:1,week:17,playoffRound:0});assert.equal(q(p,'#save-starters').disabled,false);
 const playoffQB=position(p,'QB').find(row=>row.dataset.starter==='false').dataset.playerId;choose(p,'QB',playoffQB);await commit(p);assert.equal(save(p).lineupChanges[0].week,18);
 p.state.holdPlayoff=true;q(p,'#playoff-simulate').click();await until(()=>Boolean(p.state.releasePlayoff));assert.equal(q(p,'#save-starters').disabled,true);
 const roundCalls=p.state.requests.length;q(p,'#starter-form').dispatchEvent(new p.w.Event('submit',{cancelable:true}));assert.equal(p.state.requests.length,roundCalls);
 p.state.holdPlayoff=false;p.state.releasePlayoff();await until(()=>save(p).playoffRound===1);assert.equal(save(p).lineupChanges[0].week,18);
 const roundText=q(p,'#playoff-bracket').textContent,roundSave=save(p);p.dom.window.close();p=await restore(roundSave);assert.equal(q(p,'#playoff-bracket').textContent,roundText);p.dom.window.close();
 // Corrupt or foreign choices must fail safely without replacing the checkpoint.
 for(const bad of [{week:1,starters:['miami-qb1',...JSON.parse(selected).lineupChanges[0].starters.slice(1)]},{week:22,starters:[]}]){
  const input={...JSON.parse(selected),lineupChanges:[bad]};p=page(input);await until(()=>/could not/.test(q(p,'#save-status').textContent));assert.equal(raw(p),JSON.stringify(input));assert.equal(q(p,'#schedule-section').hidden,true);p.dom.window.close();
 }
 console.log('Starter UI checks passed: 22 position slots, duplicate validation, cancel, failed/retried save, busy guards, QB promotion/rating update, reload, completed-game preservation, future-effective auto reset, weekly lock, draft/cuts/season rollover with retained preferences, and corrupt-save protection.');
}
(async()=>{const server=spawn(process.env.PYTHON||'python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8778'],{cwd:root,stdio:['ignore','pipe','pipe']});let logs='';server.stdout.on('data',d=>logs+=d);server.stderr.on('data',d=>logs+=d);try{for(let i=0;;i++){if(server.exitCode!==null)throw new Error(logs);try{if((await fetch(base+'/api/teams')).ok)break}catch{}if(i===100)throw new Error(logs);await new Promise(r=>setTimeout(r,100))}await checks()}finally{server.kill()}})().catch(e=>{console.error(e);process.exitCode=1});
