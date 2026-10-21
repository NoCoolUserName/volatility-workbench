// Offline report queue: only synthetic state and intercepted submission requests.
const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const assets=path.join(__dirname,'../src/volatility_workbench/static');
const profile={provider:'codex',model:'fixture-model',reasoning_effort:'high'};
const failed={id:'failed',request_id:'failed-request',case_id:'case',kind:'update',text:'Original failed prompt',status:'failed',error:'Synthetic report failure'};
const state={cases:[{id:'case',title:'Synthetic queue case',created_at:'2026-10-18T00:00:00Z',images:[],coins:[],
 readiness:{status:'Ready',reasons:[]},reports:[{id:'sealed',status:'sealed',created_at:'2026-10-18T00:00:00Z'}],messages:[],activity:[]}],
 jobs:[{id:'history',request_id:'history',case_id:'case',kind:'update',status:'completed',generation:profile,
 started_at:'2026-10-18T12:00:00Z',finished_at:'2026-10-18T12:02:00Z'},failed],approvals:[],account:{},evidence_root:'/synthetic'};
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.WORKBENCH_BROWSER_EXECUTABLE?{executablePath:process.env.WORKBENCH_BROWSER_EXECUTABLE}:{})});
 try{
  const page=await browser.newPage({viewport:{width:1400,height:1100}}),posts=[],errors=[];
  let hold=false,release;
  await page.addInitScript(()=>{window.EventSource=class extends EventTarget{close(){}};window.setInterval=()=>0;window.fixtureNow=Date.parse('2026-10-18T12:05:30Z');Date.now=()=>fixtureNow;});
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',async route=>{
   const request=route.request(),u=new URL(request.url());assert.equal(u.origin,'http://localhost');
   if(u.pathname==='/api/jobs'){
    const body=request.postDataJSON();posts.push(body);
    if(hold)await new Promise(resolve=>release=resolve);
    if(state.jobs.some(j=>j.case_id===body.case_id&&j.kind===body.kind&&['queued','running','stopping'].includes(j.status)&&j.text?.trim()===body.text.trim()))
     return route.fulfill({status:400,json:{error:'An identical request is already queued or running for this case'}});
    const job={...body,id:'request-'+posts.length,status:'queued',created_at:'2026-10-18T12:05:30Z',estimate_profile:profile};
    state.jobs.push(job);return route.fulfill({json:job});
   }
   assert.equal(request.method(),'GET','Only report submissions are permitted');
   if(u.pathname==='/api/settings/zoom')return route.fulfill({json:{schema:'zoom/1',percent:100}});
   if(u.pathname==='/api/state')return route.fulfill({json:state});
   if(u.pathname==='/api/file')return route.fulfill({json:{text:'# Synthetic sealed report',truncated:false}});
   if(u.pathname==='/api/artifacts')return route.fulfill({json:{files:[],truncated:false}});
   if(u.pathname==='/api/report-console')return route.fulfill({json:{case_id:'case',job_id:u.searchParams.get('job'),entries:[]}});
   if(u.pathname==='/api/report-plugins')return route.fulfill({json:{schema:'report-plugin-inventory/1',report_id:'sealed',source_status:'unavailable',summary:{},entries:[],next_offset:null,warnings:[]}});
   assert.ok(!u.pathname.startsWith('/api/'),'Unexpected request '+u.pathname);
   const name=u.pathname==='/'?'index.html':u.pathname.slice(1);
   return route.fulfill({body:fs.readFileSync(path.join(assets,name)),contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html'});
  });
  await page.goto('http://localhost/');await page.locator('#reportJobFailure').waitFor();
  await page.locator('#focus').fill('New follow-up');
  await page.locator('#reportJobFailure').getByRole('button',{name:'Rerun',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('#reportJobFailure').hidden);
  assert.equal(posts[0].text,'Original failed prompt');assert.equal(posts[0].retry_of,'failed');
  assert.equal(await page.locator('#focus').inputValue(),'New follow-up');
  await page.locator('#update').click();await page.waitForFunction(()=>document.querySelector('#focus').value==='');
  await page.waitForFunction(()=>!document.querySelector('#update').disabled);
  assert.deepEqual(state.jobs.filter(j=>j.status==='queued').map(j=>j.text),['Original failed prompt','New follow-up']);
  assert.match(await page.locator('#queueSummary').innerText(),/2 request\(s\).*4 min/);
  assert.match(await page.locator('#queue li').nth(1).innerText(),/#2.*queued.*2 min/);
  await page.locator('#focus').fill('New follow-up');await page.locator('#update').click();
  await page.getByText('An identical request is already queued or running for this case',{exact:true}).waitFor();
  assert.equal(await page.locator('#focus').inputValue(),'New follow-up');assert.equal(state.jobs.filter(j=>j.status==='queued').length,2);
  await page.locator('#focus').fill('Third submitted prompt');hold=true;
  await page.locator('#update').click();await page.waitForFunction(()=>document.querySelector('#update').disabled);
  await page.locator('#update').evaluate(node=>node.click());
  assert.equal(posts.length,4,'Repeated activation while sending is guarded');
  await page.locator('#focus').fill('Draft typed during submission');hold=false;release();
  await page.waitForFunction(()=>!document.querySelector('#update').disabled);
  assert.equal(await page.locator('#focus').inputValue(),'Draft typed during submission','Accepted request never clears a newer draft');
  const active=state.jobs.find(j=>j.id==='request-1');active.status='running';active.started_at='2026-10-18T12:05:00Z';state.active_job=active.id;
  await page.evaluate(()=>refresh());
  assert.equal(await page.evaluate(()=>typicalJobTime(state.jobs.find(j=>j.id==='request-1'),Date.now()).remaining),90);
  await page.evaluate(()=>window.fixtureNow=Date.parse('2026-10-18T12:08:00Z'));await page.evaluate(()=>refresh());
  assert.match(await page.locator('#queueSummary').innerText(),/Overall finish time is unknown/,'Past-typical active work never claims zero remaining time');
  state.jobs.filter(j=>j.status==='queued').forEach(j=>j.status='completed');active.status='completed';
  await page.evaluate(()=>refresh());assert.equal(await page.locator('#queueSummary').isHidden(),true);
  assert.deepEqual(errors,[]);
  console.log('Report queue: Rerun then distinct prompts, pending duplicates rejected, double activation, draft edits during submission, ordered queue labels, historical duration estimates and overrun/idle handling; synthetic only.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
