// Synthetic browser regression; no game, case, analyzer, or network service runs.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const assets=path.join(__dirname,'../src/volatility_workbench/static');
const state={cases:[],jobs:[],approvals:[],account:{},evidence_root:'/synthetic'};
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.WORKBENCH_BROWSER_EXECUTABLE?{executablePath:process.env.WORKBENCH_BROWSER_EXECUTABLE}:{})});
 try {
  const page=await browser.newPage({viewport:{width:1200,height:800}}), errors=[],calls=[];
  let serial=0,session=null,edition=null,output='',saves={'1977':false,'1995':false};
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
   return route.fulfill({body:fs.readFileSync(path.join(assets,name)),contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html'});
  });
  await page.goto('http://localhost/?adventure-dev=1');
  await page.locator('#adventureDevButton').waitFor({state:'visible'});
  const before=await page.evaluate(()=>({theme:document.documentElement.getAttribute('data-theme'),scroll:scrollY}));
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
  assert.ok(calls.every(x=>x==='/api/state'||x.startsWith('/api/adventure/')||x==='/api/settings/zoom'));
  assert.deepEqual(errors,[]);
  console.log('Adventure browser: both editions, input, escape safety, independent saves, relaunch, theme and console restoration passed');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
