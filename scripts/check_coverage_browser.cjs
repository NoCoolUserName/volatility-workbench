// All saved coverage is delivered automatically; no analysis or private files.
const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const assets=path.join(__dirname,'../src/volatility_workbench/static');
const makeCase=(id,title,images)=>({id,title,images,created_at:id==='a'?'2026-10-18T01:00:00Z':'2026-10-18T00:00:00Z',coins:[],reports:[],messages:[],activity:[],readiness:{status:'Unchecked',reasons:[]}});
const state={cases:[makeCase('a','Coverage A',[{id:'E001',path:'/synthetic/image.raw',size_bytes:4096}]),makeCase('b','Coverage B',[])],jobs:[],approvals:[],account:{},evidence_root:'/synthetic'};
const attempt=i=>({run_id:'saved-'+i,manifest:'saved-'+i+'/manifest.json',evidence:[],status:'success'});
const scope=i=>({entry_id:'scope-'+i,plugin:'windows.fixture.Plugin',arguments:[],question:'Scope '+i,
 effective:{execution:'success',applicability:'applicable',availability:'rows_present'},question_answered:'unknown',
 attempts:i?[]:Array.from({length:20},(_,i)=>attempt(i)),attempt_next_offset:i?null:20});
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.WORKBENCH_BROWSER_EXECUTABLE?{executablePath:process.env.WORKBENCH_BROWSER_EXECUTABLE}:{})});
 try{
  const page=await browser.newPage({viewport:{width:1400,height:850}}),requests=[],errors=[];let fail=false,hold=false,release;
  await page.addInitScript(()=>{window.EventSource=class extends EventTarget{close(){}};window.setInterval=()=>0;});
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',async route=>{
   const request=route.request(),u=new URL(request.url());assert.equal(u.origin,'http://localhost');assert.equal(request.method(),'GET');
   if(u.pathname==='/api/settings/zoom')return route.fulfill({json:{schema:'zoom/1',percent:100}});
   if(u.pathname==='/api/state')return route.fulfill({json:state});
   if(u.pathname==='/api/artifacts')return route.fulfill({json:{files:[],truncated:false}});
   if(u.pathname==='/api/coverage'){
    requests.push(u.search);if(hold)await new Promise(resolve=>release=resolve);
    const offset=Number(u.searchParams.get('offset')||0);
    if(fail&&offset===20)return route.fulfill({status:503,json:{error:'Synthetic saved-page read failed'}});
    const entries=u.searchParams.has('entry')?[{...scope(0),attempts:[attempt(20),attempt(21)],attempt_next_offset:null}]:
     Array.from({length:offset?10:20},(_,i)=>scope(i+offset));
    return route.fulfill({json:{scope:'saved_case',summary:{entries_with_successful_collection:30,declared_plan_entries:30,saved_attempts:22,physical_commands_recorded:22,reuse_requests:0},
     limitations:[],issues:[],orchestration_jobs:[],request_failures:[],entries,delivery:{next_offset:offset?null:20}}});
   }
   assert.ok(!u.pathname.startsWith('/api/'),'Unexpected API '+u.pathname);
   const name=u.pathname==='/'?'index.html':u.pathname.slice(1);
   return route.fulfill({body:fs.readFileSync(path.join(assets,name)),contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html'});
  });
  await page.goto('http://localhost/');await page.locator('#caseTitle').getByText('Coverage A').waitFor();
  await page.locator('[data-tab=coverage]').click();
  await page.waitForFunction(()=>document.querySelectorAll('.coverage-scope').length===30);
  assert.equal(await page.getByRole('button',{name:/More coverage|More attempts/}).count(),0);
  await page.locator('.coverage-scope').first().locator('summary').click();
  assert.equal(await page.getByRole('button',{name:/Open attempt/}).count(),22,'All attempt pages load without a second click');
  assert.equal(requests.length,3,'Bounded API pages are read automatically');
  await page.evaluate(()=>window.scrollTo(0,document.body.scrollHeight));await page.locator('#backToTop').waitFor();
  await page.locator('#backToTop').click();await page.waitForFunction(()=>window.scrollY<5);
  fail=true;await page.locator('#loadCoverage').click();
  await page.getByRole('alert').filter({hasText:'Synthetic saved-page read failed'}).waitFor();
  assert.equal(await page.locator('.coverage-scope').count(),20,'Read failure preserves already loaded scopes');
  fail=false;await page.locator('#loadCoverage').click();await page.waitForFunction(()=>document.querySelectorAll('.coverage-scope').length===30);
  hold=true;await page.locator('#loadCoverage').click();
  for(let n=0;n<100&&!release;n++)await page.waitForTimeout(5);
  assert.ok(release,'Synthetic held coverage request started');
  await page.getByRole('button',{name:'Coverage B',exact:true}).click();hold=false;release();
  await page.waitForTimeout(50);assert.equal(await page.locator('#coverageView .coverage-scope').count(),0,'Late case A response cannot enter case B');
  await page.locator('#loadCoverage').click();assert.match(await page.locator('#coverageView').innerText(),/No images/);
  assert.deepEqual(errors,[]);
  console.log('Coverage: all scope and attempt pages load automatically, partial-read errors and refresh recovery, stale-case protection, shared back-to-top arrow; no mutation or investigation requests.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
