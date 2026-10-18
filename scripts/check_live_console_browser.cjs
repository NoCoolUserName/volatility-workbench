// Offline console updates only; no analyzer, model, shell, or mutation requests.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const assets=path.join(__dirname,'../src/volatility_workbench/static');
const fixtureNow=Date.parse('2026-10-18T12:02:42Z');
const job={id:'job',case_id:'synthetic',kind:'update',status:'running',report_id:null,progress:'case_report_context',started_at:'2026-10-18T12:00:00Z'};
const version={id:'saved-report',status:'sealed',created_at:'2026-10-17T12:00:00Z'};
const report='# Synthetic saved report\n## Executive summary\nAI Determination: Undetermined\n'+Array.from({length:90},(_,i)=>'\nSaved synthetic paragraph '+i+'. '+ 'Synthetic saved detail. '.repeat(12)).join('');
const state={cases:[{id:'synthetic',title:'Synthetic case · Win XP',created_at:'2026-10-18T12:00:00Z',
  images:[],coins:[],readiness:{status:'Unchecked',reasons:[]},reports:[version],messages:[],activity:[]}],
  jobs:[job],approvals:[],account:{},evidence_root:'/synthetic',
  live_console:{job_id:'job',case_id:'synthetic',entries:[],earlier_entries:0}};
const entry=(id,text)=>({id:String(id),time:'2026-10-18T12:00:00Z',text});
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.WORKBENCH_BROWSER_EXECUTABLE?{executablePath:process.env.WORKBENCH_BROWSER_EXECUTABLE}:{})});
 try{
  const page=await browser.newPage({viewport:{width:1400,height:1000}}),errors=[],calls=[];
  // Transport behavior has its own synthetic VolShell/SSE checks. This fixture
  // keeps the optional terminal subscription offline while testing saved output.
  await page.addInitScript(()=>{window.EventSource=class extends EventTarget {close(){}};});
  await page.addInitScript(now=>{window.fixtureNow=now;Date.now=()=>window.fixtureNow;},fixtureNow);
  let retained=null,rejectSaved=false;
  page.on('pageerror',error=>errors.push(error.message));
  await page.route('**/*',route=>{
   const url=new URL(route.request().url());calls.push(url.pathname);
   assert.equal(url.origin,'http://localhost','Synthetic console check makes no external requests');
   assert.equal(route.request().method(),'GET');
   if(url.pathname==='/api/state')return route.fulfill({json:state});
   if(url.pathname==='/api/report-console')return rejectSaved?route.fulfill({status:503,json:{error:'Synthetic saved-console read failure'}}):route.fulfill({json:retained});
   if(url.pathname==='/api/file')return route.fulfill({json:{text:report,size:report.length,next_offset:report.length,truncated:false}});
   if(url.pathname==='/api/report-plugins')return route.fulfill({json:{schema:'report-plugin-inventory/1',report_id:version.id,scope:'bundled_saved_runs',source_status:'unavailable',summary:{},entries:[],next_offset:null,warnings:[]}});
   if(url.pathname==='/api/artifacts')return route.fulfill({json:{files:[],truncated:false}});
   assert.ok(!url.pathname.startsWith('/api/'),'Unexpected action '+url.pathname);
   const name=url.pathname==='/'?'index.html':url.pathname.slice(1);
   return route.fulfill({body:fs.readFileSync(path.join(assets,name)),contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html'});
  });
  await page.goto('http://localhost/');
  const pre=page.locator('#liveConsole'),consoleOperation=page.locator('#consoleOperation');await pre.waitFor();
  async function expectConsoleOperation(text){
   assert.equal(await consoleOperation.textContent(),text);
   assert.equal(await consoleOperation.isVisible(),!!text,'Tool/elapsed label is visible only for matching expanded live work');
  }
  await expectConsoleOperation('');
  assert.equal(await page.locator('#operation').textContent(),'case_report_context · 162s elapsed');
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
  const expand=page.locator('#expandConsole'),zoom=page.locator('#consoleZoom');
  assert.equal(await expand.innerText(),'Expand');
  assert.equal(await expand.evaluate(node=>Math.abs(node.getBoundingClientRect().right-document.querySelector('#liveConsoleSection').getBoundingClientRect().right)<2),true,'Expand sits in the upper-right console controls');
  await pre.evaluate(node=>window.retainedConsole=node);
  await expand.scrollIntoViewIfNeeded();const originalPagePosition=await page.evaluate(()=>scrollY);
  await expand.click();await zoom.waitFor();
  await expectConsoleOperation('case_report_context · 162s elapsed');
  assert.equal(await consoleOperation.textContent(),await page.locator('#operation').textContent(),'Expanded status mirrors the existing progress source');
  assert.equal(await consoleOperation.evaluate(node=>getComputedStyle(node).color),await page.locator('#operation').evaluate(node=>getComputedStyle(node).color),'Expanded status keeps the existing amber status color');
  assert.equal(await consoleOperation.evaluate(node=>{
   const status=node.getBoundingClientRect(),title=document.querySelector('#liveConsoleTitle').getBoundingClientRect();
   return status.left>=title.right&&Math.abs((status.top+status.bottom-title.top-title.bottom)/2)<12;
  }),true,'Desktop tool status sits immediately to the right of the case title');
  assert.equal(await expand.innerText(),'Collapse');assert.equal(await expand.getAttribute('aria-expanded'),'true');
  assert.equal(await pre.evaluate(node=>node===window.retainedConsole),true,'Expansion moves the same live console');
  assert.equal(await zoom.evaluate(node=>{const box=node.getBoundingClientRect();return box.width>=innerWidth*.9&&box.height>=innerHeight*.9;}),true,'Expanded monitor nearly fills the viewport');
  assert.ok((await pre.boundingBox()).height>450,'Expanded output uses the available monitor height');
  for(let i=0;i<5;i++){await page.keyboard.press('Tab');assert.equal(await zoom.evaluate(node=>node.contains(document.activeElement)),true,'Modal keeps keyboard focus in the monitor');}
  for(let i=0;i<5;i++){await page.keyboard.press('Shift+Tab');assert.equal(await zoom.evaluate(node=>node.contains(document.activeElement)),true,'Reverse tab remains inside the monitor');}
  state.live_console.entries.push(entry('follow','Following output while monitor is expanded'));
  job.progress='windows.pslist';await page.evaluate(()=>{window.fixtureNow+=5000;});
  await page.evaluate(()=>refresh());
  await expectConsoleOperation('windows.pslist · 167s elapsed');
  assert.equal(await consoleOperation.textContent(),await page.locator('#operation').textContent(),'Existing refresh updates both elapsed labels together');
  job.status='stopping';await page.evaluate(()=>refresh());
  await expectConsoleOperation('windows.pslist · 167s elapsed · stopping…');
  job.status='running';await page.evaluate(()=>refresh());
  assert.ok(await pre.evaluate(node=>node.scrollHeight-node.scrollTop-node.clientHeight<3),'Expanded output still follows appended events');
  await pre.focus();await pre.evaluate(node=>{node.scrollTop=0;node.dispatchEvent(new Event('scroll'));});
  state.live_console.entries.push(entry(41,'Live update while monitor is expanded'));
  await page.evaluate(()=>refresh());
  assert.match(await pre.innerText(),/Live update while monitor is expanded/);
  assert.equal(await pre.evaluate(node=>node===document.activeElement),true,'Live polling keeps expanded console focus');
  assert.equal(await pre.evaluate(node=>node.scrollTop),0,'Expanded paused output does not jump');
  await expand.click();await page.locator('#liveConsoleDock #liveConsoleSection').waitFor();
  await expectConsoleOperation('');
  assert.equal(await expand.innerText(),'Expand');assert.equal(await page.locator('#consoleFollow').isChecked(),false);
  assert.equal(await expand.evaluate(node=>node===document.activeElement),true,'Collapse returns focus to its control');
  assert.ok(Math.abs(await page.evaluate(()=>scrollY)-originalPagePosition)<2,'Collapse returns to the same page position');
  assert.equal(await pre.evaluate(node=>node.scrollTop),0,'Collapse retains paused scroll position');
  await expand.click();await zoom.waitFor();await page.keyboard.press('Escape');
  await page.waitForFunction(()=>document.querySelector('#expandConsole').getAttribute('aria-expanded')==='false');
  assert.equal(await zoom.isHidden(),true,'Escape closes the monitor');
  await expectConsoleOperation('');
  assert.equal(await page.locator('body').evaluate(node=>node.classList.contains('console-zoom-open')),false);
  for(const theme of ['matrix','blue','8-bit','fallout-new-vegas','fallout-2']){
   if(await page.locator('#theme').isHidden())await page.locator('#toggleTheme').click();
   await page.locator('#theme').selectOption(theme);
   await expand.click();await zoom.waitFor();
   await expectConsoleOperation('windows.pslist · 167s elapsed');
   assert.equal(await consoleOperation.evaluate(node=>getComputedStyle(node).color),await page.locator('#operation').evaluate(node=>getComputedStyle(node).color),theme+' keeps matching progress colors');
   if(theme!=='fallout-2')assert.equal(await pre.evaluate(node=>getComputedStyle(node).backgroundColor),await page.locator('body').evaluate(node=>getComputedStyle(node).backgroundColor));
   else assert.ok(await pre.evaluate(node=>{
    const style=getComputedStyle(node),luminance=value=>{
     const channels=value.match(/[\d.]+/g).slice(0,3).map(Number).map(n=>n/255).map(n=>n<=.04045?n/12.92:((n+.055)/1.055)**2.4);
     return channels[0]*.2126+channels[1]*.7152+channels[2]*.0722;
    };
    const text=luminance(style.color),background=luminance(style.backgroundColor);
    return(Math.max(text,background)+.05)/(Math.min(text,background)+.05)>=4.5;
   }),'Fallout 2 phosphor console text stays readable on its recessed screen');
   assert.equal(await pre.evaluate(node=>getComputedStyle(node).color),await page.locator('header a').evaluate(node=>getComputedStyle(node).color));
   if(theme==='matrix'&&process.env.WORKBENCH_CRT_SCREENSHOT)await zoom.screenshot({path:process.env.WORKBENCH_CRT_SCREENSHOT});
   if(theme==='fallout-2'&&process.env.WORKBENCH_FALLOUT_CRT_SCREENSHOT)await zoom.screenshot({path:process.env.WORKBENCH_FALLOUT_CRT_SCREENSHOT});
   if(theme==='fallout-new-vegas'){
    if(process.env.WORKBENCH_NEW_VEGAS_CRT_SCREENSHOT)await zoom.screenshot({path:process.env.WORKBENCH_NEW_VEGAS_CRT_SCREENSHOT});
    await page.setViewportSize({width:320,height:844});
    assert.equal(await zoom.evaluate(node=>node.scrollWidth<=node.clientWidth+1),true,'New Vegas output CRT fits the narrow viewport');
    assert.ok((await pre.boundingBox()).height>200,'New Vegas sign preserves a usable output area');
    if(process.env.WORKBENCH_NEW_VEGAS_CRT_MOBILE_SCREENSHOT)await zoom.screenshot({path:process.env.WORKBENCH_NEW_VEGAS_CRT_MOBILE_SCREENSHOT});
    await page.setViewportSize({width:1400,height:1000});
   }
   await expand.click();await page.waitForFunction(()=>document.querySelector('#expandConsole').getAttribute('aria-expanded')==='false');
  }
  await page.setViewportSize({width:2560,height:1440});
  await expand.click();await zoom.waitFor();
  assert.equal(await zoom.evaluate(node=>node.getBoundingClientRect().width>innerWidth*.95),true,'High-resolution display stays near full-screen');
  if(process.env.WORKBENCH_CRT_LARGE_SCREENSHOT)await zoom.screenshot({path:process.env.WORKBENCH_CRT_LARGE_SCREENSHOT});
  await expand.click();await page.waitForFunction(()=>document.querySelector('#expandConsole').getAttribute('aria-expanded')==='false');
  await page.setViewportSize({width:390,height:844});
  await expand.click();await zoom.waitFor();
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  assert.equal(await zoom.evaluate(node=>node.scrollWidth<=node.clientWidth+1),true,'Mobile monitor has no horizontal overflow');
  assert.ok((await pre.boundingBox()).height>300,'Mobile console remains usable');
  await expectConsoleOperation('windows.pslist · 167s elapsed');
  assert.equal(await consoleOperation.evaluate(node=>{
   const status=node.getBoundingClientRect(),title=document.querySelector('#liveConsoleTitle').getBoundingClientRect(),screen=document.querySelector('.crt-screen').getBoundingClientRect();
   return status.top>=title.bottom&&status.left>=screen.left&&status.right<=screen.right;
  }),true,'Narrow CRT wraps tool status below the title within the screen');
  if(process.env.WORKBENCH_CRT_MOBILE_SCREENSHOT)await zoom.screenshot({path:process.env.WORKBENCH_CRT_MOBILE_SCREENSHOT});
  // Live console follows its stream's job, even when a different case is selected.
  const otherCase={...state.cases[0],id:'other-live-case',title:'Other synthetic case',reports:[]};
  const otherJob={...job,id:'other-live-job',case_id:otherCase.id,progress:'other_case_tool'};
  const originalStream=state.live_console;
  state.cases.push(otherCase);state.jobs=[job,otherJob];
  state.live_console={job_id:otherJob.id,case_id:otherCase.id,entries:[entry('other','Other synthetic case output')],earlier_entries:0};
  await page.evaluate(()=>refresh());
  await page.waitForFunction(()=>!document.querySelector('#consoleZoom').open);
  await expectConsoleOperation('');
  await expand.click();await zoom.waitFor();
  await expectConsoleOperation('other_case_tool · 167s elapsed');
  assert.match(await page.locator('#liveConsoleTitle').textContent(),/Other synthetic case/);
  assert.doesNotMatch(await consoleOperation.textContent(),/windows\.pslist/,'Changing the stream case never retains another job label');
  state.jobs=[job];await page.evaluate(()=>refresh());await expectConsoleOperation('');
  state.jobs=[job,{...otherJob,case_id:'mismatched-case'}];await page.evaluate(()=>refresh());await expectConsoleOperation('');
  state.jobs=[job,otherJob];state.live_console.status='completed';await page.evaluate(()=>refresh());await expectConsoleOperation('');
  state.jobs=[job];state.live_console=originalStream;await page.evaluate(()=>refresh());
  await page.waitForFunction(()=>!document.querySelector('#consoleZoom').open);
  await expectConsoleOperation('');
  await expand.click();await zoom.waitFor();await expectConsoleOperation('windows.pslist · 167s elapsed');
  state.live_console={job_id:'next',case_id:'synthetic',entries:[entry('next','New job output')],earlier_entries:0};
  await page.evaluate(()=>refresh());assert.doesNotMatch(await pre.innerText(),/Actual synthetic output/);
  await page.waitForFunction(()=>!document.querySelector('#consoleZoom').open&&document.querySelector('#expandConsole').getAttribute('aria-expanded')==='false');
  await expectConsoleOperation('');
  const nextJob={...job,id:'next',progress:'next_tool',started_at:'2026-10-18T12:02:00Z'};
  state.jobs=[nextJob];await page.evaluate(()=>refresh());
  await expand.click();await zoom.waitFor();
  await expectConsoleOperation('next_tool · 47s elapsed');
  const finished={id:'next',case_id:'synthetic',kind:'update',status:'completed',finished_at:'2026-10-18T12:05:00Z'};
  retained={...state.live_console,status:'completed',finished_at:finished.finished_at};
  state.jobs=[finished];state.live_console=null;await page.evaluate(()=>refresh());
  await page.waitForFunction(()=>document.querySelector('#liveConsoleTitle').textContent.includes('completed'));
  assert.equal(await zoom.isVisible(),true,'Finishing a job keeps the CRT open for review');
  await expectConsoleOperation('');
  assert.match(await pre.innerText(),/New job output/);
  assert.equal(await page.locator('#consolePowerText').innerText(),'SAVED');
  assert.equal(await page.locator('#stop').isHidden(),true,'Saved output must not expose an active Stop button');
  assert.equal(await page.getByRole('progressbar').count(),0,'Saved output must not imply running work');
  assert.equal(await page.locator('#workTitle').textContent(),'Report console');
  await expand.click();await page.waitForFunction(()=>!document.querySelector('#consoleZoom').open);
  rejectSaved=true;await page.reload();await page.getByRole('button',{name:'Retry loading',exact:true}).waitFor();
  assert.match(await page.locator('#consoleNote').innerText(),/Synthetic saved-console read failure/);
  rejectSaved=false;await page.getByRole('button',{name:'Retry loading',exact:true}).click();
  await page.getByText('New job output',{exact:false}).waitFor();
  assert.match(await pre.innerText(),/New job output/,'Saved output loads after a page restart');
  await expand.click();await zoom.waitFor();assert.match(await pre.innerText(),/New job output/);
  await expectConsoleOperation('');
  await expand.click();await page.waitForFunction(()=>!document.querySelector('#consoleZoom').open);
  state.cases.push({...state.cases[0],id:'empty-case',title:'Different case',reports:[]});await page.evaluate(()=>refresh());
  await page.getByRole('button',{name:'Different case',exact:true}).click();
  assert.equal(await page.locator('#queueSection').isHidden(),true,'Another case must not inherit saved output');
  await expectConsoleOperation('');
  await page.getByRole('button',{name:'Synthetic case · Win XP',exact:true}).click();await pre.waitFor();
  assert.match(await pre.innerText(),/New job output/,'Returning to the case restores its saved console');
  assert.deepEqual(errors,[]);assert.ok(calls.every(url=>['/api/state','/api/artifacts','/api/file','/api/report-plugins','/api/report-console'].includes(url)||!url.startsWith('/api/')));
  console.log('Live/saved console: safe bounded output and CRT interactions; mirrored amber tool/elapsed updates, desktop/mobile placement, stopping and stale-label clearing across collapse/job/case/completion; completion keeps expanded review open, saved reload, case isolation; zero work/external requests.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
