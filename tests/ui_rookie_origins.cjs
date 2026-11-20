const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {spawn,execFileSync}=require('node:child_process'),{JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'..'),base='http://127.0.0.1:8801',key='arcade-league-save';
const fixture=JSON.parse(execFileSync(process.env.PYTHON||'python',['tests/test_rookie_origins.py'],{cwd:root,env:{...process.env,PYTHONPATH:root},encoding:'utf8'}));
const html=fs.readFileSync(path.join(root,'app/static/index.html'),'utf8'),script=fs.readFileSync(path.join(root,'app/static/app.js'),'utf8');
const q=(p,s)=>p.d.querySelector(s),save=p=>JSON.parse(p.w.localStorage.getItem(key));
async function until(check){for(let i=0;i<4000;i++){if(check())return;await new Promise(r=>setTimeout(r,10));}throw Error('Rookie origin UI timeout');}
async function page(checkpoint){
 const dom=new JSDOM(html,{url:base,runScripts:'outside-only'}),w=dom.window,d=w.document;
 w.localStorage.setItem(key,JSON.stringify(checkpoint));w.HTMLElement.prototype.scrollIntoView=()=>{};w.scrollTo=()=>{};
 w.HTMLDialogElement.prototype.close=function(){this.open=false};w.HTMLDialogElement.prototype.showModal=function(){this.open=true};
 w.fetch=(url,init)=>fetch(new URL(url,base),init);w.eval(script);
 const p={dom,w,d};await until(()=>/restored|could not/.test(q(p,'#save-status').textContent));assert.match(q(p,'#save-status').textContent,/restored/);return p;
}
function checkBadges(p,id,expected){
 q(p,'#roster-stats-button').click();
 const rows=p.d.querySelectorAll(`#roster-groups [data-player-id="${id}"]`);assert.ok(rows.length>=2);
 for(const row of rows){
  const badges=[...row.querySelectorAll('.rookie-badge,.free-agent-badge')];
  assert.deepEqual(badges.map(b=>b.textContent),expected);
  for(const badge of badges)assert.ok(badge.getAttribute('aria-label'));
 }
 q(p,'#roster-ratings-button').click();
}
async function checks(){
 for(const [origin,id] of Object.entries(fixture.targets)){
  let p=await page(fixture.checkpoint);
  const expected=origin==='undrafted'?['UDFA']:['R','F'];
  const button=q(p,`#fa-players [data-fa-id="${id}"]`);assert.ok(button);assert.equal(button.disabled,false);button.click();q(p,'#fa-confirm').click();
  await until(()=>save(p).freeAgency.length===1&&!q(p,'#fa-finish').disabled);
  checkBadges(p,id,expected);
  const checkpoint=save(p);p.dom.window.close();p=await page(checkpoint);checkBadges(p,id,expected);
  // Scouting uses the same player metadata and roster renderer.
  const profile=await (await fetch(base+'/api/career/seattle',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...fixture.request,action:'free_agency',free_agency:checkpoint.freeAgency,view_team:'seattle'})})).json();
  const groups=p.w.createRosterGroups(profile.profile,false);
  const row=groups.flatMap(group=>[...group.querySelectorAll(`[data-player-id="${id}"]`)]).at(0);assert.ok(row);
  assert.deepEqual([...row.querySelectorAll('.rookie-badge,.free-agent-badge')].map(b=>b.textContent),expected);
  p.dom.window.close();
 }
 console.log('Rookie origin UI passed: real UDFA and released-rookie signings, rating/stats/scouting badges, accessible labels and saved-market reloads.');
}
(async()=>{const server=spawn(process.env.PYTHON||'python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8801'],{cwd:root,stdio:['ignore','pipe','pipe']});let logs='';server.stdout.on('data',d=>logs+=d);server.stderr.on('data',d=>logs+=d);try{for(let i=0;;i++){if(server.exitCode!==null)throw Error(logs);try{if((await fetch(base+'/api/teams')).ok)break;}catch{}if(i===100)throw Error(logs);await new Promise(r=>setTimeout(r,100));}await checks();}finally{server.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
