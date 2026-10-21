// Synthetic keyboard/semantic regression. Every request is intercepted; no evidence,
// interpreter or provider is opened. Run with the existing Playwright installation.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const assets=path.join(__dirname,'../src/volatility_workbench/static');
const makeCase=id=>({id,title:'Synthetic '+id,created_at:id==='case-b'?'2026-10-19T12:00:00Z':'2026-10-18T12:00:00Z',images:[{id:'E001',path:'/synthetic/'+id+'.vmem',discovery:{detected_os:'windows'}}],coins:[],reports:[],messages:[],activity:[],readiness:{status:'Unchecked',reasons:[]}});
async function fixture(browser){
 const page=await browser.newPage({viewport:{width:1400,height:1000},reducedMotion:'reduce'}),posts=[],errors=[];
 const state={cases:['case-a','case-b'].map(makeCase),jobs:[],approvals:[],account:{},evidence_root:'/synthetic',volshell:{busy:true,session:{id:'shell-a',case_id:'case-a',image_id:'E001',mode:'windows',status:'running',ready:true,entries:[{kind:'output',text:'ONLY CASE A OUTPUT'}],earlier_entries:0}}};
 await page.addInitScript(()=>{window.EventSource=class extends EventTarget{close(){}};const interval=setInterval;window.setInterval=(fn,ms,...args)=>ms===1500?0:interval(fn,ms,...args);});
 page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/*',async route=>{
  const request=route.request(),url=new URL(request.url());assert.equal(url.origin,'http://localhost');
  if(request.method()==='GET'&&url.pathname==='/api/settings/zoom')return route.fulfill({json:{schema:'zoom/1',percent:100}});
  if(request.method()==='POST'){
   const body=request.postDataJSON();posts.push({path:url.pathname,body});
   if(url.pathname==='/api/volshell/input'){assert.equal(body.case_id,'case-a');assert.equal(body.session_id,'shell-a');return route.fulfill({json:state.volshell});}
   if(url.pathname==='/api/volshell/suggest')return route.fulfill({json:{case_id:'case-a',session_id:'shell-a',command:'ps()',explanation:'Synthetic proposal'}});
   throw Error('Unexpected mutation: '+url.pathname);
  }
  if(url.pathname==='/api/settings')return route.fulfill({json:{config:{},has_cases:true,provider:{default_provider:{provider:'codex'},cases:[]},symbols:{profile:{packs:[]}},operation:{status:'idle'},readiness:{status:'Unchecked',reasons:[]}}});
  if(url.pathname==='/api/state')return route.fulfill({json:state});
  if(url.pathname==='/api/artifacts')return route.fulfill({json:{files:[],truncated:false}});
  if(url.pathname==='/api/report-console')return route.fulfill({json:null});
  assert.ok(!url.pathname.startsWith('/api/'),'Unexpected read: '+url.pathname);
  const name=url.pathname==='/'?'index.html':url.pathname.slice(1);
  return route.fulfill({body:fs.readFileSync(path.join(assets,name)),contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':name.endsWith('.svg')?'image/svg+xml':'text/html'});
 });
 await page.goto('http://localhost/?case=case-a');await page.waitForFunction(()=>document.querySelector('#caseTitle').textContent==='Synthetic case-a');
 const focus=async id=>assert.equal(await page.evaluate(()=>document.activeElement.id),id);
 const open=async()=>{await page.locator('#openCaseConsole').focus();await page.keyboard.press('Enter');await page.locator('#consoleZoom').waitFor({state:'visible'});};
 const close=async()=>{assert.deepEqual(errors,[]);await page.close();};
 return {page,state,posts,focus,open,close};
}
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.WORKBENCH_BROWSER_EXECUTABLE?{executablePath:process.env.WORKBENCH_BROWSER_EXECUTABLE}:{})});
 const failures=[];
 const check=async(name,test)=>{const f=await fixture(browser);try{await test(f);console.log('PASS '+name);}catch(e){failures.push(name+': '+e.message);console.error('FAIL '+name+': '+e.message);}finally{await f.close();}};
 try{
 await check('Escape and Collapse restore the keyboard opener',async({page,open,focus,posts})=>{
  for(const key of ['Escape','collapse']){await open();if(key==='Escape')await page.keyboard.press('Escape');else{await page.locator('#collapseVolshell').focus();await page.keyboard.press('Enter');}await page.waitForFunction(()=>!document.querySelector('#consoleZoom').open&&document.querySelector('#expandConsole').getAttribute('aria-expanded')==='false');await focus('openCaseConsole');}assert.equal(posts.length,0);
 });
 await check('Tab and Shift+Tab cycle visible controls in all three modes',async({page,open,focus,posts})=>{
  await open();
  for(const mode of ['manual','suggestions','investigation']){
   await page.locator('#volshellInteractionMode').focus();await page.keyboard.press('Home');for(let i=0;i<['manual','suggestions','investigation'].indexOf(mode);i++)await page.keyboard.press('ArrowDown');await page.keyboard.press('Tab');
   assert.equal(await page.locator('#volshellInteractionMode').inputValue(),mode);
   const ids=['volshellOutput',mode==='manual'?'volshellInput':mode==='suggestions'?'volshellAIInput':'volshellInvestigationInput',mode==='manual'?'volshellRun':mode==='suggestions'?'volshellAISubmit':'volshellInvestigate','consoleOutputMode','consoleVolshellMode'];
   if(mode==='investigation'){ids.shift();ids.splice(ids.indexOf('consoleOutputMode'),0,'volshellInvestigationOutput');}
   // Empty manual draft disables Run, so it is omitted from the Tab sequence.
   if(mode==='manual')ids.splice(ids.indexOf('volshellRun'),1);
   for(let i=0;i<ids.length;i++){await focus(ids[i]);await page.keyboard.press('Tab');}
   await focus(''); // The connection summary has no id.
   assert.equal(await page.evaluate(()=>document.activeElement.matches('#volshellConnection > summary')),true);
   await page.keyboard.press('Shift+Tab');await focus('consoleVolshellMode');
   await page.keyboard.press('Tab');await page.keyboard.press('Tab');await focus('collapseVolshell');
   await page.keyboard.press('Tab');await focus('volshellInteractionMode');
   await page.keyboard.press('Shift+Tab');await focus('collapseVolshell');
  }
  assert.equal(posts.length,0,'Mode and focus changes never submit or connect');
 });
 await check('Closed connection disclosure keeps status in the accessibility tree',async({page,open,state,posts})=>{
  await open();assert.equal(await page.locator('#volshellConnection').evaluate(n=>n.open),false);
  assert.match(await page.locator('#consoleZoom').ariaSnapshot(),/status:.*Synthetic case-a.*Connected.*ready/);
  await page.evaluate(()=>{window.statusMutations=0;new MutationObserver(records=>window.statusMutations+=records.length).observe(document.querySelector('#volshellAnnouncement'),{childList:true,subtree:true,characterData:true});});
  await page.evaluate(()=>refresh());await page.evaluate(()=>refresh());assert.equal(await page.evaluate(()=>statusMutations),0,'Unchanged polling does not reannounce status');
  state.volshell.session.ready=false;await page.evaluate(()=>refresh());assert.match(await page.locator('#volshellAnnouncement').textContent(),/command running/);assert.ok(await page.evaluate(()=>statusMutations)>0);assert.equal(posts.length,0);
 });
 await check('Manual shortcuts accept drafts without submitting, then Enter runs exactly once',async({page,open,focus,posts})=>{
  await open();const input=page.locator('#volshellInput');await input.fill('ps');await input.press('Shift+Tab');await focus('volshellOutput');assert.equal(posts.length,0);
  await input.focus();await input.press('Tab');assert.equal(await input.inputValue(),'ps()');await focus('volshellInput');assert.equal(posts.length,0);
  await input.fill('ps');await input.press('Escape');assert.equal(await page.locator('#consoleZoom').evaluate(n=>n.open),true);assert.equal(posts.length,0);
  await input.press('Tab');await focus('volshellRun');await page.keyboard.press('Shift+Tab');await focus('volshellInput');await input.press('Shift+Enter');assert.match(await input.inputValue(),/\n/);assert.equal(posts.length,0);
  await input.fill('ps()');await input.press('Enter');await page.waitForFunction(()=>!document.querySelector('#volshellInput').disabled);assert.equal(posts.length,1);assert.equal(posts[0].body.text,'ps()');
 });
 await check('AI proposals require explicit draft adoption and explicit execution',async({page,open,posts})=>{
  await open();await page.locator('#volshellInteractionMode').selectOption('suggestions');const input=page.locator('#volshellAIInput');await input.fill('List processes');await input.press('Enter');assert.equal(posts.length,0,'Enter in AI textarea adds a line');await page.locator('#volshellAISubmit').focus();await page.keyboard.press('Enter');await page.locator('#volshellUseProposal').waitFor();assert.deepEqual(posts.map(p=>p.path),['/api/volshell/suggest']);await page.locator('#volshellUseProposal').focus();await page.keyboard.press('Enter');assert.equal(await page.locator('#volshellInput').inputValue(),'ps()');assert.equal(posts.length,1);
 });
 await check('AI investigation text and mode changes never submit implicitly',async({page,open,posts})=>{
  await open();await page.locator('#volshellInteractionMode').selectOption('investigation');
  const input=page.locator('#volshellInvestigationInput');await input.fill('Describe this synthetic capture');await input.press('Enter');assert.match(await input.inputValue(),/\n/);await input.press('Tab');await page.keyboard.press('Shift+Tab');
  await page.locator('#volshellInteractionMode').selectOption('manual');await page.locator('#volshellInteractionMode').selectOption('investigation');assert.equal(posts.length,0);
 });
 await check('Case change is explicit and never reveals another case transcript',async({page,open,posts,state})=>{
  await open();await page.locator('#volshellConnection summary').focus();await page.keyboard.press('Enter');await page.keyboard.press('Tab');await page.keyboard.press('End');await page.keyboard.press('Tab');assert.equal(await page.locator('#volshellCase').inputValue(),'case-b');assert.doesNotMatch(await page.locator('#consoleZoom').innerText(),/ONLY CASE A OUTPUT/);assert.match(await page.locator('#caseTitle').textContent(),/case-a/,'Console target does not switch main investigation context');assert.equal(await page.locator('#volshellInput').isDisabled(),true);assert.equal(state.volshell.session.case_id,'case-a');assert.equal(posts.length,0);
 });
 await check('Case buttons retain focus across polling and announce the current case',async({page,posts,state})=>{
  const current=page.getByRole('button',{name:'Synthetic case-a',exact:true});await current.focus();await page.evaluate(()=>refresh());assert.equal(await current.evaluate(n=>document.activeElement===n),true,'Polling preserves keyboard focus on the case');assert.equal(await current.getAttribute('aria-current'),'true');
  const next=page.getByRole('button',{name:'Synthetic case-b',exact:true});await page.keyboard.press('Shift+Tab');assert.equal(await next.evaluate(n=>document.activeElement===n),true);await page.keyboard.press('Enter');assert.equal(await page.locator('#caseTitle').textContent(),'Synthetic case-b');assert.equal(await next.getAttribute('aria-current'),'true');assert.equal(await current.getAttribute('aria-current'),null);assert.equal(await next.evaluate(n=>document.activeElement===n),true);assert.equal(posts.length,0);
  state.cases.find(c=>c.id==='case-a').created_at='2026-10-20T12:00:00Z';await page.evaluate(()=>refresh());assert.equal(await next.evaluate(n=>document.activeElement===n),true,'Reordering retains focus without choosing another case');assert.equal(await page.locator('#caseTitle').textContent(),'Synthetic case-b');assert.equal(posts.length,0);
 });
 await check('Settings keyboard round trip retains the selected case without actions',async({page,open,posts})=>{
  await open();await page.keyboard.press('Escape');await page.waitForFunction(()=>!document.querySelector('#consoleZoom').open);
  await page.getByRole('link',{name:'Settings',exact:true}).focus();await page.keyboard.press('Enter');await page.locator('#settings-theme').waitFor();await page.waitForFunction(()=>!document.querySelector('[data-ui-zoom-out]').disabled);
  await page.getByRole('link',{name:'← Back to Workbench',exact:true}).focus();
  for(const selector of ['[data-ui-zoom-out]','[data-ui-zoom-reset]','[data-ui-zoom-in]','#settings-theme']){await page.keyboard.press('Tab');assert.equal(await page.locator(selector).evaluate(n=>document.activeElement===n),true,'Settings keeps its text-size controls before Theme');}
  for(let i=0;i<4;i++)await page.keyboard.press('Shift+Tab');
  assert.equal(await page.getByRole('link',{name:'← Back to Workbench',exact:true}).evaluate(n=>document.activeElement===n),true);await page.keyboard.press('Enter');await page.locator('#caseTitle').waitFor();await page.waitForFunction(()=>document.querySelector('#caseTitle').textContent);
  assert.equal(await page.locator('#caseTitle').textContent(),'Synthetic case-a','Return must not select the newer case-b');await open();assert.match(await page.locator('#volshellOutput').textContent(),/ONLY CASE A OUTPUT/);assert.equal(posts.length,0);
 });
 await check('Named controls, keyboard focus indicator and reduced motion',async({page,open,posts})=>{
  await open();for(const [role,name] of [['combobox','Mode'],['textbox','Command'],['button','Collapse']])assert.equal(await page.getByRole(role,{name,exact:true}).count(),1,name);
  const client=await page.context().newCDPSession(page);const ax=await client.send('Accessibility.getFullAXTree');assert.ok(ax.nodes.some(n=>!n.ignored&&n.name?.value==='Connection options'),'Native summary has an accessible name');await client.detach();
  for(const theme of ['matrix','fallout-new-vegas']){await page.evaluate(id=>WorkbenchThemes.apply(id),theme);await page.locator('#consoleOutputMode').focus();await page.keyboard.press('Tab');assert.equal(await page.locator('#consoleVolshellMode').evaluate(n=>getComputedStyle(n).outlineStyle),'solid');assert.equal(await page.evaluate(()=>matchMedia('(prefers-reduced-motion: reduce)').matches),true);assert.deepEqual(await page.evaluate(()=>document.getAnimations().filter(a=>a.playState==='running').map(a=>a.animationName)),[]);}
  await page.evaluate(()=>{const progress=document.createElement('div');progress.className='dos-progress indeterminate';const fill=document.createElement('span');fill.id='synthetic-progress';fill.className='dos-progress-fill';progress.append(fill);document.querySelector('#volshellPanel').append(progress);});
  assert.equal(await page.locator('#synthetic-progress').evaluate(n=>getComputedStyle(n).animationName),'none');
  await page.emulateMedia({reducedMotion:'no-preference'});assert.equal(await page.locator('#synthetic-progress').evaluate(n=>getComputedStyle(n).animationName),'dos-progress-scan');await page.emulateMedia({reducedMotion:'reduce'});assert.equal(await page.locator('#synthetic-progress').evaluate(n=>getComputedStyle(n).animationName),'none');assert.equal(posts.length,0);
 });
 }finally{await browser.close();}
 assert.deepEqual(failures,[]);
 console.log('Accessibility regression: keyboard ordering, focus return, status semantics, draft boundaries, case isolation and reduced motion passed.');
})().catch(error=>{console.error(error);process.exit(1);});
