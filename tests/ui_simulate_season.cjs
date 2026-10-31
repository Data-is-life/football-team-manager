const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {spawn}=require('node:child_process'),{JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'..'),base='http://127.0.0.1:8777',key='arcade-league-save';
const html=fs.readFileSync(path.join(root,'app/static/index.html'),'utf8'),script=fs.readFileSync(path.join(root,'app/static/app.js'),'utf8');
async function until(check){for(let i=0;i<2000;i++){if(check())return;await new Promise(r=>setTimeout(r,10))}throw new Error('Season simulation UI state timed out')}
const q=(p,s)=>p.d.querySelector(s),raw=p=>p.w.localStorage.getItem(key),save=p=>JSON.parse(raw(p));
const legacy=(week=0)=>({version:1,teamId:'seattle',runSeed:1234,season:1,week,playoffRound:null});
async function api(url){const r=await fetch(base+url);assert.equal(r.ok,true,url);return r.json()}
function page(checkpoint,options={}){
 const dom=new JSDOM(html,{url:base,runScripts:'outside-only'}),w=dom.window,d=w.document;
 const state={weeks:[],saved:[],active:0,maxActive:0,other:[],...options};
 w.localStorage.setItem(key,JSON.stringify(checkpoint));w.HTMLElement.prototype.scrollIntoView=()=>{};
 w.HTMLDialogElement.prototype.close=function(){this.open=false};w.HTMLDialogElement.prototype.showModal=function(){this.open=true};
 const write=w.Storage.prototype.setItem;w.Storage.prototype.setItem=function(k,v){if(k===key)state.saved.push(JSON.parse(v).week);return write.call(this,k,v)};
 w.fetch=async(url,init)=>{
  const parsed=new URL(url,base),body=init?JSON.parse(init.body):null;
  const week=body?.action==='week'?body.week:/\/api\/season\/[^/]+\/week\/(\d+)/.exec(parsed.pathname)?.[1];
  if(!week){state.other.push({url,body});return fetch(parsed,init)}
  const number=Number(week);state.weeks.push({week:number,body});state.maxActive=Math.max(state.maxActive,++state.active);
  try{
   if(state.holdWeek===number)await new Promise(resolve=>state.release=resolve);
   if(state.failWeek===number)return {ok:false,json:async()=>({detail:'Injected weekly failure'})};
   const response=await fetch(parsed,init),data=await response.json();
   if(state.mismatchWeek===number)data.week=number+1;
   return {ok:response.ok,json:async()=>data};
  }finally{state.active--}
 };
 w.eval(script);return {dom,w,d,state};
}
async function restore(checkpoint,options){const p=page(checkpoint,options);await until(()=>/restored|could not/.test(q(p,'#save-status').textContent));assert.match(q(p,'#save-status').textContent,/restored/);p.state.weeks=[];p.state.other=[];p.state.saved=[];return p}
async function finished(p,week=17){await until(()=>save(p).week===week&&q(p,'#stop-season').hidden)}
function snapshot(p){return ['#season-record','#schedule','#roster-groups','#standings-section','#playoff-section','#gm-regular','#qualification-status'].map(id=>q(p,id).textContent)}
async function checks(){
 let p=await restore(legacy());q(p,'#view-roster').click();q(p,'#simulate-season').click();q(p,'#simulate-season').click();q(p,'#simulate-button').click();
 await finished(p);assert.deepEqual(p.state.weeks.map(r=>r.week),Array.from({length:17},(_,i)=>i+1));assert.deepEqual(p.state.saved,Array.from({length:17},(_,i)=>i+1));assert.equal(p.state.maxActive,1);
 assert.equal(q(p,'#view-roster').getAttribute('aria-selected'),'true');assert.equal(q(p,'#simulate-season').disabled,true);assert.equal(q(p,'#simulate-button').disabled,true);assert.equal(q(p,'#simulate-button').hidden,true);assert.equal(q(p,'#simulate-season').hidden,true);
 assert.equal(save(p).playoffRound,null);assert.equal(save(p).draftChoices,null);assert.equal(save(p).season,1);assert.equal(q(p,'#next-season').hidden,true);assert.equal(q(p,'#playoffs-start').hidden,false);assert.equal(p.state.other.length,0,'Batch must not reveal/simulate postseason, draft, or new season');
 const whole=snapshot(p);p.dom.window.close();p=await restore(legacy());
 for(let week=1;week<=17;week++){q(p,'#simulate-button').click();await until(()=>save(p).week===week&&!q(p,'#simulate-button').textContent.includes('Simulating'))}
 assert.deepEqual(snapshot(p),whole,'Whole-season and manual-week results/stats/standings must match');p.dom.window.close();
 p=await restore(legacy(8));q(p,'#simulate-season').click();await finished(p);assert.deepEqual(p.state.weeks.map(r=>r.week),[9,10,11,12,13,14,15,16,17]);p.dom.window.close();
 // Stop waits for the current response/save; forced duplicate actions cannot create a second loop or replace the career.
 p=await restore(legacy(),{holdWeek:3});q(p,'#simulate-season').click();await until(()=>Boolean(p.state.release));assert.equal(save(p).week,2);assert.equal(q(p,'#change-team-button').disabled,true);assert.equal(q(p,'#simulate-button').hidden,true);assert.equal(q(p,'#simulate-season').hidden,true);assert.equal(q(p,'#stop-season').hidden,false);
 q(p,'#simulate-season').disabled=false;q(p,'#simulate-season').click();q(p,'#simulate-button').disabled=false;q(p,'#simulate-button').click();
 q(p,'#change-team-button').disabled=false;q(p,'#change-team-button').click();assert.equal(q(p,'#franchise-setup').hidden,true);
 q(p,'#team-select').value='miami';q(p,'#team-form').dispatchEvent(new p.w.Event('submit',{cancelable:true}));assert.equal(p.state.other.length,0);
 q(p,'#stop-season').click();assert.match(q(p,'#season-simulation-status').textContent,/Stopping/);p.state.release();await finished(p,3);
 assert.deepEqual(p.state.weeks.map(r=>r.week),[1,2,3]);assert.deepEqual(p.state.saved,[1,2,3]);assert.equal(q(p,'#simulate-season').disabled,false);assert.equal(q(p,'#simulate-season').hidden,false);assert.equal(q(p,'#simulate-button').hidden,false);assert.equal(q(p,'#change-team-button').disabled,false);
 const stopped=save(p);p.dom.window.close();p=await restore(stopped);assert.equal(p.state.weeks.length,0,'Reload must not resume a batch automatically');assert.equal(q(p,'#stop-season').hidden,true);assert.equal(q(p,'#season-simulation-status').textContent,'');
 q(p,'#simulate-season').click();await finished(p);assert.equal(p.state.weeks[0].week,4);p.dom.window.close();
 for(const failure of ['failWeek','mismatchWeek']){
  p=await restore(legacy(),{[failure]:4});q(p,'#simulate-season').click();await until(()=>!q(p,'#error').hidden&&q(p,'#stop-season').hidden);
  assert.equal(save(p).week,3);assert.deepEqual(p.state.saved,[1,2,3]);assert.match(q(p,'#season-simulation-status').textContent,/Week 4/);assert.equal(q(p,'#simulate-season').disabled,false);assert.equal(q(p,'#simulate-season').hidden,false);assert.equal(q(p,'#simulate-button').hidden,false);
  p.state[failure]=null;q(p,'#simulate-season').click();await finished(p);assert.deepEqual(p.state.weeks.map(r=>r.week),[1,2,3,4,...Array.from({length:14},(_,i)=>i+4)]);p.dom.window.close();
 }
 // A storage failure keeps in-page progress moving and preserves the last durable checkpoint.
 p=await restore(legacy());const checkpointBeforeQuota=raw(p);
 p.w.Storage.prototype.setItem=function(){throw new Error('Quota exceeded')};
 q(p,'#simulate-season').click();await until(()=>/Regular season complete/.test(q(p,'#season-simulation-status').textContent)&&q(p,'#stop-season').hidden);
 assert.equal(raw(p),checkpointBeforeQuota);assert.match(q(p,'#save-status').textContent,/could not be saved/);assert.equal(q(p,'#simulate-season').disabled,true);assert.equal(p.state.weeks.length,17);p.dom.window.close();
 // Career requests preserve all drafted/cut rosters and use the current season's actual context.
 const later=JSON.parse(fs.readFileSync(path.join(root,'benchmarks/year8.json'),'utf8'));p=await restore(later);q(p,'#simulate-season').click();await finished(p);
 assert.deepEqual(p.state.weeks.map(r=>r.week),[9,10,11,12,13,14,15,16,17]);
 for(const r of p.state.weeks){assert.equal(r.body.action,'week');assert.equal(r.body.season,8);assert.equal(r.body.lineup_rules,6);assert.deepEqual(r.body.career,later.career.map(step=>({...step,draft_rounds:4})))}
 assert.equal(save(p).season,8);assert.equal(save(p).playoffRound,null);assert.deepEqual(save(p).career,later.career.map(step=>({...step,draft_rounds:4})));p.dom.window.close();
 // New contract careers still show qualification/owner feedback; fourth-year failure ends play.
 const modern={version:12,contracts:true,teamId:'seattle',runSeed:1234,season:1,week:16,playoffRound:null,lineupRules:6,developmentStart:1,rebuildTeam:'seattle',priorStandings:{},history:[],career:[],draftChoices:null,dropped:[]};
 p=await restore(modern);q(p,'#simulate-season').click();await finished(p);assert.equal(q(p,'#qualification-status').hidden,false);assert.ok(q(p,'#owner-feedback').textContent);p.dom.window.close();
 const regular=await api('/api/season/seattle/week/17?season=4&run_seed=1234');const ranks=Object.fromEntries(regular.standings.groups.flatMap(g=>g.teams).map(r=>[r.team.id,r.rank]));
 const final=await api(`/api/season/seattle/week/17?season=4&run_seed=1234&prior_standings=${encodeURIComponent(JSON.stringify(ranks))}`);
 const id=final.standings.groups.flatMap(g=>g.teams).find(row=>!final.standings.playoff_race.some(f=>f.team.id===row.team.id)).team.id;
 const dead={...modern,teamId:id,season:4,lineupRules:1,developmentStart:null,rebuildTeam:null,priorStandings:ranks,history:[1,2,3].map(season=>({season,wins:6,losses:11,ties:0,championId:'seattle',playoffFinish:'Missed playoffs'}))};
 p=await restore(dead);q(p,'#simulate-season').click();await finished(p);assert.match(q(p,'#contract-status').textContent,/Fired/);assert.match(q(p,'#season-simulation-status').textContent,/career has ended/);assert.equal(q(p,'#playoffs-start').hidden,true);assert.equal(q(p,'#simulate-season').disabled,true);
 const count=p.state.weeks.length;q(p,'#simulate-season').disabled=false;q(p,'#simulate-season').click();assert.equal(p.state.weeks.length,count);p.dom.window.close();
 console.log('Season simulation UI checks passed: 17 sequential weekly saves, manual-result parity, partial saves, safe stop/reload/resume, duplicate and team-change guards, failed/mismatched-response recovery, later-season roster context, postseason/draft boundaries, qualification messages, and firing.');
}
(async()=>{const server=spawn(process.env.PYTHON||'python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8777'],{cwd:root,stdio:['ignore','pipe','pipe']});let logs='';server.stdout.on('data',d=>logs+=d);server.stderr.on('data',d=>logs+=d);try{for(let i=0;;i++){if(server.exitCode!==null)throw new Error(logs);try{if((await fetch(base+'/api/teams')).ok)break}catch{}if(i===100)throw new Error(logs);await new Promise(r=>setTimeout(r,100))}await checks()}finally{server.kill()}})().catch(e=>{console.error(e);process.exitCode=1});
