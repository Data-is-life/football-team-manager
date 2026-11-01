const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {spawn}=require('node:child_process'),{JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'..'),base='http://127.0.0.1:8781',key='arcade-league-save';
const script=fs.readFileSync(path.join(root,'app/static/app.js'),'utf8'),html=fs.readFileSync(path.join(root,'app/static/index.html'),'utf8');
const q=(p,s)=>p.d.querySelector(s),raw=p=>p.w.localStorage.getItem(key),save=p=>JSON.parse(raw(p));
async function until(check){for(let i=0;i<3000;i++){if(check())return;await new Promise(r=>setTimeout(r,10))}throw new Error('Leaders UI timed out')}
async function api(body,owner='seattle'){const r=await fetch(base+'/api/career/'+owner,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});assert.equal(r.ok,true);return r.json()}
function page(checkpoint){const dom=new JSDOM(html,{url:base,runScripts:'outside-only'}),w=dom.window,d=w.document,state={leaders:[],fail:false,hold:false,mismatch:false};
 w.localStorage.setItem(key,JSON.stringify(checkpoint));w.HTMLElement.prototype.scrollIntoView=()=>{};
 w.HTMLDialogElement.prototype.showModal=function(){this.open=true};w.HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new w.Event('close'))};
 Object.defineProperty(w.crypto,'getRandomValues',{value:a=>{a[0]=5678;return a}});
 w.fetch=async(url,init)=>{const body=init?JSON.parse(init.body):null;
  if(body?.action==='leaders'){
   state.leaders.push(body);if(state.hold)await new Promise(resolve=>state.release=resolve);
   if(state.fail)return {ok:false,json:async()=>({detail:'Injected leaders failure'})};
   const r=await fetch(new URL(url,base),init),data=await r.json();if(state.mismatch)data.week++;
   return {ok:r.ok,json:async()=>data};
  }
  return fetch(new URL(url,base),init);
 };
 w.eval(script);return {dom,w,d,state};
}
async function restore(checkpoint){const p=page(checkpoint);await until(()=>/restored|could not/.test(q(p,'#save-status').textContent));assert.match(q(p,'#save-status').textContent,/restored/);assert.equal(p.state.leaders.length,0,'Restore never eagerly computes leaders');return p}
async function loaded(p){await until(()=>q(p,'#leaders-status').textContent.includes('Regular season through')||!q(p,'#leaders-retry').hidden)}
function check(p,data){
 const sections=[...p.d.querySelectorAll('#leaders-lists .leaders-category')];assert.equal(sections.length,5);
 let outside=0;
 for(let i=0;i<5;i++){
  const section=sections[i],category=data.categories[i];assert.equal(section.querySelector('h3').textContent,category.label);
  const rows=[...section.querySelectorAll('tbody tr')];assert.equal(rows.length,category.leaders.length);assert.ok(rows.length<=10);
  for(let j=0;j<rows.length;j++){
   const row=rows[j],entry=category.leaders[j];assert.equal(row.dataset.playerId,entry.player_id);
   assert.equal(row.cells[0].textContent,String(entry.rank));assert.equal(row.cells[1].textContent,`${entry.player} · ${entry.position}`);
   assert.ok(row.cells[2].textContent.startsWith(entry.team.city));assert.equal(row.cells[3].textContent,String(entry.value));
   assert.equal(row.classList.contains('leader-own'),entry.team.id===data.team.id);
   assert.equal(Boolean(row.querySelector('.your-team-badge')),entry.team.id===data.team.id);
  }
  const best=category.your_best,own=section.querySelector('.leaders-your-best');
  const show=best&&!category.leaders.some(row=>row.player_id===best.player_id);assert.equal(Boolean(own),Boolean(show));
  if(show){outside++;assert.equal(own.dataset.playerId,best.player_id);assert.ok(own.textContent.includes(`#${best.rank}`));assert.ok(own.textContent.includes(best.player));assert.ok(own.classList.contains('leader-own'))}
 }
 assert.match(q(p,'#leaders-status').textContent,new RegExp(`Season ${data.season}.*Week ${data.week}`));return outside;
}
const checkpoint={version:16,draftRounds:6,careerStartWeek:1,lineupChanges:[],contracts:false,teamId:'seattle',runSeed:1234,season:1,week:8,playoffRound:null,lineupRules:7,developmentStart:1,rebuildTeam:'seattle',priorStandings:{},history:[],career:[],draftChoices:null,dropped:[]};
async function checks(){
 let p=await restore({...checkpoint,week:0});const first=raw(p);q(p,'#league-leaders-button').click();assert.equal(q(p,'#leaders-dialog').open,true);assert.match(q(p,'#leaders-status').textContent,/Play Week 1/);assert.equal(p.state.leaders.length,0);assert.equal(raw(p),first);p.dom.window.close();
 p=await restore(checkpoint);q(p,'#view-standings').click();assert.equal(q(p,'#league-leaders-button').closest('#panel-standings').id,'panel-standings');
 const before=raw(p);p.state.fail=true;q(p,'#league-leaders-button').click();await until(()=>!q(p,'#leaders-retry').hidden);assert.equal(raw(p),before);assert.equal(q(p,'#leaders-lists').children.length,0);
 p.state.fail=false;q(p,'#leaders-retry').click();await loaded(p);assert.equal(q(p,'#leaders-retry').hidden,true);
 const expected=await api(p.state.leaders.at(-1));assert.ok(check(p,expected)>0,'Rebuilding team still gets its best-player rank outside top 10');assert.equal(raw(p),before);
 q(p,'#leaders-close').click();p.state.hold=true;q(p,'#league-leaders-button').click();await until(()=>Boolean(p.state.release));const release=p.state.release,requests=p.state.leaders.length;
 q(p,'#league-leaders-button').click();assert.equal(p.state.leaders.length,requests,'Duplicate loading cannot start another full aggregation');
 q(p,'#leaders-close').click();p.state.hold=false;q(p,'#league-leaders-button').click();await loaded(p);const rendered=q(p,'#leaders-lists').textContent;release();await new Promise(r=>setTimeout(r,100));assert.equal(q(p,'#leaders-lists').textContent,rendered,'Closed request cannot replace reopened results');check(p,expected);
 q(p,'#leaders-close').click();const count=p.state.leaders.length;q(p,'#simulate-button').click();await until(()=>save(p).week===9&&!q(p,'#simulate-button').disabled);assert.equal(p.state.leaders.length,count,'Weekly updates never compute hidden leader tables');assert.equal(q(p,'#leaders-lists').children.length,0);
 q(p,'#league-leaders-button').click();await loaded(p);assert.equal(p.state.leaders.at(-1).week,9);check(p,await api(p.state.leaders.at(-1)));q(p,'#leaders-close').click();
 p.state.mismatch=true;q(p,'#league-leaders-button').click();await until(()=>!q(p,'#leaders-retry').hidden);assert.equal(q(p,'#leaders-lists').children.length,0);p.state.mismatch=false;q(p,'#leaders-retry').click();await loaded(p);assert.equal(q(p,'#leaders-retry').hidden,true);p.dom.window.close();
 // Postseason leaders still stop at regular Week 17.
 p=await restore({...checkpoint,week:17,playoffRound:2});q(p,'#league-leaders-button').click();await loaded(p);assert.equal(p.state.leaders.at(-1).week,17);check(p,await api(p.state.leaders.at(-1)));assert.equal(save(p).playoffRound,2);p.dom.window.close();
 // Past offseasons and current draft/cuts use the same completed-season cohort.
 const later=JSON.parse(fs.readFileSync(path.join(root,'benchmarks/year4.json'),'utf8'));p=await restore(later);const saved=raw(p);q(p,'#league-leaders-button').click();await loaded(p);assert.deepEqual(p.state.leaders.at(-1).career,later.career.map(step=>({...step,draft_rounds:4})));check(p,await api(p.state.leaders.at(-1)));assert.equal(raw(p),saved);
 q(p,'#leaders-close').click();p.state.hold=true;q(p,'#league-leaders-button').click();await until(()=>Boolean(p.state.release));const stale=p.state.release;q(p,'#leaders-close').click();
 q(p,'#change-team-button').click();q(p,'#team-select').value='seattle';q(p,'#team-form').dispatchEvent(new p.w.Event('submit',{cancelable:true}));await until(()=>save(p).runSeed===5678);stale();await new Promise(r=>setTimeout(r,100));assert.equal(q(p,'#leaders-dialog').open,false);assert.equal(q(p,'#leaders-lists').children.length,0);assert.equal(q(p,'#leaders-status').textContent,'');p.dom.window.close();
 console.log('League leaders UI checks passed: lazy loading, Week 0, five exact top-10 tables, own-team highlights/outside rank, read-only saves, failure/retry/mismatch handling, duplicate guards, close/reopen stale response, weekly cutoff/invalidation, regular-only postseason totals, career/draft-cut context, and replacement reset.');
}
(async()=>{const server=spawn(process.env.PYTHON||'python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8781'],{cwd:root,stdio:['ignore','pipe','pipe']});let logs='';server.stdout.on('data',d=>logs+=d);server.stderr.on('data',d=>logs+=d);try{for(let i=0;;i++){if(server.exitCode!==null)throw new Error(logs);try{if((await fetch(base+'/api/teams')).ok)break}catch{}if(i===100)throw new Error(logs);await new Promise(r=>setTimeout(r,100))}await checks()}finally{server.kill()}})().catch(e=>{console.error(e);process.exitCode=1});
