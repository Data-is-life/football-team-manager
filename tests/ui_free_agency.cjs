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
 w.fetch=async(url,init)=>{const body=init&&JSON.parse(init.body);if(body?.action==='free_agency'){state.calls++;if(state.fail)return {ok:false,json:async()=>({detail:'Market temporarily unavailable'})};}const response=await fetch(new URL(url,base),init);if(!response.ok) console.error('Free agency test API error:',url,await response.clone().text());if(response.ok&&body?.action==='free_agency')state.market=await response.clone().json();return response;};
 w.eval(script);const p={dom,w,d,state};await until(()=>/restored|could not/.test(q(p,'#save-status').textContent));assert.match(q(p,'#save-status').textContent,/restored/);return p;
}
function checkMarketTab(p) {
 const tab=q(p,'#view-free-agency'),panel=q(p,'#panel-free-agency');
 assert.equal(tab.hidden,false);assert.equal(tab.getAttribute('aria-controls'),panel.id);
 assert.equal(panel.getAttribute('aria-labelledby'),tab.id);
 assert.ok(panel.contains(q(p,'#free-agency')));
 tab.click();assert.equal(panel.hidden,false);
 assert.equal(p.d.querySelectorAll('.view-panel:not([hidden])').length,1);
 const checkpoint=raw(p),calls=p.state.calls;
 q(p,'#fa-review-own').click();assert.equal(q(p,'#panel-roster').hidden,false);
 assert.equal(panel.hidden,true);assert.equal(q(p,'#roster-fa-return').hidden,false);
 q(p,'#roster-fa-return').click();assert.equal(panel.hidden,false);
 assert.equal(tab.getAttribute('aria-selected'),'true');
 q(p,'#view-roster').dispatchEvent(new p.w.KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}));
 assert.equal(tab.getAttribute('aria-selected'),'true');
 assert.equal(raw(p),checkpoint);assert.equal(p.state.calls,calls);
}
function checkFreeAgentBadge(p, id) {
 q(p,'#roster-stats-button').click();
 const rows=p.d.querySelectorAll(`#roster-groups [data-player-id="${id}"]`);
 assert.ok(rows.length>=2,'Rating and stats rows exist');
 for(const row of rows){const badge=row.querySelector('.free-agent-badge');if(row.querySelector('.rookie-badge')?.textContent==='UDFA'){assert.equal(badge,null);}else{assert.ok(badge);assert.equal(badge.textContent,'F');assert.equal(badge.getAttribute('aria-label'),'Free-agent signing');}}
 q(p,'#roster-ratings-button').click();
}
function checkRankings(p,profile){
 const rows=[...p.d.querySelectorAll('#rankings-rows tr')];assert.equal(rows.length,30);
 const expected=new Map(profile.rankings.map(row=>[row.team.id,row.ratings]));
 for(const row of rows){const ratings=expected.get(row.dataset.teamId);assert.deepEqual([...row.children].slice(2).map(c=>c.textContent),[ratings.overall,ratings.offense,ratings.defense].map(v=>String(Math.round(v))));}
 assert.equal(q(p,'#overall-rating').textContent,String(Math.round((profile.ratings.offense+profile.ratings.defense)/2)));
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
 checkMarketTab(p);
 assert.equal(q(p,'#free-agency').hidden,false);assert.match(q(p,'#fa-status').textContent,/Wave 1.*120%.*Cap space/);
 const before=raw(p);q(p,'#fa-sort').value='potential_rating';q(p,'#fa-sort').dispatchEvent(new p.w.Event('change'));
 const values=[...p.d.querySelectorAll('#fa-players tr')].map(row=>Number(row.children[4].textContent));assert.deepEqual(values,[...values].sort((a,b)=>b-a));assert.equal(raw(p),before);
 q(p,'#fa-position').value='QB';q(p,'#fa-position').dispatchEvent(new p.w.Event('change'));assert.ok([...p.d.querySelectorAll('#fa-players tr')].every(row=>row.children[1].textContent==='QB'));
 q(p,'#fa-position').value='';q(p,'#fa-position').dispatchEvent(new p.w.Event('change'));
 const filterSave=raw(p),filterCalls=p.state.calls;
 const pool=p.state.market.free_agency??p.state.market;
 const age=pool.available[0].age;
 for(const id of ['fa-age-min','fa-age-max']){q(p,'#'+id).value=String(age);q(p,'#'+id).dispatchEvent(new p.w.Event('input'));}
 q(p,'#fa-cap-space').value='fits';q(p,'#fa-cap-space').dispatchEvent(new p.w.Event('change'));
 const expected=pool.available.filter(player=>player.age===age&&player.annual_salary<=pool.profile.payroll.cap_space).map(player=>player.id).sort();
 assert.deepEqual([...p.d.querySelectorAll('#fa-players [data-fa-id]')].map(button=>button.dataset.faId).sort(),expected);
 assert.equal(raw(p),filterSave);assert.equal(p.state.calls,filterCalls);
 for(const id of ['fa-age-min','fa-age-max']){q(p,'#'+id).value='';q(p,'#'+id).dispatchEvent(new p.w.Event('input'));}
 q(p,'#fa-cap-space').value='';q(p,'#fa-cap-space').dispatchEvent(new p.w.Event('change'));
 const button=q(p,'#fa-players button:not([disabled])');assert.ok(button);const id=button.dataset.faId;
 const offer=pool.available.find(player=>player.id===id);
 const pay=pool.profile.payroll, money=value=>`$${(value/1e6).toFixed(2)}M`;
 button.click();
 const confirmation=q(p,'#fa-confirmation'),confirm=q(p,'#fa-confirm');
 assert.equal(confirmation.hidden,false);
 assert.equal(q(p,`[data-fa-id="${id}"]`).closest('tr').nextElementSibling,confirmation.closest('tr'));
 assert.equal(q(p,'#fa-confirm-text').textContent,`Sign ${offer.name} (${offer.position}) for ${money(offer.annual_salary)}/year, ${offer.years} years, starting Season 2?`);
 assert.deepEqual([...q(p,'#fa-impact').children].map(line=>line.textContent),[
  `Current payroll: ${money(pay.total)}`,`Payroll after signing: ${money(pay.total+offer.annual_salary)}`,
  `Salary cap: ${money(pay.cap)}`,`Cap space after signing: ${money(pay.cap_space-offer.annual_salary)}`
 ]);
 assert.equal(p.d.activeElement,confirm);
 q(p,'#fa-cancel').click();assert.equal(confirmation.hidden,true);assert.equal(p.d.activeElement.dataset.faId,id);
 assert.equal(raw(p),before);assert.equal(p.state.calls,filterCalls);
 q(p,`[data-fa-id="${id}"]`).click();
 q(p,'#fa-age-max').value=String(offer.age-1);q(p,'#fa-age-max').dispatchEvent(new p.w.Event('input'));
 assert.equal(confirmation.hidden,true);assert.equal(p.state.calls,filterCalls);
 q(p,'#fa-age-max').value='';q(p,'#fa-age-max').dispatchEvent(new p.w.Event('input'));
 p.state.fail=true;q(p,`[data-fa-id="${id}"]`).click();confirm.click();
 await until(()=>!q(p,'#fa-error').hidden);assert.equal(raw(p),before);assert.equal(confirmation.hidden,false);
 p.state.fail=false;confirm.click();confirm.click();await until(()=>save(p).freeAgency.length===1);
 assert.equal(p.state.calls,filterCalls+2);assert.equal(confirmation.hidden,true);
 assert.equal(save(p).freeAgency[0].player_id,id);assert.equal(q(p,`[data-fa-id="${id}"]`),null);assert.ok(q(p,`#roster-groups [data-player-id="${id}"]`));
 checkFreeAgentBadge(p,id);
 assert.match(q(p,'#fa-status').textContent,/Wave 2.*110%/);const signed=save(p);p.dom.window.close();p=await page(signed);
 checkMarketTab(p);
 assert.match(q(p,'#fa-status').textContent,/Wave 2/);assert.ok(q(p,`#roster-groups [data-player-id="${id}"]`));checkFreeAgentBadge(p,id);
 q(p,'#fa-pass').click();await until(()=>save(p).freeAgency.length===2);assert.match(q(p,'#fa-status').textContent,/Wave 3.*105%/);
 q(p,'#fa-finish').click();await until(()=>save(p).season===2);
 assert.equal(q(p,'#free-agency').hidden,true);assert.equal(save(p).lineupRules,31);assert.equal(save(p).career[0].free_agency.at(-1).kind,'finish');
 const finished=save(p);p.dom.window.close();p=await page(finished);assert.equal(save(p).season,2);assert.ok(q(p,`#roster-groups [data-player-id="${id}"]`));checkFreeAgentBadge(p,id);p.dom.window.close();
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
 q(p,`[data-fa-id="${modernTarget.id}"]`).click();q(p,'#fa-confirm').click();await until(()=>save(p).freeAgency.length===1);
 const modernSave=save(p);p.dom.window.close();p=await page(modernSave);
 assert.equal(save(p).lineupRules,34);assert.match(q(p,'#fa-status').textContent,/Wave 2.*Team premium/);
 const after=await api({...modernRequest,action:'free_agency',manual_picks:modernDraft.manual_picks,free_agency:modernSave.freeAgency});
 assert.equal(after.profile.roster.find(p=>p.id===modernTarget.id).contract.annual_salary,modernTarget.annual_salary);
 assert.deepEqual(after.free_agency.destination_premium,premium);checkRankings(p,after.profile);p.dom.window.close();
 // Seeded cap: draft, market and next-season UI agree before and after reload.
 for (const salaryRules of [36,37,38,39,40,41]) {
 const seededRequest={...request,lineup_rules:salaryRules};
 const seededDraft=await api({...seededRequest,action:'draft',auto_draft:true});
 if(salaryRules===40) assert.ok(seededDraft.picks.every(p=>p.player.age>=21&&p.player.age<=23));
 const seededArgs={...seededRequest,manual_picks:seededDraft.manual_picks};
 const seededMarket=await api({...seededArgs,action:'free_agency'});
 if(salaryRules===40) assert.ok(seededMarket.free_agency.available.filter(p=>p.id.startsWith('rookie-1234-2-')).every(p=>p.age>=21&&p.age<=23));
 const upcoming=seededMarket.profile.payroll;
 assert.ok(upcoming.cap>=204000000&&upcoming.cap<=220000000);
 assert.ok(upcoming.cap_growth_percent>=2&&upcoming.cap_growth_percent<=10);
 p=await page({...checkpoint,version:41,lineupRules:salaryRules,trainingCamp:false,draftChoices:seededDraft.manual_picks,dropped:[],rosterActions:[],freeAgency:[]});
 checkMarketTab(p);
 const capLabel=`$${(upcoming.cap/1e6).toFixed(2)}M cap`;
 assert.ok(q(p,'#payroll-status').textContent.includes(capLabel));
 assert.ok(q(p,'#payroll-status').textContent.includes(`Cap growth +${upcoming.cap_growth_percent.toFixed(2)}%`));
 assert.match(q(p,'#salary-growth-guide').textContent,/2–10%.*6%/);
 assert.match(q(p,'#salary-growth-guide').textContent,/QB 21%.*LB 16%.*K 2.5%.*Wave pricing/);
 if(salaryRules===41){
  // Server-supplied affordability must block confirmation, not offer inspection.
  const candidate=seededMarket.profile.roster.find(v=>v.renewal_offer&&v.renewal_offer.annual_change>1000000);assert.ok(candidate);
  const before=raw(p),calls=p.state.calls,money=v=>`$${(v/1e6).toFixed(2)}M`;
  q(p,'#fa-review-own').click();
  for(const total of [upcoming.cap+1000000,upcoming.cap-1000000]){
   const profile={...seededMarket.profile,payroll:{...upcoming,total,over_cap:Math.max(0,total-upcoming.cap),cap_space:upcoming.cap-total},roster:seededMarket.profile.roster.map(v=>v.id===candidate.id?{...v,renewal_offer:{...v.renewal_offer,affordable:false}}:v)};
   p.w.renderTeamProfile(profile);p.w.renderCuts();
   const button=q(p,`[data-resign-id="${candidate.id}"]`);assert.ok(button);assert.equal(button.disabled,false);button.click();
   assert.equal(q(p,'#cut-confirmation').hidden,false);assert.equal(q(p,'#cut-impact').hidden,false);
   const projected=total-candidate.contract.annual_salary+candidate.renewal_offer.annual_salary;
   assert.ok(q(p,'#cut-confirm-text').textContent.includes(money(candidate.renewal_offer.annual_salary)+'/year'));
   const impact=q(p,'#cut-impact').textContent;
   assert.ok(impact.includes('Current payroll: '+money(total)));assert.ok(impact.includes('Payroll after re-signing: '+money(projected)));
   assert.ok(impact.includes('Over cap after re-signing: '+money(projected-upcoming.cap)));assert.match(impact,/Clear cap space before confirming/);
   if(total>upcoming.cap)assert.ok(impact.includes('Currently over cap: '+money(total-upcoming.cap)));
   assert.equal(q(p,'#cut-confirm').disabled,true);assert.equal(p.d.activeElement.id,'cut-cancel');
   q(p,'#cut-confirm').dispatchEvent(new p.w.Event('click',{bubbles:true}));
   assert.equal(p.state.calls,calls);assert.equal(raw(p),before);
   q(p,'#cut-cancel').click();assert.equal(q(p,'#cut-confirmation').hidden,true);assert.equal(raw(p),before);
  }
  p.w.renderTeamProfile(seededMarket.profile);p.w.renderCuts();
  q(p,`[data-resign-id="${candidate.id}"]`).click();
  assert.equal(q(p,'#cut-confirm').disabled,false);assert.match(q(p,'#cut-impact').textContent,/Cap space after re-signing:/);
  q(p,'#cut-cancel').click();assert.equal(p.state.calls,calls);assert.equal(raw(p),before);
 }
 const seededSave=save(p);p.dom.window.close();p=await page(seededSave);
 assert.ok(q(p,'#payroll-status').textContent.includes(capLabel));p.dom.window.close();
 const seededActions=seededMarket.profile.roster.filter(p=>p.renewal_offer||p.contract_offer).map(p=>({kind:'drop',player_id:p.id}));
 seededActions.push({kind:'finish',player_id:''});
 const review=await api({...seededArgs,action:'free_agency',free_agency:seededActions});
 const pre=review.payroll_floor_adjustment?[{kind:'raise',player_id:review.payroll_floor_adjustment.player_id}]:[];
 const seededCamp=await api({...seededArgs,action:'camp',free_agency:seededActions,pre_camp_actions:pre});
 assert.equal(seededCamp.can_continue,salaryRules<41);
 p=await page({...seededSave,freeAgency:seededActions,preCampActions:pre,trainingCamp:true});
 checkRankings(p,seededCamp.profile);
 q(p,'#next-season').click();await until(()=>save(p).season===2);
 assert.equal(q(p,'#view-free-agency').hidden,true);assert.equal(q(p,'#roster-fa-return').hidden,true);
 assert.equal(save(p).lineupRules,salaryRules);assert.equal(save(p).career[0].lineup_rules,salaryRules);checkRankings(p,seededCamp.profile);
 assert.ok(q(p,'#payroll-status').textContent.includes(capLabel));
 const seededNext=save(p);p.dom.window.close();p=await page(seededNext);
 assert.equal(save(p).lineupRules,salaryRules);assert.ok(q(p,'#payroll-status').textContent.includes(capLabel));p.dom.window.close();
 if(salaryRules===37) {const guide=await page(seededNext);assert.match(q(guide,'#salary-curve-guide').textContent,/doubling tiers.*69.*3.8.*85.*12/);assert.match(q(guide,'#re-signing-guide').textContent,/current.*potential.*2 years/);assert.doesNotMatch(q(guide,'#salary-demand-guide').textContent,/current rating and age/);guide.dom.window.close();}
 const badgesPage=await page(seededNext);
 function badgeLabels(player){const cell=badgesPage.d.createElement('td');badgesPage.w.addRookieBadge(cell,player);badgesPage.w.addFreeAgentBadge(cell,player);return [...cell.querySelectorAll('span')].map(b=>b.textContent);}
 assert.deepEqual(badgeLabels({id:'veteran',contract:{category:'young'}}),[]);
 assert.deepEqual(badgeLabels({id:'veteran',contract_offer:{category:'replacement'}}),[]);
 assert.deepEqual(badgeLabels({id:'veteran',contract:{category:'free_agent'}}),['F']);
 assert.deepEqual(badgeLabels({id:'rookie-1234-2-999',contract:{category:'free_agent'}}),['R','F']);
 assert.deepEqual(badgeLabels({id:'rookie-1234-2-999',rookie_origin:'undrafted',contract:{category:'free_agent'}}),['UDFA']);
 assert.deepEqual(badgeLabels({id:'rookie-1234-2-999',rookie_origin:'released',contract:{category:'free_agent'}}),['R','F']);
 assert.deepEqual(badgeLabels({id:'rookie-1234-2-999'}),['R']);
 assert.deepEqual(badgeLabels({id:'rookie-1234-1-999',rookie_origin:'undrafted',contract:{category:'free_agent'}}),['F']);
 const cpuSigning=after.free_agency.transactions.find(t=>t.team.id!=='seattle');assert.ok(cpuSigning);
 const scouting=await api({...modernRequest,action:'free_agency',manual_picks:modernDraft.manual_picks,free_agency:modernSave.freeAgency,view_team:cpuSigning.team.id});
 const scout=badgesPage.d.createElement('div');scout.append(...badgesPage.w.createRosterGroups(scouting.profile,false));
 assert.ok(scout.querySelector(`[data-player-id="${cpuSigning.player_id}"] .free-agent-badge`));
 badgesPage.dom.window.close();
 }
 console.log('Free agency UI passed: entry, sorting/filtering, failure retry, duplicate-click guard, user-first signing, pool removal, pass, reload, finish/advance, next-season replay and corrupt-save preservation.');
}
(async()=>{const server=spawn(process.env.PYTHON||'python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8784'],{cwd:root,stdio:['ignore','pipe','pipe']});let logs='';server.stdout.on('data',d=>logs+=d);server.stderr.on('data',d=>logs+=d);try{for(let i=0;;i++){if(server.exitCode!==null)throw new Error(logs);try{if((await fetch(base+'/api/teams')).ok)break;}catch{}if(i===100)throw new Error(logs);await new Promise(r=>setTimeout(r,100));}try{await checks();}catch(error){console.error(logs);throw error;}}finally{server.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
