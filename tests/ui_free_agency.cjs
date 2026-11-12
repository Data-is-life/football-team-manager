const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {spawn}=require('node:child_process'),{JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'..'),base='http://127.0.0.1:8784',key='arcade-league-save';
const html=fs.readFileSync(path.join(root,'app/static/index.html'),'utf8'),script=fs.readFileSync(path.join(root,'app/static/app.js'),'utf8');
const q=(p,s)=>p.d.querySelector(s),raw=p=>p.w.localStorage.getItem(key),save=p=>JSON.parse(raw(p));
async function until(check){for(let i=0;i<6000;i++){if(check())return;await new Promise(r=>setTimeout(r,10));}throw new Error('Free agency UI timed out');}
async function api(body){const r=await fetch(base+'/api/career/seattle',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});assert.equal(r.ok,true,await r.clone().text());return r.json();}
async function page(checkpoint){
 const dom=new JSDOM(html,{url:base,runScripts:'outside-only'}),w=dom.window,d=w.document,state={fail:false,calls:0};
 w.localStorage.setItem(key,JSON.stringify(checkpoint));w.HTMLElement.prototype.scrollIntoView=()=>{};w.scrollTo=()=>{};
 w.HTMLDialogElement.prototype.close=function(){this.open=false};w.HTMLDialogElement.prototype.showModal=function(){this.open=true};
 w.fetch=async(url,init)=>{const body=init&&JSON.parse(init.body);if(body?.action==='free_agency'){state.calls++;if(state.fail)return {ok:false,json:async()=>({detail:'Market temporarily unavailable'})};}const response=await fetch(new URL(url,base),init);if(!response.ok) console.error('Free agency test API error:',url,await response.clone().text());return response;};
 w.eval(script);const p={dom,w,d,state};await until(()=>/restored|could not/.test(q(p,'#save-status').textContent));assert.match(q(p,'#save-status').textContent,/restored/);return p;
}
async function checks(){
 const request={season:1,run_seed:1234,lineup_rules:29,rebuild_team:'seattle',draft_rounds:6};
 const draft=await api({...request,action:'draft',auto_draft:true});
 const camp=await api({...request,action:'camp',manual_picks:draft.manual_picks});
 const dropped=camp.profile.roster.filter(p=>p.contract_offer||p.renewal_offer).map(p=>p.id);
 const checkpoint={version:39,welcomeDismissed:true,ownerUpdateDismissed:0,draftRounds:6,careerStartWeek:17,lineupChanges:[],contracts:false,teamId:'seattle',runSeed:1234,season:1,week:17,lineupRules:29,developmentStart:1,rebuildTeam:'seattle',priorStandings:{},history:[],draftChoices:draft.manual_picks,dropped,rosterActions:dropped.map(player_id=>({kind:'drop',player_id})),career:[],playoffRound:4,trainingCamp:true};
 let p=await page(checkpoint);
 assert.equal(q(p,'#next-season').textContent,'Open free agency');q(p,'#next-season').click();
 await until(()=>Array.isArray(save(p).freeAgency));
 assert.equal(q(p,'#free-agency').hidden,false);assert.match(q(p,'#fa-status').textContent,/Wave 1.*120%.*Cap space/);
 const before=raw(p);q(p,'#fa-sort').value='potential_rating';q(p,'#fa-sort').dispatchEvent(new p.w.Event('change'));
 const values=[...p.d.querySelectorAll('#fa-players tr')].map(row=>Number(row.children[4].textContent));assert.deepEqual(values,[...values].sort((a,b)=>b-a));assert.equal(raw(p),before);
 q(p,'#fa-position').value='QB';q(p,'#fa-position').dispatchEvent(new p.w.Event('change'));assert.ok([...p.d.querySelectorAll('#fa-players tr')].every(row=>row.children[1].textContent==='QB'));
 q(p,'#fa-position').value='';q(p,'#fa-position').dispatchEvent(new p.w.Event('change'));
 const button=q(p,'#fa-players button:not([disabled])');assert.ok(button);const id=button.dataset.faId;
 p.state.fail=true;button.click();await until(()=>!q(p,'#fa-error').hidden);assert.equal(raw(p),before);
 p.state.fail=false;q(p,`[data-fa-id="${id}"]`).click();q(p,`[data-fa-id="${id}"]`).click();await until(()=>save(p).freeAgency.length===1);
 assert.equal(save(p).freeAgency[0].player_id,id);assert.equal(q(p,`[data-fa-id="${id}"]`),null);assert.ok(q(p,`#roster-groups [data-player-id="${id}"]`));
 assert.match(q(p,'#fa-status').textContent,/Wave 2.*110%/);const signed=save(p);p.dom.window.close();p=await page(signed);
 assert.match(q(p,'#fa-status').textContent,/Wave 2/);assert.ok(q(p,`#roster-groups [data-player-id="${id}"]`));
 q(p,'#fa-pass').click();await until(()=>save(p).freeAgency.length===2);assert.match(q(p,'#fa-status').textContent,/Wave 3.*105%/);
 q(p,'#fa-finish').click();await until(()=>save(p).season===2);
 assert.equal(q(p,'#free-agency').hidden,true);assert.equal(save(p).lineupRules,31);assert.equal(save(p).career[0].free_agency.at(-1).kind,'finish');
 const finished=save(p);p.dom.window.close();p=await page(finished);assert.equal(save(p).season,2);assert.ok(q(p,`#roster-groups [data-player-id="${id}"]`));p.dom.window.close();
 const beforeDraft={...checkpoint,version:38,lineupRules:28,week:16,playoffRound:null,draftChoices:null,dropped:[],rosterActions:[],trainingCamp:false};
 p=await page(beforeDraft);q(p,'#simulate-button').click();await until(()=>save(p).week===17);assert.equal(save(p).lineupRules,31);p.dom.window.close();
 const acceptedCamp={...checkpoint,version:38,lineupRules:28};p=await page(acceptedCamp);assert.equal(q(p,'#next-season').textContent,'Continue to Season 2');assert.equal(q(p,'#free-agency').hidden,true);p.dom.window.close();
 const corrupt={...signed,freeAgency:[{kind:'finish',player_id:''},{kind:'pass',player_id:''}]};
 // Frontend rejects malformed checkpoints without replacing the user's save.
 const dom=new JSDOM(html,{url:base,runScripts:'outside-only'});dom.window.localStorage.setItem(key,JSON.stringify(corrupt));dom.window.fetch=(url,init)=>fetch(new URL(url,base),init);dom.window.eval(script);await new Promise(r=>setTimeout(r,200));assert.equal(dom.window.localStorage.getItem(key),JSON.stringify(corrupt));dom.window.close();
 // New rules show destination pricing and retain the signed quote after reload.
 const modernRequest={...request,lineup_rules:34};
 const modernDraft=await api({...modernRequest,action:'draft',auto_draft:true});
 const modern=await api({...modernRequest,action:'free_agency',manual_picks:modernDraft.manual_picks});
 const premium=modern.free_agency.destination_premium;
 assert.ok(premium.basis_points>0&&premium.basis_points<=2000);
 p=await page({...checkpoint,version:41,lineupRules:34,trainingCamp:false,draftChoices:modernDraft.manual_picks,dropped:[],rosterActions:[],freeAgency:[]});
 assert.ok(q(p,'#fa-status').textContent.includes(`Team premium +${(premium.basis_points/100).toFixed(2)}%`));
 assert.match(q(p,'#fa-flow-guide').textContent,/weaker rosters or losing records/);
 const modernTarget=modern.free_agency.available.find(p=>p.affordable);
 const quotedRow=q(p,`[data-fa-id="${modernTarget.id}"]`).closest('tr');
 assert.equal(quotedRow.children[5].textContent,`$${(modernTarget.annual_salary/1e6).toFixed(2)}M`);
 q(p,`[data-fa-id="${modernTarget.id}"]`).click();await until(()=>save(p).freeAgency.length===1);
 const modernSave=save(p);p.dom.window.close();p=await page(modernSave);
 assert.equal(save(p).lineupRules,34);assert.match(q(p,'#fa-status').textContent,/Wave 2.*Team premium/);
 const after=await api({...modernRequest,action:'free_agency',manual_picks:modernDraft.manual_picks,free_agency:modernSave.freeAgency});
 assert.equal(after.profile.roster.find(p=>p.id===modernTarget.id).contract.annual_salary,modernTarget.annual_salary);
 assert.deepEqual(after.free_agency.destination_premium,premium);p.dom.window.close();
 // Seeded cap: draft, market and next-season UI agree before and after reload.
 const seededRequest={...request,lineup_rules:35};
 const seededDraft=await api({...seededRequest,action:'draft',auto_draft:true});
 const seededArgs={...seededRequest,manual_picks:seededDraft.manual_picks};
 const seededMarket=await api({...seededArgs,action:'free_agency'});
 const upcoming=seededMarket.profile.payroll;
 assert.ok(upcoming.cap>=204000000&&upcoming.cap<=220000000);
 assert.ok(upcoming.cap_growth_percent>=2&&upcoming.cap_growth_percent<=10);
 p=await page({...checkpoint,version:41,lineupRules:35,trainingCamp:false,draftChoices:seededDraft.manual_picks,dropped:[],rosterActions:[],freeAgency:[]});
 const capLabel=`$${(upcoming.cap/1e6).toFixed(2)}M cap`;
 assert.ok(q(p,'#payroll-status').textContent.includes(capLabel));
 assert.ok(q(p,'#payroll-status').textContent.includes(`Cap growth +${upcoming.cap_growth_percent.toFixed(2)}%`));
 assert.match(q(p,'#salary-growth-guide').textContent,/2–10%.*6%/);
 const seededSave=save(p);p.dom.window.close();p=await page(seededSave);
 assert.ok(q(p,'#payroll-status').textContent.includes(capLabel));p.dom.window.close();
 const seededActions=seededMarket.profile.roster.filter(p=>p.renewal_offer||p.contract_offer).map(p=>({kind:'drop',player_id:p.id}));
 seededActions.push({kind:'finish',player_id:''});
 const review=await api({...seededArgs,action:'free_agency',free_agency:seededActions});
 const pre=review.payroll_floor_adjustment?[{kind:'raise',player_id:review.payroll_floor_adjustment.player_id}]:[];
 const seededCamp=await api({...seededArgs,action:'camp',free_agency:seededActions,pre_camp_actions:pre});
 assert.equal(seededCamp.can_continue,true);
 p=await page({...seededSave,freeAgency:seededActions,preCampActions:pre,trainingCamp:true});
 q(p,'#next-season').click();await until(()=>save(p).season===2);
 assert.equal(save(p).lineupRules,35);assert.equal(save(p).career[0].lineup_rules,35);
 assert.ok(q(p,'#payroll-status').textContent.includes(capLabel));
 const seededNext=save(p);p.dom.window.close();p=await page(seededNext);
 assert.equal(save(p).lineupRules,35);assert.ok(q(p,'#payroll-status').textContent.includes(capLabel));p.dom.window.close();
 console.log('Free agency UI passed: entry, sorting/filtering, failure retry, duplicate-click guard, user-first signing, pool removal, pass, reload, finish/advance, next-season replay and corrupt-save preservation.');
}
(async()=>{const server=spawn(process.env.PYTHON||'python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8784'],{cwd:root,stdio:['ignore','pipe','pipe']});let logs='';server.stdout.on('data',d=>logs+=d);server.stderr.on('data',d=>logs+=d);try{for(let i=0;;i++){if(server.exitCode!==null)throw new Error(logs);try{if((await fetch(base+'/api/teams')).ok)break;}catch{}if(i===100)throw new Error(logs);await new Promise(r=>setTimeout(r,100));}try{await checks();}catch(error){console.error(logs);throw error;}}finally{server.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
