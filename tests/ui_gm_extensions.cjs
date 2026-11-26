const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {spawn}=require('node:child_process'),{JSDOM}=require('jsdom');
const {finishOffseason}=require('./ui_offseason_helpers.cjs');
const root=path.resolve(__dirname,'..'),base='http://127.0.0.1:8802',key='arcade-league-save';
const html=fs.readFileSync(path.join(root,'app/static/index.html'),'utf8'),script=require('./historical-save-fixtures.cjs').allowHistoricalFixtures(fs.readFileSync(path.join(root,'app/static/app.js'),'utf8'));
const q=(p,s)=>p.d.querySelector(s),raw=p=>p.w.localStorage.getItem(key),save=p=>JSON.parse(raw(p));
async function until(check){for(let i=0;i<4000;i++){if(check())return;await new Promise(r=>setTimeout(r,10));}throw Error('GM extension UI timeout');}
async function api(url){const r=await fetch(base+url);assert.ok(r.ok);return r.json();}
function checkpoint(id){return {version:12,contracts:true,gmExtensionRules:2,teamId:id,runSeed:1234,season:1,week:17,playoffRound:0,lineupRules:1,developmentStart:null,rebuildTeam:null,priorStandings:{},history:[],draftChoices:null,dropped:[],career:[]};}
function page(checkpoint){
 const dom=new JSDOM(html,{url:base,runScripts:'outside-only'}),w=dom.window,d=w.document;
 w.localStorage.setItem(key,JSON.stringify(checkpoint));w.HTMLElement.prototype.scrollIntoView=()=>{};w.scrollTo=()=>{};
 w.HTMLDialogElement.prototype.close=function(){this.open=false};w.HTMLDialogElement.prototype.showModal=function(){this.open=true};
 w.fetch=(url,init)=>fetch(new URL(url,base),init);w.eval(script);return {dom,w,d};
}
async function restore(checkpoint){const p=page(checkpoint);await until(()=>/restored|could not/.test(q(p,'#save-status').textContent));assert.match(q(p,'#save-status').textContent,/restored/);return p;}
const loser=game=>game.winner.team.id===game.home.team.id?game.away.team.id:game.home.team.id;
async function checks(){
 const final=await api('/api/playoffs/seattle/round/4?run_seed=1234');
 const wildLoser=loser(final.rounds[0].games[0]),champion=final.champion.team.id;
 let p=await restore(checkpoint(wildLoser));
 const status=p.w.contractStatus;
 const finishes=['Lost in Wild Card','Lost in Quarterfinals','Lost in Semifinals','Lost in Championship','Champions'];
 for(const [index,playoffFinish] of finishes.entries()){
  for(const [wins,losses,ties] of [[12,5,0],[7,10,0],[8,8,1]]){
   const historical={season:1,playoffFinish,wins,losses,ties,gmExtensionRules:2};
   assert.equal(status([historical],2).end,4+index+1,'Highest milestone applies regardless of regular-season record');
  }
 }
 for(const [wins,losses,ties,reward] of [[9,8,0,1],[8,7,2,1],[8,8,1,0],[7,10,0,0]]){
  assert.equal(status([],1,{complete:true,qualified:false,wins,losses,ties},1,2).reward,reward);
 }
 for(let reached=1;reached<=4;reached++)assert.equal(status([],1,{complete:true,qualified:true,wins:12,losses:5,playoffRoundReached:reached},1,2).end,4+reached);
 assert.equal(status([],1,{complete:true,qualified:true,champion:true,wins:12,losses:5,playoffRoundReached:4},1,2).end,9);
 const old={season:1,playoffFinish:'Lost in Wild Card',wins:8,losses:9,ties:0};
 assert.equal(status([old],2).end,6,'Unmarked historical playoff awards stay at two years');
 assert.equal(status([{...old,gmExtensionRules:2}],2).end,5);
 assert.equal(status([{...old,season:1,playoffFinish:'Champions',gmExtensionRules:2}],2,null,2).end,5,'Intro season remains extension-free');
 const missed=Array.from({length:4},(_,i)=>({season:i+1,playoffFinish:'Missed playoffs',wins:9,losses:8,ties:0,gmExtensionRules:2}));
 assert.equal(status(missed,5).reason,'deadline');
 assert.equal(status([...missed.slice(0,3),{...old,season:4,gmExtensionRules:2}],5).fired,false);
 assert.match(q(p,'#contract-rules').textContent,/playoffs \+1 year; quarterfinals \+2; semifinals \+3; final \+4; championship \+5/);
 p.dom.window.close();
 const ids=new Set([wildLoser,...final.rounds.slice(1).map(round=>loser(round.games[0])),champion,final.field[0].team.id]);
 for(const id of ids){
  p=await restore(checkpoint(id));
  let reward=final.field.find(team=>team.team.id===id).seed<=2?2:1;
  assert.equal(p.w.currentContract().reward,reward,'Byes count as reaching round two');
  for(let round=1;round<=4;round++){
   const game=final.rounds[round-1].games.find(game=>game.home.team.id===id||game.away.team.id===id);
   if(game)reward=game.winner.team.id===id?round+1:round;
   q(p,'#playoff-simulate').click();await until(()=>save(p).playoffRound===round);
   assert.equal(p.w.currentContract().reward,reward);
   assert.equal(p.w.currentContract().end,4+reward);
   const before=raw(p);p.w.renderGMRecords();p.w.renderGMRecords();assert.equal(raw(p),before);
   if(game&&game.winner.team.id!==id)assert.doesNotMatch(q(p,'#owner-feedback').textContent,/Further playoff progress/);
  }
  const saved=save(p);p.dom.window.close();p=await restore(saved);assert.equal(p.w.currentContract().end,4+reward);p.dom.window.close();
 }
 // Record the new one-year Wild Card award and reload it as historical credit.
 for(const legacy of [false,true]){
  const start={...checkpoint(wildLoser),playoffRound:4};if(legacy)delete start.gmExtensionRules;
  p=await restore(start);assert.equal(p.w.currentContract().end,legacy?6:5);
  await finishOffseason(p,until);q(p,'#next-season').click();await until(()=>save(p).season===2);
  assert.equal(save(p).gmExtensionRules,2,'Existing careers adopt new milestones next season');
  assert.equal(save(p).history[0].gmExtensionRules,legacy?undefined:2);
  assert.equal(p.w.currentContract().end,legacy?6:5);
  const saved=save(p);p.dom.window.close();p=await restore(saved);assert.equal(p.w.currentContract().end,legacy?6:5);p.dom.window.close();
 }
 for(const bad of [0,3,true,'2',null]){
  p=page({...checkpoint(wildLoser),gmExtensionRules:bad});await until(()=>/could not be read/.test(q(p,'#save-status').textContent));assert.equal(save(p).gmExtensionRules,bad);p.dom.window.close();
 }
 console.log('GM milestone extensions passed: all five awards, live rounds, byes, elimination, no stacking, ties, intro/deadline rules, historical credit, migration, rollover, invalid saves and reload idempotence.');
}
(async()=>{const server=spawn(process.env.PYTHON||'python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8802'],{cwd:root,stdio:['ignore','pipe','pipe']});let logs='';server.stdout.on('data',d=>logs+=d);server.stderr.on('data',d=>logs+=d);try{for(let i=0;;i++){if(server.exitCode!==null)throw Error(logs);try{if((await fetch(base+'/api/teams')).ok)break;}catch{}if(i===100)throw Error(logs);await new Promise(r=>setTimeout(r,100));}await checks();}finally{server.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
