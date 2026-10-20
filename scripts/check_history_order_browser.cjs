// Synthetic history only: sorting never submits investigation or plugin work.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const assets=path.join(__dirname,'../src/volatility_workbench/static');
const makeCase=(id,title,created_at)=>({id,title,created_at,images:[],coins:[],reports:[],readiness:{status:'Unchecked',reasons:[]},
 messages:[{role:'user',time:'2026-10-18T13:00:00Z',text:'Later'},
  {role:'assistant',time:'2026-10-18T07:00:00-05:00',text:'Earlier'},
  {role:'user',time:'2026-10-18T13:00:00Z',text:'Same-time follow-up'},
  {role:'assistant',time:'unknown',text:'Undated'}],
 activity:[{time:'2026-10-18T13:00:00Z',kind:'later',detail:{fixture:true}},
  {time:'2026-10-18T12:00:00Z',kind:'earlier',detail:{fixture:true}}]});
const state={cases:[makeCase('a','Case A','2026-10-18T01:00:00Z'),makeCase('b','Case B','2026-10-17T01:00:00Z')],
 jobs:[],approvals:[],account:{},evidence_root:'/synthetic'};
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.WORKBENCH_BROWSER_EXECUTABLE?{executablePath:process.env.WORKBENCH_BROWSER_EXECUTABLE}:{})});
 try{
  const page=await browser.newPage({viewport:{width:1400,height:1000}}),errors=[],saves=[];
  let fail=false;
  await page.addInitScript(()=>{window.EventSource=class extends EventTarget{close(){}};window.setInterval=()=>0;});
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',route=>{
   const request=route.request(),url=new URL(request.url());assert.equal(url.origin,'http://localhost');
   if(url.pathname==='/api/history-order'){
    const body=request.postDataJSON();saves.push(body);
    if(fail)return route.fulfill({status:503,json:{error:'Synthetic preference save failed'}});
    const c=state.cases.find(c=>c.id===body.case_id);c.history_order={...c.history_order,[body.section]:body.order};
    return route.fulfill({json:body});
   }
   assert.equal(request.method(),'GET','Only sort preference saves are allowed');
   if(url.pathname==='/api/settings/zoom')return route.fulfill({json:{schema:'zoom/1',percent:100}});
   if(url.pathname==='/api/state')return route.fulfill({json:state});
   if(url.pathname==='/api/artifacts')return route.fulfill({json:{files:[],truncated:false}});
   assert.ok(!url.pathname.startsWith('/api/'),'Unexpected request '+url.pathname);
   const name=url.pathname==='/'?'index.html':url.pathname.slice(1);
   return route.fulfill({body:fs.readFileSync(path.join(assets,name)),contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html'});
  });
  const messages=()=>page.locator('#messages > div').evaluateAll(nodes=>nodes.map(n=>n.textContent.split('\n').at(-1)));
  const activity=()=>page.locator('#activityList summary').evaluateAll(nodes=>nodes.map(n=>n.textContent.split(' · ').at(-1)));
  async function choose(section,order){
   const response=page.waitForResponse(r=>r.url().endsWith('/api/history-order'));
   await page.locator('#'+section+'Order').selectOption(order);await response;
   await page.waitForFunction(section=>!document.getElementById(section+'Order').disabled,section);
  }
  await page.goto('http://localhost/');await page.locator('#messages .message').first().waitFor({state:'attached'});
  await page.locator('[data-tab=conversation]').click();
  assert.deepEqual(await messages(),['Earlier','Later','Same-time follow-up','Undated']);
  await choose('conversation','newest');
  assert.deepEqual(await messages(),['Same-time follow-up','Later','Earlier','Undated']);
  await page.evaluate(()=>refresh());assert.equal(await page.locator('#conversationOrder').inputValue(),'newest');
  await page.locator('[data-tab=activity]').click();assert.deepEqual(await activity(),['later','earlier']);
  await choose('activity','oldest');assert.deepEqual(await activity(),['earlier','later']);
  await page.reload();await page.locator('#messages .message').first().waitFor({state:'attached'});
  assert.equal(await page.locator('#conversationOrder').inputValue(),'newest');
  assert.equal(await page.locator('#activityOrder').inputValue(),'oldest');
  await page.getByRole('button',{name:'Case B',exact:true}).click();
  assert.equal(await page.locator('#conversationOrder').inputValue(),'oldest');
  assert.equal(await page.locator('#activityOrder').inputValue(),'newest');
  await page.getByRole('button',{name:'Case A',exact:true}).click();
  assert.equal(await page.locator('#conversationOrder').inputValue(),'newest');
  assert.equal(await page.locator('#activityOrder').inputValue(),'oldest');
  assert.deepEqual(await page.evaluate(()=>caseNow().messages.map(m=>m.text)),['Later','Earlier','Same-time follow-up','Undated'],'Sort never mutates saved conversation sequence');
  state.cases[0].messages.push({role:'assistant',time:'2026-10-18T14:00:00Z',text:'Newest addition'});
  await page.evaluate(()=>refresh());assert.equal((await messages())[0],'Newest addition');
  await page.locator('[data-tab=activity]').click();fail=true;await choose('activity','newest');
  assert.equal(await page.locator('#activityOrder').inputValue(),'oldest','Failed save restores confirmed order');
  assert.match(await page.locator('#error').textContent(),/Synthetic preference save failed/);
  for(const id of ['matrix','fallout-3-robco','fallout-3-vault-112']){
   await page.evaluate(id=>WorkbenchThemes.apply(id),id);await page.setViewportSize({width:320,height:844});
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Sorting control fits narrow '+id+' view');
  }
  assert.deepEqual(errors,[]);assert.equal(saves.length,3);
  console.log('Case history: chronological/reverse ordering, timestamp offsets and ties, undated records, per-case independent preferences, reload/refresh/new arrivals/save failures, mobile controls; no investigation or evidence requests.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
