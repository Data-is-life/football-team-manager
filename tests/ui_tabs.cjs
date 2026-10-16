const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {spawn} = require('node:child_process');
const root = path.resolve(__dirname, '..');
const {JSDOM} = require('jsdom');
const base = 'http://127.0.0.1:8767';
async function until(check) {
  for (let i=0;i<300;i++) { if(check()) return; await new Promise(r=>setTimeout(r,10)); }
  throw new Error('Expected UI state did not arrive');
}
async function checkUI() {
 const finished=await (await fetch(base+'/api/playoffs/seattle/round/4')).json();
 const teams=(await (await fetch(base+'/api/teams')).json()).teams;
 const field=finished.field;
 const firstLoser=finished.rounds[0].games[0];
 const loserId=firstLoser.winner.team.id===firstLoser.home.team.id ? firstLoser.away.team.id : firstLoser.home.team.id;
 const cases=[field[0].team.id, loserId, finished.champion.team.id, teams.find(t=>!field.some(f=>f.team.id===t.id)).id];
 for(const [index,id] of cases.entries()) {
  const dom=new JSDOM(await (await fetch(base)).text(),{url:base,runScripts:'outside-only'});
  const w=dom.window, d=w.document;
  let fail=false;
  w.fetch=path=> fail && path.startsWith('/api/playoffs/') ? Promise.resolve({ok:false}) : fetch(new URL(path,base));
  w.HTMLElement.prototype.scrollIntoView=()=>{};
  w.eval(fs.readFileSync(path.join(root,'app/static/app.js'),'utf8'));
  await until(()=>d.querySelector('#team-select').options.length===31);
  d.querySelector('#team-select').value=id;
  d.querySelector('#team-form').dispatchEvent(new w.Event('submit',{cancelable:true}));
  await until(()=>!d.querySelector('#schedule-section').hidden);
  assert.equal(d.querySelectorAll('.roster-player').length,38);
  assert.equal(d.querySelectorAll('.roster-group').length,10);
  const expected={QB:[2,1],WR:[4,2],TE:[2,1],RB:[2,1],OL:[8,5],K:[2,1],DL:[6,4],LB:[5,3],CB:[4,2],S:[3,2]};
  for(const [position,[count,min]] of Object.entries(expected)) {
   const group=d.querySelector(`[data-position="${position}"]`);
   assert.equal(group.querySelectorAll('.roster-player').length,count);
   assert.equal(group.querySelector('summary').textContent,`${position} · ${count} players · minimum ${min}`);
   group.open=false; assert.equal(group.open,false); group.open=true;
  }
  const api=await (await fetch(base+`/api/team/${id}`)).json();
  assert.deepEqual([...d.querySelectorAll('.roster-player')].map(row=>row.dataset.playerId),api.roster.map(player=>player.id));
  assert.equal(d.querySelector('.roster-player').children[2].textContent,`${api.roster[0].experience} yr`);
  const views=['roster','game','schedule','standings','league','race','playoffs'];
  assert.deepEqual([...d.querySelectorAll('.view-tab')].map(tab=>tab.id),views.map(view=>`view-${view}`));
  let requests=0;
  const originalFetch=w.fetch;
  w.fetch=(...args)=>{requests++;return originalFetch(...args)};
  function checkView(id) {
   assert.equal(d.querySelectorAll('.view-tab[aria-selected="true"]').length,1);
   assert.equal(d.querySelectorAll('.view-panel:not([hidden])').length,1);
   for (const name of views) {
    const button=d.querySelector(`#view-${name}`),panel=d.querySelector(`#panel-${name}`);
    assert.equal(button.tabIndex,name===id?0:-1);
    assert.equal(button.getAttribute('aria-controls'),panel.id);
    assert.equal(panel.getAttribute('aria-labelledby'),button.id);
    assert.equal(panel.hidden,name!==id);
   }
   assert.equal(d.querySelector('#simulate-button').closest('[role="tabpanel"]'),null);
   assert.equal(d.querySelector('#playoff-simulate').closest('[role="tabpanel"]'),null);
  }
  function go(id) {d.querySelector(`#view-${id}`).click();checkView(id)}
  checkView('schedule');
  for(const view of views) go(view);
  assert.equal(requests,0,'Switching views must not fetch or reset the season');
  for(const view of ['game','league','standings','race','playoffs']) assert.equal(d.querySelector(`#${view}-empty`).hidden,false);
  function key(from,key,to) {
   const button=d.querySelector(`#view-${from}`);button.focus();
   button.dispatchEvent(new w.KeyboardEvent('keydown',{key,bubbles:true,cancelable:true}));
   checkView(to);assert.equal(d.activeElement.id,`view-${to}`);
  }
  key('roster','ArrowLeft','playoffs');
  key('playoffs','ArrowRight','roster');
  key('schedule','End','playoffs');
  key('playoffs','Home','roster');
  key('roster','ArrowRight','game');
  const rosterGroup=d.querySelector('.roster-group');rosterGroup.open=false;
  go('schedule');go('roster');assert.equal(rosterGroup.open,false);
  go('league');
  d.querySelector('#change-team-button').click();d.querySelector('#cancel-team-change').click();checkView('league');
  const panels=[['league-results-toggle','league-results','league results'],['standings-toggle','group-standings','group standings'],['playoff-race-toggle','playoff-race-content','playoff race']];
  function checkPanel(panel,expanded) {
   const [bid,cid,label]=panel, button=d.getElementById(bid), content=d.getElementById(cid);
   assert.equal(button.getAttribute('aria-controls'),cid);
   assert.equal(button.getAttribute('aria-expanded'),String(expanded));
   assert.equal(button.textContent,`${expanded?'Hide':'Show'} ${label}`);
   assert.equal(content.hidden,!expanded);
   assert.equal(button.hidden,false);
  }
  panels.forEach(p=>checkPanel(p,true));
  function checkEfficiency(root,box) {
   const sections=root.querySelectorAll('.stat-section');
   const fields=[['completion_percentage','yards_per_attempt','passer_rating'],['yards_per_carry'],['yards_per_reception']];
   const indexes=[[3,5,8],[3],[3]];
   ['passing','rushing','receiving'].forEach((key,i)=>{
    const rows=sections[i].querySelectorAll('tbody tr');
    box[key].forEach((row,j)=>fields[i].forEach((field,k)=>{
     const value=row[field];
     assert.equal(rows[j].children[indexes[i][k]].textContent,value==null?'—':value.toFixed(1)+(field==='completion_percentage'?'%':''));
    }));
   });
  }
  function checkKicking(root,box) {
   const table=root.querySelectorAll('.stat-section')[3];
   assert.deepEqual([...table.querySelectorAll('th')].map(cell=>cell.textContent),['Player','FGM','FGA','FG%','Long FG','XPM','XPA','Pts']);
   const rows=table.querySelectorAll('tbody tr');
   box.kicking.forEach((row,index)=>{
    const values=[row.player,String(row.field_goals_made),String(row.field_goals_attempted),row.field_goal_percentage==null?'—':`${row.field_goal_percentage.toFixed(1)}%`,row.longest_field_goal==null?'—':`${row.longest_field_goal} yd`,String(row.extra_points_made),String(row.extra_points_attempted),String(row.kicking_points)];
    assert.deepEqual([...rows[index].children].map(cell=>cell.textContent),values);
   });
  }
  function checkRoster(snapshot,competition) {
   const before=[...d.querySelectorAll('.roster-group')].map(group=>group.open);
   const mode=d.querySelector('#roster-stats-button'),filter=d.querySelector('#roster-competition');
   mode.click();filter.value=competition;filter.dispatchEvent(new w.Event('change'));
   assert.equal(mode.getAttribute('aria-pressed'),'true');
   assert.equal(d.querySelector('#roster-ratings-button').getAttribute('aria-pressed'),'false');
   assert.equal(d.querySelector('#roster-competition-control').hidden,false);
   assert.match(d.querySelector('#roster-stats-status').textContent,new RegExp(`${snapshot.games} team game`));
   const schemas={
    QB:[['passing','completions'],['passing','attempts'],['passing','completion_percentage'],['passing','yards'],['passing','touchdowns'],['passing','interceptions'],['passing','yards_per_attempt'],['passing','passer_rating']],
    RB:[['rushing','attempts'],['rushing','yards'],['rushing','yards_per_carry'],['rushing','touchdowns'],['receiving','receptions'],['receiving','yards'],['receiving','yards_per_reception'],['receiving','touchdowns']],
    WR:[['receiving','receptions'],['receiving','yards'],['receiving','yards_per_reception'],['receiving','touchdowns']],
    TE:[['receiving','receptions'],['receiving','yards'],['receiving','yards_per_reception'],['receiving','touchdowns']],
    K:[['kicking','field_goals_made'],['kicking','field_goals_attempted'],['kicking','field_goal_percentage'],['kicking','longest_field_goal'],['kicking','extra_points_made'],['kicking','extra_points_attempted'],['kicking','kicking_points']]
   };
   for(const player of api.roster) {
    const group=d.querySelector(`.roster-group[data-position="${player.position}"]`);
    const schema=schemas[player.position];
    if(!schema) {
     assert.equal(group.querySelector('.roster-rating-wrap').hidden,false);
     assert.equal(group.querySelector('.roster-untracked-note').hidden,false);
     assert.equal(group.querySelector('.roster-stats-wrap').hidden,true);
     continue;
    }
    assert.equal(group.querySelector('.roster-rating-wrap').hidden,true);
    assert.equal(group.querySelector('.roster-stats-wrap').hidden,false);
    const total=snapshot.players.find(row=>row.player_id===player.id);
    const cells=group.querySelector(`.roster-season-player[data-player-id="${player.id}"]`).children;
    assert.equal(cells[0].textContent,String(player.depth));assert.equal(cells[1].textContent,player.name);
    schema.forEach(([category,field],i)=>{
     const value=total[category][field];
     const expected=value==null?'—':field.includes('percentage')?`${value.toFixed(1)}%`:field==='longest_field_goal'?`${value} yd`:field.startsWith('yards_per_')||field==='passer_rating'?value.toFixed(1):String(value);
     assert.equal(cells[i+2].textContent,expected,`${player.id} ${category}.${field}`);
    });
   }
   assert.deepEqual([...d.querySelectorAll('.roster-group')].map(group=>group.open),before);
  }
  const initialRequests=requests;
  go('roster');checkRoster(api.roster_stats,'regular');checkRoster(api.roster_stats,'playoffs');
  assert.equal(requests,initialRequests,'Roster controls must not fetch or simulate games');
  d.querySelector('#roster-ratings-button').click();
  assert.equal(d.querySelector('#roster-competition-control').hidden,true);
  assert.equal(d.querySelector('#roster-stats-status').hidden,true);
  go('schedule');
  const start=d.querySelector('#playoffs-start'), advance=d.querySelector('#playoff-simulate');
  assert.equal(start.hidden,true);
  for(let week=1;week<=17;week++) {
   const selected=views[(week-1)%views.length];go(selected);
   if (week===1 && index===0) {
    const previous=w.fetch;w.fetch=()=>Promise.resolve({ok:false});
    d.querySelector('#simulate-button').click();
    await until(()=>!d.querySelector('#error').hidden && !d.querySelector('#simulate-button').disabled);
    checkView(selected);assert.equal(d.querySelectorAll('#schedule .completed').length,0);
    w.fetch=previous;
   }
   d.querySelector('#simulate-button').click();
   await until(()=>d.querySelector('#simulate-button').textContent===(week===17?'Regular season complete':`Simulate Week ${week+1}`));
   assert.equal(start.hidden,week!==17);
   checkView(selected);
   assert.match(d.querySelector('#season-status').textContent,new RegExp(`Week ${week} final:`));
   for(const name of ['game','league','standings','race']) assert.equal(d.querySelector(`#${name}-empty`).hidden,true);
   for (const [i,p] of panels.entries()) {
    checkPanel(p,week===1);
    if (week===1) {
     d.getElementById(p[0]).click(); checkPanel(p,false);
     panels.forEach((other,j)=>checkPanel(other,j>i));
    }
   }
   assert.equal(d.querySelectorAll('#league-results article').length,14);
   assert.equal(d.querySelectorAll('#group-standings article').length,6);
   assert.equal(d.querySelectorAll('#playoff-race tr').length,14);
   assert.match(d.querySelector('#league-results-title').textContent,new RegExp(`Week ${week}$`));
   if (week===17) panels.forEach(p=>{ d.getElementById(p[0]).click(); checkPanel(p,true); d.getElementById(p[0]).click(); checkPanel(p,false); });
   const weekData=await (await fetch(base+`/api/season/${id}/week/${week}?season=1`)).json();
   const history=weekData.game_results;
   go('roster');checkRoster(weekData.roster_stats,'regular');checkRoster(api.roster_stats,'playoffs');go(selected);
   const cards=d.querySelectorAll('#schedule .game-card');
   assert.equal(d.querySelectorAll('#schedule .completed').length,week);
   history.forEach((game,i)=> {
    assert.equal(cards[i].querySelector('.game-final').textContent,`${game.outcome} · ${game.team_score}–${game.opponent_score}${game.overtime ? ' · OT' : ''}`);
    assert.match(cards[i].querySelector('.game-final').getAttribute('aria-label'),/Win|Loss|Tie/);
   });
   for(let i=week;i<17;i++) assert.equal(cards[i].querySelector('.game-final').textContent,'Not played');
   assert.match(d.querySelector('#team-comparison').textContent,/Total plays/);
   const result=weekData.result;
   for (const side of ['away','home']) {
    d.querySelector(`#${side}-tab`).click();
    checkEfficiency(d.querySelector('#player-stats'),result[side]);
    checkKicking(d.querySelector('#player-stats'),result[side]);
    assert.equal(d.querySelector(`#${side}-tab`).getAttribute('aria-pressed'),'true');
   }
   const tables=d.querySelectorAll('#player-stats tbody');
   assert.equal(tables[1].children.length,2);
   assert.equal(tables[2].children.length,8);
  }
  const regularFinal=(await (await fetch(base+`/api/season/${id}/week/17?season=1`)).json()).roster_stats;
  const record=d.querySelector('#season-record').textContent;
  assert.match(d.querySelector('#playoffs-empty p').textContent,/field is set/);
  go('roster');
  if(index===0) {
   fail=true;start.click();
   await until(()=>!d.querySelector('#error').hidden && !start.disabled);
   assert.equal(start.hidden,false);
   assert.equal(d.querySelector('#postseason-section').hidden,true);
   fail=false;
  }
  start.click();
  await until(()=>!d.querySelector('#postseason-section').hidden);
  assert.equal(start.hidden,true);
  assert.equal(advance.textContent,'Simulate Wild Card');
  checkView('playoffs');assert.equal(advance.hidden,false);
  assert.equal(d.querySelector('#playoffs-empty').hidden,true);
  if(index===0) assert.match(d.querySelector('#postseason-status').textContent,/bye/);
  if(index===3) assert.match(d.querySelector('#postseason-status').textContent,/missed/);
  for(let round=1;round<=4;round++) {
   if(index===0 && round===2) {
    fail=true;advance.click();
    await until(()=>!d.querySelector('#error').hidden && !advance.disabled);
    assert.equal(advance.textContent,'Simulate Quarterfinals');
    fail=false;
   }
   go('schedule');advance.click();
   const labels=['','Simulate Quarterfinals','Simulate Semifinals','Simulate Championship','Postseason complete'];
   await until(()=>advance.textContent===labels[round]);
   checkView('playoffs');
   const state=await (await fetch(base+`/api/playoffs/${id}/round/${round}`)).json();
   go('roster');checkRoster(state.roster_stats,'playoffs');checkRoster(regularFinal,'regular');checkRoster(state.roster_stats,'playoffs');go('playoffs');
   const latest=state.rounds.at(-1);
   const own=latest.games.find(g=>g.home.team.id===id||g.away.team.id===id);
   assert.equal(d.querySelector('#your-playoff-game').hidden,!own);
   assert.equal(d.querySelectorAll('#playoff-league-games article').length,latest.games.length-(own?1:0));
   if(own) {
    assert.match(d.querySelector('#your-playoff-game').textContent,/Your .* game/);
    const holder=d.querySelector('#your-playoff-game');
    const stats=holder.querySelectorAll('.player-stats');
    checkEfficiency(stats[0],own.result[own.home.team.id===id?'home':'away']);
    checkKicking(stats[0],own.result[own.home.team.id===id?'home':'away']);
   }
   if(state.eliminated) assert.match(d.querySelector('#postseason-status').textContent,/eliminated/);
   assert.equal(d.querySelector('#season-record').textContent,record);
   assert.equal(d.querySelector('#franchise-setup').hidden,true);
  }
  assert.equal(advance.disabled,true);
  assert.match(d.querySelector('#champion-banner').textContent,new RegExp(finished.champion.team.city));
  if(index===2) assert.match(d.querySelector('#postseason-status').textContent,/champions/);
  go('race');
  d.querySelector('#change-team-button').click();
  d.querySelector('#cancel-team-change').click();
  checkView('race');
  assert.equal(d.querySelector('#roster-stats-button').getAttribute('aria-pressed'),'true');
  assert.equal(d.querySelector('#roster-competition').value,'playoffs');
  assert.equal(advance.textContent,'Postseason complete');
  panels.forEach(p=>checkPanel(p,false));
  d.querySelector('#change-team-button').click();
  d.querySelector('#team-select').value='seattle';
  d.querySelector('#team-form').dispatchEvent(new w.Event('submit',{cancelable:true}));
  await until(()=>!d.querySelector('#schedule-section').hidden);
  assert.equal(d.querySelector('#postseason-section').hidden,true);
  assert.equal(d.querySelectorAll('#schedule .completed').length,0);
  assert.equal(d.querySelector('#roster-ratings-button').getAttribute('aria-pressed'),'true');
  assert.equal(d.querySelector('#roster-competition').value,'regular');
  go('roster');
  // The new roster has Seattle IDs, so inspect zero totals directly after switching teams.
  d.querySelector('#roster-stats-button').click();
  assert.match(d.querySelector('#roster-stats-status').textContent,/0 team games/);
  assert.equal(d.querySelector('.roster-season-player[data-player-id="seattle-qb1"]').children[3].textContent,'0');
  go('schedule');
  checkView('schedule');
  assert.equal(advance.hidden,true);
  for(const view of ['game','league','standings','race','playoffs']) assert.equal(d.querySelector(`#${view}-empty`).hidden,false);
  assert.equal(d.querySelector('#season-status').textContent,'Ready for Week 1.');
  panels.forEach(p=>checkPanel(p,true));
  assert.equal(d.querySelectorAll('#schedule .game-final').length,17);
  assert.equal(start.hidden,true);
  assert.equal(d.querySelectorAll('.roster-player').length,38);
  assert.equal(d.querySelectorAll('.roster-group').length,10);
  const zero={passing:[{player:'QB',completions:0,attempts:0,yards:0,touchdowns:0,interceptions:0,completion_percentage:null,yards_per_attempt:null,passer_rating:null}],rushing:[{player:'RB',attempts:0,yards:0,touchdowns:0,yards_per_carry:null}],receiving:[{player:'WR',receptions:0,yards:0,touchdowns:0,yards_per_reception:null}],kicking:[{player:'K',field_goals_made:0,field_goals_attempted:0,field_goal_percentage:null,longest_field_goal:null,extra_points_made:3,extra_points_attempted:3,kicking_points:3}]};
  const fixture=d.createElement('div'); fixture.innerHTML=w.playerStatsMarkup(zero);
  checkEfficiency(fixture,zero);
  checkKicking(fixture,zero);
  zero.kicking[0].field_goals_attempted=1;zero.kicking[0].field_goal_percentage=0;
  fixture.innerHTML=w.playerStatsMarkup(zero);checkKicking(fixture,zero);
  assert.equal(fixture.querySelectorAll('.stat-section')[3].querySelectorAll('td')[3].textContent,'0.0%');
  assert.doesNotMatch(fixture.textContent,/NaN|Infinity|null|undefined/);
  dom.window.close();
 }
 console.log('UI checks passed: seven tabs, keyboard navigation, empty states, unchanged views across weeks, collapse state, efficiency/kicking/roster season stats, full seasons/playoffs, retry, and team reset/cancel.');
 }
(async()=>{
 const server=spawn(process.env.PYTHON || 'python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8767'],{cwd:root,stdio:['ignore','pipe','pipe']});
 let logs='';
 server.stdout.on('data',data=>{logs+=data});server.stderr.on('data',data=>{logs+=data});
 let spawnError;
 server.on('error',error=>{spawnError=error});
 try {
  let ready=false;
  for(let i=0;i<100;i++) {
   if(spawnError) throw spawnError;
   if(server.exitCode!==null) throw new Error(`Test server exited: ${logs}`);
   try {const response=await fetch(base+'/api/teams');if(response.ok){ready=true;break}} catch {}
   await new Promise(resolve=>setTimeout(resolve,100));
  }
  if(!ready) throw new Error(`Test server did not start: ${logs}`);
  await checkUI();
 } finally {server.kill()}
})().catch(error=>{console.error(error);process.exitCode=1});
