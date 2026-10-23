// Fully intercepted synthetic UI: no server, interpreter, provider, or evidence access.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const assets=path.join(__dirname,'../src/volatility_workbench/static');
const stamp='2026-10-18T12:00:00Z';
const makeCase=(id,title,os)=>({id,title,created_at:stamp,images:[{id:'E001',path:'/synthetic/'+id+'.vmem',size_bytes:4096,discovery:{detected_os:os}}],coins:[],readiness:{status:'Unchecked',reasons:[]},reports:[],messages:[],activity:[]});
const state={cases:[makeCase('case-a','Synthetic Windows case','windows'),makeCase('case-b','Synthetic Linux case','linux')],jobs:[],approvals:[],account:{},evidence_root:'/synthetic',live_console:null,volshell:{session:null,busy:false}};
const entry=(kind,text)=>({id:String(++entryId),kind,text,time:stamp});
let entryId=0;
// Fresh fixtures isolate connection decisions from the long-lived interaction
// tests below. Every POST is intercepted; no interpreter or image is opened.
async function checkBezelConnection(browser){
 const existing=(caseId='case-b',status='running')=>({id:'existing-shell',case_id:caseId,image_id:'E001',mode:caseId==='case-b'?'linux':'windows',status,ready:status==='running',entries:[entry('output','Private output for '+caseId)],earlier_entries:0});
 const fixture=async({images,session=null,jobs=[],reply='start'}={})=>{
  const page=await browser.newPage({viewport:{width:1400,height:1000}}),requests=[],closes=[],errors=[];
  const value={cases:[makeCase('case-a','Synthetic Windows case','windows'),makeCase('case-b','Synthetic Linux case','linux')],jobs,approvals:[],account:{},evidence_root:'/synthetic',live_console:null,volshell:{session,busy:!!session}};
  if(images)value.cases[1].images=images;
  const control={reply,returned:null,closeReply:'closed',heldClose:null};
  await page.addInitScript(()=>{
   window.fixtureStreams=[];window.EventSource=class extends EventTarget{static CLOSED=2;constructor(){super();this.readyState=1;fixtureStreams.push(this);}close(){this.readyState=2;}emit(value){this.dispatchEvent(new MessageEvent('volshell',{data:JSON.stringify(value)}));}};
   const interval=setInterval;window.setInterval=(callback,delay,...args)=>delay===1500?0:interval(callback,delay,...args);
  });
  page.on('pageerror',error=>errors.push(error.message));
  await page.route('**/*',async route=>{
    if (new URL(route.request().url()).pathname === '/api/settings/zoom') return route.fulfill({json:{schema:'zoom/1',percent:100}});
   const request=route.request(),url=new URL(request.url());
   assert.equal(url.origin,'http://localhost');
   if(request.method()==='GET'){
    if(url.pathname==='/api/state')return route.fulfill({json:value});
    if(url.pathname==='/api/artifacts')return route.fulfill({json:{files:[],truncated:false}});
    if(url.pathname==='/api/report-console')return route.fulfill({json:null});
    assert.ok(!url.pathname.startsWith('/api/'),'Unexpected read '+url.pathname);
    const name=url.pathname==='/'?'index.html':url.pathname.slice(1);
    return route.fulfill({body:fs.readFileSync(path.join(assets,name)),contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html'});
   }
   if(url.pathname==='/api/volshell/close'){
    const body=request.postDataJSON();closes.push(body);
    assert.deepEqual(body,{case_id:value.volshell.session.case_id,session_id:value.volshell.session.id},'Close addresses the exact owning session');
    if(control.closeReply==='hold'){control.heldClose=route;return;}
    if(control.closeReply==='fail')return route.fulfill({status:500,json:{error:'Synthetic close failed; process remains alive'}});
    const closed={busy:false,session:{...value.volshell.session,status:'closed',ready:false}};
    if(control.closeReply!=='lag')value.volshell=closed;
    return route.fulfill({json:closed});
   }
   assert.equal(url.pathname,'/api/volshell/start','Connection controls never execute commands');
   const body=request.postDataJSON();requests.push(body);
   if(control.reply==='fail')return route.fulfill({status:500,json:{error:'Synthetic interpreter could not start'}});
   control.returned={busy:true,session:{id:'new-shell-'+requests.length,case_id:body.case_id,image_id:body.image_id,mode:body.mode,status:control.reply==='ready'?'running':'starting',ready:control.reply==='ready',entries:[],earlier_entries:0}};
   if(control.reply!=='lag')value.volshell=control.returned;
   return route.fulfill({json:control.returned});
  });
  await page.goto('http://localhost/?case=case-b');await page.locator('#openCaseConsole').click();
  const refresh=()=>page.evaluate(()=>refresh());
  const click=async()=>{await page.locator('#consoleVolshellMode').click();await page.waitForFunction(()=>document.querySelector('#volshellStatus').textContent!=='Request in progress…');};
  const close=async()=>{assert.deepEqual(errors,[]);await page.close();};
  return {page,value,requests,closes,control,refresh,click,close};
 };
 let f=await fixture();
 assert.equal(await f.page.locator('#volshellConnection').evaluate(node=>node.open),false);
 await f.page.locator('#collapseVolshell').click();await f.page.locator('#openCaseConsole').click();
 await f.page.locator('#consoleOutputMode').click();
 assert.equal(f.requests.length,0,'Opening/reopening the monitor and viewing Output never connect');
 await f.click();assert.deepEqual(f.requests,[{case_id:'case-b',image_id:'E001',mode:'linux'}],'Bezel connects the selected Linux case, not the first Windows case');
 await f.click();await f.refresh();assert.equal(f.requests.length,1,'A starting session is reused');
 f.value.volshell.session.status='running';f.value.volshell.session.ready=true;await f.refresh();
 assert.equal(await f.page.locator('#volshellInput').evaluate(node=>document.activeElement===node),true,'The first ready prompt focuses its input when focus stayed on Collapse');
 assert.equal(f.requests.length,1);assert.equal(await f.page.locator('#volshellInput').isDisabled(),false);await f.close();

 f=await fixture({reply:'ready'});await f.click();
 assert.equal(await f.page.locator('#volshellInput').evaluate(node=>document.activeElement===node),true,'An immediately ready POST response waits for the input to be enabled before focusing it');await f.close();
 for(const selector of ['#volshellInteractionMode','#volshellConnection summary']){
  f=await fixture();await f.click();await f.page.locator(selector).focus();
  f.value.volshell.session.status='running';f.value.volshell.session.ready=true;await f.refresh();
  assert.equal(await f.page.locator(selector).evaluate(node=>document.activeElement===node),true,'Readiness never steals focus from '+selector);await f.close();
 }
 f=await fixture();await f.click();await f.page.locator('#collapseVolshell').click();
 f.value.volshell.session.status='running';f.value.volshell.session.ready=true;await f.refresh();
 assert.equal(await f.page.locator('#consoleZoom').isHidden(),true,'Readiness never reopens a collapsed monitor');
 assert.equal(await f.page.locator('#volshellInput').evaluate(node=>document.activeElement===node),false);await f.close();

 f=await fixture({session:existing()});
 assert.equal(f.requests.length,0,'Opening an existing same-case connection does not toggle it');assert.equal(await f.page.locator('#volshellInput').isDisabled(),false);await f.close();
 // The Vault 112 amber switch collapses the monitor while a synthetic session
 // remains connected. It must never act as the VolShell disconnect control.
 f=await fixture({session:existing()});
 await f.page.evaluate(()=>WorkbenchThemes.apply('fallout-3-vault-112-2'));
 const vaultPower=f.page.locator('#fieldConsoleCollapse');
 for(const interaction of ['keyboard','mouse']){
  assert.equal(await f.page.locator('#volshellPanel').isVisible(),true,'Vault 112 power is tested with active VolShell controls');
  assert.equal(await f.page.locator('#volshellLED').getAttribute('data-state'),'ready');
  assert.equal(await f.page.locator('#volshellInput').isEnabled(),true);
  if(interaction==='keyboard'){
   await f.page.keyboard.press('Tab');await vaultPower.focus();
   assert.equal(await vaultPower.evaluate(node=>getComputedStyle(node).outlineStyle),'solid','Vault 112 power shows keyboard focus during VolShell');
   await f.page.keyboard.press('Enter');
  }else await vaultPower.click();
  await f.page.waitForFunction(()=>!document.querySelector('#consoleZoom').open);
  assert.equal(f.requests.length,0,'Collapsing active VolShell never starts a session');
  assert.equal(f.closes.length,0,'The amber power control collapses without disconnecting VolShell');
  assert.equal(f.value.volshell.session.id,'existing-shell');
  if(interaction==='keyboard')await f.page.locator('#openCaseConsole').click();
 }
 await f.close();
 f=await fixture({session:existing('case-a')});await f.click();
 assert.equal(f.requests.length,0,'Another case is never disconnected or rebound implicitly');
 assert.equal(await f.page.locator('#volshellConnection').evaluate(node=>node.open),true);
 assert.match(await f.page.locator('#volshellDisconnect').textContent(),/Synthetic Windows case/);
 assert.doesNotMatch(await f.page.locator('#volshellOutput').textContent(),/Private output for case-a/);await f.close();

 f=await fixture({jobs:[{id:'busy-job',case_id:'case-a',kind:'question',status:'running'}]});await f.click();
 assert.equal(f.requests.length,0,'An unrelated active investigation blocks connection');
 assert.match(await f.page.locator('#volshellStatus').textContent(),/investigation is active/);
 f.value.jobs=[];await f.refresh();assert.equal(f.requests.length,0,'Finishing an investigation does not submit a deferred connection');
 await f.click();assert.equal(f.requests.length,1);await f.close();

 f=await fixture({images:[]});await f.click();
 assert.equal(f.requests.length,0);assert.equal(await f.page.locator('#volshellConnection').evaluate(node=>node.open),true);
 assert.equal(await f.page.locator('#volshellImage').isDisabled(),true);assert.equal(await f.page.locator('#volshellConnect').isDisabled(),true);await f.close();
 const images=[{id:'E001',path:'/synthetic/linux.vmem',discovery:{detected_os:'linux'}},{id:'E002',path:'/synthetic/mac.vmem',discovery:{detected_os:'macos'}}];
 f=await fixture({images});await f.click();
 assert.equal(f.requests.length,0,'Multiple captures require an explicit choice');
 assert.equal(await f.page.locator('#volshellImage').evaluate(node=>document.activeElement===node),true);
 await f.page.locator('#volshellImage').selectOption('E002');await f.click();
 assert.deepEqual(f.requests[0],{case_id:'case-b',image_id:'E002',mode:'mac'});
 f.value.volshell.session.status='exited';f.value.volshell.session.ready=false;f.value.volshell.busy=false;await f.refresh();
 assert.equal(f.requests.length,1,'Interpreter EOF does not reconnect automatically');
 await f.click();assert.deepEqual(f.requests[1],f.requests[0],'A deliberate reconnect retains the chosen capture and OS');
 f.value.volshell.session.status='exited';f.value.volshell.busy=false;await f.refresh();
 await f.page.locator('#volshellConnection summary').click();await f.page.locator('#volshellMode').selectOption('generic');
 await f.page.locator('#volshellConnect').click();await f.page.waitForFunction(()=>document.querySelector('#volshellStatus').textContent!=='Request in progress…');
 assert.deepEqual(f.requests[2],{case_id:'case-b',image_id:'E002',mode:'generic'},'Explicit connection options retain OS overrides');await f.close();
 for(const [detected,expected] of [['darwin','mac'],['unknown','generic']]){
  f=await fixture({images:[{id:'E007',path:'/synthetic/fixture.vmem',discovery:{detected_os:detected}}]});await f.click();
  assert.deepEqual(f.requests[0],{case_id:'case-b',image_id:'E007',mode:expected});await f.close();
 }
 f=await fixture({reply:'fail'});await f.click();
 assert.equal(f.requests.length,1);assert.equal(await f.page.locator('#volshellConnection').evaluate(node=>node.open),true);
 assert.match(await f.page.locator('#volshellError').innerText(),/Synthetic interpreter could not start/);
 assert.equal(await f.page.locator('#volshellInput').isDisabled(),true);
 await f.refresh();await f.page.locator('#collapseVolshell').click();await f.page.locator('#openCaseConsole').click();await f.refresh();
 assert.equal(f.requests.length,1,'A failed start never retries from polling or monitor reopen');
 f.control.reply='start';await f.click();assert.equal(f.requests.length,2,'Retry requires another explicit bezel action');await f.close();

 f=await fixture({reply:'lag'});await f.click();await f.click();await f.refresh();await f.click();
 assert.equal(f.requests.length,1,'A successful start response stays latched while the full-state poll still lacks its session');
 assert.equal(await f.page.locator('#volshellLED').getAttribute('data-state'),'pending');
 f.value.volshell=f.control.returned;await f.refresh();await f.click();assert.equal(f.requests.length,1);await f.close();
 f=await fixture();
 const emit=async value=>{await f.page.evaluate(value=>fixtureStreams.at(-1).emit(value),value);await f.page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));};
 await emit({case_id:'case-b',session:null,busy:false,agent_activity:null});
 await f.click();await f.refresh();await f.click();
 assert.equal(f.requests.length,1,'An older valid SSE snapshot cannot cause a duplicate start after the POST and poll already saw the new session');
 assert.equal(await f.page.locator('#volshellInput').isDisabled(),true);
 f.value.volshell.session.status='running';f.value.volshell.session.ready=true;
 await emit({case_id:'case-b',...f.value.volshell,agent_activity:null});
 assert.equal(await f.page.locator('#volshellInput').isDisabled(),false);await f.close();

 // A connected bezel is an explicit off switch, including from Output. Close
 // acknowledgements and process exit are deliberately separate in this fixture.
 f=await fixture({session:existing()});f.control.closeReply='hold';
 const led=()=>f.page.locator('#volshellLED').getAttribute('data-state');
 const emitClose=async value=>{await f.page.evaluate(value=>fixtureStreams.at(-1).emit(value),value);await f.page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));};
 assert.equal(await led(),'ready');assert.equal(await f.page.locator('#volshellDisconnect').isHidden(),true);
 await f.page.locator('#consoleOutputMode').click();assert.equal(f.closes.length,0,'Output alone leaves the process connected');
 await f.page.locator('#consoleVolshellMode').click();
 await f.page.waitForFunction(()=>document.querySelector('#volshellInput').disabled);
 assert.deepEqual(f.closes,[{case_id:'case-b',session_id:'existing-shell'}],'Connected bezel closes the selected-case session directly from Output');
 assert.equal(await led(),'ready','A pending close does not optimistically turn the LED off');
 await emitClose({case_id:'case-b',session:null,busy:false,agent_activity:null});
 assert.equal(await led(),'ready','An older empty SSE snapshot cannot imply process exit');
 await f.page.locator('#consoleVolshellMode').evaluate(node=>{node.click();node.click();});
 assert.equal(f.closes.length,1,'Repeated clicks never send concurrent close requests');assert.equal(f.requests.length,0);
 f.value.volshell.session.status='stopping';f.value.volshell.session.ready=false;
 await f.refresh();assert.equal(await led(),'ready','Stopping retains the established connection LED');
 assert.ok(f.control.heldClose);await f.control.heldClose.fulfill({json:f.value.volshell});
 await f.page.waitForFunction(()=>document.querySelector('#volshellStatus').textContent!=='Request in progress…');
 await emitClose({case_id:'case-b',session:{...f.value.volshell.session,status:'running',ready:true},busy:true,agent_activity:null});
 assert.equal(await f.page.locator('#volshellInput').isDisabled(),true,'A stale ready frame cannot enable input during shutdown');
 assert.equal(await f.page.locator('#volshellInterrupt').isDisabled(),true);
 assert.match(await f.page.locator('#volshellStatus').textContent(),/Disconnecting/);
 await f.page.locator('#consoleVolshellMode').click();assert.equal(f.closes.length,1,'A stopping response is not an invitation to close again');
 const completed={case_id:'case-b',session:{...f.value.volshell.session,status:'closed',ready:false},busy:false,agent_activity:null};
 await emitClose(completed);assert.equal(await led(),'off','Only a backend terminal state extinguishes the LED');
 await f.refresh();assert.equal(await led(),'off','An older stopping poll cannot resurrect the closed process');
 await emitClose({...completed,session:{...completed.session,status:'running',ready:true},busy:true});
 assert.equal(await led(),'off','A delayed active SSE frame cannot resurrect a confirmed exit');
 await f.page.locator('#consoleVolshellMode').dispatchEvent('click',{detail:2});
 assert.equal(f.requests.length,0,'The second event in a double-click never reconnects');
 await f.page.locator('#collapseVolshell').click();await f.page.locator('#openCaseConsole').click();
 assert.equal(f.requests.length,0);assert.equal(f.closes.length,1,'Collapse/reopen does not change process state');
 f.control.reply='fail';await f.click();assert.equal(f.requests.length,1);
 assert.equal(await led(),'off','A failed reconnect cannot resurrect the old closed session from stale SSE');
 f.control.reply='start';await f.click();assert.equal(f.requests.length,2,'A failed reconnect remains explicitly retryable');
 assert.equal(f.closes.length,1);assert.equal(await led(),'pending');await f.close();

 f=await fixture({session:existing()});f.control.closeReply='fail';await f.click();
 assert.equal(await f.page.locator('#volshellLED').getAttribute('data-state'),'ready');
 assert.equal(await f.page.locator('#volshellInput').isDisabled(),false,'A failed close leaves the live input usable');
 assert.match(await f.page.locator('#volshellError').innerText(),/Synthetic close failed/);
 await f.refresh();assert.equal(f.closes.length,1,'Close errors do not retry in the background');
 f.control.closeReply='closed';await f.click();assert.equal(f.closes.length,2);assert.equal(await f.page.locator('#volshellLED').getAttribute('data-state'),'off');await f.close();

 f=await fixture({session:{...existing(),ready:false}});f.control.closeReply='lag';
 assert.equal(await f.page.locator('#volshellLED').getAttribute('data-state'),'ready','Running a command does not extinguish the connection LED');
 await f.page.locator('#consoleVolshellMode').dblclick();
 await f.page.waitForFunction(()=>document.querySelector('#volshellStatus').textContent!=='Request in progress…');
 assert.equal(f.closes.length,1,'A double-click closes a busy command once');assert.equal(f.requests.length,0);
 assert.equal(await f.page.locator('#volshellLED').getAttribute('data-state'),'off','A confirmed close response wins over a stale full-state poll');await f.close();

 for(const status of ['failed','exited']){
  f=await fixture({session:existing('case-b',status)});f.value.volshell.busy=false;await f.refresh();
  assert.equal(await f.page.locator('#volshellLED').getAttribute('data-state'),'off');
  assert.equal(f.requests.length,0);assert.equal(f.closes.length,0,'Terminal states never automatically reconnect or close');await f.close();
 }
 f=await fixture({session:existing(),jobs:[{id:'busy-job',case_id:'case-b',kind:'question',status:'running'}]});await f.click();
 assert.equal(f.closes.length,0,'An investigation owns the session until it finishes');assert.equal(await f.page.locator('#volshellInput').isDisabled(),true);await f.close();
}
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.WORKBENCH_BROWSER_EXECUTABLE?{executablePath:process.env.WORKBENCH_BROWSER_EXECUTABLE}:{})});
 try{
  await checkBezelConnection(browser);
  const page=await browser.newPage({viewport:{width:1400,height:1000}}),errors=[],posts=[];
  await page.addInitScript(()=>{Date.now=()=>Date.parse('2026-10-18T12:02:42Z');});
  await page.addInitScript(()=>{
   window.fixtureStreams=[];
   window.fixtureRetries=new Map();let retryId=0;
   class FixtureEventSource extends EventTarget {
    static CONNECTING=0;static OPEN=1;static CLOSED=2;
    constructor(url){super();this.url=new URL(url,location.href).href;this.readyState=1;this.closed=false;window.fixtureStreams.push(this);}
    close(){this.closed=true;this.readyState=2;}
    emit(value){this.dispatchEvent(new MessageEvent('volshell',{data:typeof value==='string'?value:JSON.stringify(value)}));}
    fail(closed=false){this.readyState=closed?2:0;this.onerror?.(new Event('error'));}
   }
   window.EventSource=FixtureEventSource;
   // Every full-state refresh in this test is explicit. Stream assertions cannot
   // accidentally pass because the normal1500ms polling loop supplied output.
   const interval=window.setInterval;
   window.setInterval=(callback,delay,...args)=>delay===1500?0:interval(callback,delay,...args);
   const timeout=window.setTimeout,clear=window.clearTimeout;
   window.setTimeout=(callback,delay,...args)=>{
    if([1000,2000,4000,8000,15000].includes(delay)){
     const id=--retryId;fixtureRetries.set(id,{id,delay,fire:()=>callback(...args)});return id;
    }
    return timeout(callback,delay,...args);
   };
   window.clearTimeout=id=>fixtureRetries.has(id)?fixtureRetries.delete(id):clear(id);
   window.fireFixtureRetry=id=>{const timer=fixtureRetries.get(id);fixtureRetries.delete(id);timer?.fire();};
  });
  let suggestion={command:'ps()',explanation:'List processes in the selected Windows capture.'},heldSuggestion=null,holdSuggestion=false,stateReads=0;
  page.on('pageerror',error=>errors.push(error.message));
  await page.route('**/*',async route=>{
    if (new URL(route.request().url()).pathname === '/api/settings/zoom') return route.fulfill({json:{schema:'zoom/1',percent:100}});
   const request=route.request(),url=new URL(request.url());
   assert.equal(url.origin,'http://localhost','All requests remain inside the synthetic route handler');
   if(request.method()==='GET'){
    if(url.pathname==='/api/state'){stateReads++;return route.fulfill({json:state});}
    if(url.pathname==='/api/artifacts')return route.fulfill({json:{files:[],truncated:false}});
    if(url.pathname==='/api/report-console')return route.fulfill({json:null});
    assert.ok(!url.pathname.startsWith('/api/'),'Unexpected read '+url.pathname);
    const name=url.pathname==='/'?'index.html':url.pathname.slice(1);
    return route.fulfill({body:fs.readFileSync(path.join(assets,name)),contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html'});
   }
   assert.equal(request.method(),'POST');
   const body=request.postDataJSON();posts.push({path:url.pathname,body});
   if(url.pathname==='/api/volshell/start'){
    assert.deepEqual(body,{case_id:'case-a',image_id:'E001',mode:'windows'});
    state.volshell={busy:true,session:{id:'shell-a',case_id:body.case_id,image_id:body.image_id,mode:body.mode,status:'starting',ready:false,continuation:false,entries:[],earlier_entries:0,started_at:stamp}};
   }else if(url.pathname==='/api/volshell/input'){
    assert.equal(body.case_id,'case-a');assert.equal(body.session_id,'shell-a');
    state.volshell.session.entries.push(entry('input',body.text),entry('output','Synthetic command result\n(layer) >>> '));
    state.volshell.session.ready=false;
   }else if(url.pathname==='/api/volshell/suggest'){
    const json={case_id:body.case_id,session_id:body.session_id,...suggestion};
    if(holdSuggestion){holdSuggestion=false;heldSuggestion=()=>route.fulfill({json});return;}
    return route.fulfill({json});
   }else if(url.pathname==='/api/volshell/investigate'){
    assert.equal(body.case_id,'case-a');assert.equal(body.session_id,'shell-a');assert.match(body.request_id,/^[0-9a-f-]{36}$/);
    const job={id:'ai-job',case_id:body.case_id,kind:'question',status:'running',progress:'case_saved_context',started_at:stamp,volshell_session_id:body.session_id};
    state.jobs=[job];state.volshell.investigation={job,console:{entries:[entry('output','Synthetic saved evidence tool output\n<img src=x onerror="window.injected=true">')]},messages:[{role:'assistant',text:'Synthetic answer only. <script>window.injected=true</script>'}]};
    return route.fulfill({json:job});
   }else if(url.pathname==='/api/volshell/interrupt'){
    state.volshell.session.ready=true;state.volshell.session.continuation=false;
   }else if(url.pathname==='/api/volshell/close'||url.pathname==='/api/stop'){
    if(url.pathname.endsWith('/close'))assert.deepEqual(body,{case_id:'case-a',session_id:'shell-a'},'Disconnect always addresses the owning session');
    state.volshell.session.status='closed';state.volshell.session.ready=false;state.volshell.busy=false;
    state.jobs.forEach(job=>job.status='cancelled');
   }else assert.fail('Unexpected mutation '+url.pathname);
   return route.fulfill({json:state.volshell});
  });
  const count=endpoint=>posts.filter(item=>item.path==='/api/'+endpoint).length;
  const settle=()=>page.waitForFunction(()=>document.querySelector('#volshellStatus').textContent!=='Request in progress…');
  const refresh=()=>page.evaluate(()=>refresh());
  const mode=value=>page.locator('#volshellInteractionMode').selectOption(value);
  const connectionOptions=async()=>{if(!await page.locator('#volshellConnection').evaluate(node=>node.open))await page.locator('#volshellConnection summary').click();};
  const chooseShellCase=async value=>{await connectionOptions();await page.locator('#volshellCase').selectOption(value);};
  const ready=async()=>{state.volshell.session.ready=true;state.volshell.session.status='running';await refresh();await settle();};
  const screenshot=async name=>{
   if(!process.env.WORKBENCH_VOLSHELL_SCREENSHOT_DIR)return;
   fs.mkdirSync(process.env.WORKBENCH_VOLSHELL_SCREENSHOT_DIR,{recursive:true});
   await page.locator('#consoleZoom').screenshot({path:path.join(process.env.WORKBENCH_VOLSHELL_SCREENSHOT_DIR,name+'.png')});
  };
  await page.goto('http://localhost/');
  await page.locator('#openCaseConsole').click();
  const zoom=page.locator('#consoleZoom'),input=page.locator('#volshellInput');
  await zoom.waitFor();
  assert.equal(await page.locator('#volshellCase').inputValue(),'case-a');
  assert.equal(await page.locator('#volshellMode').inputValue(),'windows');
  assert.equal(await page.locator('#volshellLED').getAttribute('data-state'),'off');
  assert.equal(await input.isDisabled(),true);assert.equal(posts.length,0,'Opening the CRT never starts a session');
  for(const selector of ['#volshellCase','#volshellImage','#volshellMode','#volshellConnect','#volshellInterrupt','#volshellDisconnect','#volshellStatus','#volshellBinding'])assert.equal(await page.locator(selector).isVisible(),false,'Connection setup stays collapsed: '+selector);
  assert.equal(await page.locator('#collapseVolshell').isVisible(),true);
  await page.locator('#consoleVolshellMode').evaluate(node=>{node.click();node.click();});await settle();
  assert.equal(count('volshell/start'),1);assert.equal(await input.isDisabled(),true);
  assert.equal(await page.locator('#volshellLED').getAttribute('data-state'),'pending');
  await page.locator('#consoleVolshellMode').click();await refresh();assert.equal(count('volshell/start'),1,'Starting session is reused on repeated bezel clicks and refresh');
  state.volshell.session.entries=[entry('output','Volshell 2.28.2 · synthetic fixture\n(layer) >>> '),entry('output','<img src=x onerror="window.injected=true">\n')];
  await ready();
  assert.equal(await page.locator('#volshellLED').getAttribute('data-state'),'ready');
  assert.equal(await page.locator('#volshellDisconnect').isVisible(),false,'The bezel replaces the same-case Disconnect button');
  assert.match(await page.locator('#consoleVolshellMode').getAttribute('title'),/Disconnect VolShell/);
  assert.equal(await page.locator('#volshellConnection').evaluate(node=>node.open),false);
  for(const [value,id] of [['manual','volshellInput'],['suggestions','volshellAIInput'],['investigation','volshellInvestigationInput']]){
   await mode(value);await page.locator('#collapseVolshell').click();await page.locator('#openCaseConsole').click();
   assert.equal(await page.locator('#'+id).evaluate(node=>document.activeElement===node),true,'Reopening '+value+' focuses its visible input');
  }
  assert.equal(count('volshell/start'),1,'All three modes reuse the existing connection');
  await mode('manual');
  assert.equal(await page.locator('#volshellInterrupt').isDisabled(),true,'Idle prompt has no command to interrupt');
  assert.equal(await page.locator('#volshellOutput img, #volshellOutput script').count(),0);
  await input.fill('ps');await input.press('Tab');
  assert.equal(await input.inputValue(),'ps()');assert.equal(count('volshell/input'),0,'Tab accepts the draft without running it');
  await input.fill('ps');await input.press('Escape');
  assert.equal(await page.locator('#volshellGhostSuffix').textContent(),'');assert.equal(await zoom.isVisible(),true,'Escape dismisses ghost before closing CRT');
  await input.fill('ps');await input.press('Enter');await settle();
  assert.equal(posts.find(item=>item.path==='/api/volshell/input').body.text,'ps','Enter executes only typed text, never the ghost suffix');
  assert.equal(await input.isDisabled(),true);assert.equal(await page.locator('#volshellLED').getAttribute('data-state'),'ready','The LED stays green while a command runs');
  assert.equal(await page.locator('#volshellInterrupt').isDisabled(),false);
  await connectionOptions();await page.locator('#volshellInterrupt').click();await settle();
  assert.equal(count('volshell/interrupt'),1);await input.fill('value = 1');await input.press('Shift+Enter');
  assert.match(await input.inputValue(),/\n$/);assert.equal(count('volshell/input'),1,'Shift+Enter adds a line without submitting');
  state.volshell.session.continuation=true;await input.fill('');await refresh();
  assert.equal(await page.locator('#volshellRun').innerText(),'Finish block');
  await page.locator('#volshellRun').click();await settle();
  assert.equal(posts.filter(item=>item.path==='/api/volshell/input').at(-1).body.text,'');
  state.volshell.session.continuation=false;await ready();
  await input.fill('case_a_draft');await chooseShellCase('case-b');
  assert.equal(await input.isDisabled(),true);assert.doesNotMatch(await page.locator('#volshellOutput').innerText(),/Volshell 2.28.2/);
  assert.match(await page.locator('#volshellDisconnect').textContent(),/Synthetic Windows case/);
  await chooseShellCase('case-a');assert.equal(await input.inputValue(),'case_a_draft');
  await mode('suggestions');
  await page.locator('#volshellAIInput').fill('List processes');await page.locator('#volshellAISubmit').click();
  await page.waitForFunction(()=>document.querySelector('#volshellAIStatus').textContent.includes('Proposal ready'));
  const submittedBeforeProposal=count('volshell/input');
  await page.locator('#volshellUseProposal').click();
  assert.equal(await input.inputValue(),'ps()');assert.equal(await page.locator('#volshellInteractionMode').inputValue(),'manual');
  assert.equal(count('volshell/input'),submittedBeforeProposal,'Using an AI draft never submits it');
  await mode('suggestions');suggestion={command:'',explanation:'Which process should be inspected?'};
  await page.locator('#volshellAISubmit').click();await page.waitForFunction(()=>document.querySelector('#volshellAIStatus').textContent.includes('No command was proposed'));
  assert.equal(await page.locator('#volshellUseProposal').isDisabled(),true);assert.equal(await page.locator('#volshellProposalCommand').isHidden(),true);
  suggestion={command:'<img src=x onerror="window.injected=true">',explanation:'<script>window.injected=true</script>'};
  await page.locator('#volshellAISubmit').click();await page.waitForFunction(()=>document.querySelector('#volshellAIStatus').textContent.includes('Proposal ready'));
  assert.equal(await page.locator('#volshellProposal img, #volshellProposal script').count(),0);
  suggestion={command:'ps()',explanation:'Wrong binding',session_id:'different-session'};
  await page.locator('#volshellAISubmit').click();await page.waitForFunction(()=>document.querySelector('#volshellAIStatus').textContent.includes('different session'));
  assert.equal(await page.locator('#volshellProposal').isHidden(),true);
  suggestion={command:'ps()',explanation:'Late fixture proposal'};holdSuggestion=true;
  await page.locator('#volshellAISubmit').click();await page.waitForFunction(()=>document.querySelector('#volshellAIStatus').textContent.includes('Preparing'));
  await chooseShellCase('case-b');
  assert.ok(heldSuggestion);await heldSuggestion();heldSuggestion=null;
  await chooseShellCase('case-a');await mode('suggestions');
  assert.equal(await page.locator('#volshellProposal').isHidden(),true,'Late response cannot populate a different case/session view');
  assert.equal(count('volshell/input'),submittedBeforeProposal);
  await mode('investigation');assert.equal(count('volshell/investigate'),0,'Selecting AI investigation never starts work');
  await page.locator('#volshellInvestigationInput').fill('Review the saved evidence for this synthetic case.');
  await page.locator('#volshellInvestigate').click();await settle();
  assert.equal(count('volshell/investigate'),1);assert.equal(count('volshell/input'),submittedBeforeProposal);
  assert.match(await page.locator('#volshellInvestigationOutput').innerText(),/Synthetic saved evidence/);
  assert.equal(await page.locator('#volshellInvestigation img, #volshellInvestigation script').count(),0);
  assert.equal(await page.locator('#volshellLED').getAttribute('data-state'),'ready','Idle Python connection remains ready while AI tools work');
  assert.equal(await page.locator('#volshellDisconnect').isDisabled(),true);assert.equal(await page.locator('#volshellInterrupt').isDisabled(),true);
  await mode('manual');assert.equal(await input.isDisabled(),true);await mode('suggestions');assert.equal(await page.locator('#volshellAISubmit').isDisabled(),true);
  await mode('investigation');
  const matchingInvestigation=state.volshell.investigation;
  state.volshell.investigation={...matchingInvestigation,job:{...matchingInvestigation.job,volshell_session_id:'stale-session'}};await refresh();
  assert.equal(await page.locator('#volshellInvestigationOutput').textContent(),'','Other session tool output remains hidden');
  state.volshell.investigation=matchingInvestigation;await refresh();
  state.approvals=[{id:'approval-one',case_id:'case-a',method:'item/tool/requestUserInput',params:{questions:[{id:'reason',question:'Synthetic approval decision'}]}}];
  await refresh();await page.waitForFunction(()=>!document.querySelector('#consoleZoom').open);
  assert.equal(await page.locator('#volshellApprovalNotice').isVisible(),true);
  assert.match(await page.locator('#approvals').innerText(),/Synthetic approval decision/);
  await page.locator('#openCaseConsole').click();await refresh();assert.equal(await zoom.isVisible(),true,'An already surfaced approval does not repeatedly close review');
  assert.equal(await page.locator('#volshellInteractionMode').inputValue(),'investigation');
  state.approvals=[];await refresh();
  state.volshell.session.entries=[entry('output','Volshell 2.28.2 · synthetic fixture\n(layer) >>> ps()\nPID    Name\n4      System\n120    fixture.exe\n(layer) >>> ')];
  state.volshell.investigation.console.entries=[entry('output','case_saved_context\nSaved process records loaded for the selected case.\nNo new collection requested.')];
  state.volshell.investigation.messages=[{role:'assistant',text:'The saved process records are ready to review. This demonstration uses only synthetic evidence.'}];
  await refresh();
  await page.locator('#collapseVolshell').click();await page.locator('#toggleTheme').click();await page.locator('#theme').selectOption('fallout-2');
  await page.locator('#openCaseConsole').click();
  if(await page.locator('#volshellConnection').evaluate(node=>node.open))await page.locator('#volshellConnection summary').click();
  await screenshot('volshell-ai-desktop');
  state.jobs[0].status='completed';await refresh();await mode('manual');assert.equal(await input.isDisabled(),false,'Manual session resumes after the AI job completes');
  await input.fill('ps');await screenshot('volshell-manual-desktop');
  const themeStyles=[],spacingIssues=[];
  for(const theme of await page.evaluate(()=>window.WorkbenchThemes.catalog)){
   await page.evaluate(id=>window.WorkbenchThemes.apply(id),theme.id);
   const styles=await page.locator('#consoleVolshellMode').evaluate(node=>{
    const css=getComputedStyle(node),parse=value=>value.match(/[\d.]+/g).slice(0,3).map(Number),
     luminance=rgb=>{const c=rgb.map(n=>n/255).map(n=>n<=.04045?n/12.92:((n+.055)/1.055)**2.4);return c[0]*.2126+c[1]*.7152+c[2]*.0722;};
    const base=css.backgroundImage.slice(css.backgroundImage.lastIndexOf('linear-gradient(')),text=luminance(parse(css.color));
    const stops=[...base.matchAll(/rgb\([^)]+\)/g)].map(match=>luminance(parse(match[0])));
    return {signature:JSON.stringify([css.backgroundImage,css.borderRadius,css.borderStyle,css.boxShadow,css.fontFamily,css.letterSpacing]),
     minimumContrast:Math.min(...stops.map(background=>(Math.max(text,background)+.05)/(Math.min(text,background)+.05))),
     animation:css.animationName};
   });
   assert.ok(Number.isFinite(styles.minimumContrast)&&styles.minimumContrast>=4.5,theme.id+' VolShell label remains readable across its plate base: '+styles.minimumContrast);
   const clearance=await page.locator('#consoleVolshellMode').evaluate(node=>{
    const root=document.documentElement,previous=root.style.getPropertyValue('--text-scale'),scaled=root.dataset.textScaled;
    try{return [1,2].map(scale=>{
     root.style.setProperty('--text-scale',String(scale));root.dataset.textScaled=String(scale!==1);
     const range=document.createRange();range.selectNodeContents([...node.childNodes].find(child=>child.nodeType===Node.TEXT_NODE&&child.textContent.trim()));
     const text=range.getBoundingClientRect(),led=node.querySelector('.volshell-led').getBoundingClientRect(),button=node.getBoundingClientRect();
     return {scale,gap:Math.max(text.left-led.right,led.left-text.right,text.top-led.bottom,led.top-text.bottom),inside:led.left>=button.left&&led.right<=button.right&&text.left>=button.left&&text.right<=button.right&&led.top>=button.top&&led.bottom<=button.bottom&&text.top>=button.top&&text.bottom<=button.bottom,width:button.width,textWidth:text.width};
    });}finally{if(previous)root.style.setProperty('--text-scale',previous);else root.style.removeProperty('--text-scale');if(scaled===undefined)delete root.dataset.textScaled;else root.dataset.textScaled=scaled;}
   });
   for(const result of clearance){
    if(result.gap<7.5||!result.inside)spacingIssues.push({theme:theme.id,...result});
   }
   assert.equal(styles.animation,'none');assert.equal(await page.locator('#volshellLED').getAttribute('data-state'),'ready');
   await page.locator('#consoleOutputMode').focus();await page.keyboard.press('Tab');
   assert.equal(await page.locator('#consoleVolshellMode').evaluate(node=>document.activeElement===node&&getComputedStyle(node).outlineStyle==='solid'),true,theme.id+' bezel shows keyboard focus');
   assert.equal(await page.locator('.crt-vegas-sign').isVisible(),theme.id==='fallout-new-vegas','New Vegas sign stays confined to its own skin');
   themeStyles.push({id:theme.id,...styles});
   if(process.env.WORKBENCH_VOLSHELL_SCREENSHOT_DIR)await page.locator('#consoleVolshellMode').screenshot({path:path.join(process.env.WORKBENCH_VOLSHELL_SCREENSHOT_DIR,'bezel-'+theme.id+'.png')});
   if(['matrix','fallout-new-vegas','fallout-3-robco','fallout-3-vault-112'].includes(theme.id))await screenshot('volshell-'+theme.id+'-desktop');
  }
  assert.deepEqual(spacingIssues,[],'Every theme reserves at least 8px between the VolShell label and its LED at 100% and 200% text, inside the button');
  assert.equal(themeStyles.length,37,'The current catalog contains all 37 themes');
  assert.equal(new Set(themeStyles.map(theme=>theme.signature)).size,themeStyles.length,'Every catalog theme has a distinct VolShell bezel');
  for(const id of ['fallout-3-robco','fallout-3-vault-112']){
   await page.evaluate(id=>window.WorkbenchThemes.apply(id),id);
   assert.equal(await page.locator('.crt-brand').evaluate(node=>getComputedStyle(node,'::before').content),id==='fallout-3-robco'?'"ROBCO / TERMLINK"':'"VAULT 112"');
   for(const width of [1400,390,320]){
    await page.setViewportSize({width,height:1000});
    assert.equal(await zoom.evaluate(node=>node.scrollWidth<=node.clientWidth+1),true,id+' console fits '+width+'px');
    assert.equal(await page.locator('.crt-screen').evaluate(node=>getComputedStyle(node).backgroundImage),'none','Terminal glass stays free of textures');
    await page.locator('#volshellPanel').evaluate(node=>node.scrollTop=0);await screenshot('volshell-'+id+'-'+width);
    await page.locator('#consoleOutputMode').click();await screenshot('output-'+id+'-'+width);
    await page.evaluate(caseId=>window.WorkbenchVolshell.open(caseId),state.volshell.session.case_id);
   }
  }
  await page.setViewportSize({width:1400,height:1000});
  await page.evaluate(()=>window.WorkbenchThemes.apply('fallout-new-vegas'));
  assert.equal(await page.locator('.crt-vegas-sign').getAttribute('aria-hidden'),'true');
  assert.equal(await page.locator('.vegas-welcome i').count(),7);
  assert.equal(await page.locator('.vegas-welcome i').nth(4).evaluate(node=>getComputedStyle(node).textShadow),'none','A fixed failed sign letter remains dark');
  assert.equal(await page.locator('.vegas-lamps').evaluate(node=>getComputedStyle(node).pointerEvents),'none');
  assert.ok(await page.locator('.crt-vegas-sign,.vegas-lamps,.vegas-lamps span').evaluateAll(nodes=>nodes.every(node=>getComputedStyle(node).animationName==='none')),'Sign and bulbs never flash');
  await page.locator('#consoleOutputMode').click();await screenshot('output-fallout-new-vegas-desktop');await page.locator('#collapseEmptyConsole').click();await page.locator('#openCaseConsole').click();
  for(const width of [390,320]){
   await page.setViewportSize({width,height:844});
   assert.equal(await zoom.evaluate(node=>node.scrollWidth<=node.clientWidth+1),true,'New Vegas monitor fits '+width+'px');
   assert.equal(await page.locator('.crt-vegas-sign').evaluate(node=>{const b=node.getBoundingClientRect(),screen=document.querySelector('.crt-screen').getBoundingClientRect();return b.left>=0&&b.right<=innerWidth&&b.bottom<=screen.top;}),true,'New Vegas sign stays above the opaque screen');
   for(const value of ['manual','suggestions','investigation']){
    await mode(value);
    assert.equal(await page.locator('#volshellInteractionMode').evaluate(node=>{const control=node.getBoundingClientRect(),pane=document.querySelector('#volshellPanel').getBoundingClientRect();return control.left>=pane.left&&control.right<=pane.right;}),true,'Entire '+value+' mode selector fits inside the '+width+'px New Vegas screen');
   }
   await mode('manual');
   await page.locator('#volshellPanel').evaluate(node=>node.scrollTop=0);await screenshot('volshell-fallout-new-vegas-'+width);
   await page.locator('#volshellRun').scrollIntoViewIfNeeded();await screenshot('volshell-fallout-new-vegas-controls-'+width);
   await page.locator('#consoleOutputMode').click();await screenshot('output-fallout-new-vegas-'+width);await page.locator('#collapseEmptyConsole').click();await page.locator('#openCaseConsole').click();
  }
  await page.evaluate(()=>window.WorkbenchThemes.apply('fallout-2'));
  for(const width of [390,320]){
   await page.setViewportSize({width,height:844});await refresh();
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,'No page overflow at '+width);
   assert.equal(await zoom.evaluate(node=>node.scrollWidth<=node.clientWidth+1),true,'No CRT overflow at '+width);
   assert.equal(await page.locator('#volshellPanel').evaluate(node=>node.scrollWidth<=node.clientWidth+1),true,'No panel overflow at '+width);
   await screenshot('volshell-manual-'+width);
   await page.locator('#volshellRun').scrollIntoViewIfNeeded();await screenshot('volshell-manual-controls-'+width);
   await mode('investigation');await screenshot('volshell-ai-'+width);
   await page.locator('#volshellInvestigationMessages').scrollIntoViewIfNeeded();await screenshot('volshell-ai-output-'+width);await mode('manual');
  }
  await page.setViewportSize({width:1400,height:1000});
  await mode('investigation');state.jobs[0].status='running';await refresh();
  await page.locator('#volshellStopAI').click();await settle();assert.equal(count('stop'),1);
  assert.equal(await page.locator('#volshellLED').getAttribute('data-state'),'off');
  assert.equal(await page.locator('#volshellConnect').isDisabled(),false);
  state.volshell.session.status='failed';state.volshell.session.error='Synthetic startup failure';await refresh();
  assert.match(await page.locator('#volshellError').innerText(),/Synthetic startup failure/);
  state.volshell.session.status='exited';state.volshell.session.error=null;await refresh();
  assert.equal(count('volshell/start'),1,'EOF, failure, refresh and mode changes never restart the interpreter');
  state.volshell.session.status='running';state.volshell.session.ready=true;state.volshell.busy=true;await refresh();
  await chooseShellCase('case-b');
  assert.equal(await page.locator('#volshellConnection').evaluate(node=>node.open),false);
  assert.equal(await page.locator('#volshellDisconnect').isVisible(),false,'Other-case disconnect is an explicit gear fallback');
  await connectionOptions();assert.equal(await page.locator('#volshellDisconnect').isVisible(),true);
  await page.locator('#volshellDisconnect').click();await settle();
  assert.equal(count('volshell/close'),1,'Other-case disconnect is an explicit request bound to the original session');
  assert.equal(await page.locator('#volshellDisconnect').isVisible(),false,'Disconnect hides when the session has closed');
  assert.equal(await page.locator('#volshellLED').getAttribute('data-state'),'off');
  assert.equal(await input.isDisabled(),true);
  assert.equal(await page.locator('#consoleVolshellMode').evaluate(node=>document.activeElement===node),true,'Closing a session restores focus to the reconnect bezel');
  await page.locator('#consoleOutputMode').click();assert.equal(await page.locator('#expandedConsoleHost').isVisible(),true);
  await page.locator('#consoleVolshellMode').click();assert.equal(await page.locator('#volshellPanel').isVisible(),true);
  await page.keyboard.press('Escape');await page.waitForFunction(()=>!document.querySelector('#consoleZoom').open);
  // Streaming transport is simulated independently of /api/state. The server's
  // real authenticated SSE framing/flush behavior is exercised in test_volshell.
  await page.waitForFunction(()=>fixtureStreams.every(source=>source.closed));
  assert.equal(await page.evaluate(()=>fixtureStreams.every(source=>source.closed)),true,'Collapse releases every EventSource');
  state.jobs=[];state.live_console=null;state.volshell={busy:true,session:{id:'stream-shell',case_id:'case-a',image_id:'E001',mode:'windows',status:'running',ready:false,continuation:false,entries:[entry('output','Older polled output')],earlier_entries:0}};
  await refresh();await page.locator('#openCaseConsole').click();
  const streamIndex=()=>page.evaluate(()=>fixtureStreams.length-1);
  const deliver=async(value,index)=>{
   if(index===undefined)index=await streamIndex();
   await page.evaluate(({index,value})=>fixtureStreams[index].emit(value),{index,value});
   await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
  };
  const streamFrame=(text,ready=false)=>({case_id:'case-a',session:{...state.volshell.session,ready,entries:[entry('output',text)]},busy:true,agent_activity:null});
  let source=await streamIndex(),readsBefore=stateReads;
  assert.match(await page.evaluate(index=>fixtureStreams[index].url,source),/\/api\/volshell\/events\?case=case-a$/);
  await deliver(streamFrame('Immediate fragment without newline'));
  assert.equal(await page.locator('#volshellOutput').textContent(),'Immediate fragment without newline');
  assert.equal(await input.isDisabled(),true);assert.equal(stateReads,readsBefore,'Partial output renders without a full-state poll');
  await refresh();assert.equal(await page.locator('#volshellOutput').textContent(),'Immediate fragment without newline','Older polled output cannot overwrite the newer streamed snapshot');
  const beforeInvalid=await page.locator('#volshellOutput').textContent();
  for(const invalid of ['not json',{case_id:'case-b',session:null,busy:false},{...streamFrame('Wrong case'),session:{...state.volshell.session,case_id:'case-b'}},{...streamFrame('Wrong agent'),agent_activity:{case_id:'case-b',status:'running'}}])await deliver(invalid);
  assert.equal(await page.locator('#volshellOutput').textContent(),beforeInvalid,'Malformed and cross-case stream frames are ignored');
  const longOutput=Array.from({length:90},(_,i)=>'Streamed synthetic line '+i).join('\n');
  await deliver(streamFrame(longOutput));
  await page.locator('#volshellOutput').evaluate(node=>node.scrollTop=0);
  await deliver(streamFrame(longOutput+'\nNew partial é'));
  assert.equal(await page.locator('#volshellOutput').evaluate(node=>node.scrollTop),0,'Streaming preserves reading position in earlier output');
  await page.evaluate(index=>fixtureStreams[index].fail(),source);await refresh();
  assert.equal(await page.locator('#volshellOutput').textContent(),'Older polled output','A disconnected stream falls back to ordinary snapshots');
  assert.equal(await page.evaluate(()=>fixtureRetries.size),0,'CONNECTING keeps native retry without a duplicate application timer');
  await deliver(streamFrame('Reconnected complete snapshot',true),source);
  assert.equal(await page.locator('#volshellOutput').textContent(),'Reconnected complete snapshot');assert.equal(await input.isDisabled(),false);
  for(const delay of [1000,2000,4000,8000,15000,15000]){
   const previousSource=source;
   await page.evaluate(index=>{fixtureStreams[index].fail(true);fixtureStreams[index].fail(true);},source);
   const timers=await page.evaluate(()=>[...fixtureRetries.values()].map(({id,delay})=>({id,delay})));
   assert.equal(timers.length,1,'A fatal error schedules one retry timer');assert.equal(timers[0].delay,delay,'Fatal retries use capped exponential backoff');
   await refresh();assert.equal(await streamIndex(),source,'Full-state refresh does not bypass retry backoff');
   await page.evaluate(id=>fireFixtureRetry(id),timers[0].id);source=await streamIndex();
   assert.equal(source,previousSource+1);assert.equal(await page.evaluate(index=>fixtureStreams[index].closed,previousSource),true);
   await deliver(streamFrame('STALE closed-source frame',true),previousSource);
   await page.evaluate(index=>fixtureStreams[index].fail(true),previousSource);
   assert.equal(await page.evaluate(()=>fixtureRetries.size),0,'Stale source failures cannot schedule retries');
   assert.doesNotMatch(await page.locator('#volshellOutput').textContent(),/STALE closed-source/);
  }
  await deliver(streamFrame('Recovered after fatal status',true),source);
  await page.evaluate(index=>fixtureStreams[index].fail(true),source);
  const resetTimer=await page.evaluate(()=>[...fixtureRetries.values()].map(({id,delay})=>({id,delay}))[0]);
  assert.equal(resetTimer.delay,1000,'A successful snapshot resets retry backoff');
  await page.evaluate(id=>fireFixtureRetry(id),resetTimer.id);source=await streamIndex();
  await deliver(streamFrame('Recovered after fatal status',true),source);
  // AI state can arrive before the next job snapshot and must still pause input.
  const earlyActivity={id:'early-ai',case_id:'case-a',job_id:'early-job',image_id:'E001',mode:'windows',command:'ps()',status:'running',entries:[entry('output','Early AI tool fragment')],started_at:stamp,truncated:false};
  await deliver({...streamFrame('Manual prompt remains idle',true),agent_activity:earlyActivity});
  assert.equal(await page.locator('#volshellAgentPanel').isVisible(),true);
  await page.locator('#volshellInteractiveMode').click();assert.equal(await input.isDisabled(),true,'Streamed AI activity pauses manual input before the jobs poll');
  assert.equal(await page.locator('#volshellDisconnect').isDisabled(),true);assert.equal(await page.locator('#volshellInterrupt').isDisabled(),true);
  await page.evaluate(index=>fixtureStreams[index].fail(true),source);
  await chooseShellCase('case-b');
  assert.equal(await page.evaluate(()=>fixtureRetries.size),0,'Changing case cancels a pending retry');
  assert.equal(await page.evaluate(index=>fixtureStreams[index].closed,source),true,'Changing selected case closes its stream');
  const otherSource=await streamIndex();assert.notEqual(otherSource,source);
  await deliver(streamFrame('Late old-case output',true),source);
  await deliver({case_id:'case-b',session:null,busy:true,agent_activity:null},otherSource);
  assert.doesNotMatch(await page.locator('#volshellOutput').textContent(),/Late old-case|Manual prompt|Reconnected/);
  await page.evaluate(index=>fixtureStreams[index].fail(true),otherSource);
  await page.locator('#collapseVolshell').click();
  await page.waitForFunction(index=>fixtureStreams[index].closed,otherSource);
  await page.waitForFunction(()=>fixtureRetries.size===0);
  assert.equal(await page.evaluate(index=>fixtureStreams[index].closed,otherSource),true);
  // A normal report job can expose AI-owned shell activity in its Output CRT.
  const ordinaryJob={id:'ordinary-job',case_id:'case-a',kind:'report',status:'running',progress:'Reading saved evidence',started_at:stamp};
  state.jobs=[ordinaryJob];state.volshell={session:null,busy:false,agent_activity:null};
  state.live_console={job_id:ordinaryJob.id,case_id:'case-a',entries:[entry('output','Ordinary investigation output')],earlier_entries:0};
  await refresh();await page.locator('#expandConsole').click();
  assert.equal(await page.locator('#expandedConsoleHost').isVisible(),true);
  source=await streamIndex();readsBefore=stateReads;
  const activity={...earlyActivity,id:'observation-1',job_id:ordinaryJob.id,command:'db(0x1000, count=32)',entries:[entry('output','00001000  41 42 43 44  ABCD\nPartial synthetic observation')],observation_path:'volshell-observations/synthetic.json'};
  await page.evaluate(()=>Adventure.launch({edition:'select'}));
  await deliver({case_id:'case-a',session:null,busy:false,agent_activity:activity},source);
  assert.equal(await page.evaluate(()=>WorkbenchVolshell.currentMode()),'adventure','Incoming AI activity cannot replace Adventure');
  assert.equal(await page.locator('#adventurePanel').isVisible(),true);
  await page.evaluate(()=>Adventure.exit());
  assert.equal(await page.evaluate(()=>WorkbenchVolshell.currentMode()),'output','Adventure restores the investigation console after incoming AI activity');
  await deliver({case_id:'case-a',session:null,busy:false,agent_activity:activity},source);
  assert.equal(await page.locator('#volshellAgentPanel').isVisible(),true,'Active shell tool switches an already expanded matching case CRT');
  const startsBeforeAgent=count('volshell/start');await page.locator('#consoleVolshellMode').click();
  assert.equal(count('volshell/start'),startsBeforeAgent,'The bezel keeps active AI output read-only without starting a manual session');

  assert.equal(await page.locator('#volshellLED').getAttribute('data-state'),'ready');assert.match(await page.locator('#volshellLEDLabel').textContent(),/AI active/);
  assert.equal(await page.locator('#volshellAgentPanel input,#volshellAgentPanel textarea').count(),0,'AI output is read-only');
  assert.equal(await page.locator('#volshellAgentOutput').evaluate(node=>getComputedStyle(node).color),await page.locator('#volshellOutput').evaluate(node=>getComputedStyle(node).color),'AI output shares the theme terminal color');
  assert.equal(await page.locator('#volshellAgentOutput').evaluate(node=>getComputedStyle(node).fontSize),'13px');
  assert.equal(stateReads,readsBefore,'AI tool output and LED update without polling');
  await screenshot('volshell-agent-stream-desktop');
  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.locator('#volshellAgentPanel').evaluate(node=>node.scrollWidth<=node.clientWidth+1),true,'AI activity fits a narrow screen');
  await screenshot('volshell-agent-stream-390');
  await page.evaluate(()=>window.WorkbenchThemes.apply('fallout-new-vegas'));await page.setViewportSize({width:320,height:844});
  assert.equal(await page.locator('#volshellAgentPanel').evaluate(node=>node.scrollWidth<=node.clientWidth+1),true,'AI activity fits the New Vegas320 screen');
  await screenshot('volshell-agent-stream-new-vegas-320');
  await deliver({case_id:'case-a',session:null,busy:false,agent_activity:{...activity,command:'synthetic_long_command_'.repeat(40),error:'synthetic_long_error_'.repeat(40)}},source);
  assert.equal(await page.locator('#volshellAgentPanel').evaluate(node=>node.scrollWidth<=node.clientWidth+1),true,'Long AI command and error remain contained in the New Vegas320 screen');
  await deliver({case_id:'case-a',session:null,busy:false,agent_activity:activity},source);
  await page.evaluate(()=>window.WorkbenchThemes.apply('fallout-2'));await page.setViewportSize({width:1400,height:1000});
  await page.locator('#consoleOutputMode').click();
  activity.entries.push(entry('output','\nMore output after choosing Output'));
  await deliver({case_id:'case-a',session:null,busy:false,agent_activity:activity},source);
  assert.equal(await page.locator('#expandedConsoleHost').isVisible(),true,'Further fragments do not repeatedly steal the selected pane');
  activity.id='observation-2';activity.command='ps()';activity.entries=[entry('output','<img src=x onerror="window.injected=true">')];
  await deliver({case_id:'case-a',session:null,busy:false,agent_activity:activity},source);
  assert.equal(await page.locator('#volshellAgentPanel').isVisible(),true,'A new tool observation can switch to its own live output');
  assert.equal(await page.locator('#volshellAgentOutput img,#volshellAgentOutput script').count(),0);
  activity.status='completed';activity.finished_at=stamp;
  await deliver({case_id:'case-a',session:null,busy:false,agent_activity:activity},source);
  assert.equal(await page.locator('#volshellLED').getAttribute('data-state'),'off');assert.equal(await page.locator('#volshellAgentPanel').isVisible(),true,'Completed AI output remains reviewable');
  state.approvals=[{id:'agent-only-approval',case_id:'case-a',method:'item/tool/requestUserInput',params:{questions:[{id:'decision',question:'Synthetic agent-only decision'}]}}];
  await refresh();await page.waitForFunction(()=>!document.querySelector('#consoleZoom').open);
  assert.equal(await page.locator('#volshellApprovalNotice').isVisible(),true,'Agent-only approval is surfaced without a manual session');
  assert.match(await page.locator('#approvals').innerText(),/Synthetic agent-only decision/);
  await page.locator('#expandConsole').click();await refresh();assert.equal(await zoom.isVisible(),true,'The same agent-only approval does not repeatedly close review');
  state.approvals=[];await refresh();await page.locator('#expandConsole').click();
  await page.waitForFunction(()=>!document.querySelector('#consoleZoom').open);
  state.volshell.agent_activity={...activity,id:'closed-monitor-activity',status:'running'};await refresh();
  assert.equal(await zoom.isVisible(),false,'New AI activity never opens a collapsed CRT');
  await deliver({case_id:'case-a',session:null,busy:false,agent_activity:{...activity,status:'running'}},source);
  assert.equal(await zoom.isVisible(),false,'Late events from a closed source cannot reopen the CRT');
  assert.equal(await page.evaluate(()=>window.injected),undefined);assert.deepEqual(errors,[]);
  if(process.env.WORKBENCH_VOLSHELL_SCREENSHOT_DIR)fs.writeFileSync(path.join(process.env.WORKBENCH_VOLSHELL_SCREENSHOT_DIR,'bezel-contrast.json'),JSON.stringify(themeStyles,null,2)+'\n');
  console.log('VolShell: direct bezel connect/disconnect, green through commands/stopping until confirmed exit, delayed/failed close and double-click guards; explicit input, ghost drafts, three modes, case/session isolation, AI approvals, pause and Stop all; no-poll SSE fragments, stale/malformed/cross-case rejection, reconnect, scroll preservation, AI tool LED and expanded-only activity;37 distinct bezels, original Fallout 3 terminals and New Vegas desktop/mobile; fully synthetic requests.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
