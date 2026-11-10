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
 assert.equal(q(p,'#free-agency').hidden,true);assert.equal(save(p).lineupRules,30);assert.equal(save(p).career[0].free_agency.at(-1).kind,'finish');
 const finished=save(p);p.dom.window.close();p=await page(finished);assert.equal(save(p).season,2);assert.ok(q(p,`#roster-groups [data-player-id="${id}"]`));p.dom.window.close();
 const beforeDraft={...checkpoint,version:38,lineupRules:28,week:16,playoffRound:null,draftChoices:null,dropped:[],rosterActions:[],trainingCamp:false};
 p=await page(beforeDraft);q(p,'#simulate-button').click();await until(()=>save(p).week===17);assert.equal(save(p).lineupRules,30);p.dom.window.close();
 const acceptedCamp={...checkpoint,version:38,lineupRules:28};p=await page(acceptedCamp);assert.equal(q(p,'#next-season').textContent,'Continue to Season 2');assert.equal(q(p,'#free-agency').hidden,true);p.dom.window.close();
 const corrupt={...signed,freeAgency:[{kind:'finish',player_id:''},{kind:'pass',player_id:''}]};
 // Frontend rejects malformed checkpoints without replacing the user's save.
 const dom=new JSDOM(html,{url:base,runScripts:'outside-only'});dom.window.localStorage.setItem(key,JSON.stringify(corrupt));dom.window.fetch=(url,init)=>fetch(new URL(url,base),init);dom.window.eval(script);await new Promise(r=>setTimeout(r,200));assert.equal(dom.window.localStorage.getItem(key),JSON.stringify(corrupt));dom.window.close();
 console.log('Free agency UI passed: entry, sorting/filtering, failure retry, duplicate-click guard, user-first signing, pool removal, pass, reload, finish/advance, next-season replay and corrupt-save preservation.');
}
(async()=>{const server=spawn(process.env.PYTHON||'python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8784'],{cwd:root,stdio:['ignore','pipe','pipe']});let logs='';server.stdout.on('data',d=>logs+=d);server.stderr.on('data',d=>logs+=d);try{for(let i=0;;i++){if(server.exitCode!==null)throw new Error(logs);try{if((await fetch(base+'/api/teams')).ok)break;}catch{}if(i===100)throw new Error(logs);await new Promise(r=>setTimeout(r,100));}try{await checks();}catch(error){console.error(logs);throw error;}}finally{server.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
