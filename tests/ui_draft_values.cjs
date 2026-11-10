const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {spawn}=require('node:child_process'),{JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'..'),base='http://127.0.0.1:8785',key='arcade-league-save';
const html=fs.readFileSync(path.join(root,'app/static/index.html'),'utf8'),script=fs.readFileSync(path.join(root,'app/static/app.js'),'utf8');
const q=(p,s)=>p.d.querySelector(s),raw=p=>p.w.localStorage.getItem(key),save=p=>JSON.parse(raw(p));
async function until(check){for(let i=0;i<3000;i++){if(check())return;await new Promise(r=>setTimeout(r,10));}throw new Error('Draft values UI timed out');}
async function page(checkpoint){
 const dom=new JSDOM(html,{url:base,runScripts:'outside-only'}),w=dom.window,d=w.document,state={calls:0,board:null};
 w.localStorage.setItem(key,JSON.stringify(checkpoint));w.HTMLElement.prototype.scrollIntoView=()=>{};w.scrollTo=()=>{};
 w.HTMLDialogElement.prototype.close=function(){this.open=false};w.HTMLDialogElement.prototype.showModal=function(){this.open=true};
 w.fetch=async(url,init)=>{state.calls++;const response=await fetch(new URL(url,base),init);if(init&&(JSON.parse(init.body).action==='draft'||url.startsWith('/api/draft/'))&&response.ok)state.board=await response.clone().json();return response;};
 w.eval(script);const p={dom,w,d,state};await until(()=>/restored|could not/.test(q(p,'#save-status').textContent));assert.match(q(p,'#save-status').textContent,/restored/);return p;
}
function sortedIds(p,sort,position=''){
 const value=p=>sort==='value'?p.draft_value:sort==='current'?p.current_rating:p.potential_rating;
 const avg=p=>(p.current_rating+p.potential_rating)/2;
 return [...p.state.board.available].sort((a,b)=>value(b)-value(a)||(sort==='potential'?b.current_rating-a.current_rating:avg(b)-avg(a))||a.id.localeCompare(b.id)).filter(p=>!position||p.position===position).map(p=>p.id);
}
const rowIds=p=>[...p.d.querySelectorAll('#draft-prospects tr')].map(r=>r.dataset.prospectId);
async function checks(){
 const checkpoint={version:40,welcomeDismissed:true,ownerUpdateDismissed:0,draftRounds:6,careerStartWeek:17,lineupChanges:[],contracts:false,teamId:'seattle',runSeed:1234,season:1,week:17,lineupRules:30,developmentStart:1,rebuildTeam:'seattle',priorStandings:{},history:[],draftChoices:null,dropped:[],career:[],playoffRound:4};
 let p=await page(checkpoint);q(p,'#draft-button').click();await until(()=>Array.isArray(save(p).draftChoices));
 assert.equal(q(p,'#draft-sort').value,'value');assert.deepEqual(rowIds(p),sortedIds(p,'value'));
 const calls=p.state.calls,choices=JSON.stringify(save(p).draftChoices),available=JSON.stringify(p.state.board.available);
 for(const mode of ['potential','current','value','potential']){
  q(p,'#draft-sort').value=mode;q(p,'#draft-sort').dispatchEvent(new p.w.Event('change'));
  assert.deepEqual(rowIds(p),sortedIds(p,mode));assert.equal(p.state.calls,calls);assert.equal(JSON.stringify(save(p).draftChoices),choices);assert.equal(JSON.stringify(p.state.board.available),available);
 }
 q(p,'#draft-position').value='QB';q(p,'#draft-position').dispatchEvent(new p.w.Event('change'));assert.deepEqual(rowIds(p),sortedIds(p,'potential','QB'));
 const selected=save(p);p.dom.window.close();p=await page(selected);assert.equal(q(p,'#draft-sort').value,'potential');assert.equal(q(p,'#draft-position').value,'QB');assert.deepEqual(rowIds(p),sortedIds(p,'potential','QB'));
 const target=q(p,'#draft-prospects [data-draft-id]').dataset.draftId;q(p,'#draft-prospects [data-draft-id]').click();await until(()=>save(p).draftChoices.length===1);assert.equal(save(p).draftChoices[0],target);assert.equal(save(p).draftSort,'potential');
 const accepted={...save(p),version:39,lineupRules:29};p.dom.window.close();p=await page(accepted);assert.equal(save(p).lineupRules,29);assert.equal(q(p,'#draft-sort').value,'potential');assert.equal(save(p).draftChoices[0],target);p.dom.window.close();
 console.log('Draft value UI passed: three sorts, tiebreaks, position filter, read-only ordering, preserved available payload, selection/reload and accepted legacy-draft rules.');
}
(async()=>{const server=spawn(process.env.PYTHON||'python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8785'],{cwd:root,stdio:['ignore','pipe','pipe']});let logs='';server.stdout.on('data',d=>logs+=d);server.stderr.on('data',d=>logs+=d);try{for(let i=0;;i++){if(server.exitCode!==null)throw new Error(logs);try{if((await fetch(base+'/api/teams')).ok)break;}catch{}if(i===100)throw new Error(logs);await new Promise(r=>setTimeout(r,100));}try{await checks();}catch(error){console.error(logs);throw error;}}finally{server.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
