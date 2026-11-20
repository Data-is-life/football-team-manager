const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {JSDOM}=require('jsdom'),root=path.resolve(__dirname,'..');
const dom=new JSDOM(fs.readFileSync(path.join(root,'app/static/index.html'),'utf8'),{url:'http://localhost',runScripts:'outside-only'}),w=dom.window,d=w.document;
let requests=0;w.fetch=async()=>{requests++;return {ok:true,json:async()=>({teams:[]})};};
const players=[
 {id:'young',name:'Young',position:'QB',age:21,current_rating:80,potential_rating:90,annual_salary:1000000,years:2,affordable:true},
 {id:'edge',name:'Exact cap',position:'QB',age:25,current_rating:85,potential_rating:88,annual_salary:2000000,years:2,affordable:true},
 {id:'over',name:'Over cap',position:'QB',age:29,current_rating:90,potential_rating:92,annual_salary:2000001,years:2,affordable:false},
 {id:'other',name:'Other position',position:'WR',age:25,current_rating:75,potential_rating:95,annual_salary:1500000,years:2,affordable:false},
 {id:'old',name:'Veteran',position:'QB',age:35,current_rating:70,potential_rating:70,annual_salary:500000,years:1,affordable:true}
];
w.eval(fs.readFileSync(path.join(root,'app/static/app.js'),'utf8')+`
freeAgencyState=${JSON.stringify({available:players,profile:{payroll:{cap_space:2000000},roster:[]},order:[],transactions:[],complete:false})};window.setTestCap=value=>{freeAgencyState.profile.payroll.cap_space=value;renderFreeAgency();};renderFreeAgency();`);
const q=s=>d.querySelector(s),ids=()=>[...d.querySelectorAll('[data-fa-id]')].map(b=>b.dataset.faId);
const change=(id,value)=>{q(id).value=value;q(id).dispatchEvent(new w.Event(id.includes('age-')?'input':'change'));};
assert.deepEqual(ids(),['over','edge','young','other','old']);
const before=w.localStorage.getItem('arcade-league-save'),calls=requests;
change('#fa-age-min','25');assert.deepEqual(ids(),['over','edge','other','old']);
change('#fa-age-max','29');assert.deepEqual(ids(),['over','edge','other']);
change('#fa-position','QB');assert.deepEqual(ids(),['over','edge']);
change('#fa-cap-space','fits');assert.deepEqual(ids(),['edge'],'Exact cap fits; one dollar over does not');
change('#fa-age-max','25');assert.deepEqual(ids(),['edge'],'Age endpoints are inclusive');
change('#fa-age-min','26');assert.deepEqual(ids(),[]);assert.equal(q('#fa-empty').hidden,false);assert.match(q('#fa-empty').textContent,/filters/);
change('#fa-age-min','');change('#fa-age-max','');change('#fa-position','');
assert.deepEqual(ids(),['edge','young','other','old']);
assert.equal(q('[data-fa-id="other"]').disabled,true,'Cap fit does not bypass other signing restrictions');
change('#fa-sort','potential_rating');assert.deepEqual(ids(),['other','young','edge','old']);
w.setTestCap(1000000);assert.deepEqual(ids(),['young','old'],'Active filter refreshes when cap space changes');
w.setTestCap(-1);assert.deepEqual(ids(),[]);
change('#fa-cap-space','');assert.equal(ids().length,5);
change('#fa-age-max','21');assert.deepEqual(ids(),['young']);change('#fa-age-max','');assert.equal(ids().length,5);
assert.equal(requests,calls,'Filtering never sends a request');assert.equal(w.localStorage.getItem('arcade-league-save'),before);
for(const id of ['fa-age-min','fa-age-max','fa-cap-space'])assert.ok(d.querySelector(`label[for="${id}"]`));
w.close();console.log('Free-agent filters UI passed: age bounds, combined position/cap filters, exact cap, empty/reset, sort, cap refresh, signing eligibility, labels, and no requests/save changes.');
