const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {spawn,execFileSync}=require('node:child_process'),{JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'..'),base='http://127.0.0.1:8796',key='arcade-league-save';
const html=fs.readFileSync(path.join(root,'app/static/index.html'),'utf8'),script=fs.readFileSync(path.join(root,'app/static/app.js'),'utf8');
const fixture=JSON.parse(execFileSync(process.env.PYTHON||'python',['tests/trade_fixtures.py'],{cwd:root,env:{...process.env,PYTHONPATH:root},encoding:'utf8'}));
const q=(p,s)=>p.d.querySelector(s),save=p=>JSON.parse(p.w.localStorage.getItem(key));
async function until(check){for(let i=0;i<4000;i++){if(check())return;await new Promise(r=>setTimeout(r,10));}throw Error('Trade UI timeout');}
async function page(checkpoint,valid=true){
 const dom=new JSDOM(html,{url:base,runScripts:'outside-only'}),w=dom.window,d=w.document,state={calls:0,fail:false};
 w.localStorage.setItem(key,JSON.stringify(checkpoint));w.HTMLElement.prototype.scrollIntoView=()=>{};w.scrollTo=()=>{};
 w.HTMLDialogElement.prototype.close=function(){this.open=false};w.HTMLDialogElement.prototype.showModal=function(){this.open=true};
 w.fetch=(url,init)=>{state.calls++;if(state.fail&&init&&JSON.parse(init.body).action==='trades')return Promise.resolve({ok:false,json:async()=>({detail:'Temporary trade failure'})});return fetch(new URL(url,base),init)};
 w.eval(script);const p={dom,w,d,state};await until(()=>/restored|could not/.test(q(p,'#save-status').textContent));assert.match(q(p,'#save-status').textContent,valid?/restored/:/could not/);return p;
}
async function checks(){
 let p=await page(fixture.checkpoint);
 assert.equal(q(p,'#view-trades').hidden,false);assert.equal(q(p,'#panel-trades').hidden,false);
 assert.equal(p.d.querySelectorAll('.view-panel:not([hidden])').length,1);
 assert.equal(q(p,'#trade-confirm').hidden,true);
 const before=p.w.localStorage.getItem(key),count=p.state.calls;
 q(p,'#view-roster').click();q(p,'#view-trades').click();assert.equal(p.state.calls,count);assert.equal(p.w.localStorage.getItem(key),before);
 // A lopsided request returns reasons and never exposes confirmation or saves.
 const own=fixture.camp.trading.own_players.find(p=>p.position==='K');
 const cpu=fixture.camp.trading.teams.find(t=>t.players.some(p=>p.position==='QB'));
 q(p,'#trade-own').value=own.id;q(p,'#trade-own').dispatchEvent(new p.w.Event('change'));
 q(p,'#trade-team').value=cpu.id;q(p,'#trade-team').dispatchEvent(new p.w.Event('change'));
 q(p,'#trade-other').value=cpu.players.find(p=>p.position==='QB').id;q(p,'#trade-other').dispatchEvent(new p.w.Event('change'));
 q(p,'#trade-preview').click();await until(()=>/cap usage/.test(q(p,'#trade-result').textContent));
 assert.equal(q(p,'#trade-confirm').hidden,true);assert.match(q(p,'#trade-result').textContent,/value|quarterback|QB|salary|roster/i);assert.equal(p.w.localStorage.getItem(key),before);
 const proposal=fixture.proposal;
 q(p,'#trade-own').value=proposal.give_id;q(p,'#trade-own').dispatchEvent(new p.w.Event('change'));
 q(p,'#trade-team').value=proposal.other_team;q(p,'#trade-team').dispatchEvent(new p.w.Event('change'));
 q(p,'#trade-other').value=proposal.receive_id;q(p,'#trade-other').dispatchEvent(new p.w.Event('change'));
 q(p,'#trade-preview').click();await until(()=>!q(p,'#trade-confirm').hidden);
 assert.match(q(p,'#trade-result').textContent,/Accepted.*cap usage/);assert.equal(p.w.localStorage.getItem(key),before);
 p.state.fail=true;q(p,'#trade-confirm').click();await until(()=>!q(p,'#trade-error').hidden);assert.equal(p.w.localStorage.getItem(key),before);
 p.state.fail=false;q(p,'#trade-confirm').click();q(p,'#trade-confirm').click();await until(()=>save(p).tradeActions?.length===1);
 assert.equal(save(p).tradeActions[0].give_id,proposal.give_id);
 assert.ok(q(p,`#roster-groups [data-player-id="${proposal.receive_id}"]`));assert.equal(q(p,`#roster-groups [data-player-id="${proposal.give_id}"]`),null);
 assert.equal(q(p,'#trade-log').children.length,1);assert.equal(q(p,'#trade-confirm').hidden,true);
 const checkpoint=save(p);p.dom.window.close();p=await page(checkpoint);
 assert.equal(q(p,'#trade-log').children.length,1);assert.ok(q(p,`#roster-groups [data-player-id="${proposal.receive_id}"]`));
 // Invalid saved actions are rejected without overwriting the checkpoint.
 const bad={...checkpoint,tradeActions:[{kind:'swap',other_team:'',give_id:'bad',receive_id:''}]};
 const broken=await page(bad,false);assert.deepEqual(save(broken),bad);broken.dom.window.close();
 q(p,'#trade-finish').click();await until(()=>save(p).season===2);
 assert.equal(save(p).career[0].trade_actions.length,2);assert.equal(save(p).career[0].trade_actions[1].kind,'finish');
 assert.equal(q(p,'#view-trades').hidden,true);assert.equal(save(p).tradeActions,undefined);
 const next=save(p);p.dom.window.close();p=await page(next);
 assert.ok(q(p,`#roster-groups [data-player-id="${proposal.receive_id}"]`));assert.equal(save(p).career[0].trade_actions.length,2);p.dom.window.close();
 console.log('Trades UI passed: post-camp window, read-only preview, cap explanation, confirm, failure/retry, duplicate guard, roster and log update, reload, finish and Season 2 replay.');
}
(async()=>{const server=spawn(process.env.PYTHON||'python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8796'],{cwd:root,stdio:['ignore','pipe','pipe']});let logs='';server.stdout.on('data',d=>logs+=d);server.stderr.on('data',d=>logs+=d);try{for(let i=0;;i++){if(server.exitCode!==null)throw Error(logs);try{if((await fetch(base+'/api/teams')).ok)break;}catch{}if(i===100)throw Error(logs);await new Promise(r=>setTimeout(r,100));}await checks();}finally{server.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
