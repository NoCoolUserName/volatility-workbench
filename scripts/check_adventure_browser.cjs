// Synthetic browser regression; no game, case, analyzer, or network service runs.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const assets=path.join(__dirname,'../src/volatility_workbench/static');
const csp="default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'";
const state={cases:[],jobs:[],approvals:[],account:{},evidence_root:'/synthetic'};
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.WORKBENCH_BROWSER_EXECUTABLE?{executablePath:process.env.WORKBENCH_BROWSER_EXECUTABLE}:{})});
 try {
  const page=await browser.newPage({viewport:{width:1200,height:800}}), errors=[],calls=[];
  let serial=0,session=null,edition=null,output='',saves={'1977':false,'1995':false};
  let slowNextStart=false,releaseStart=null;
  page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{window.EventSource=class extends EventTarget {close(){}};});
  await page.route('http://localhost/**',async route=>{
   const url=new URL(route.request().url()),method=route.request().method();
   if(url.pathname==='/api/settings/zoom')return route.fulfill({json:{schema:'zoom/1',percent:100}});
   if(url.pathname.startsWith('/api/')) {
    calls.push(url.pathname);
    if(url.pathname==='/api/state')return route.fulfill({json:state});
    if(url.pathname==='/api/adventure/status')return route.fulfill({json:{session_id:session,edition,status:session?'running':'idle',output,saved:saves[edition],error:null}});
    assert.equal(method,'POST');
    const body=route.request().postDataJSON();
    if(url.pathname==='/api/adventure/start') {
     if(slowNextStart){slowNextStart=false;await new Promise(resolve=>{releaseStart=resolve;});}
     assert.ok(['1977','1995'].includes(body.edition));edition=body.edition;
     if(body.new)saves[edition]=false;
     session='synthetic-'+(++serial);output=(saves[edition]?'RESTORED ':'NEW ')+edition+' CAVE\n';
     return route.fulfill({json:{session_id:session,edition,status:'running',output,saved:saves[edition],error:null}});
    }
    if(url.pathname==='/api/adventure/input') {
     assert.equal(body.session_id,session);output+='CAVE: '+body.command+'\n';
     return route.fulfill({json:{session_id:session,edition,status:'running',output,saved:saves[edition],error:null}});
    }
    if(url.pathname==='/api/adventure/close') {
     assert.equal(body.session_id,session);saves[edition]=true;session=null;
     return route.fulfill({json:{session_id:null,edition:null,status:'closed',output,saved:true,error:null}});
    }
    throw Error('Unexpected API '+url.pathname);
   }
   const name=url.pathname==='/'?'index.html':url.pathname.slice(1);
   return route.fulfill({body:fs.readFileSync(path.join(assets,name)),headers:{'content-security-policy':csp},contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':name.endsWith('.png')?'image/png':name.endsWith('.svg')?'image/svg+xml':'text/html'});
  });
  await page.goto('http://localhost/?adventure-dev=1');
  assert.equal(await page.locator('#adventureDevButton').evaluate(x=>x.hidden),false);
  const before=await page.evaluate(()=>({theme:document.documentElement.getAttribute('data-theme'),scroll:scrollY}));
  await page.evaluate(async()=>{
    const original=WorkbenchVolshell;
    window.WorkbenchVolshell=Object.freeze({...original,restoreMode: mode=>{window.adventureRestoredMode=mode;original.restoreMode(mode);}});
    document.querySelector('#consoleZoom').showModal();
    original.restoreMode('volshell');
    await Adventure.launch({edition:'select'});
  });
  assert.equal(await page.evaluate(()=>WorkbenchVolshell.currentMode()),'adventure');
  await page.locator('#adventureExit').click();
  assert.equal(await page.evaluate(()=>window.adventureRestoredMode),'volshell');
  await page.evaluate(()=>document.querySelector('#consoleZoom').close());
  await page.evaluate(()=>Adventure.launch({edition:'select'}));
  assert.equal(await page.locator('#consoleZoom').evaluate(x=>x.open),true);
  assert.equal(await page.locator('#adventure1977').isEnabled(),true);
  assert.equal(await page.locator('#adventure1977').evaluate(x=>document.activeElement===x),true);
  await page.locator('#adventure1977').click();
  await page.locator('#adventureOutput').getByText('NEW 1977 CAVE').waitFor();
  await page.locator('#adventureInput').fill('<img src=x onerror="window.injected=true">');
  await page.locator('#adventureSend').click();
  await page.waitForFunction(()=>document.querySelector('#adventureOutput').textContent.includes('CAVE: <img'));
  assert.equal(await page.locator('#adventureOutput img').count(),0);
  assert.equal(await page.evaluate(()=>window.injected),undefined);
  await page.locator('#adventureExit').click();
  await page.waitForFunction(()=>!document.querySelector('#consoleZoom').open);
  assert.equal(await page.evaluate(()=>WorkbenchVolshell.currentMode()),'output');
  assert.deepEqual(await page.evaluate(()=>({theme:document.documentElement.getAttribute('data-theme'),scroll:scrollY})),before);
  await page.evaluate(()=>Adventure.launch({edition:'1977'}));
  await page.locator('#adventureOutput').getByText('RESTORED 1977 CAVE').waitFor();
  await page.locator('#adventureExit').click();
  await page.waitForFunction(()=>!document.querySelector('#consoleZoom').open);
  await page.evaluate(()=>Adventure.launch({edition:'1995'}));
  await page.locator('#adventureOutput').getByText('NEW 1995 CAVE').waitFor();
  await page.locator('#adventureExit').click();
  await page.waitForFunction(()=>!document.querySelector('#consoleZoom').open);
  await page.evaluate(()=>Adventure.launch({edition:'1995'}));
  await page.locator('#adventureOutput').getByText('RESTORED 1995 CAVE').waitFor();
  await page.locator('#adventureExit').click();
  await page.waitForFunction(()=>!document.querySelector('#consoleZoom').open);
  slowNextStart=true;
  await page.evaluate(()=>{window.firstRapidLaunch=Adventure.launch({edition:'1977'});});
  for(let attempt=0;attempt<100&&!releaseStart;attempt++)await new Promise(resolve=>setTimeout(resolve,10));
  assert.ok(releaseStart,'Delayed start did not reach the synthetic route');
  await page.locator('#adventureExit').click();
  await page.waitForFunction(()=>!document.querySelector('#consoleZoom').open);
  await page.evaluate(()=>{window.secondRapidLaunch=Adventure.launch({edition:'select'});});
  releaseStart();
  await page.evaluate(()=>window.firstRapidLaunch);
  await page.evaluate(()=>window.secondRapidLaunch);
  assert.equal(await page.locator('#adventureMenu').evaluate(x=>x.hidden),false);
  assert.equal(await page.locator('#adventureOutput').evaluate(x=>x.hidden),true);
  await page.locator('#adventure1995').click();
  await page.locator('#adventureOutput').getByText('RESTORED 1995 CAVE').waitFor();
  await page.locator('#adventureExit').click();
  await page.waitForFunction(()=>!document.querySelector('#consoleZoom').open);
  await page.evaluate(async()=>{try{await Adventure.launch({edition:'invalid'});}catch(e){window.invalidEditionMessage=e.message;}});
  assert.equal(await page.evaluate(()=>window.invalidEditionMessage),'Unknown Adventure edition');
  assert.equal(await page.locator('#consoleZoom').evaluate(x=>x.open),false);
  // Production knob access is confined to the open Field Terminal console.
  await page.goto('http://localhost/');
  assert.equal(await page.locator('#adventureDevButton').evaluate(x=>x.hidden),true);
  await page.evaluate(()=>{WorkbenchThemes.apply('fallout-76-field-terminal');document.querySelector('#consoleZoom').showModal();WorkbenchVolshell.restoreMode('volshell');});
  const upper=page.locator('#fieldAdventure1977'),lower=page.locator('#fieldAdventure1995');
  for(const [width,height,scale] of [[1400,1000,1],[900,600,1],[800,400,1],[701,1000,2],[900,600,2],[390,844,1],[320,844,2]]){
   await page.setViewportSize({width,height});
   await page.evaluate(scale=>{document.documentElement.style.setProperty('--text-scale',String(scale));document.documentElement.dataset.textScaled=String(scale!==1);},scale);
   const geometry=await page.evaluate(()=>{
    const box=selector=>{const r=document.querySelector(selector).getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width,height:r.height};};
    const frame=box('#consoleZoom'),upper=box('#fieldAdventure1977'),lower=box('#fieldAdventure1995');
    return {frame,upper,lower,screen:box('.crt-screen'),output:box('#consoleOutputMode'),shell:box('#consoleVolshellMode'),saved:box('.crt-power'),savedVisible:getComputedStyle(document.querySelector('.crt-power')).display!=='none',
     fallback:getComputedStyle(document.querySelector('.crt-mode-controls')).position==='static',
     labelsFit:['#consoleOutputMode','#consoleVolshellMode'].every(selector=>{const node=document.querySelector(selector),texts=document.createTreeWalker(node,NodeFilter.SHOW_TEXT);let text;while((text=texts.nextNode())){if(!text.textContent.trim())continue;const range=document.createRange();range.selectNodeContents(text);if(range.getClientRects().length>1)return false;}return node.scrollWidth<=node.clientWidth+1;}),
     upperHit:document.elementFromPoint(frame.left+frame.width*.915,frame.top+frame.height*.63)?.id,
     lowerHit:document.elementFromPoint(frame.left+frame.width*.92,frame.top+frame.height*.875)?.id};
   });
   assert.equal(geometry.upperHit,'fieldAdventure1977','Upper knob face must be clickable at every scale');
   assert.equal(geometry.lowerHit,'fieldAdventure1995','Lower knob face must be clickable at every scale');
   assert.ok(geometry.upper.bottom<geometry.lower.top,'The two knob targets must not overlap');
   for(const button of [geometry.output,geometry.shell])assert.ok(button.left>=0&&button.right<=width&&button.top>=0&&button.bottom<=height,'Mode buttons remain reachable');
   assert.ok(geometry.labelsFit,`Mode labels remain unbroken and contained at ${width}×${height}/${scale}`);
   assert.ok(geometry.saved.bottom<=height,'Saved status stays within the viewport');
   if(!geometry.fallback){
    assert.ok(geometry.output.top>=geometry.frame.top+geometry.frame.height*.46,'Output sits below the silver latch');
    assert.ok(geometry.output.bottom<=geometry.shell.top&&geometry.shell.right<geometry.screen.left,'Mode buttons stack on the left housing');
    assert.ok(geometry.shell.bottom<geometry.frame.bottom,'Mode buttons remain on the metal housing');
   }else{
    assert.ok(geometry.output.top>=geometry.frame.bottom,'Small housings use the below-frame controls');
    if(geometry.savedVisible)assert.ok(Math.max(geometry.output.bottom,geometry.shell.bottom)<=geometry.saved.top,'Saved status cannot overlap the mode controls');
   }
   if(process.env.WORKBENCH_FIELD_TERMINAL_SCREENSHOTS){
    fs.mkdirSync(process.env.WORKBENCH_FIELD_TERMINAL_SCREENSHOTS,{recursive:true});
    await page.screenshot({path:path.join(process.env.WORKBENCH_FIELD_TERMINAL_SCREENSHOTS,`field-${width}x${height}-${scale*100}.png`)});
   }
  }
  await page.setViewportSize({width:1400,height:1000});
  await page.evaluate(()=>{document.documentElement.style.removeProperty('--text-scale');document.documentElement.dataset.textScaled='false';});
  let startsBefore=serial;
  await upper.click();await page.waitForTimeout(100);
  assert.equal(serial,startsBefore,'A single knob click must not start a game');
  const frame=await page.locator('#consoleZoom').boundingBox();
  await page.mouse.dblclick(frame.x+frame.width*.9,frame.y+frame.height*.4);
  await page.waitForTimeout(100);assert.equal(serial,startsBefore,'Adjacent metal must not launch a game');
  await upper.dblclick();await page.locator('#adventureOutput').getByText('RESTORED 1977 CAVE').waitFor();
  assert.equal(serial,startsBefore+1);assert.equal(edition,'1977');
  await upper.dblclick();await lower.dblclick();await page.waitForTimeout(100);
  assert.equal(serial,startsBefore+1,'Repeated knob activation must preserve the running game');
  await page.locator('#adventureExit').click();
  assert.equal(await page.evaluate(()=>WorkbenchVolshell.currentMode()),'volshell');
  assert.equal(await upper.evaluate(x=>document.activeElement===x),true,'Return restores focus to the activating knob');
  await lower.dblclick();await page.locator('#adventureOutput').getByText('RESTORED 1995 CAVE').waitFor();
  assert.equal(edition,'1995');await page.locator('#adventureExit').click();
  await upper.focus();await upper.press('Enter');await page.locator('#adventureOutput').getByText('RESTORED 1977 CAVE').waitFor();
  assert.equal(await upper.evaluate(x=>getComputedStyle(x).backgroundColor),'rgba(0, 0, 0, 0)','The artwork supplies the visible knob');
  await page.locator('#adventureExit').click();
  await lower.focus();await lower.press('Space');await page.locator('#adventureOutput').getByText('RESTORED 1995 CAVE').waitFor();
  await page.locator('#adventureExit').click();
  assert.equal(await page.locator('html').getAttribute('data-theme'),'fallout-76-field-terminal','Knob access must preserve the theme');
  startsBefore=serial;
  for(const theme of ['matrix','fallout-76-camden-park','fallout-3-robco']){
   await page.evaluate(theme=>WorkbenchThemes.apply(theme),theme);
   assert.equal(await upper.isVisible(),false);assert.equal(await lower.isVisible(),false);
   await upper.dispatchEvent('dblclick');
  }
  await page.evaluate(()=>{WorkbenchThemes.apply('fallout-76-field-terminal');document.querySelector('#consoleZoom').close();});
  await upper.dispatchEvent('dblclick');await page.waitForTimeout(100);
  assert.equal(serial,startsBefore,'Other themes and a closed console cannot activate the knobs');
  assert.ok(calls.every(x=>x==='/api/state'||x.startsWith('/api/adventure/')||x==='/api/settings/zoom'));
  assert.deepEqual(errors,[]);
  console.log('Adventure browser: both editions, input, escape safety, independent saves, relaunch, theme/console restoration, Field Terminal knob mapping, keyboard access, single-click and theme guards passed');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
