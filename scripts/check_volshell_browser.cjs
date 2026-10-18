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
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.WORKBENCH_BROWSER_EXECUTABLE?{executablePath:process.env.WORKBENCH_BROWSER_EXECUTABLE}:{})});
 try{
  const page=await browser.newPage({viewport:{width:1400,height:1000}}),errors=[],posts=[];
  await page.addInitScript(()=>{Date.now=()=>Date.parse('2026-10-18T12:02:42Z');});
  let suggestion={command:'ps()',explanation:'List processes in the selected Windows capture.'},heldSuggestion=null,holdSuggestion=false;
  page.on('pageerror',error=>errors.push(error.message));
  await page.route('**/*',async route=>{
   const request=route.request(),url=new URL(request.url());
   assert.equal(url.origin,'http://localhost','All requests remain inside the synthetic route handler');
   if(request.method()==='GET'){
    if(url.pathname==='/api/state')return route.fulfill({json:state});
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
  await page.locator('#volshellConnect').click();await settle();
  assert.equal(count('volshell/start'),1);assert.equal(await input.isDisabled(),true);
  assert.equal(await page.locator('#volshellLED').getAttribute('data-state'),'pending');
  state.volshell.session.entries=[entry('output','Volshell 2.28.2 · synthetic fixture\n(layer) >>> '),entry('output','<img src=x onerror="window.injected=true">\n')];
  await ready();
  assert.equal(await page.locator('#volshellLED').getAttribute('data-state'),'ready');
  for(const [value,id] of [['manual','volshellInput'],['suggestions','volshellAIInput'],['investigation','volshellInvestigationInput']]){
   await mode(value);await page.locator('#consoleOutputMode').click();await page.locator('#consoleVolshellMode').click();
   assert.equal(await page.locator('#'+id).evaluate(node=>document.activeElement===node),true,'Returning to '+value+' focuses its visible input');
  }
  await mode('manual');
  assert.equal(await page.locator('#volshellInterrupt').isDisabled(),true,'Idle prompt has no command to interrupt');
  assert.equal(await page.locator('#volshellOutput img, #volshellOutput script').count(),0);
  await input.fill('ps');await input.press('Tab');
  assert.equal(await input.inputValue(),'ps()');assert.equal(count('volshell/input'),0,'Tab accepts the draft without running it');
  await input.fill('ps');await input.press('Escape');
  assert.equal(await page.locator('#volshellGhostSuffix').textContent(),'');assert.equal(await zoom.isVisible(),true,'Escape dismisses ghost before closing CRT');
  await input.fill('ps');await input.press('Enter');await settle();
  assert.equal(posts.find(item=>item.path==='/api/volshell/input').body.text,'ps','Enter executes only typed text, never the ghost suffix');
  assert.equal(await input.isDisabled(),true);assert.equal(await page.locator('#volshellLED').getAttribute('data-state'),'pending');
  assert.equal(await page.locator('#volshellInterrupt').isDisabled(),false);
  await page.locator('#volshellInterrupt').click();await settle();
  assert.equal(count('volshell/interrupt'),1);await input.fill('value = 1');await input.press('Shift+Enter');
  assert.match(await input.inputValue(),/\n$/);assert.equal(count('volshell/input'),1,'Shift+Enter adds a line without submitting');
  state.volshell.session.continuation=true;await input.fill('');await refresh();
  assert.equal(await page.locator('#volshellRun').innerText(),'Finish block');
  await page.locator('#volshellRun').click();await settle();
  assert.equal(posts.filter(item=>item.path==='/api/volshell/input').at(-1).body.text,'');
  state.volshell.session.continuation=false;await ready();
  await input.fill('case_a_draft');await page.locator('#volshellCase').selectOption('case-b');
  assert.equal(await input.isDisabled(),true);assert.doesNotMatch(await page.locator('#volshellOutput').innerText(),/Volshell 2.28.2/);
  assert.match(await page.locator('#volshellDisconnect').innerText(),/Synthetic Windows case/);
  await page.locator('#volshellCase').selectOption('case-a');assert.equal(await input.inputValue(),'case_a_draft');
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
  await page.locator('#volshellCase').selectOption('case-b');
  assert.ok(heldSuggestion);await heldSuggestion();heldSuggestion=null;
  await page.locator('#volshellCase').selectOption('case-a');await mode('suggestions');
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
  await page.locator('#openCaseConsole').click();await screenshot('volshell-ai-desktop');
  state.jobs[0].status='completed';await refresh();await mode('manual');assert.equal(await input.isDisabled(),false,'Manual session resumes after the AI job completes');
  await input.fill('ps');await screenshot('volshell-manual-desktop');
  const themeStyles=[];
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
   assert.equal(styles.animation,'none');assert.equal(await page.locator('#volshellLED').getAttribute('data-state'),'ready');
   await page.locator('#consoleOutputMode').focus();await page.keyboard.press('Tab');
   assert.equal(await page.locator('#consoleVolshellMode').evaluate(node=>document.activeElement===node&&getComputedStyle(node).outlineStyle==='solid'),true,theme.id+' bezel shows keyboard focus');
   assert.equal(await page.locator('.crt-vegas-sign').isVisible(),theme.id==='fallout-new-vegas','New Vegas sign stays confined to its own skin');
   themeStyles.push({id:theme.id,...styles});
   if(process.env.WORKBENCH_VOLSHELL_SCREENSHOT_DIR)await page.locator('#consoleVolshellMode').screenshot({path:path.join(process.env.WORKBENCH_VOLSHELL_SCREENSHOT_DIR,'bezel-'+theme.id+'.png')});
   if(['matrix','fallout-new-vegas'].includes(theme.id))await screenshot('volshell-'+theme.id+'-desktop');
  }
  assert.equal(new Set(themeStyles.map(theme=>theme.signature)).size,31,'All 31 themes have a distinct VolShell bezel');
  await page.evaluate(()=>window.WorkbenchThemes.apply('fallout-new-vegas'));
  assert.equal(await page.locator('.crt-vegas-sign').getAttribute('aria-hidden'),'true');
  assert.equal(await page.locator('.vegas-welcome i').count(),7);
  assert.equal(await page.locator('.vegas-welcome i').nth(4).evaluate(node=>getComputedStyle(node).textShadow),'none','A fixed failed sign letter remains dark');
  assert.equal(await page.locator('.vegas-lamps').evaluate(node=>getComputedStyle(node).pointerEvents),'none');
  assert.ok(await page.locator('.crt-vegas-sign,.vegas-lamps,.vegas-lamps span').evaluateAll(nodes=>nodes.every(node=>getComputedStyle(node).animationName==='none')),'Sign and bulbs never flash');
  await page.locator('#consoleOutputMode').click();await screenshot('output-fallout-new-vegas-desktop');await page.locator('#consoleVolshellMode').click();
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
   await page.locator('#consoleOutputMode').click();await screenshot('output-fallout-new-vegas-'+width);await page.locator('#consoleVolshellMode').click();
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
  await page.locator('#volshellCase').selectOption('case-b');await page.locator('#volshellDisconnect').click();await settle();
  assert.equal(count('volshell/close'),1,'Other-case disconnect is an explicit request bound to the original session');
  await page.locator('#consoleOutputMode').click();assert.equal(await page.locator('#expandedConsoleHost').isVisible(),true);
  await page.locator('#consoleVolshellMode').click();assert.equal(await page.locator('#volshellPanel').isVisible(),true);
  await page.keyboard.press('Escape');await page.waitForFunction(()=>!document.querySelector('#consoleZoom').open);
  assert.equal(await page.evaluate(()=>window.injected),undefined);assert.deepEqual(errors,[]);
  if(process.env.WORKBENCH_VOLSHELL_SCREENSHOT_DIR)fs.writeFileSync(path.join(process.env.WORKBENCH_VOLSHELL_SCREENSHOT_DIR,'bezel-contrast.json'),JSON.stringify(themeStyles,null,2)+'\n');
  console.log('VolShell: explicit connection/input, readiness LED, editable ghost completion, continuation, case/session isolation, inert AI drafts and stale responses, three modes, explicit AI investigation/approval/manual pause/Stop all, desktop/mobile CRT, failure/EOF without restart; 31 distinct readable bezels and isolated static New Vegas sign; fully intercepted synthetic requests.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
