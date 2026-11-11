const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {spawn}=require('node:child_process'),{JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'..'),base='http://127.0.0.1:8787',key='arcade-league-save';
const html=fs.readFileSync(path.join(root,'app/static/index.html'),'utf8'),script=fs.readFileSync(path.join(root,'app/static/app.js'),'utf8');
const q=(p,s)=>p.d.querySelector(s),raw=p=>p.w.localStorage.getItem(key),save=p=>JSON.parse(raw(p));
async function until(check){for(let i=0;i<6000;i++){if(check())return;await new Promise(r=>setTimeout(r,10));}throw new Error('Pre-camp UI timed out');}
async function api(body){const r=await fetch(base+'/api/career/seattle',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});assert.equal(r.ok,true,await r.clone().text());return r.json();}
async function page(checkpoint){
 const dom=new JSDOM(html,{url:base,runScripts:'outside-only'}),w=dom.window,d=w.document,state={failMarket:false,failCamp:false,last:null};
 w.localStorage.setItem(key,JSON.stringify(checkpoint));w.HTMLElement.prototype.scrollIntoView=()=>{};w.scrollTo=()=>{};
 w.HTMLDialogElement.prototype.close=function(){this.open=false};w.HTMLDialogElement.prototype.showModal=function(){this.open=true};
 w.fetch=async(url,init)=>{const body=init&&JSON.parse(init.body);if((body?.action==='free_agency'&&state.failMarket)||(body?.action==='camp'&&state.failCamp))return {ok:false,json:async()=>({detail:'Temporarily unavailable'})};const response=await fetch(new URL(url,base),init);if(init&&response.ok)state.last=await response.clone().json();if(!response.ok)console.error('Pre-camp API error',await response.clone().text());return response;};
 w.eval(script);const p={dom,w,d,state};await until(()=>/restored|could not/.test(q(p,'#save-status').textContent));assert.match(q(p,'#save-status').textContent,/restored/);return p;
}
async function drop(p,id,phase='preCampActions'){
 const count=(save(p)[phase]??[]).length;q(p,`[data-drop-id="${id}"]`).click();q(p,'#cut-confirm').click();await until(()=>(save(p)[phase]??[]).length===count+1);
}
async function checks(){
 const baseRequest={run_seed:1234,lineup_rules:31,rebuild_team:'seattle',draft_rounds:6};
 const draft=await api({...baseRequest,action:'draft',auto_draft:true});
 const checkpoint={version:41,welcomeDismissed:true,ownerUpdateDismissed:0,draftRounds:6,careerStartWeek:17,lineupChanges:[],contracts:false,teamId:'seattle',runSeed:1234,season:1,week:17,lineupRules:31,developmentStart:1,rebuildTeam:'seattle',priorStandings:{},history:[],draftChoices:draft.manual_picks,dropped:[],career:[],playoffRound:4};
 let p=await page(checkpoint);assert.equal(q(p,'#training-camp-button').hidden,true);assert.equal(q(p,'#next-season').textContent,'Open free agency');assert.equal(q(p,'#next-season').disabled,false);
 q(p,'#next-season').click();await until(()=>Array.isArray(save(p).freeAgency));assert.equal(save(p).trainingCamp,undefined);assert.equal(q(p,'#training-camp-button').hidden,true);assert.match(q(p,'#fa-flow-guide').textContent,/above 38/);
 const initial=new Map(p.state.last.profile.roster.map(p=>[p.id,{rating:p.current_rating,age:p.age,salary:(p.contract??p.contract_offer)?.annual_salary}]));
 const candidates=p.state.last.free_agency.available.filter(p=>p.affordable).sort((a,b)=>a.annual_salary-b.annual_salary);assert.ok(candidates.length);const target=candidates[0];
 const unchanged=raw(p);p.state.failMarket=true;q(p,`[data-fa-id="${target.id}"]`).click();await until(()=>!q(p,'#fa-error').hidden);assert.equal(raw(p),unchanged);p.state.failMarket=false;
 q(p,`[data-fa-id="${target.id}"]`).click();q(p,`[data-fa-id="${target.id}"]`).click();await until(()=>save(p).freeAgency.length===1);
 assert.ok(p.state.last.profile.roster.length>38);assert.equal(p.state.last.profile.roster.find(p=>p.id===target.id).contract.annual_salary,target.annual_salary);
 q(p,'#fa-finish').click();await until(()=>save(p).freeAgency.at(-1)?.kind==='finish');assert.equal(save(p).season,1);assert.equal(save(p).trainingCamp,undefined);assert.equal(q(p,'#training-camp-button').hidden,false);assert.equal(q(p,'#training-camp-button').disabled,true);
 q(p,'#view-roster').click();q(p,'#roster-ratings-button').click();
 const offers=p.state.last.profile.roster.filter(p=>p.contract_offer);const keep=offers[0]?.id;
 for(const player of offers)if(player.id!==keep)await drop(p,player.id);
 // Release a large contract during review to exercise hard-floor remediation.
 const profile=p.state.last.profile;const counts=Object.fromEntries(profile.roster_rules.map(r=>[r.position,r.count]));
 const expensive=profile.roster.filter(p=>p.contract&&counts[p.position]>profile.roster_rules.find(r=>r.position===p.position).minimum).sort((a,b)=>b.contract.annual_salary-a.contract.annual_salary)[0];
 await drop(p,expensive.id);assert.ok(p.state.last.profile.payroll.below_floor>0);assert.equal(q(p,'#training-camp-button').disabled,true);assert.equal(q(p,'#meet-payroll-floor').hidden,false);
 const beforeRaise=raw(p);q(p,'#meet-payroll-floor').click();assert.match(q(p,'#floor-confirm-text').textContent,/fully guaranteed/);q(p,'#floor-cancel').click();assert.equal(raw(p),beforeRaise);q(p,'#meet-payroll-floor').click();q(p,'#floor-confirm').click();await until(()=>save(p).preCampActions.at(-1)?.kind==='raise');assert.equal(p.state.last.profile.payroll.below_floor,0);
 const reviewed=save(p);const beforeCamp=new Map(p.state.last.profile.roster.map(p=>[p.id,p]));p.dom.window.close();p=await page(reviewed);assert.equal(q(p,'#training-camp-button').disabled,false);
 const campSave=raw(p);p.state.failCamp=true;q(p,'#training-camp-button').click();await until(()=>!q(p,'#error').hidden);assert.equal(raw(p),campSave);p.state.failCamp=false;q(p,'#training-camp-button').click();await until(()=>save(p).trainingCamp===true);if(q(p,'#development-dialog').open)q(p,'#development-close').click();
 const afterCamp=p.state.last.profile;
 for(const player of afterCamp.roster){const old=beforeCamp.get(player.id);if(old&&!player.id.startsWith('rookie-')&&!player.id.startsWith('replacement-'))assert.equal(player.age,old.age+1);if(old)assert.equal((player.contract??player.contract_offer).annual_salary,(old.contract??old.contract_offer).annual_salary);}
 const campCheckpoint=save(p);p.dom.window.close();p=await page(campCheckpoint);assert.equal(save(p).trainingCamp,true);assert.equal(q(p,'#training-camp-button').hidden,true);q(p,'#next-season').click();await until(()=>save(p).season===2);
 assert.equal(save(p).lineupRules,31);assert.equal(save(p).career[0].pre_camp_actions.at(-1).kind,'raise');assert.ok(save(p).career[0].free_agency.length);const next=save(p);p.dom.window.close();p=await page(next);assert.equal(save(p).season,2);p.dom.window.close();
 console.log('Pre-camp UI passed: draft/market/review/camp/season order, oversized signing, pre-development prices, failed requests, floor confirmation, save/reload and next-season replay.');
}
(async()=>{const server=spawn(process.env.PYTHON||'python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8787'],{cwd:root,stdio:['ignore','pipe','pipe']});let logs='';server.stdout.on('data',d=>logs+=d);server.stderr.on('data',d=>logs+=d);try{for(let i=0;;i++){if(server.exitCode!==null)throw new Error(logs);try{if((await fetch(base+'/api/teams')).ok)break;}catch{}if(i===100)throw new Error(logs);await new Promise(r=>setTimeout(r,100));}try{await checks();}catch(error){console.error(logs);throw error;}}finally{server.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
