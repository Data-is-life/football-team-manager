const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {spawn,execFileSync}=require('node:child_process'),{JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'..'),base='http://127.0.0.1:8797',key='arcade-league-save';
const fixture=JSON.parse(execFileSync(process.env.PYTHON||'python',['tests/simple_offseason_fixtures.py'],{cwd:root,env:{...process.env,PYTHONPATH:root},encoding:'utf8'}));
const html=fs.readFileSync(path.join(root,'app/static/index.html'),'utf8'),script=fs.readFileSync(path.join(root,'app/static/app.js'),'utf8');
const draftRules=Number(process.env.TEST_DRAFT_RULES||42);
const q=(p,s)=>p.d.querySelector(s),raw=p=>p.w.localStorage.getItem(key),save=p=>JSON.parse(raw(p));
async function until(check){for(let i=0;i<4000;i++){if(check())return;await new Promise(r=>setTimeout(r,10));}throw Error('Simple offseason UI timeout');}
async function page(checkpoint){
 const dom=new JSDOM(html,{url:base,runScripts:'outside-only'}),w=dom.window,d=w.document,state={calls:[],fail:false};
 w.localStorage.setItem(key,JSON.stringify(checkpoint));w.HTMLElement.prototype.scrollIntoView=()=>{};w.scrollTo=()=>{};
 w.HTMLDialogElement.prototype.close=function(){this.open=false};w.HTMLDialogElement.prototype.showModal=function(){this.open=true};
 w.fetch=async(url,init)=>{const b=init&&JSON.parse(init.body);if(b)state.calls.push(b);if(state.fail&&b?.action==='own_players')return {ok:false,json:async()=>({detail:'Temporary signing failure'})};const r=await fetch(new URL(url,base),init);if(!r.ok)console.error('API:',b?.action,await r.clone().text());return r;};
 w.eval(script);const p={dom,w,d,state};await until(()=>/restored|could not/.test(q(p,'#save-status').textContent));assert.match(q(p,'#save-status').textContent,/restored/);return p;
}
function assertDraftNavigation(p, visible){
 for(const selector of ['#draft-button','#roster-draft-return','#view-draft'])assert.equal(q(p,selector).hidden,!visible,selector);
}
async function checks(){
 const draftCheckpoint={...fixture.checkpoint};delete draftCheckpoint.freeAgency;delete draftCheckpoint.ownActions;
 let p=await page(draftCheckpoint);
 assert.equal(q(p,'#own-signing').hidden,true);assert.equal(q(p,'#next-season').textContent,'Sign your own players');
 q(p,'#next-season').click();await until(()=>!q(p,'#own-signing').hidden&&save(p).ownActions&&q(p,'#roster-groups [data-resign-id]:not([disabled])'));

 assert.equal(q(p,'#own-signing').hidden,false);assert.equal(q(p,'#panel-roster').hidden,false);
 assert.equal(q(p,'#training-camp-button').hidden,true);assert.equal(q(p,'#view-free-agency').hidden,true);assert.equal(q(p,'#view-trades').hidden,true);
 assert.match(q(p,'#own-signing-status').textContent,/decisions remaining/);
 const initial=raw(p),first=fixture.actions[0];
 q(p,`[data-drop-id="${first.player_id}"]`).click();p.state.fail=true;q(p,'#cut-confirm').click();await until(()=>!q(p,'#cut-error').hidden&&!q(p,'#cut-confirm').disabled);assert.equal(raw(p),initial);p.state.fail=false;q(p,'#cut-cancel').click();
 for(const a of fixture.actions.filter(a=>a.kind!=='finish')){
  const n=save(p).ownActions.length;
  const selector=a.kind==='drop'?'data-drop-id':'data-resign-id';
  q(p,`[${selector}="${a.player_id}"]`).click();
  if(a.kind==='sign'){assert.equal(q(p,'#cut-confirm').textContent,'Confirm signing');assert.match(q(p,'#cut-confirm-text').textContent,/Sign .* for \$/);}
  q(p,'#cut-confirm').click();q(p,'#cut-confirm').click();await until(()=>save(p).ownActions.length===n+1);
  assert.equal(save(p).ownActions.at(-1).kind,a.kind);
 }
 const ownSave=save(p);p.dom.window.close();p=await page(ownSave);
 assert.equal(q(p,'#own-signing').hidden,false);assert.equal(q(p,'#own-signing-finish').disabled,false);assertDraftNavigation(p,true);
 q(p,'#own-signing-finish').click();q(p,'#own-signing-finish').click();await until(()=>save(p).ownActions.at(-1).kind==='finish'&&!q(p,'#panel-free-agency').hidden&&!q(p,'#fa-finish').disabled);
 assert.equal(q(p,'#own-signing').hidden,true);assert.equal(q(p,'#training-camp-button').hidden,true);assertDraftNavigation(p,false);
 assert.equal(q(p,'#fa-pass').hidden,true);assert.equal(q(p,'#fa-review-own').hidden,true);assert.equal(q(p,'#fa-pricing-guide').hidden,true);
 assert.match(q(p,'#fa-status').textContent,/Fixed asking prices/);assert.doesNotMatch(q(p,'#fa-status').textContent,/Wave|undefined/);
 const prices=new Map([...p.d.querySelectorAll('#fa-players tr')].map(r=>[r.querySelector('[data-fa-id]').dataset.faId,r.children[5].textContent]));
 const sign=q(p,'#fa-players button:not([disabled])');assert.ok(sign);const id=sign.dataset.faId;
 sign.click();sign.click();await until(()=>save(p).freeAgency.length===1&&!q(p,'#fa-finish').disabled);
 assert.equal(save(p).freeAgency[0].player_id,id);
 for(const row of p.d.querySelectorAll('#fa-players tr'))assert.equal(row.children[5].textContent,prices.get(row.querySelector('[data-fa-id]').dataset.faId));
 assert.ok(q(p,`#roster-groups [data-player-id="${id}"]`));
 const marketSave=save(p);p.dom.window.close();p=await page(marketSave);
 assert.equal(q(p,'#fa-pass').hidden,true);assert.match(q(p,'#fa-status').textContent,/Fixed asking prices/);assertDraftNavigation(p,false);
 q(p,'#fa-finish').click();await until(()=>save(p).freeAgency.at(-1)?.kind==='finish'&&!q(p,'#panel-roster').hidden);
 assertDraftNavigation(p,false);assert.equal(q(p,'#training-camp-button').hidden,true);assert.equal(q(p,'#panel-trades').hidden,true);assert.equal(q(p,'#view-free-agency').hidden,true);
 if(!q(p,'#meet-payroll-floor').hidden){q(p,'#meet-payroll-floor').click();q(p,'#floor-confirm').click();await until(()=>q(p,'#meet-payroll-floor').hidden);}
 assert.equal(q(p,'#view-trades').hidden,true);assert.equal(q(p,'#next-season').textContent,'Start season');
 const before=save(p);q(p,'#next-season').click();await until(()=>save(p).season===2);
 assert.equal(save(p).lineupRules,draftRules);assert.equal(save(p).career[0].own_actions.at(-1).kind,'finish');assert.equal(save(p).career[0].trade_actions.at(-1).kind,'finish');
 assert.equal(q(p,'#training-camp-button').hidden,true);assert.equal(q(p,'#own-signing').hidden,true);assert.equal(q(p,'#view-trades').hidden,true);
 assert.equal(q(p,'#development-dialog').open,true);assert.ok(q(p,`#roster-groups [data-player-id="${id}"]`));
 const next=save(p);p.dom.window.close();p=await page(next);assert.deepEqual(save(p),next);assert.ok(q(p,`#roster-groups [data-player-id="${id}"]`));
 assert.ok(!p.state.calls.some(c=>c.action==='camp'));p.dom.window.close();
 console.log('Simple offseason UI passed: own-player signing and rookies, failure/retry, duplicate guards, fixed-price market with no pass or camp, CPU competition, payroll review, trades, automatic development, saves and Season 2 replay.');
}
(async()=>{const server=spawn(process.env.PYTHON||'python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8797'],{cwd:root,stdio:['ignore','pipe','pipe']});let logs='';server.stdout.on('data',d=>logs+=d);server.stderr.on('data',d=>logs+=d);try{for(let i=0;;i++){if(server.exitCode!==null)throw Error(logs);try{if((await fetch(base+'/api/teams')).ok)break;}catch{}if(i===100)throw Error(logs);await new Promise(r=>setTimeout(r,100));}await checks();}finally{server.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
