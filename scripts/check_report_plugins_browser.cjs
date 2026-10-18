// Offline selected-report inventory check. No case, analyzer or model operations.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const assets=path.join(__dirname,'../src/volatility_workbench/static');
const csp="default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'";
const report=id=>({id,status:'sealed',created_at:'2026-10-18T12:00:00Z'});
const sample=(id,reports,created_at)=>({id,title:id,created_at,images:[],coins:[],readiness:{status:'Unchecked',reasons:[]},reports,messages:[],activity:[]});
const state={cases:[sample('Synthetic A',['legacy','partial','delayed','current'].map(report),'2026-10-18T12:00:00Z'),sample('Synthetic B',[report('other')],'2026-10-17T12:00:00Z')],jobs:[],approvals:[],account:{},evidence_root:'/synthetic'};
const hostile='<img src=x onerror="window.injected=true">';
const entries=Array.from({length:21},(_,i)=>({kind:i===1?'reuse_receipt':i===2?'request_failure':'plugin_run',execution_recorded:i===1||i===2?false:true,
  synthetic:i===3,execution_kind:i===3?'simulated':i===1||i===2?'unknown':'physical',provenance:i===1?'investigation_log':'core_manifest',run_id:'run-'+i,call_id:'call-'+i,image_id:'E001',plugin:i===0?'windows.synthetic.'+hostile:'windows.synthetic.Plugin'+i,
  status:i===0?'failed':i===1?'reused':i===2?'denied':'completed',arguments:i===1?null:['--pid','123',i===0?hostile+'x'.repeat(12000):''],argv:i===1||i===2?null:[['python','-m','vol','--pid','123']],
  started_at:'2026-10-18T12:00:00Z',finished_at:i===1?null:'2026-10-18T12:00:01Z',reuse_count:i===0?2:0,source_path:i===0?'artifacts/C-synthetic/manifest.json':i===2?'../escape.json':null}));
const payload=(id,rows,status='available',next=null)=>({schema:'report-plugin-inventory/1',report_id:id,scope:'bundled_saved_runs',source_status:status,
  summary:status==='unavailable'?{executions:null,plugins:null,failures:null,reuse_receipts:null,request_failures:null}:{executions:18,plugins:20,failures:1,reuse_receipts:1,request_failures:1,unknown_execution_records:1,simulated_runs:1},
  entries:rows,next_offset:next,warnings:status==='partial'?['Synthetic missing manifest <script>window.injected=true</script>']:[]});
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.WORKBENCH_BROWSER_EXECUTABLE?{executablePath:process.env.WORKBENCH_BROWSER_EXECUTABLE}:{})});
 try{
  const page=await browser.newPage({viewport:{width:1400,height:1000}});
  const calls=[],errors=[],policies=[];let delayedRelease=null,failCurrent=false;
  page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(/Content Security Policy|violates the following/.test(m.text()))policies.push(m.text());});
  await page.route('**/*',async route=>{
   const u=new URL(route.request().url());assert.equal(u.origin,'http://localhost');assert.equal(route.request().method(),'GET','Inventory never starts work');calls.push(u.pathname+u.search);
   if(u.pathname==='/api/state')return route.fulfill({json:state});
   if(u.pathname==='/api/artifacts')return route.fulfill({json:{files:[],truncated:false}});
   if(u.pathname==='/api/file')return route.fulfill({json:{text:u.searchParams.get('path').endsWith('manifest.json')?'{"synthetic":"manifest only"}':'# Synthetic report\n## Investigative workflow\n<!-- report-plugin-inventory -->\nDuplicate generated inventory text\n<!-- /report-plugin-inventory -->\n## Observation\nHarmless fixture only.',size:128,next_offset:128,truncated:false}});
   if(u.pathname==='/api/report-plugins'){
    const id=u.searchParams.get('report'),offset=Number(u.searchParams.get('offset'));assert.equal(u.searchParams.get('limit'),'20');
    if(id==='delayed')await new Promise(resolve=>{delayedRelease=resolve;});
    if(id==='current'&&failCurrent){failCurrent=false;return route.fulfill({status:500,json:{error:'Synthetic inventory failure'}});}
    return route.fulfill({json:id==='legacy'?payload(id,[],'unavailable'):id==='partial'?payload(id,[entries[0]],'partial'):id==='current'?payload(id,entries.slice(offset,offset+20),'available',offset===0?20:null):payload(id,[{...entries[3],plugin:id+'-plugin'}])});
   }
   assert.ok(!u.pathname.startsWith('/api/'),'Unexpected analysis/action '+u.pathname);
   const name=u.pathname==='/'?'index.html':u.pathname.slice(1);
   return route.fulfill({body:fs.readFileSync(path.join(assets,name)),headers:{'content-security-policy':csp},contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':name.endsWith('.svg')?'image/svg+xml':name.endsWith('.png')?'image/png':'text/html'});
  });
  const inventory=page.locator('#reportPluginInventory'),table=inventory.locator('tbody');
  const choose=async id=>{await page.locator(`.report-version[data-report-id="${id}"] > button:first-child`).click();};
  await page.goto('http://localhost/');
  await page.waitForFunction(()=>document.querySelector('#reportPluginInventory summary')?.textContent.includes('18 recorded executions'));
  assert.equal(await inventory.locator('details.report-plugin-inventory').getAttribute('open'),null,'Large inventory starts collapsed');
  await inventory.locator('> details > summary').focus();await page.keyboard.press('Space');
  assert.equal(await inventory.locator('> details').getAttribute('open'),'');
  assert.equal(await table.locator('tr').count(),20);
  assert.doesNotMatch(await page.locator('#reportView').innerText(),/Duplicate generated inventory text/);
  assert.match(await table.locator('tr').nth(3).innerText(),/Simulated execution record/);
  assert.match(await inventory.innerText(),/earlier saved executions and reuse receipts/);
  assert.match(await inventory.innerText(),/1 execution failures · 1 reuse receipts · 1 request failures/);
  assert.match(await inventory.innerText(),/1 records with unknown execution provenance/);
  assert.match(await inventory.innerText(),/1 explicitly simulated run records/);
  assert.match(await table.locator('tr').nth(1).innerText(),/Saved result reuse.*No execution recorded/s);
  assert.match(await table.locator('tr').nth(2).innerText(),/Failed or denied request.*No execution recorded/s);
  assert.equal(await inventory.locator('img,script').count(),0);assert.equal(await page.evaluate(()=>window.injected),undefined);
  assert.equal(await inventory.getByRole('link',{name:'Open manifest'}).count(),1,'Traversal path never becomes link');
  await table.locator('tr').first().locator('td').nth(3).locator('summary').first().click();
  assert.equal(await table.locator('tr').first().locator('pre').first().textContent(),JSON.stringify(entries[0].arguments,null,2));
  const before=calls.filter(x=>x.startsWith('/api/report-plugins')).length;
  await page.waitForTimeout(1700);
  assert.equal(calls.filter(x=>x.startsWith('/api/report-plugins')).length,before,'Polling must not fetch inventory again');
  assert.equal(await table.locator('tr').first().locator('td').nth(3).locator('details').first().getAttribute('open'),'','Polling preserves expanded exact args');
  await inventory.getByRole('button',{name:'More plugin records'}).click();
  await page.waitForFunction(()=>document.querySelectorAll('#reportPluginInventory tbody tr').length===21);
  assert.equal(await inventory.getByRole('button',{name:'More plugin records'}).count(),0);
  assert.match(await page.evaluate(()=>document.activeElement.textContent),/All saved plugin records loaded/);
  await choose('legacy');
  await page.waitForFunction(()=>document.querySelector('#reportPluginInventory summary')?.textContent.includes('Inventory unavailable'));
  await inventory.locator('> details > summary').click();
  assert.match(await inventory.innerText(),/does not mean no plugins ran/);assert.equal(await inventory.locator('table').count(),0);
  assert.doesNotMatch(await inventory.innerText(),/0 recorded executions/);
  await choose('partial');await page.waitForFunction(()=>document.querySelector('#reportPluginInventory .inventory-warning')?.textContent.includes('Partial'));
  await inventory.locator('> details > summary').click();assert.match(await inventory.innerText(),/Synthetic missing manifest <script>/);assert.equal(await inventory.locator('script').count(),0);
  await choose('delayed');await page.waitForFunction(()=>document.querySelector('#reportPluginInventory summary')?.textContent.includes('Loading'));
  await choose('current');assert.equal(await table.locator('tr').count(),21,'Returning to cached report preserves pagination');
  assert.ok(delayedRelease);delayedRelease();await page.waitForTimeout(100);
  assert.doesNotMatch(await inventory.innerText(),/delayed-plugin/,'Stale reply never replaces current report');
  await page.getByRole('button',{name:'Synthetic B',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('#reportPluginInventory tbody')?.textContent.includes('other-plugin'));
  await page.getByRole('button',{name:'Synthetic A',exact:true}).click();assert.equal(await table.locator('tr').count(),21);
  assert.equal(await page.locator('.report-version.selected').getAttribute('data-report-id'),'current');
  failCurrent=true;await inventory.getByRole('button',{name:'Refresh saved inventory'}).click();
  await page.waitForFunction(()=>document.querySelector('#reportPluginInventory [role=alert]'));
  assert.match(await inventory.innerText(),/Synthetic inventory failure/);assert.equal(await table.locator('tr').count(),21,'Failed refresh retains last good snapshot');
  await inventory.getByRole('button',{name:'Retry plugin inventory'}).click();
  await page.waitForFunction(()=>document.querySelectorAll('#reportPluginInventory tbody tr').length===20);
  assert.equal(await inventory.locator('[role=alert]').count(),0);
  for(const id of await page.evaluate(()=>window.WorkbenchThemes.catalog.map(t=>t.id))){
   await page.locator('#theme').selectOption(id);assert.equal(await table.locator('tr').count(),20);assert.equal(await page.locator('.report-version.selected').getAttribute('data-report-id'),'current');
   const ratio=await table.evaluate(node=>{const c=getComputedStyle(node),parse=s=>s.match(/[\d.]+/g).slice(0,3).map(Number).map(n=>{n/=255;return n<=.04045?n/12.92:((n+.055)/1.055)**2.4;}),lum=a=>a[0]*.2126+a[1]*.7152+a[2]*.0722;const text=lum(parse(c.color)),bg=lum(parse(getComputedStyle(node.closest('.report-plugin-inventory')).backgroundColor));return(text+.05)/(bg+.05);});
   assert.ok(ratio>=4.5,id+' table text contrast');
  }
  if(process.env.WORKBENCH_REPORT_PLUGIN_SCREENSHOT)await page.screenshot({path:process.env.WORKBENCH_REPORT_PLUGIN_SCREENSHOT,fullPage:true});
  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Only table region scrolls on mobile');
  const region=inventory.getByRole('region');await region.focus();assert.equal(await region.evaluate(e=>getComputedStyle(e).outlineStyle),'solid');
  assert.ok(await region.evaluate(e=>e.scrollWidth>e.clientWidth));
  await page.setViewportSize({width:1400,height:1000});
  await inventory.getByRole('link',{name:'Open manifest'}).click();
  await page.waitForFunction(()=>document.querySelector('#artifactView').textContent.includes('manifest only'));
  assert.ok(calls.some(x=>x.startsWith('/api/file?')&&decodeURIComponent(x).includes('reports/current/artifacts/C-synthetic/manifest.json')));
  assert.deepEqual(errors,[]);assert.deepEqual(policies,[]);assert.equal(await page.evaluate(()=>window.injected),undefined);
  console.log('Report plugins browser: counts/scope, runs/reuse/denied, exact hostile/huge args, paging, polling cache, legacy/partial/retry, report/case/stale races, local manifest, keyboard/mobile, 31 themes passed; only synthetic local GETs.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
