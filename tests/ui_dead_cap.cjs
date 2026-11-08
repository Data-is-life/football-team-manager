const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {spawn}=require('node:child_process'),{JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'..'),base='http://127.0.0.1:8781',key='arcade-league-save';
const html=fs.readFileSync(path.join(root,'app/static/index.html'),'utf8'),script=fs.readFileSync(path.join(root,'app/static/app.js'),'utf8');
const q=(p,s)=>p.d.querySelector(s),raw=p=>p.w.localStorage.getItem(key),save=p=>JSON.parse(raw(p));
async function until(check){for(let i=0;i<2000;i++){if(check())return;await new Promise(r=>setTimeout(r,10));}throw new Error('Dead-cap UI state timed out');}
async function api(body){const r=await fetch(base+'/api/career/seattle',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});assert.equal(r.ok,true,await r.clone().text());return r.json();}
async function page(checkpoint,blockedId=null){
 const dom=new JSDOM(html,{url:base,runScripts:'outside-only'}),w=dom.window,d=w.document,state={fail:false,calls:0,last:null};
 w.localStorage.setItem(key,JSON.stringify(checkpoint));w.HTMLElement.prototype.scrollIntoView=()=>{};w.scrollTo=()=>{};
 w.HTMLDialogElement.prototype.close=function(){this.open=false};w.HTMLDialogElement.prototype.showModal=function(){this.open=true};
 w.fetch=async(url,init)=>{const body=init&&JSON.parse(init.body);if(body?.action==='cuts'){state.calls++;if(state.fail)return {ok:false,json:async()=>({detail:'Release temporarily unavailable'})};}
  const r=await fetch(new URL(url,base),init);if(body?.action==='cuts'&&r.ok)state.last=await r.clone().json();
  if(blockedId&&r.ok&&body){const payload=await r.clone().json();const player=payload.profile?.roster.find(v=>v.id===blockedId);if(player?.release_preview){player.release_preview.allowed=false;player.release_preview.reason='Required replacement exceeds cap';}r.json=async()=>payload;}return r;};
 w.eval(script);const p={dom,w,d,state};await until(()=>/restored|could not/.test(q(p,'#save-status').textContent));assert.match(q(p,'#save-status').textContent,/restored/);return p;
}
async function checks(){
 const request={season:1,run_seed:1234,lineup_rules:24,rebuild_team:'seattle',draft_rounds:6};
 const draft=await api({...request,action:'draft',auto_draft:true});
 const camp=await api({...request,action:'camp',manual_picks:draft.manual_picks});
 const checkpoint={version:36,welcomeDismissed:true,ownerUpdateDismissed:0,draftRounds:6,careerStartWeek:17,lineupChanges:[],contracts:false,teamId:'seattle',runSeed:1234,season:1,week:17,lineupRules:24,developmentStart:1,rebuildTeam:'seattle',priorStandings:{},history:[],draftChoices:draft.manual_picks,dropped:[],career:[],playoffRound:4,trainingCamp:true};
 let p=await page(checkpoint);const player=camp.profile.roster.find(v=>v.position==='K'&&v.contract?.status==='active') ?? camp.profile.roster.find(v=>v.contract?.status==='active');
 q(p,'#view-roster').click();q(p,'#roster-ratings-button').click();
 const before=raw(p),initialPay=camp.profile.payroll.total;
 q(p,`[data-drop-id="${player.id}"]`).click();assert.equal(q(p,'#cut-impact').hidden,false);
 assert.match(q(p,'#cut-impact').textContent,/new dead cap:/);
 assert.match(q(p,'#cut-impact').textContent,/Cap space after release:/);
 assert.match(q(p,'#cut-impact').textContent,/Remaining guaranteed obligation:/);
 assert.match(q(p,'#cut-impact caption').textContent,/New dead-cap charges/);
 assert.equal(q(p,'#cut-impact tbody').rows.length,player.release_preview.dead_cap_schedule.length);
 assert.equal(q(p,'#cut-impact').textContent.includes(`$${(player.release_preview.total_obligation/1e6).toFixed(2)}M`),true);
 assert.equal(q(p,'#cut-confirm').disabled,false);
 assert.equal(p.d.activeElement,q(p,'#cut-confirm'));
 q(p,'#cut-cancel').click();assert.equal(raw(p),before);assert.equal(q(p,'#cut-impact').hidden,true);
 const rookie=camp.profile.roster.find(v=>v.contract_offer);
 q(p,`[data-drop-id="${rookie.id}"]`).click();assert.match(q(p,'#cut-impact').textContent,/No dead-cap penalty/);
 assert.match(q(p,'#cut-impact').textContent,/unsigned rookie hold/);assert.equal(q(p,'#cut-impact table'),null);
 q(p,'#cut-cancel').click();
 const expired=camp.profile.roster.find(v=>v.renewal_offer?.affordable);
 if(expired){q(p,`[data-drop-id="${expired.id}"]`).click();assert.match(q(p,'#cut-impact').textContent,/expired-contract hold/);q(p,'#cut-cancel').click();
 q(p,`[data-resign-id="${expired.id}"]`).click();assert.equal(q(p,'#cut-impact').hidden,true);assert.equal(q(p,'#cut-impact').textContent,'');q(p,'#cut-cancel').click();} 
 q(p,`[data-drop-id="${player.id}"]`).click();p.state.fail=true;q(p,'#cut-confirm').click();await until(()=>!q(p,'#cut-error').hidden&&!q(p,'#cut-confirm').disabled);assert.equal(raw(p),before);
 p.state.fail=false;const calls=p.state.calls;q(p,'#cut-confirm').click();q(p,'#cut-confirm').click();assert.equal(p.state.calls,calls+1);
 await until(()=>save(p).dropped.length===1);assert.equal(q(p,`.roster-rating-wrap [data-player-id="${player.id}"]`),null);
 assert.match(q(p,'#payroll-status').textContent,new RegExp(`\\$${(player.contract.annual_salary/1e6).toFixed(2).replace('.','\\.')}M dead cap`));
 assert.equal(p.state.last.profile.payroll.dead_cap,player.contract.annual_salary);assert.ok(p.state.last.profile.payroll.total>=initialPay);assert.equal(p.state.last.profile.payroll.cap_space,player.release_preview.cap_space_after);
 const released=save(p),payText=q(p,'#payroll-status').textContent;p.dom.window.close();p=await page(released);
 assert.equal(raw(p),JSON.stringify(released));assert.equal(q(p,'#payroll-status').textContent,payText);assert.equal(q(p,`.roster-rating-wrap [data-player-id="${player.id}"]`),null);
 // A server-blocked projection stays reviewable and cannot submit a cut.
 p.dom.window.close();p=await page(checkpoint,player.id);q(p,'#view-roster').click();q(p,'#roster-ratings-button').click();
 q(p,`[data-drop-id="${player.id}"]`).click();assert.equal(q(p,'#cut-confirm').disabled,true);assert.equal(p.d.activeElement,q(p,'#cut-cancel'));
 assert.match(q(p,'#cut-impact').textContent,/Required replacement exceeds cap/);const blockedCalls=p.state.calls;
 q(p,'#cut-confirm').dispatchEvent(new p.w.Event('click'));assert.equal(p.state.calls,blockedCalls);q(p,'#cut-cancel').click();assert.equal(raw(p),JSON.stringify(checkpoint));
 // Existing cuts keep the original policy when a pre-guarantee camp is restored.
 const old={...released,version:32,lineupRules:22};p.dom.window.close();p=await page(old);
 assert.equal(raw(p),JSON.stringify(old));assert.doesNotMatch(q(p,'#payroll-status').textContent,/dead cap/);p.dom.window.close();
 console.log('Dead-cap UI checks passed: guaranteed release warning, cancel/failure/retry, duplicate-click protection, cap charge, reload, retained picks and legacy-camp compatibility.');
}
(async()=>{const server=spawn(process.env.PYTHON||'python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8781'],{cwd:root,stdio:['ignore','pipe','pipe']});let logs='';server.stdout.on('data',d=>logs+=d);server.stderr.on('data',d=>logs+=d);try{for(let i=0;;i++){if(server.exitCode!==null)throw new Error(logs);try{if((await fetch(base+'/api/teams')).ok)break;}catch{}if(i===100)throw new Error(logs);await new Promise(r=>setTimeout(r,100));}await checks();}finally{server.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
