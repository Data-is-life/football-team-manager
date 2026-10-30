const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {spawn}=require('node:child_process'),{JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'..'),base='http://127.0.0.1:8776',key='arcade-league-save';
const html=fs.readFileSync(path.join(root,'app/static/index.html'),'utf8'),script=fs.readFileSync(path.join(root,'app/static/app.js'),'utf8');
const checkpoint=JSON.parse(fs.readFileSync(path.join(root,'benchmarks/year4.json'),'utf8'));
async function until(check){for(let i=0;i<2000;i++){if(check())return;await new Promise(r=>setTimeout(r,10))}throw new Error('Restore UI state timed out')}
const q=(p,s)=>p.d.querySelector(s),raw=p=>p.w.localStorage.getItem(key);
function page({hold=false,fail=null}={}){
 const dom=new JSDOM(html,{url:base,runScripts:'outside-only'}),w=dom.window,d=w.document,state={actions:[],profileReady:false,fail};
 w.localStorage.setItem(key,JSON.stringify(checkpoint));w.HTMLElement.prototype.scrollIntoView=()=>{};
 w.HTMLDialogElement.prototype.close=function(){this.open=false};w.HTMLDialogElement.prototype.showModal=function(){this.open=true};
 let release;const gate=hold?new Promise(r=>release=r):Promise.resolve();state.release=release;
 w.fetch=async(url,init)=>{
  const action=init?JSON.parse(init.body).action:null;
  if(action){state.actions.push(action);if(action==='profile')await gate;else assert.equal(state.profileReady,true,'Dependent endpoints must wait for career reconstruction');}
  if(action&&state.fail===action)return {ok:false,json:async()=>({detail:'Injected restore failure'})};
  const response=await fetch(new URL(url,base),init);
  return {ok:response.ok,json:async()=>{const data=await response.json();if(action==='profile')state.profileReady=true;return data}};
 };
 w.eval(script);return {dom,w,d,state};
}
function snapshot(p){return ['#team-name','#season-record','#roster-groups','#schedule','#playoff-bracket','#draft-picks','#gm-regular'].map(id=>q(p,id).textContent)}
async function checks(){
 let p=page({hold:true});await until(()=>p.state.actions.includes('profile'));
 assert.deepEqual(p.state.actions,['profile']);assert.equal(raw(p),JSON.stringify(checkpoint));assert.equal(q(p,'#schedule-section').hidden,true);
 p.state.release();await until(()=>/restored/.test(q(p,'#save-status').textContent));
 assert.deepEqual(p.state.actions,['profile','week','playoffs','cuts']);assert.equal(raw(p),JSON.stringify(checkpoint));
 const expected=snapshot(p);assert.equal(p.d.querySelectorAll('#roster-groups .roster-player').length,38);p.dom.window.close();
 for(const action of ['profile','week']){
  p=page({fail:action});await until(()=>/could not be loaded/.test(q(p,'#save-status').textContent));
  assert.equal(raw(p),JSON.stringify(checkpoint));assert.equal(q(p,'#schedule-section').hidden,true);assert.equal(q(p,'#resume-save').hidden,false);
  if(action==='profile')assert.deepEqual(p.state.actions,['profile'],'No dependent endpoint should start after a failed profile');
  p.state.fail=null;q(p,'#resume-save').click();await until(()=>/restored/.test(q(p,'#save-status').textContent));
  assert.deepEqual(snapshot(p),expected);assert.equal(raw(p),JSON.stringify(checkpoint));p.dom.window.close();
 }
 console.log('Restore sequencing UI checks passed: one initial career reconstruction, dependent endpoints wait, complete draft/cuts replay, immutable checkpoint, atomic failure, retry, identical rosters/results/stats/history, and no progress reset.');
}
(async()=>{const server=spawn(process.env.PYTHON||'python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8776'],{cwd:root,stdio:['ignore','pipe','pipe']});let logs='';server.stdout.on('data',d=>logs+=d);server.stderr.on('data',d=>logs+=d);try{for(let i=0;;i++){if(server.exitCode!==null)throw new Error(logs);try{if((await fetch(base+'/api/teams')).ok)break}catch{}if(i===100)throw new Error(logs);await new Promise(r=>setTimeout(r,100))}await checks()}finally{server.kill()}})().catch(e=>{console.error(e);process.exitCode=1});
