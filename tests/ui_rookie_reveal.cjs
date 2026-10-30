const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {createHash}=require('node:crypto'),{spawn}=require('node:child_process'),{JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'..'),base='http://127.0.0.1:8780',key='arcade-league-save';
const html=fs.readFileSync(path.join(root,'app/static/index.html'),'utf8'),script=fs.readFileSync(path.join(root,'app/static/app.js'),'utf8');
async function until(check){for(let i=0;i<2000;i++){if(check())return;await new Promise(r=>setTimeout(r,10))}throw new Error('Rookie reveal UI state timed out')}
async function api(url,body){const r=await fetch(base+url,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:undefined);assert.equal(r.ok,true,url);return r.json()}
const q=(p,s)=>p.d.querySelector(s),raw=p=>p.w.localStorage.getItem(key),save=p=>JSON.parse(raw(p));
function page(checkpoint){const dom=new JSDOM(html,{url:base,runScripts:'outside-only'}),w=dom.window,d=w.document;
 w.localStorage.setItem(key,JSON.stringify(checkpoint));w.HTMLElement.prototype.scrollIntoView=()=>{};
 w.HTMLDialogElement.prototype.close=function(){this.open=false};w.HTMLDialogElement.prototype.showModal=function(){this.open=true};
 w.fetch=(url,init)=>fetch(new URL(url,base),init);w.eval(script);return {dom,w,d};}
async function restore(checkpoint){const p=page(checkpoint);await until(()=>/restored|could not/.test(q(p,'#save-status').textContent));assert.match(q(p,'#save-status').textContent,/restored/);return p}
const roll=id=>Number(createHash('sha256').update(`development-v1:1234:${id}:rookie-reveal-v1`).digest().readBigUInt64BE()%100n);
const row=(p,id,scope='#roster-groups')=>q(p,`${scope} [data-player-id="${id}"]`);
function snapshot(p){return q(p,'#roster-groups').textContent}
function body(checkpoint,action='profile',extra={}){return {action,run_seed:checkpoint.runSeed,season:checkpoint.season,lineup_rules:checkpoint.lineupRules,development_start:checkpoint.developmentStart,rebuild_team:checkpoint.rebuildTeam,career:checkpoint.career,prior_standings:checkpoint.priorStandings,...extra}}
async function checks(){
 const picks=[],estimates=[];let board;
 for(const target of ['boom','bust','normal','normal']){
  board=await api('/api/draft/seattle',{season:1,run_seed:1234,lineup_rules:6,rebuild_team:'seattle',manual_picks:picks});
  const player=board.available.find(p=>p.position!=='K'&&(target==='boom'?roll(p.id)<15&&p.potential_rating<90:target==='bust'?roll(p.id)>=15&&roll(p.id)<30:roll(p.id)>=30));
  assert.ok(player,target);estimates.push(player);picks.push(player.id);
 }
 board=await api('/api/draft/seattle',{season:1,run_seed:1234,lineup_rules:6,rebuild_team:'seattle',manual_picks:picks});assert.equal(board.complete,true);
 const checkpoint={version:14,careerStartWeek:1,contracts:false,lineupChanges:[],teamId:'seattle',runSeed:1234,season:1,week:17,playoffRound:4,lineupRules:6,developmentStart:1,rebuildTeam:'seattle',priorStandings:{},history:[],career:[],draftChoices:picks,dropped:[]};
 let p=await restore(checkpoint);
 for(const player of estimates){assert.equal(row(p,player.id).children[3].textContent,String(player.current_rating));assert.equal(row(p,player.id).children[4].textContent,String(player.potential_rating));assert.equal(row(p,player.id).querySelector('.potential-change'),null)}
 // Keep the four sampled rookies while making legal cuts before seeing their outcomes.
 q(p,'#manage-roster').click();
 while(p.d.querySelectorAll('#roster-groups .roster-player').length>38){const count=save(p).dropped.length;const button=[...p.d.querySelectorAll('#roster-groups [data-drop-id]:not([disabled])')].find(b=>!picks.includes(b.dataset.dropId));assert.ok(button);button.click();q(p,'#cut-confirm').click();await until(()=>save(p).dropped.length===count+1)}
 assert.equal(save(p).lineupRules,6);const frozen=save(p);p.dom.window.close();p=await restore(frozen);
 for(const player of estimates)assert.equal(row(p,player.id).children[4].textContent,String(player.potential_rating));
 q(p,'#next-season').click();await until(()=>save(p).season===2);assert.equal(save(p).lineupRules,7);assert.equal(save(p).version,15);assert.equal(save(p).career[0].lineup_rules,6);
 const current=await api('/api/career/seattle',body(save(p)));const byId=new Map(current.roster.map(player=>[player.id,player]));
 for(let i=0;i<estimates.length;i++){
  const original=estimates[i],player=byId.get(original.id),view=row(p,original.id),delta=player.potential_rating-original.potential_rating;
  assert.equal(player.rookie_outcome,i===0?'boom':i===1?'bust':'normal');assert.equal(player.potential_change,delta);assert.equal(player.rating_change,player.current_rating-original.current_rating);
  assert.equal(player.age,original.age);assert.equal(player.experience,0);assert.ok(view.querySelector('.rookie-badge'));assert.equal(view.children[3].firstChild.textContent,String(player.current_rating));assert.equal(view.children[4].firstChild.textContent,String(player.potential_rating));
  const arrow=view.querySelector('.potential-change');
  if(delta){assert.ok(arrow);assert.equal(arrow.classList.contains(delta>0?'improved':'declined'),true);assert.match(arrow.textContent,new RegExp(delta>0?'↑ \\+'+delta:'↓ '+delta));assert.match(arrow.getAttribute('aria-label'),/Potential.*from.*to/);assert.match(arrow.title,/draft estimate/)}else assert.equal(arrow,null);
 }
 const recorded=snapshot(p),entered=save(p);p.dom.window.close();p=await restore(entered);assert.equal(snapshot(p),recorded);
 q(p,'#simulate-button').click();await until(()=>save(p).week===1&&!q(p,'#simulate-button').disabled);assert.equal(snapshot(p),recorded);
 const after=await api('/api/career/seattle',body(save(p)));assert.deepEqual(after,current,'Playing cannot reroll ability or potential');
 // Scouting shares potential arrows and cannot mutate the managed career.
 let other,profile;for(const button of p.d.querySelectorAll('.team-roster-link')){if(button.dataset.teamId==='seattle')continue;const candidate=await api('/api/career/seattle',body(save(p),'profile',{view_team:button.dataset.teamId}));if(candidate.roster.some(player=>player.potential_change)){other=button;profile=candidate;break}}
 assert.ok(other);const beforeScout=raw(p);other.click();await until(()=>/38 players/.test(q(p,'#scout-status').textContent));
 assert.equal(p.d.querySelectorAll('#scout-groups .potential-change').length,profile.roster.filter(player=>player.potential_change).length);assert.equal(raw(p),beforeScout);q(p,'#scout-close').click();
 const nextDraft=await api('/api/career/seattle',body(save(p),'draft'));
 assert.ok(nextDraft.available.every(player=>player.potential_change===0&&player.rookie_outcome===undefined),'Future draft estimates must not reveal outcomes');
 p.dom.window.close();
 // Replaying the prior offseason still gives the original draft estimates, with no leaked state.
 const replay=await api('/api/draft/seattle',{season:1,run_seed:1234,lineup_rules:6,rebuild_team:'seattle',manual_picks:picks});assert.deepEqual(replay,board);
 console.log('Rookie reveal UI checks passed: unrevealed draft/cuts/reload, legacy-to-new rules transition, seeded boom/bust/normal current and potential changes, positive/negative accessible arrows, rookies stay age/experience unchanged, reload/weekly idempotence, read-only scouting arrows, and frozen future/past draft estimates.');
}
(async()=>{const server=spawn(process.env.PYTHON||'python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8780'],{cwd:root,stdio:['ignore','pipe','pipe']});let logs='';server.stdout.on('data',d=>logs+=d);server.stderr.on('data',d=>logs+=d);try{for(let i=0;;i++){if(server.exitCode!==null)throw new Error(logs);try{if((await fetch(base+'/api/teams')).ok)break}catch{}if(i===100)throw new Error(logs);await new Promise(r=>setTimeout(r,100))}await checks()}finally{server.kill()}})().catch(e=>{console.error(e);process.exitCode=1});
