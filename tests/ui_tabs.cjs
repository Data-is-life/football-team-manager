const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {spawn} = require('node:child_process');
const root = path.resolve(__dirname, '..');
const {JSDOM} = require('jsdom');
const base = 'http://127.0.0.1:8767';
// Fresh careers use the new rules; explicit legacy queries remain untouched.
const fetch=(input,init)=>{
 const url=new URL(input,base);
 if(/^\/api\/(team|season|playoffs)\//.test(url.pathname)&&!url.searchParams.has('lineup_rules'))url.searchParams.set('lineup_rules','4');
 return globalThis.fetch(url,init);
};
async function until(check) {
  for (let i=0;i<300;i++) { if(check()) return; await new Promise(r=>setTimeout(r,10)); }
  throw new Error('Expected UI state did not arrive');
}
const fixtureSeed=1234;
async function checkUI() {
 for(const endpoint of ['/api/team/seattle','/api/season/seattle/week/1','/api/playoffs/seattle/round/0']) {
  for(const bad of ['-1','4294967296','abc']) assert.equal((await fetch(base+endpoint+'?run_seed='+bad)).status,422);
 }
 const finished=await (await fetch(base+'/api/playoffs/seattle/round/4?run_seed='+fixtureSeed)).json();
 const teams=(await (await fetch(base+'/api/teams')).json()).teams;
 const ratingsByTeam=new Map(await Promise.all(teams.map(async team=>[team.id,(await (await fetch(base+`/api/team/${team.id}?run_seed=${fixtureSeed}`)).json()).ratings])));
 const field=finished.field;
 const firstLoser=finished.rounds[0].games[0];
 const loserId=firstLoser.winner.team.id===firstLoser.home.team.id ? firstLoser.away.team.id : firstLoser.home.team.id;
 const cases=[field[0].team.id, loserId, finished.champion.team.id, teams.find(t=>!field.some(f=>f.team.id===t.id)).id];
 for(const [index,id] of cases.entries()) {
  const dom=new JSDOM(await (await fetch(base)).text(),{url:base,runScripts:'outside-only'});
  const w=dom.window, d=w.document;
  // jsdom does not implement native dialog opening/closing or focus trapping.
  w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};
  w.HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new w.Event('close'));};
  let fail=false,randomCalls=0;
  const usedSeeds=[];
  Object.defineProperty(w.crypto,'getRandomValues',{value:array=>{array[0]=fixtureSeed+1+randomCalls++;return array}});
  w.fetch=path=>{
   const url=new URL(path,base);
   if(/^\/api\/(season|playoffs)\//.test(url.pathname)) usedSeeds.push(Number(url.searchParams.get('run_seed')));
   return fail && path.startsWith('/api/playoffs/') ? Promise.resolve({ok:false}) : fetch(url);
  };
  w.HTMLElement.prototype.scrollIntoView=()=>{};
  // Restore pre-rebuild careers to retain explicit bye/elimination/champion coverage.
  w.localStorage.setItem('arcade-league-save',JSON.stringify({version:7,teamId:id,runSeed:fixtureSeed,season:1,week:0,lineupRules:4,developmentStart:1,priorStandings:{},history:[],draftChoices:null,dropped:[],career:[],playoffRound:null}));
  w.eval(fs.readFileSync(path.join(root,'app/static/app.js'),'utf8'));
  await until(()=>d.querySelector('#team-select').options.length===31);
  await until(()=>/restored/.test(d.querySelector('#save-status').textContent));
  await until(()=>!d.querySelector('#schedule-section').hidden);
  const helpTopics=['team-ratings','career-records','player-development','roster-limits','roster-cuts','starter-selection','playoff-format','draft-format'];
  assert.equal(d.querySelectorAll('.info-control').length,helpTopics.length);
  const beforeHelp=w.localStorage.getItem('arcade-league-save');
  for(const topic of helpTopics){
   const help=d.getElementById(topic+'-info'),summary=help.firstElementChild;
   assert.equal(help.tagName,'DETAILS');assert.equal(help.open,false);assert.equal(summary.tagName,'SUMMARY');
   assert.ok(summary.textContent.replace('ⓘ','').trim().length>0,'Help has a descriptive visible label');
   assert.equal(summary.querySelector('span').getAttribute('aria-hidden'),'true');
   // Expose each control's containing view/dialog, as a user would before focusing it.
   const hidden=[],closed=[],dialogs=[];
   for(let parent=help.parentElement;parent;parent=parent.parentElement){
    if(parent.hidden){hidden.push(parent);parent.hidden=false;}
    if(parent.tagName==='DETAILS'&&!parent.open){closed.push(parent);parent.open=true;}
    if(parent.tagName==='DIALOG'&&!parent.open){dialogs.push(parent);parent.showModal();}
   }
   summary.focus();assert.equal(d.activeElement,summary);summary.click();assert.equal(help.open,true);summary.click();assert.equal(help.open,false);
   for(const dialog of dialogs)dialog.close();for(const detail of closed)detail.open=false;for(const node of hidden)node.hidden=true;
  }
  assert.equal(w.localStorage.getItem('arcade-league-save'),beforeHelp,'Reading help cannot alter saved progress');
  for(const selector of ['[role="status"]','[role="alert"]','#starter-timing','#cut-count','#cut-confirmation','#qualification-status','#roster-stats-note','#gm-legacy-note']){
   for(const node of d.querySelectorAll(selector))assert.equal(node.closest('.info-control'),null,'Progress, warnings and action timing stay outside help');
  }
  assert.equal(d.querySelector('#rating-method').closest('.info-control').id,'team-ratings-info');
  assert.equal(d.querySelector('#development-note').closest('.info-control').id,'player-development-info');
  assert.match(d.querySelector('#rating-method').textContent,/80% starters/);
  assert.match(d.querySelector('#development-note').textContent,/Ratings change once each offseason/);
  assert.equal(d.querySelectorAll('#schedule .opponent-record').length,17);
  for(const record of d.querySelectorAll('#schedule .opponent-record')) assert.equal(record.textContent,'Record: 0–0');
  assert.equal(d.querySelectorAll('.roster-player').length,38);
  assert.equal(d.querySelectorAll('.roster-group').length,10);
  const expected={QB:[2,1],WR:[4,2],TE:[2,1],RB:[2,1],OL:[8,5],K:[2,1],DL:[6,4],LB:[5,3],CB:[4,2],S:[3,2]};
  for(const [position,[count,min]] of Object.entries(expected)) {
   const group=d.querySelector(`[data-position="${position}"]`);
   assert.equal(group.querySelectorAll('.roster-player').length,count);
   assert.equal(group.querySelector('summary').textContent,`${position} · ${count} players · minimum ${min}`);
   group.open=false; assert.equal(group.open,false); group.open=true;
  }
  const api=await (await fetch(base+`/api/team/${id}?run_seed=${fixtureSeed}`)).json();
  assert.deepEqual([...d.querySelectorAll('.roster-player')].map(row=>row.dataset.playerId),api.roster.map(player=>player.id));
  function checkRatings(profile) {
   for (const rule of profile.roster_rules) {
    const group=d.querySelector(`#roster-groups .roster-group[data-position="${rule.position}"]`);
    const headings=[...group.querySelectorAll('.roster-rating-wrap th')].map(cell=>cell.textContent);
    assert.deepEqual(headings,['Depth','Player','Age','Current','Potential']);
    for(const player of profile.roster.filter(player=>player.position===rule.position)) {
     const cells=group.querySelector(`.roster-player[data-player-id="${player.id}"]`).children;
     assert.deepEqual([...cells].map(cell=>cell.textContent),[`${player.position}${player.depth}`,player.name,String(player.age),String(player.current_rating),String(player.potential_rating)]);
     assert.equal(group.querySelector(`.roster-player[data-player-id="${player.id}"]`).dataset.starter,String(player.depth<=rule.minimum));
     assert.equal(player.current_rating,player.rating);
     assert.ok(player.potential_rating>=player.current_rating);
     assert.equal(player.rating_change,0,'Fresh careers have no prior offseason change');
    }
   }
   assert.equal(d.querySelector('#attribute-guide-list'),null);
   assert.doesNotMatch(d.querySelector('#roster-groups').textContent,/Scouting rating|Football IQ|Clutch Factor/);
  }
  checkRatings(api);
  const views=['roster','game','schedule','standings','league','race','playoffs','gm'];
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
  key('roster','ArrowLeft','gm');
  key('gm','ArrowRight','roster');
  key('schedule','End','gm');
  key('gm','Home','roster');
  key('roster','ArrowRight','game');
  const rosterGroup=d.querySelector('.roster-group');rosterGroup.open=false;
  go('schedule');go('roster');assert.equal(rosterGroup.open,false);
  go('league');
  d.querySelector('#change-team-button').click();d.querySelector('#cancel-team-change').click();checkView('league');
  function checkLeagueContent() {
   for(const [buttonId,contentId] of [['league-results-toggle','league-results'],['standings-toggle','group-standings'],['playoff-race-toggle','playoff-race-content']]) {
    assert.equal(d.getElementById(buttonId),null);
    assert.equal(d.getElementById(contentId).hidden,false);
   }
  }
  checkLeagueContent();
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
    OL:[['blocking','pass_block_snaps'],['blocking','run_block_snaps'],['blocking','sacks_allowed']],
    ...Object.fromEntries(['DL','LB','CB','S'].map(position=>[position,[['defense','snaps'],['defense','tackles'],['defense','sacks'],['defense','interceptions']]])),
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
    assert.equal(group.querySelector('.roster-untracked-note').hidden,true);
    assert.equal(group.querySelector('.roster-stats-wrap').hidden,false);
    const total=snapshot.players.find(row=>row.player_id===player.id);
    const cells=group.querySelector(`.roster-season-player[data-player-id="${player.id}"]`).children;
    assert.equal(cells[0].textContent,String(player.depth));assert.equal(cells[1].textContent,player.name);
    assert.equal(cells[2].textContent,String(player.age));
    assert.equal(group.querySelectorAll('.roster-season-table th')[2].textContent,'Age');
    schema.forEach(([category,field],i)=>{
     const value=total[category][field];
     const expected=value==null?'—':field.includes('percentage')?`${value.toFixed(1)}%`:field==='longest_field_goal'?`${value} yd`:field.startsWith('yards_per_')||field==='passer_rating'?value.toFixed(1):String(value);
     assert.equal(cells[i+3].textContent,expected,`${player.id} ${category}.${field}`);
    });
   }
   assert.equal(d.querySelectorAll('#roster-groups .roster-season-player').length,38);
   assert.equal(d.querySelector('#roster-stats-note').hidden,false);
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
   checkLeagueContent();
   assert.equal(d.querySelectorAll('#league-results article').length,14);
   assert.equal(d.querySelectorAll('#group-standings article').length,6);
   assert.equal(d.querySelectorAll('#playoff-race tr').length,14);
   assert.match(d.querySelector('#league-results-title').textContent,new RegExp(`Week ${week}$`));
   const weekData=await (await fetch(base+`/api/season/${id}/week/${week}?season=1&run_seed=${fixtureSeed}`)).json();
   if(index===0 && week===1) {
    go('standings');
    const links=[...d.querySelectorAll('#group-standings .team-roster-link')];
    assert.equal(links.length,30);
    assert.deepEqual(new Set(links.map(button=>button.dataset.teamId)),new Set(teams.map(team=>team.id)));
    const before={roster:d.querySelector('#roster-groups').innerHTML,team:d.querySelector('#team-name').textContent,record:d.querySelector('#season-record').textContent,week:d.querySelector('#simulate-button').textContent,seedCalls:randomCalls};
    const dialog=d.querySelector('#team-roster-dialog');
    const target=links.find(button=>button.dataset.teamId!==id);
    target.click();
    await until(()=>d.querySelectorAll('#scout-groups .roster-player').length===38);
    assert.equal(dialog.open,true);
    checkView('standings');
    const profile=await (await fetch(base+`/api/team/${target.dataset.teamId}?run_seed=${fixtureSeed}`)).json();
    assert.equal(d.querySelector('#scout-title').textContent,`${profile.team.city} roster`);
    assert.match(d.querySelector('#scout-status').textContent,new RegExp(`Offense ${profile.ratings.offense} · Defense ${profile.ratings.defense}`));
    for(const player of profile.roster) {
     const row=d.querySelector(`#scout-groups [data-player-id="${player.id}"]`);
     assert.ok(row);
     const rule=profile.roster_rules.find(rule=>rule.position===player.position);
     assert.deepEqual([...row.children].map(cell=>cell.textContent),[`${player.position}${player.depth}`,player.name,String(player.age),String(player.current_rating),String(player.potential_rating)]);
    }
    d.querySelector('#scout-close').click();
    assert.equal(dialog.open,false);
    assert.equal(d.querySelector('#scout-groups').children.length,0);
    // Failed inspection can retry without disturbing the managed team.
    const realFetch=w.fetch;
    w.fetch=url=>url.startsWith(`/api/team/${target.dataset.teamId}?run_seed=${fixtureSeed}&`)?Promise.resolve({ok:false}):realFetch(url);
    target.click();await until(()=>!d.querySelector('#scout-retry').hidden);
    assert.equal(dialog.open,true);
    w.fetch=realFetch;d.querySelector('#scout-retry').click();
    await until(()=>d.querySelectorAll('#scout-groups .roster-player').length===38);
    d.querySelector('#scout-close').click();
    // A late response from a closed inspection must not replace the next roster.
    let release;
    w.fetch=url=>url.startsWith(`/api/team/${target.dataset.teamId}?run_seed=${fixtureSeed}&`)?Promise.resolve({ok:true,json:()=>new Promise(resolve=>{release=()=>resolve(profile);})}):realFetch(url);
    target.click();await until(()=>Boolean(release));d.querySelector('#scout-close').click();
    const ownLink=links.find(button=>button.dataset.teamId===id);
    ownLink.click();await until(()=>d.querySelectorAll('#scout-groups .roster-player').length===38);
    release();await new Promise(resolve=>setImmediate(resolve));
    assert.deepEqual([...d.querySelectorAll('#scout-groups .roster-player')].map(row=>row.dataset.playerId),api.roster.map(player=>player.id));
    d.querySelector('#scout-close').click();w.fetch=realFetch;
    assert.deepEqual({roster:d.querySelector('#roster-groups').innerHTML,team:d.querySelector('#team-name').textContent,record:d.querySelector('#season-record').textContent,week:d.querySelector('#simulate-button').textContent,seedCalls:randomCalls},before);
    go(selected);
   }
   assert.equal(d.querySelector('#gm-regular').textContent,`${weekData.record.wins}–${weekData.record.losses}–${weekData.record.ties}`);
   assert.equal(d.querySelector('#gm-appearances').textContent,String(week===17&&weekData.standings.playoff_race.some(entry=>entry.team.id===id)?1:0));
   assert.equal(d.querySelector('#gm-playoffs').textContent,'0–0');assert.equal(d.querySelector('#gm-championships').textContent,'0');
   const qualification=d.querySelector('#qualification-status');
   assert.equal(qualification.hidden,week<17,'Qualification is only announced after the regular season');
   assert.equal(qualification.getAttribute('role'),'status');
   if(week<17){assert.equal(qualification.textContent,'');assert.equal(qualification.dataset.outcome,'neutral');}
   else{
    const seed=weekData.standings.playoff_race.find(entry=>entry.team.id===id);
    assert.equal(qualification.dataset.outcome,seed?'win':'loss');
    assert.match(qualification.textContent,seed?/Congratulations!.*qualified/:/Sorry!.*missed/);
    assert.match(qualification.textContent,new RegExp(`Final record: ${weekData.record.wins}–${weekData.record.losses}${weekData.record.ties?'–'+weekData.record.ties:''}`));
    if(seed){assert.ok(qualification.textContent.includes(`seed #${seed.seed} (${seed.qualification})`));assert.equal(qualification.textContent.includes('first-round bye'),seed.bye);}
   }
   const groupCards=d.querySelectorAll('#group-standings .standings-card');
   weekData.standings.groups.forEach((group,i)=>{
    assert.deepEqual([...groupCards[i].querySelectorAll('th')].map(cell=>cell.textContent),['#','Team','Offense','Defense','Record','Diff']);
    const rows=groupCards[i].querySelectorAll('tbody tr');
    assert.equal(rows.length,5);
    group.teams.forEach((team,j)=>{
     const ratings=ratingsByTeam.get(team.team.id),cells=rows[j].children;
     assert.equal(cells[1].querySelector('.team-roster-link').dataset.teamId,team.team.id);
     assert.ok(cells[1].textContent.startsWith(team.team.city));
     assert.equal(cells[2].textContent,String(ratings.offense));
     assert.equal(cells[3].textContent,String(ratings.defense));
     assert.equal(cells[4].textContent,team.record);
     assert.equal(cells[5].textContent,`${team.point_differential>0?'+':''}${team.point_differential}`);
     assert.equal(rows[j].classList.contains('selected-team'),team.team.id===id);
    });
   });
   const history=weekData.game_results;
   go('roster');checkRoster(weekData.roster_stats,'regular');checkRoster(api.roster_stats,'playoffs');go(selected);
   const cards=d.querySelectorAll('#schedule .game-card');
   const opponentRows=new Map(weekData.standings.groups.flatMap(group=>group.teams).map(row=>[row.team.id,row]));
   cards.forEach(card=>{
    const row=opponentRows.get(card.dataset.opponentId);
    assert.ok(row,'Schedule opponents must match real standings teams');
    assert.equal(card.querySelector('.opponent-record').textContent,`Record: ${row.wins}–${row.losses}${row.ties?`–${row.ties}`:''}`);
    assert.equal(row.wins+row.losses+row.ties,week);
   });
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
   checkRatings(api);
   const tables=d.querySelectorAll('#player-stats tbody');
   assert.equal(tables[1].children.length,2);
   assert.equal(tables[2].children.length,8);
  }
  const regularFinal=(await (await fetch(base+`/api/season/${id}/week/17?season=1&run_seed=${fixtureSeed}`)).json()).roster_stats;
  const record=d.querySelector('#season-record').textContent;
  const qualificationText=d.querySelector('#qualification-status').textContent;
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
  assert.equal(d.querySelector('#postseason-status').dataset.outcome,'neutral');
  function checkPlayoffHighlight(state) {
   function checkGames(selector,games) {
    const cards=d.querySelectorAll(`${selector} .playoff-game-card`);
    assert.equal(cards.length,games.length);
    games.forEach((game,i)=>{
     const rows=cards[i].querySelectorAll('.league-team');
     ['away','home'].forEach((side,j)=>{
      const selected=game[side].team.id===id;
      assert.equal(rows[j].classList.contains('playoff-team-selected'),selected);
      assert.equal(rows[j].querySelector('.playoff-team-name').dataset.teamId,game[side].team.id);
      assert.equal(rows[j].querySelectorAll('.your-team-badge').length,selected?1:0);
      assert.equal(rows[j].classList.contains('winner'),Boolean(game.result && game.winner.team.id===game[side].team.id));
      assert.equal(rows[j].querySelector('strong').textContent,game.result?String(game.result[side].score):'');
     });
     assert.match(cards[i].querySelector('.control-label').textContent,game.result?(game.result.overtime?/Final · OT/:/Final/):game.neutral_site?/Neutral-site championship/:/Higher seed hosts/);
    });
   }
   const columns=d.querySelectorAll('#playoff-bracket .bracket-round');
   assert.equal(columns.length,4);
   assert.deepEqual([...columns].map(column=>column.querySelector('h3').textContent),['Wild Card','Quarterfinals','Semifinals','Championship']);
   assert.equal(d.querySelector('.bracket-scroll').tabIndex,0);
   assert.match(d.querySelector('#bracket-format').textContent,/Reseeded after every round/);
   columns.forEach((column,i)=>{
    const number=i+1, completed=state.rounds.find(round=>round.number===number);
    const upcoming=state.upcoming?.number===number?state.upcoming:null;
    const known=completed||upcoming;
    checkGames(`#playoff-bracket [data-round="${number}"]`,known?.games??[]);
    assert.equal(column.querySelector('.bracket-round-status').textContent,completed?'Complete':upcoming?'Up next':'Awaiting reseeding');
    const placeholders=column.querySelectorAll('.bracket-placeholder');
    assert.equal(placeholders.length,known?0:[6,4,2,1][i]);
    placeholders.forEach(card=>assert.equal(card.querySelectorAll('[data-team-id]').length,0,'Future opponents must not be predicted before reseeding'));
   });
   const latest=state.rounds.at(-1)?.games??[];
   const own=latest.filter(game=>game.home.team.id===id||game.away.team.id===id);
   // The last own game remains in the hidden holder after elimination.
   if(own.length) checkGames('#your-playoff-game',own);
   const byes=d.querySelectorAll('#playoff-bracket .bracket-bye .playoff-team-name');
   const expectedByes=state.field.filter(entry=>entry.bye);
   assert.equal(byes.length,2);
   byes.forEach((row,i)=>{
    assert.equal(row.dataset.teamId,expectedByes[i].team.id);
    assert.equal(row.querySelectorAll('.your-team-badge').length,row.dataset.teamId===id?1:0);
   });
  }
  checkPlayoffHighlight(await (await fetch(base+`/api/playoffs/${id}/round/0?run_seed=${fixtureSeed}`)).json());
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
   const state=await (await fetch(base+`/api/playoffs/${id}/round/${round}?run_seed=${fixtureSeed}`)).json();
   checkPlayoffHighlight(state);
   go('roster');checkRoster(state.roster_stats,'playoffs');checkRoster(regularFinal,'regular');checkRoster(state.roster_stats,'playoffs');go('playoffs');
   const latest=state.rounds.at(-1);
   const own=latest.games.find(g=>g.home.team.id===id||g.away.team.id===id);
   const latestOwn=state.rounds.flatMap(r=>r.games).filter(g=>g.home.team.id===id||g.away.team.id===id).at(-1);
   const outcome=d.querySelector('#postseason-status');
   const expectedOutcome=!state.qualified?'neutral':latestOwn?(latestOwn.winner.team.id===id?'win':'loss'):'neutral';
   assert.equal(outcome.dataset.outcome,expectedOutcome);
   if(expectedOutcome==='win') assert.match(outcome.textContent,/Congratulations!/);
   if(expectedOutcome==='loss') assert.match(outcome.textContent,/Sorry!.*eliminated/);
   if(expectedOutcome==='neutral') assert.doesNotMatch(outcome.textContent,/Congratulations!|Sorry!/);
   assert.equal(d.querySelector('#your-playoff-game').hidden,!own);
   assert.equal(d.querySelectorAll('#playoff-bracket .playoff-game-card').length,state.rounds.reduce((sum,r)=>sum+r.games.length,0)+(state.upcoming?.games.length??0));
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
  assert.equal(advance.disabled,true);assert.equal(d.querySelector('#qualification-status').textContent,qualificationText,'Regular-season qualification remains accurate through the playoffs');
  assert.match(d.querySelector('#champion-banner').textContent,new RegExp(finished.champion.team.city));
  if(index===2) assert.match(d.querySelector('#postseason-status').textContent,/champions/);
  go('race');
  d.querySelector('#change-team-button').click();
  d.querySelector('#cancel-team-change').click();
  checkView('race');
  assert.equal(d.querySelector('#roster-stats-button').getAttribute('aria-pressed'),'true');
  assert.equal(d.querySelector('#roster-competition').value,'playoffs');
  assert.equal(advance.textContent,'Postseason complete');
  checkLeagueContent();
  d.querySelector('#change-team-button').click();
  assert.equal(randomCalls,0,'Tab changes, weeks, rounds, retries and cancel must retain the run seed');
  assert.ok(usedSeeds.length>0 && usedSeeds.every(seed=>seed===fixtureSeed));
  d.querySelector('#team-select').value='seattle';
  const realFetch=w.fetch;
  const previousRoster=d.querySelector('#roster-groups').innerHTML;
  w.fetch=()=>Promise.resolve({ok:false});
  d.querySelector('#team-form').dispatchEvent(new w.Event('submit',{cancelable:true}));
  await until(()=>!d.querySelector('#error').hidden && !d.querySelector('#team-form button[type=submit]').disabled);
  assert.equal(randomCalls,1,'A failed start can draw a candidate seed without replacing the active run');
  assert.equal(d.querySelector('#roster-groups').innerHTML,previousRoster);
  assert.equal(d.querySelector('#season-record').textContent,record);
  w.fetch=realFetch;
  d.querySelector('#team-form').dispatchEvent(new w.Event('submit',{cancelable:true}));
  await until(()=>!d.querySelector('#schedule-section').hidden);
  assert.equal(d.querySelector('#postseason-section').hidden,true);
  assert.equal(d.querySelectorAll('#schedule .completed').length,16);
  assert.equal(d.querySelector('#postseason-status').dataset.outcome,'neutral');
  assert.equal(d.querySelector('#postseason-status').textContent,'');
  assert.equal(d.querySelector('#gm-regular').textContent,'0–0–0');
  assert.equal(d.querySelector('#roster-ratings-button').getAttribute('aria-pressed'),'true');
  assert.equal(d.querySelector('#roster-competition').value,'regular');
  const freshProfile=await (await fetch(base+`/api/team/seattle?run_seed=${fixtureSeed+2}&lineup_rules=6&rebuild_team=seattle`)).json();
  const oldSeattle=await (await fetch(base+`/api/team/seattle?run_seed=${fixtureSeed}`)).json();
  checkRatings(freshProfile);
  assert.notDeepEqual(freshProfile.roster.map(player=>player.name),oldSeattle.roster.map(player=>player.name));
  assert.deepEqual([...d.querySelectorAll('#roster-groups .roster-player')].map(row=>row.children[1].textContent),freshProfile.roster.map(player=>player.name));
  assert.equal(d.querySelector('#offense-rating').textContent,String(freshProfile.ratings.offense));
  assert.equal(d.querySelector('#defense-rating').textContent,String(freshProfile.ratings.defense));
  go('roster');
  // The new roster has Seattle IDs, so inspect zero totals directly after switching teams.
  d.querySelector('#roster-stats-button').click();
  assert.match(d.querySelector('#roster-stats-status').textContent,/16 team games/);
  assert.equal(d.querySelector('#career-start-note').hidden,false);
  go('schedule');
  checkView('schedule');
  assert.equal(advance.hidden,true);
  for(const view of ['playoffs']) assert.equal(d.querySelector(`#${view}-empty`).hidden,false);
  assert.match(d.querySelector('#season-status').textContent,/before Week 17/);assert.equal(d.querySelector('#qualification-status').hidden,true);assert.equal(d.querySelector('#qualification-status').textContent,'');
  checkLeagueContent();
  assert.equal(d.querySelectorAll('#schedule .game-final').length,17);
  assert.equal(start.hidden,true);
  assert.equal(d.querySelectorAll('.roster-player').length,38);
  assert.equal(d.querySelectorAll('.roster-group').length,10);
  assert.equal(randomCalls,2,'Starting another season gets a fresh seed');
  d.querySelector('#simulate-button').click();
  await until(()=>d.querySelector('#simulate-button').textContent==='Regular season complete');
  assert.equal(usedSeeds.at(-1),fixtureSeed+2);
  const freshGame=await (await fetch(base+`/api/season/seattle/week/17?run_seed=${fixtureSeed+2}&lineup_rules=6&rebuild_team=seattle`)).json();
  assert.equal(d.querySelector('#season-record').textContent,`${freshGame.record.wins}–${freshGame.record.losses}${freshGame.record.ties?`–${freshGame.record.ties}`:''}`);
  assert.equal(d.querySelector('#schedule .game-final').textContent,`${freshGame.game_results[0].outcome} · ${freshGame.game_results[0].team_score}–${freshGame.game_results[0].opponent_score}${freshGame.game_results[0].overtime?' · OT':''}`);
  if(index===0) {
   d.querySelector('#change-team-button').click();d.querySelector('#team-select').value='seattle';d.querySelector('#team-form').dispatchEvent(new w.Event('submit',{cancelable:true}));
   await until(()=>!d.querySelector('#schedule-section').hidden && d.querySelector('#simulate-button').textContent==='Simulate Week 17');
   const oldData=await (await fetch(base+`/api/season/seattle/week/17?run_seed=${fixtureSeed+3}&lineup_rules=6&rebuild_team=seattle`)).json();
   const live=w.fetch;let release;
   w.fetch=path=>path.startsWith('/api/season/') && new URL(path,base).pathname.endsWith('/17') ? Promise.resolve({ok:true,json:()=>new Promise(resolve=>{release=()=>resolve(oldData)})}) : live(path);
   d.querySelector('#simulate-button').click();await until(()=>Boolean(release));
   d.querySelector('#change-team-button').click();
   d.querySelector('#team-select').value='seattle';
   d.querySelector('#team-form').dispatchEvent(new w.Event('submit',{cancelable:true}));
   await until(()=>!d.querySelector('#schedule-section').hidden && d.querySelector('#simulate-button').textContent==='Simulate Week 17');
   release();await new Promise(resolve=>setImmediate(resolve));
   assert.equal(d.querySelector('#simulate-button').textContent,'Simulate Week 17','A late response from the old run must not overwrite the new run');
   assert.equal(d.querySelector('#gm-regular').textContent,'0–0–0');
   assert.equal(d.querySelectorAll('#schedule .completed').length,16);
   w.fetch=live;
  }
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
 console.log('UI checks passed: eight tabs, keyboard navigation, empty states, unchanged views across weeks, roster collapse state, always-expanded league content, efficiency/kicking/roster season stats, full seasons/playoffs, retry, team reset/cancel, and labeled native info disclosures with focus/click toggling, unchanged saves, live dynamic help and visible statuses.');
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
