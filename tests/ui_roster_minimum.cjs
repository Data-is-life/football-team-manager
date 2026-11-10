const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {spawn}=require('node:child_process'),{JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'..'),base='http://127.0.0.1:8782',key='arcade-league-save';
const html=fs.readFileSync(path.join(root,'app/static/index.html'),'utf8'),script=fs.readFileSync(path.join(root,'app/static/app.js'),'utf8');
const q=(p,s)=>p.d.querySelector(s),raw=p=>p.w.localStorage.getItem(key),save=p=>JSON.parse(raw(p));
const count=p=>p.d.querySelectorAll('#roster-groups .roster-rating-wrap .roster-player').length;
async function until(check){for(let i=0;i<2000;i++){if(check())return;await new Promise(r=>setTimeout(r,10));}throw new Error('Roster-minimum UI state timed out');}
async function api(body){const r=await fetch(base+'/api/career/seattle',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});assert.equal(r.ok,true,await r.clone().text());return r.json();}
async function page(checkpoint){
 const dom=new JSDOM(html,{url:base,runScripts:'outside-only'}),w=dom.window,d=w.document;
 w.localStorage.setItem(key,JSON.stringify(checkpoint));w.HTMLElement.prototype.scrollIntoView=()=>{};w.scrollTo=()=>{};
 w.HTMLDialogElement.prototype.close=function(){this.open=false};w.HTMLDialogElement.prototype.showModal=function(){this.open=true};
 w.fetch=(url,init)=>fetch(new URL(url,base),init);w.eval(script);const p={dom,w,d};
 await until(()=>/restored|could not/.test(q(p,'#save-status').textContent));assert.match(q(p,'#save-status').textContent,/restored/);return p;
}
async function checks(){
 const request={season:1,run_seed:1234,lineup_rules:24,rebuild_team:'seattle',draft_rounds:6};
 const initial=await api({...request,action:'profile'});assert.equal(initial.roster.length,35);assert.deepEqual(initial.roster_limits,{minimum:31,maximum:38});
 const draft=await api({...request,action:'draft',auto_draft:true});
 const checkpoint={version:33,welcomeDismissed:true,ownerUpdateDismissed:0,draftRounds:6,careerStartWeek:17,lineupChanges:[],contracts:false,teamId:'seattle',runSeed:1234,season:1,week:17,lineupRules:23,developmentStart:1,rebuildTeam:'seattle',priorStandings:{},history:[],draftChoices:draft.manual_picks,dropped:[],career:[],playoffRound:4,trainingCamp:true};
 let p=await page(checkpoint);assert.equal(raw(p),JSON.stringify(checkpoint));
 assert.match(q(p,'#roster-limit-note').textContent,/starts with 35.*31–38/);assert.match(q(p,'#draft-format').textContent,/31–38/);
 q(p,'#view-roster').click();q(p,'#roster-ratings-button').click();let firstRelease;
 while(count(p)>31){
  const before=count(p),drops=save(p).dropped.length;
  const kicker=q(p,'[data-position="K"] [data-drop-id]');
  if(p.d.querySelectorAll('#roster-groups [data-position="K"] .roster-player').length===1)assert.equal(kicker.disabled,true);
  const button=q(p,'#roster-groups [data-drop-id]:not([disabled])');assert.ok(button);firstRelease??=button.dataset.dropId;
  button.click();q(p,'#cut-confirm').click();await until(()=>save(p).dropped.length===drops+1);
  assert.equal(count(p),before-1,'A surplus cut cannot refill the optional bench');
  assert.equal(save(p).lineupRules,24);assert.equal(save(p).version,40);
 }
 assert.match(q(p,'#cut-count').textContent,/31\/38 players \(minimum 31\).*No more cuts needed/);
 assert.ok([...p.d.querySelectorAll('#roster-groups [data-drop-id]')].every(b=>b.disabled));
 assert.equal(q(p,'#next-season').disabled,false);
 const minimum=save(p),pay=q(p,'#payroll-status').textContent;p.dom.window.close();p=await page(minimum);
 assert.equal(count(p),31);assert.equal(raw(p),JSON.stringify(minimum));assert.equal(q(p,'#payroll-status').textContent,pay);
 q(p,'#next-season').click();await until(()=>save(p).season===2);assert.equal(count(p),31);
 const yearTwo=save(p);p.dom.window.close();p=await page(yearTwo);assert.equal(count(p),31);
 q(p,'#simulate-button').click();await until(()=>save(p).week===1);assert.equal(count(p),31);p.dom.window.close();
 const old={...checkpoint,rosterActions:[{kind:'drop',player_id:firstRelease}],dropped:[firstRelease]};
 p=await page(old);assert.equal(raw(p),JSON.stringify(old));assert.match(q(p,'#roster-limit-note').textContent,/35–38/);p.dom.window.close();
 console.log('Roster minimum UI checks passed: 35 at creation, 31–38 guidance, position safeguards, cuts to 31 without refills, minimum stop, dead-cap/reload preservation, next-season weekly play, and committed legacy-camp compatibility.');
}
(async()=>{const server=spawn(process.env.PYTHON||'python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8782'],{cwd:root,stdio:['ignore','pipe','pipe']});let logs='';server.stdout.on('data',d=>logs+=d);server.stderr.on('data',d=>logs+=d);try{for(let i=0;;i++){if(server.exitCode!==null)throw new Error(logs);try{if((await fetch(base+'/api/teams')).ok)break;}catch{}if(i===100)throw new Error(logs);await new Promise(r=>setTimeout(r,100));}await checks();}finally{server.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
