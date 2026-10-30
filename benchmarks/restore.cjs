// Local HTTP + jsdom timings. Fresh process != Render platform wake-up or real-browser paint.
const fs=require('node:fs'),path=require('node:path'),{spawn}=require('node:child_process');
const {performance}=require('node:perf_hooks'),{createHash}=require('node:crypto'),{JSDOM}=require('jsdom');
const root=path.resolve(process.argv[2]||'.'),fixtureDir=__dirname,port=8785,base=`http://127.0.0.1:${port}`;
const html=fs.readFileSync(path.join(root,'app/static/index.html'),'utf8'),script=fs.readFileSync(path.join(root,'app/static/app.js'),'utf8');
async function page(save){
 const dom=new JSDOM(html,{url:base,runScripts:'outside-only'}),w=dom.window,d=w.document,requests=[];
 w.localStorage.setItem('arcade-league-save',JSON.stringify(save));
 w.HTMLElement.prototype.scrollIntoView=()=>{};w.HTMLDialogElement.prototype.close=function(){this.open=false};w.HTMLDialogElement.prototype.showModal=function(){this.open=true};
 w.fetch=async(url,init)=>{const start=performance.now(),response=await fetch(new URL(url,base),init);return {ok:response.ok,json:async()=>{const data=await response.json();requests.push({url,ms:performance.now()-start});return data}}};
 w.eval(script.replace(/loadTeams\(\);\s*$/,`let benchDepth=0;window.benchRender=0;for(const name of ['renderTeamProfile','renderSchedule','renderResult','renderPostseason','applyDraft']){const original=window[name];window[name]=function(...args){const outer=benchDepth++===0,start=performance.now();try{return original(...args)}finally{benchDepth--;if(outer)window.benchRender+=performance.now()-start}}}loadTeams();`));
 const start=performance.now();
 for(;;){const status=d.querySelector('#save-status').textContent;if(/could not/.test(status))throw Error(status);if(/restored/.test(status))break;await new Promise(r=>setTimeout(r,1))}
 const elapsed=performance.now()-start;
 const snapshot=['#team-name','#season-record','#schedule','#roster-groups','#standings-groups','#playoff-bracket','#gm-regular','#draft-picks'].map(selector=>d.querySelector(selector)?.textContent||'').join('\n');
 const result={ms:+elapsed.toFixed(2),render_ms:+w.benchRender.toFixed(2),requests:requests.map(r=>({...r,ms:+r.ms.toFixed(2)})),signature:createHash('sha256').update(snapshot).digest('hex')};
 dom.window.close();return result;
}
(async()=>{
 const rows=[];
 for(const name of ['fresh','year4','year8'])for(let trial=0;trial<Number(process.env.RESTORE_TRIALS||1);trial++){
  const start=performance.now(),server=spawn(process.env.PYTHON||'python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port',String(port)],{cwd:root,stdio:['ignore','pipe','pipe']});let logs='';server.stderr.on('data',d=>logs+=d);
  try{
   for(;;){if(server.exitCode!==null)throw Error(logs);try{if((await fetch(base+'/api/teams')).ok)break}catch{}if(performance.now()-start>20000)throw Error('Startup timeout: '+logs);await new Promise(r=>setTimeout(r,10))}
   const startup=performance.now()-start,save=JSON.parse(fs.readFileSync(path.join(fixtureDir,name+'.json')));
   for(let sample=0;sample<4;sample++)rows.push({fixture:name,trial,cache:sample?'warm':'empty',sample,startup_ms:+startup.toFixed(2),...await page(save)});
  }finally{server.kill();await new Promise(resolve=>server.once('exit',resolve))}
 }
 console.log(JSON.stringify(rows,null,2));
})().catch(e=>{console.error(e);process.exitCode=1});
