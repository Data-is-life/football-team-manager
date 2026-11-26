const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {spawn,execFileSync}=require('node:child_process'),{JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'..'),base='http://127.0.0.1:8796',key='arcade-league-save';
const html=fs.readFileSync(path.join(root,'app/static/index.html'),'utf8'),script=require('./historical-save-fixtures.cjs').allowHistoricalFixtures(fs.readFileSync(path.join(root,'app/static/app.js'),'utf8'));
const fixture=JSON.parse(execFileSync(process.env.PYTHON||'python',['tests/trade_fixtures.py'],{cwd:root,env:{...process.env,PYTHONPATH:root},encoding:'utf8'}));
const q=(p,s)=>p.d.querySelector(s),save=p=>JSON.parse(p.w.localStorage.getItem(key));
async function until(check){for(let i=0;i<4000;i++){if(check())return;await new Promise(r=>setTimeout(r,10));}throw Error('Trade UI timeout');}
async function page(checkpoint,valid=true){
 const dom=new JSDOM(html,{url:base,runScripts:'outside-only'}),w=dom.window,d=w.document,state={calls:0,fail:false,tradeRequests:[]};
 w.localStorage.setItem(key,JSON.stringify(checkpoint));w.HTMLElement.prototype.scrollIntoView=()=>{};w.scrollTo=()=>{};
 w.HTMLDialogElement.prototype.close=function(){this.open=false};w.HTMLDialogElement.prototype.showModal=function(){this.open=true};
 w.fetch=(url,init)=>{state.calls++;if(init&&JSON.parse(init.body).action==='trades')state.tradeRequests.push(JSON.parse(init.body));if(state.fail&&init&&JSON.parse(init.body).action==='trades')return Promise.resolve({ok:false,json:async()=>({detail:'Temporary trade failure'})});return fetch(new URL(url,base),init)};
 w.eval(script);const p={dom,w,d,state};await until(()=>/restored|could not/.test(q(p,'#save-status').textContent));assert.match(q(p,'#save-status').textContent,valid?/restored/:/could not/);return p;
}
async function checks(){
 let p=await page(fixture.checkpoint);
 assert.equal(q(p,'#view-trades').hidden,true);assert.equal(q(p,'#panel-trades').hidden,true);
 assert.equal(q(p,'#panel-roster').hidden,false);
 const before=p.w.localStorage.getItem(key),count=p.state.calls;
 q(p,'#view-trades').click();assert.equal(q(p,'#trade-preview'),null);assert.equal(q(p,'#trade-confirm'),null);assert.equal(q(p,'#trade-finish'),null);
 assert.equal(p.state.calls,count);assert.equal(p.w.localStorage.getItem(key),before);
 p.dom.window.close();
 // Existing accepted offers remain part of the checkpoint, without exposing new offers.
 const proposal=fixture.proposal;
 const checkpoint={...fixture.checkpoint,tradeActions:[proposal]};
 p=await page(checkpoint);
 assert.equal(q(p,'#view-trades').hidden,true);assert.equal(q(p,'#panel-trades').hidden,true);
 assert.ok(q(p,`#roster-groups [data-player-id="${proposal.receive_id}"]`));
 // Invalid saved actions are rejected without overwriting the checkpoint.
 const bad={...checkpoint,tradeActions:[{kind:'swap',other_team:'',give_id:'bad',receive_id:''}]};
 const broken=await page(bad,false);assert.deepEqual(save(broken),bad);broken.dom.window.close();
 const savedBefore=p.w.localStorage.getItem(key);p.state.fail=true;q(p,'#next-season').click();
 await until(()=>p.state.tradeRequests.length===1&&!q(p,'#next-season').disabled);
 assert.equal(p.w.localStorage.getItem(key),savedBefore);assert.equal(q(p,'#panel-trades').hidden,true);
 p.state.fail=false;q(p,'#next-season').click();q(p,'#next-season').click();await until(()=>save(p).season===2);
 assert.equal(p.state.tradeRequests.length,2);assert.ok(p.state.tradeRequests.every(r=>!r.trade_proposal&&r.trade_actions.at(-1).kind==='finish'));
 assert.equal(save(p).career[0].trade_actions.length,2);assert.equal(save(p).career[0].trade_actions[1].kind,'finish');
 assert.equal(q(p,'#view-trades').hidden,true);assert.equal(save(p).tradeActions,undefined);
 const next=save(p);p.dom.window.close();p=await page(next);
 assert.ok(q(p,`#roster-groups [data-player-id="${proposal.receive_id}"]`));assert.equal(save(p).career[0].trade_actions.length,2);p.dom.window.close();
 console.log('Trading pause UI passed: hidden navigation and controls, blocked offer events, legacy accepted-swap restore, invalid-save preservation, start-season failure/retry and duplicate guards, unchanged contracts and Season 2 replay.');
}
(async()=>{const server=spawn(process.env.PYTHON||'python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8796'],{cwd:root,stdio:['ignore','pipe','pipe']});let logs='';server.stdout.on('data',d=>logs+=d);server.stderr.on('data',d=>logs+=d);try{for(let i=0;;i++){if(server.exitCode!==null)throw Error(logs);try{if((await fetch(base+'/api/teams')).ok)break;}catch{}if(i===100)throw Error(logs);await new Promise(r=>setTimeout(r,100));}await checks();}finally{server.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
