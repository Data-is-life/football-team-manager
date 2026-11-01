const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {finishOffseason}=require('./ui_offseason_helpers.cjs');
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
const roll=id=>Number(createHash('sha256').update(`development-v1:1234:${id}:rookie-reveal-v2`).digest().readBigUInt64BE()%100n);
const row=(p,id,scope='#roster-groups')=>q(p,`${scope} [data-player-id="${id}"]`);
function snapshot(p){return q(p,'#roster-groups').textContent}
function body(checkpoint,action='profile',extra={}){return {action,run_seed:checkpoint.runSeed,season:checkpoint.season,lineup_rules:checkpoint.lineupRules,development_start:checkpoint.developmentStart,rebuild_team:checkpoint.rebuildTeam,career:checkpoint.career,prior_standings:checkpoint.priorStandings,...extra}}
function checkDevelopment(p, profile, all=false) {
 assert.equal(q(p,'#development-recap-button').hidden,false);
 const expected=profile.roster.filter(x=>all||x.rating_change||x.potential_change||['boom','bust'].includes(x.rookie_outcome));
 const rows=[...p.d.querySelectorAll('#development-recap-rows tr')];
 assert.deepEqual(rows.map(r=>r.dataset.playerId),expected.map(x=>x.id));
 for(let i=0;i<expected.length;i++){
  const x=expected[i],r=rows[i];assert.equal(r.cells[0].textContent,x.name);assert.equal(r.cells[1].textContent,x.position);
  for(const [index,key,value] of [[3,'rating_change','current_rating'],[4,'potential_change','potential_rating']]){
   const delta=x[key];assert.equal(r.cells[index].textContent,`${x[value]-delta} → ${x[value]} (${delta>0?'+':''}${delta})`);
   if(delta)assert.equal(r.cells[index].className,delta>0?'development-improved':'development-declined');
  }
  if(['boom','bust'].includes(x.rookie_outcome))assert.equal(r.cells[2].textContent,x.rookie_outcome==='boom'?'Boom':'Bust');
 }
 assert.equal(q(p,'#development-recap-legacy').hidden,true);
 assert.equal(q(p,'#development-recap-scroll').tabIndex,0);assert.match(q(p,'#development-recap-title').textContent,/Season 2/);
}
async function checks(){
 const picks=[],estimates=[];let board;
 for(const target of ['boom','bust','normal','normal']){
  board=await api('/api/draft/seattle',{season:1,run_seed:1234,lineup_rules:6,rebuild_team:'seattle',manual_picks:picks});
  const player=board.available.find(p=>p.position!=='K'&&(target==='boom'?roll(p.id)<20&&p.potential_rating<90:target==='bust'?roll(p.id)>=20&&roll(p.id)<25:roll(p.id)>=25));
  assert.ok(player,target);estimates.push(player);picks.push(player.id);
 }
 board=await api('/api/draft/seattle',{season:1,run_seed:1234,lineup_rules:6,rebuild_team:'seattle',manual_picks:picks});assert.equal(board.complete,true);
 const checkpoint={version:14,careerStartWeek:1,contracts:false,lineupChanges:[],teamId:'seattle',runSeed:1234,season:1,week:17,playoffRound:4,lineupRules:6,developmentStart:1,rebuildTeam:'seattle',priorStandings:{},history:[],career:[],draftChoices:picks,dropped:[]};
 let p=await restore(checkpoint);assert.equal(q(p,'#development-recap-button').hidden,true);
 for(const player of estimates){assert.equal(row(p,player.id).children[3].textContent,String(player.current_rating));assert.equal(row(p,player.id).children[4].textContent,String(player.potential_rating));assert.equal(row(p,player.id).querySelector('.potential-change'),null)}
 // Keep the four sampled rookies while making legal cuts before seeing their outcomes.
 q(p,'#manage-roster').click();
 while(p.d.querySelectorAll('#roster-groups .roster-player').length>38){const count=save(p).dropped.length;const button=[...p.d.querySelectorAll('#roster-groups [data-drop-id]:not([disabled])')].find(b=>!picks.includes(b.dataset.dropId));assert.ok(button);button.click();q(p,'#cut-confirm').click();await until(()=>save(p).dropped.length===count+1)}
 assert.equal(save(p).lineupRules,6);const frozen=save(p);p.dom.window.close();p=await restore(frozen);
 for(const player of estimates)assert.equal(row(p,player.id).children[4].textContent,String(player.potential_rating));
 q(p,'#next-season').click();await until(()=>save(p).season===2);assert.equal(save(p).lineupRules,8);assert.equal(save(p).version,17);assert.equal(save(p).career[0].lineup_rules,6);
 assert.equal(q(p,'#development-dialog').open,true);
 const current=await api('/api/career/seattle',body(save(p)));checkDevelopment(p,current);
 const unchanged=q(p,'#development-show-unchanged');unchanged.checked=true;unchanged.dispatchEvent(new p.w.Event('change'));checkDevelopment(p,current,true);
 unchanged.checked=false;unchanged.dispatchEvent(new p.w.Event('change'));checkDevelopment(p,current);
 const recap=q(p,'#development-recap-rows').textContent;const checkpointBeforeReview=raw(p);q(p,'#development-close').click();assert.equal(raw(p),checkpointBeforeReview);
 const byId=new Map(current.roster.map(player=>[player.id,player]));
 for(let i=0;i<estimates.length;i++){
  const original=estimates[i],player=byId.get(original.id),view=row(p,original.id),delta=player.potential_rating-original.potential_rating;
  assert.equal(player.rookie_outcome,i===0?'boom':i===1?'bust':'normal');if(i>=2){const room=original.potential_rating-original.current_rating;assert.equal(delta,0);assert.ok(player.current_rating-original.current_rating>=Math.min(1,room));assert.ok(player.current_rating-original.current_rating<=Math.min(2,room));}assert.equal(player.potential_change,delta);assert.equal(player.rating_change,player.current_rating-original.current_rating);
  assert.equal(player.age,original.age);assert.equal(player.experience,0);assert.ok(view.querySelector('.rookie-badge'));assert.equal(view.children[3].firstChild.textContent,String(player.current_rating));assert.equal(view.children[4].firstChild.textContent,String(player.potential_rating));
  const arrow=view.querySelector('.potential-change');
  if(delta){assert.ok(arrow);assert.equal(arrow.classList.contains(delta>0?'improved':'declined'),true);assert.match(arrow.textContent,new RegExp(delta>0?'↑ \\+'+delta:'↓ '+delta));assert.match(arrow.getAttribute('aria-label'),/Potential.*from.*to/);assert.match(arrow.title,/draft estimate/)}else assert.equal(arrow,null);
 }
 const recorded=snapshot(p),entered=save(p);p.dom.window.close();p=await restore(entered);assert.equal(snapshot(p),recorded);assert.equal(q(p,'#development-dialog').open,false);checkDevelopment(p,current);q(p,'#development-recap-button').click();assert.equal(q(p,'#development-dialog').open,true);q(p,'#development-close').click();assert.equal(q(p,'#development-recap-rows').textContent,recap);
 q(p,'#simulate-button').click();await until(()=>save(p).week===1&&!q(p,'#simulate-button').disabled);assert.equal(snapshot(p),recorded);
 const after=await api('/api/career/seattle',body(save(p)));assert.deepEqual(after,current,'Playing cannot reroll ability or potential');checkDevelopment(p,current);
 // Scouting shares potential arrows and cannot mutate the managed career.
 let other,profile;for(const button of p.d.querySelectorAll('.team-roster-link')){if(button.dataset.teamId==='seattle')continue;const candidate=await api('/api/career/seattle',body(save(p),'profile',{view_team:button.dataset.teamId}));if(candidate.roster.some(player=>player.potential_change)){other=button;profile=candidate;break}}
 assert.ok(other);const beforeScout=raw(p);other.click();await until(()=>/38 players/.test(q(p,'#scout-status').textContent));
 assert.equal(p.d.querySelectorAll('#scout-groups .potential-change').length,profile.roster.filter(player=>player.potential_change).length);assert.equal(raw(p),beforeScout);checkDevelopment(p,current);q(p,'#scout-close').click();
 const nextDraft=await api('/api/career/seattle',body(save(p),'draft'));
 assert.ok(nextDraft.available.every(player=>player.potential_change===0&&player.rookie_outcome===undefined),'Future draft estimates must not reveal outcomes');
 const completedDraft=await api('/api/career/seattle',body(save(p),'draft',{draft_rounds:6,auto_draft:true}));
 const draftedSave={...save(p),week:17,playoffRound:4,draftChoices:completedDraft.manual_picks,dropped:[]};
 p.dom.window.close();p=await restore(draftedSave);checkDevelopment(p,current);
 q(p,'#manage-roster').click();q(p,'#roster-groups [data-drop-id]:not([disabled])').click();q(p,'#cut-confirm').click();await until(()=>save(p).dropped.length===1);checkDevelopment(p,current);
 const afterCut=save(p);p.dom.window.close();p=await restore(afterCut);checkDevelopment(p,current);
 await finishOffseason(p,until);q(p,'#next-season').click();await until(()=>save(p).season===3);
 assert.equal(q(p,'#development-dialog').open,true);assert.match(q(p,'#development-recap-title').textContent,/Season 3/);assert.equal(q(p,'#development-show-unchanged').checked,false);
 q(p,'#development-close').click();q(p,'#change-team-button').click();q(p,'#team-select').value='seattle';q(p,'#team-form').dispatchEvent(new p.w.Event('submit',{cancelable:true}));await until(()=>save(p).season===1&&save(p).careerStartWeek===17);
 assert.equal(q(p,'#development-recap-button').hidden,true);assert.equal(q(p,'#development-dialog').open,false);assert.equal(q(p,'#development-recap-rows').children.length,0);
 // Edge cases: unchanged, potential-only changes, and capped zero-change booms.
 const untouched=raw(p),sample={id:'sample',name:'<b>Sample</b>',position:'WR',current_rating:70,potential_rating:80,rating_change:0,potential_change:0};
 p.w.setDevelopmentRecap({lineup_rules:7,roster:[sample]},2);assert.equal(q(p,'#development-recap-empty').hidden,false);assert.equal(q(p,'#development-recap-scroll').hidden,true);
 p.w.setDevelopmentRecap({lineup_rules:7,roster:[sample,{...sample,id:'potential',potential_rating:85,potential_change:5},{...sample,id:'capped',current_rating:99,potential_rating:99,rookie_outcome:'boom'}]},2);
 assert.equal(q(p,'#development-recap-rows').children.length,2);assert.match(q(p,'#development-recap-summary').textContent,/1 potential-only changes/);assert.equal(q(p,'#development-recap-rows tr').cells[2].textContent,'Potential increased');assert.equal(q(p,'#development-recap-rows tr').cells[4].textContent,'80 → 85 (+5)');assert.equal(q(p,'#development-recap-rows tr:last-child').cells[2].textContent,'Boom');assert.equal(q(p,'#development-recap-rows').querySelector('b'),null);assert.equal(raw(p),untouched);
 p.dom.window.close();
 // Replaying the prior offseason still gives the original draft estimates, with no leaked state.
 const replay=await api('/api/draft/seattle',{season:1,run_seed:1234,lineup_rules:6,rebuild_team:'seattle',manual_picks:picks});assert.deepEqual(replay,board);
 console.log('Rookie reveal UI checks passed: unrevealed draft/cuts/reload, legacy-to-new rules transition, seeded boom/bust/normal current and potential changes, positive/negative accessible arrows, rookies stay age/experience unchanged, reload/weekly idempotence, read-only scouting arrows, frozen future/past draft estimates, and development recap with exact deltas, rookie labels, changed/all filter, transition opening, read-only reopening, reloads, weekly/scout stability.');
}
(async()=>{const server=spawn(process.env.PYTHON||'python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8780'],{cwd:root,stdio:['ignore','pipe','pipe']});let logs='';server.stdout.on('data',d=>logs+=d);server.stderr.on('data',d=>logs+=d);try{for(let i=0;;i++){if(server.exitCode!==null)throw new Error(logs);try{if((await fetch(base+'/api/teams')).ok)break}catch{}if(i===100)throw new Error(logs);await new Promise(r=>setTimeout(r,100))}await checks()}finally{server.kill()}})().catch(e=>{console.error(e);process.exitCode=1});
