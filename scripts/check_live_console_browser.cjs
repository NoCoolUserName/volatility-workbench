// Offline console updates only; no analyzer, model, shell, or mutation requests.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const assets=path.join(__dirname,'../src/volatility_workbench/static');
const job={id:'job',case_id:'synthetic',kind:'update',status:'running',report_id:null,progress:'Starting'};
const version={id:'saved-report',status:'sealed',created_at:'2026-10-17T12:00:00Z'};
const report='# Synthetic saved report\n## Executive summary\nAI Determination: Undetermined\n'+Array.from({length:90},(_,i)=>'\nSaved synthetic paragraph '+i+'. '+ 'Synthetic saved detail. '.repeat(12)).join('');
const state={cases:[{id:'synthetic',title:'Synthetic case',created_at:'2026-10-18T12:00:00Z',
  images:[],coins:[],readiness:{status:'Unchecked',reasons:[]},reports:[version],messages:[],activity:[]}],
  jobs:[job],approvals:[],account:{},evidence_root:'/synthetic',
  live_console:{job_id:'job',case_id:'synthetic',entries:[],earlier_entries:0}};
const entry=(id,text)=>({id:String(id),time:'2026-10-18T12:00:00Z',text});
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.WORKBENCH_BROWSER_EXECUTABLE?{executablePath:process.env.WORKBENCH_BROWSER_EXECUTABLE}:{})});
 try{
  const page=await browser.newPage({viewport:{width:1400,height:1000}}),errors=[],calls=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.route('http://localhost/**',route=>{
   const url=new URL(route.request().url());calls.push(url.pathname);
   assert.equal(route.request().method(),'GET');
   if(url.pathname==='/api/state')return route.fulfill({json:state});
   if(url.pathname==='/api/file')return route.fulfill({json:{text:report,size:report.length,next_offset:report.length,truncated:false}});
   if(url.pathname==='/api/report-plugins')return route.fulfill({json:{schema:'report-plugin-inventory/1',report_id:version.id,scope:'bundled_saved_runs',source_status:'unavailable',summary:{},entries:[],next_offset:null,warnings:[]}});
   if(url.pathname==='/api/artifacts')return route.fulfill({json:{files:[],truncated:false}});
   assert.ok(!url.pathname.startsWith('/api/'),'Unexpected action '+url.pathname);
   const name=url.pathname==='/'?'index.html':url.pathname.slice(1);
   return route.fulfill({body:fs.readFileSync(path.join(assets,name)),contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html'});
  });
  await page.goto('http://localhost/');
  const pre=page.locator('#liveConsole');await pre.waitFor();
  assert.match(await pre.innerText(),/Waiting for tool output/);
  await page.locator('.report-determinations').waitFor();
  assert.equal(await page.locator('#queueSection').evaluate(node=>!!(node.compareDocumentPosition(document.querySelector('#case'))&Node.DOCUMENT_POSITION_FOLLOWING)),true,'Console and Current work precede the long report');
  assert.equal(await page.locator('#liveConsoleSection').isVisible(),true,'Starting update exposes console before draft creation');
  assert.equal(await page.locator('#liveConsoleTitle').evaluate(node=>{const box=node.getBoundingClientRect();return box.top>=0&&box.bottom<=innerHeight;}),true,'Console heading is visible without scrolling through a saved report');
  assert.match(await page.locator('#reportView').innerText(),/Saved synthetic paragraph 89/);
  assert.equal(await page.locator('#activeReportProgress').getByRole('progressbar').count(),1);
  assert.equal(await page.locator('#activeReportProgress').getByRole('progressbar').isVisible(),true,'DOS progress is styled and visible outside reportView');
  assert.equal(await page.locator('#liveConsoleSection input:not([type=checkbox]),#liveConsoleSection textarea').count(),0);
  state.live_console.entries=Array.from({length:40},(_,i)=>entry(i,i===0?'<img src=x onerror="window.injected=true">':'Actual synthetic output '+i+'\n'+'fixture '.repeat(20)));
  await page.evaluate(()=>refresh());
  assert.equal(await pre.locator('span').count(),40);
  assert.equal(await pre.locator('img,script').count(),0);assert.equal(await page.evaluate(()=>window.injected),undefined);
  assert.ok(await pre.evaluate(node=>node.scrollHeight-node.scrollTop-node.clientHeight<3),'New output follows the bottom');
  if(process.env.WORKBENCH_CONSOLE_SCREENSHOT)await page.locator('#liveConsoleSection').screenshot({path:process.env.WORKBENCH_CONSOLE_SCREENSHOT});
  await pre.focus();
  await pre.evaluate(node=>{node.scrollTop=0;node.dispatchEvent(new Event('scroll'));});
  assert.equal(await page.locator('#consoleFollow').isChecked(),false,'Reading earlier output pauses following');
  state.live_console.entries.push(entry(40,'Next real fixture output'));
  await page.evaluate(()=>refresh());assert.equal(await pre.evaluate(node=>node.scrollTop),0);
  assert.equal(await pre.evaluate(node=>node===document.activeElement),true,'Polling preserves keyboard focus in the console');
  await page.locator('#consoleFollow').check();
  assert.ok(await pre.evaluate(node=>node.scrollHeight-node.scrollTop-node.clientHeight<3));
  const first=await pre.locator('span').first().evaluate(node=>(node.dataset.retained='yes'));
  await page.evaluate(()=>refresh());assert.equal(await pre.locator('span').first().getAttribute('data-retained'),first,'Polling retains existing output nodes');
  for(const theme of ['matrix','blue','8-bit']){
   if(await page.locator('#theme').isHidden())await page.locator('#toggleTheme').click();
   await page.locator('#theme').selectOption(theme);
   assert.equal(await pre.evaluate(node=>getComputedStyle(node).backgroundColor),await page.locator('body').evaluate(node=>getComputedStyle(node).backgroundColor));
   assert.equal(await pre.evaluate(node=>getComputedStyle(node).color),await page.locator('header a').evaluate(node=>getComputedStyle(node).color));
  }
  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  state.live_console={job_id:'next',case_id:'synthetic',entries:[entry('next','New job output')],earlier_entries:0};
  await page.evaluate(()=>refresh());assert.doesNotMatch(await pre.innerText(),/Actual synthetic output/);
  state.jobs=[];state.live_console=null;await page.evaluate(()=>refresh());
  assert.equal(await page.locator('#queueSection').isHidden(),true);
  assert.deepEqual(errors,[]);assert.ok(calls.every(url=>['/api/state','/api/artifacts','/api/file','/api/report-plugins'].includes(url)||!url.startsWith('/api/')));
  console.log('Live console: visible before a long saved report and before draft creation, active progress, preserved focus, actual event append, plain text, scroll/follow pause, stable nodes, job isolation, theme colors, mobile, idle hiding; zero work requests.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
