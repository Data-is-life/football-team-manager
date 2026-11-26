const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {spawn,execFileSync}=require('node:child_process'),{JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'..'),base='http://127.0.0.1:8803',key='arcade-league-save';
const fixture=JSON.parse(execFileSync(process.env.PYTHON||'python',['tests/test_flexible_offseason.py'],{cwd:root,env:{...process.env,PYTHONPATH:root},encoding:'utf8'}));
const html=fs.readFileSync(path.join(root,'app/static/index.html'),'utf8'),script=require('./historical-save-fixtures.cjs').allowHistoricalFixtures(fs.readFileSync(path.join(root,'app/static/app.js'),'utf8'));
const q=(p,s)=>p.d.querySelector(s),save=p=>JSON.parse(p.w.localStorage.getItem(key));
async function until(check){for(let i=0;i<4000;i++){if(check())return;await new Promise(r=>setTimeout(r,10));}throw Error('Flexible offseason UI timeout');}
async function page(checkpoint){
 const dom=new JSDOM(html,{url:base,runScripts:'outside-only'}),w=dom.window,d=w.document,state={profile:null,fail:false};
 w.localStorage.setItem(key,JSON.stringify(checkpoint));w.HTMLElement.prototype.scrollIntoView=()=>{};w.scrollTo=()=>{};
 w.HTMLDialogElement.prototype.close=function(){this.open=false};w.HTMLDialogElement.prototype.showModal=function(){this.open=true};
 w.fetch=async(url,init)=>{if(state.fail&&init)return {ok:false,json:async()=>({detail:'Temporary failure'})};const r=await fetch(new URL(url,base),init);if(r.ok&&init){const data=await r.clone().json();if(data.profile)state.profile=data.profile;}return r;};w.eval(script);
 const p={dom,w,d,state};await until(()=>/restored|could not/.test(q(p,'#save-status').textContent));assert.match(q(p,'#save-status').textContent,/restored/);return p;
}
async function drop(p,id){q(p,`[data-drop-id="${id}"]`).click();assert.equal(q(p,'#cut-confirm').disabled,false);assert.doesNotMatch(q(p,'#cut-impact').textContent,/Required minimum-pay replacements:/);q(p,'#cut-confirm').click();await until(()=>!q(p,'#cut-error').hidden||!q(p,`#roster-groups [data-player-id="${id}"]`));assert.equal(q(p,'#cut-error').hidden,true);}
async function checks(){
 // A pending rookie can still be signed while below the roster minimum.
 let partial={...fixture.checkpoint,ownActions:fixture.checkpoint.ownActions.slice(0,-2),freeAgency:[]};
 let p=await page(partial);assert.ok(p.d.querySelectorAll('#roster-groups .roster-player').length<31);
 const sign=q(p,'[data-resign-id]:not([disabled])');assert.ok(sign);sign.click();q(p,'#cut-confirm').click();await until(()=>q(p,'#cut-confirmation').hidden);assert.equal(q(p,'#cut-error').hidden,true);p.dom.window.close();
 p=await page(fixture.checkpoint);
 assert.ok(p.d.querySelectorAll('#roster-groups .roster-player').length<31);
 assert.equal(q(p,'#view-free-agency').hidden,false);
 q(p,'#fa-finish').click();await until(()=>save(p).freeAgency.at(-1)?.kind==='finish');
 assert.equal(q(p,'#next-season').disabled,true);assert.equal(q(p,'#roster-fa-return').hidden,false);
 q(p,'#view-roster').click();
 const kicker=[...p.d.querySelectorAll('#roster-groups .roster-player')].find(row=>row.dataset.playerId&&row.closest('.roster-group').dataset.position==='K');assert.ok(kicker);
 const id=kicker.dataset.playerId,before=p.d.querySelectorAll('#roster-groups .roster-player').length;
 await drop(p,id);assert.equal(p.d.querySelectorAll('#roster-groups .roster-player').length,before-1);
 const checkpoint=save(p);assert.equal(checkpoint.freeAgency.at(-1).kind,'drop');p.dom.window.close();p=await page(checkpoint);
 assert.equal(q(p,`#roster-groups [data-player-id="${id}"]`),null);
 q(p,'#roster-fa-return').click();assert.equal(q(p,'#panel-free-agency').hidden,false);
 q(p,'#view-roster').click();q(p,'#next-season').click();await until(()=>!q(p,'#panel-free-agency').hidden);
 // Failed signing preserves the full finish/drop history and allows retry.
 const available=[...p.d.querySelectorAll('#fa-players tr')].filter(row=>row.children[1].textContent==='K'&&!row.querySelector('button').disabled).sort((a,b)=>Number(a.children[5].textContent.replace(/[^0-9.]/g,''))-Number(b.children[5].textContent.replace(/[^0-9.]/g,'')))[0];assert.ok(available);
 const signId=available.querySelector('button').dataset.faId,raw=p.w.localStorage.getItem(key);p.state.fail=true;available.querySelector('button').click();q(p,'#fa-confirm').click();await until(()=>!q(p,'#fa-error').hidden);assert.equal(p.w.localStorage.getItem(key),raw);p.state.fail=false;
 q(p,'#fa-confirm').click();await until(()=>save(p).freeAgency.at(-1)?.player_id===signId);
 for(let i=0;i<40;i++){
  const profile=p.state.profile;const missing=profile.roster_rules.find(rule=>profile.roster.filter(player=>player.position===rule.position).length<rule.minimum);
  if(!missing&&profile.roster.length>=31)break;
  const row=[...p.d.querySelectorAll('#fa-players tr')].filter(row=>(!missing||row.children[1].textContent===missing.position)&&!row.querySelector('button').disabled).sort((a,b)=>Number(a.children[5].textContent.replace(/[^0-9.]/g,''))-Number(b.children[5].textContent.replace(/[^0-9.]/g,'')))[0];assert.ok(row);
  const count=save(p).freeAgency.length;row.querySelector('button').click();q(p,'#fa-confirm').click();await until(()=>save(p).freeAgency.length===count+1);
 }
 q(p,'#fa-finish').click();await until(()=>save(p).freeAgency.at(-1)?.kind==='finish'&&!q(p,'#panel-roster').hidden);
 if(!q(p,'#meet-payroll-floor').hidden){q(p,'#meet-payroll-floor').click();q(p,'#floor-confirm').click();await until(()=>q(p,'#meet-payroll-floor').hidden);assert.equal(save(p).freeAgency.at(-1).kind,'raise');}
 assert.equal(q(p,'#next-season').disabled,false);const ready=save(p);p.dom.window.close();p=await page(ready);
 assert.equal(q(p,'#next-season').disabled,false);q(p,'#next-season').click();await until(()=>save(p).season===2);
 const seasonTwo=save(p);p.dom.window.close();p=await page(seasonTwo);assert.deepEqual(save(p),seasonTwo);p.dom.window.close();
 console.log('Flexible offseason UI passed: below-minimum signing, final-position release without refill, closed-market repair, failure/retry, ordered action reload, minimum restoration, payroll raise, season start and Season 2 replay.');
}
(async()=>{const server=spawn(process.env.PYTHON||'python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8803'],{cwd:root,stdio:['ignore','pipe','pipe']});let logs='';server.stdout.on('data',d=>logs+=d);server.stderr.on('data',d=>logs+=d);try{for(let i=0;;i++){if(server.exitCode!==null)throw Error(logs);try{if((await fetch(base+'/api/teams')).ok)break;}catch{}if(i===100)throw Error(logs);await new Promise(r=>setTimeout(r,100));}await checks();}finally{server.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
