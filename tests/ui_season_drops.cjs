const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {spawn}=require('node:child_process'),{JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'..'),base='http://127.0.0.1:8805',key='arcade-league-save';
const html=fs.readFileSync(path.join(root,'app/static/index.html'),'utf8'),script=fs.readFileSync(path.join(root,'app/static/app.js'),'utf8');
async function until(check){for(let i=0;i<2000;i++){if(check())return;await new Promise(r=>setTimeout(r,10));}throw Error('Season drops UI timeout');}
const q=(p,s)=>p.d.querySelector(s),save=p=>JSON.parse(p.w.localStorage.getItem(key));
async function page(checkpoint){
 const dom=new JSDOM(html,{url:base,runScripts:'outside-only'}),w=dom.window,d=w.document,state={fail:false,calls:0};
 w.localStorage.setItem(key,JSON.stringify(checkpoint));w.HTMLElement.prototype.scrollIntoView=()=>{};w.scrollTo=()=>{};
 w.HTMLDialogElement.prototype.close=function(){this.open=false};w.HTMLDialogElement.prototype.showModal=function(){this.open=true};
 w.fetch=async(url,init)=>{if(init&&JSON.parse(init.body).action==='season_drop'){state.calls++;if(state.fail)return {ok:false,json:async()=>({detail:'Temporary release failure'})};}const r=await fetch(new URL(url,base),init);if(!r.ok)console.error(await r.clone().text(),init?.body);return r;};
 w.eval(script);const p={dom,w,d,state};await until(()=>/restored|could not/.test(q(p,'#save-status').textContent));assert.match(q(p,'#save-status').textContent,/restored/);return p;
}
async function checks(){
 let p=await page({version:51,welcomeDismissed:true,ownerUpdateDismissed:0,draftRounds:6,careerStartWeek:1,lineupChanges:[],contracts:false,gmExtensionRules:2,teamId:'seattle',runSeed:1234,season:1,week:3,lineupRules:50,developmentStart:1,rebuildTeam:'seattle',priorStandings:{},history:[],draftChoices:null,dropped:[],career:[],playoffRound:null});
 q(p,'#view-roster').click();assert.equal(q(p,'#roster-management').hidden,false);
 const record=q(p,'#season-record').textContent;
 const button=q(p,'#roster-groups [data-position="QB"] [data-drop-id]:not([disabled])');assert.ok(button);const id=button.dataset.dropId;
 button.click();assert.match(q(p,'#cut-confirm-text').textContent,/current roster/);q(p,'#cut-cancel').click();assert.equal(p.state.calls,0);
 q(p,`[data-drop-id="${id}"]`).click();p.state.fail=true;q(p,'#cut-confirm').click();await until(()=>!q(p,'#cut-error').hidden);assert.equal(save(p).seasonDrops,undefined);
 p.state.fail=false;q(p,'#cut-confirm').click();q(p,'#cut-confirm').click();await until(()=>save(p).seasonDrops?.length===1&&!q(p,'#simulate-button').disabled);
 assert.equal(p.state.calls,2);assert.equal(save(p).seasonDrops[0].week,4);assert.equal(q(p,`[data-player-id="${id}"]`),null);assert.equal(q(p,'#season-record').textContent,record);
 assert.equal(q(p,'#roster-groups [data-position="QB"] [data-drop-id]').disabled,true);
 let raw=save(p);p.dom.window.close();p=await page(raw);assert.equal(q(p,`[data-player-id="${id}"]`),null);assert.equal(q(p,'#season-record').textContent,record);
 q(p,'#simulate-button').click();await until(()=>{if(!q(p,'#error').hidden)throw Error(q(p,'#error').textContent);return save(p).week===4;});assert.equal(q(p,'#error').hidden,true);
 // Drop legal reserves until the hard total minimum, then every release is disabled.
 q(p,'#view-roster').click();
 while(p.d.querySelectorAll('#roster-groups .roster-player').length>31){
  const n=save(p).seasonDrops.length;q(p,'#roster-groups [data-drop-id]:not([disabled])').click();q(p,'#cut-confirm').click();await until(()=>save(p).seasonDrops.length===n+1);
 }
 assert.equal(q(p,'#roster-groups [data-drop-id]:not([disabled])'),null);
 raw=save(p);p.dom.window.close();p=await page(raw);q(p,'#view-roster').click();assert.equal(p.d.querySelectorAll('#roster-groups .roster-player').length,31);assert.equal(q(p,'#roster-groups [data-drop-id]:not([disabled])'),null);p.dom.window.close();
 console.log('Season drops UI passed: current-season confirmation, cancel/failure/retry, duplicate guard, position and roster minimums, effective weeks, retained record, future simulation, and reload.');
}
(async()=>{const server=spawn(process.env.PYTHON||'python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8805'],{cwd:root,stdio:['ignore','pipe','pipe']});let logs='';server.stdout.on('data',d=>logs+=d);server.stderr.on('data',d=>logs+=d);try{for(let i=0;;i++){if(server.exitCode!==null)throw Error(logs);try{if((await fetch(base+'/api/teams')).ok)break;}catch{}if(i===100)throw Error(logs);await new Promise(r=>setTimeout(r,100));}try{await checks();}catch(e){console.error(logs);throw e;}}finally{if(process.exitCode)console.error(logs);server.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
