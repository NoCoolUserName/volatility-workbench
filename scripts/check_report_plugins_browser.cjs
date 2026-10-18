// Offline selected-report inventory check. No case, analyzer or model operations.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const assets=path.join(__dirname,'../src/volatility_workbench/static');
const csp="default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'";
const report=id=>({id,status:'sealed',created_at:'2026-10-18T12:00:00Z'});
const sample=(id,reports,created_at)=>({id,title:id,created_at,images:[{id:'E001',path:'/synthetic/image.raw',size_bytes:12,discovery:{detected_os:'windows'}}],coins:[],readiness:{status:'Unchecked',reasons:[]},reports,messages:[],activity:[]});
const state={cases:[sample('Synthetic A',['legacy','partial','delayed','current'].map(report),'2026-10-18T12:00:00Z'),sample('Synthetic B',[report('other')],'2026-10-17T12:00:00Z')],jobs:[],approvals:[],account:{},evidence_root:'/synthetic'};
const hostile='<img src=x onerror="window.injected=true">';
const entries=Array.from({length:21},(_,i)=>({kind:i===1?'reuse_receipt':i===2?'request_failure':'plugin_run',execution_recorded:i===1||i===2?false:true,
  synthetic:i===3,execution_kind:i===3?'simulated':i===1||i===2?'unknown':'physical',provenance:i===1?'investigation_log':'core_manifest',run_id:'run-'+i,call_id:'call-'+i,image_id:'E001',plugin:i===0?'windows.synthetic.'+hostile:'windows.synthetic.Plugin'+i,
  status:i===0?'failed':i===1?'reused':i===2?'denied':'completed',arguments:i===1?null:['--pid','123',i===0?hostile+'x'.repeat(12000):''],argv:i===1||i===2?null:[['python','-m','vol','--pid','123']],
  started_at:i===4?'2026-10-06 04:22:14Z':'2026-10-18T12:00:00Z',
  finished_at:i===1?null:i===4?'2026-10-06 04:22:15Z':'2026-10-18T12:00:01Z',reuse_count:i===0?2:0,source_path:i===0?'artifacts/C-synthetic/manifest.json':i===2?'../escape.json':null}));
const payload=(id,rows,status='available',next=null)=>({schema:'report-plugin-inventory/1',report_id:id,scope:'bundled_saved_runs',source_status:status,
  summary:status==='unavailable'?{executions:null,plugins:null,failures:null,reuse_receipts:null,request_failures:null}:{executions:18,plugins:20,failures:1,reuse_receipts:1,request_failures:1,unknown_execution_records:1,simulated_runs:1},
  entries:rows,next_offset:next,
  executed_plugin_names:status==='unavailable'?[]:entries.filter(e=>e.kind==='plugin_run'&&e.execution_recorded&&!e.synthetic).map(e=>e.plugin),
  errored_entries:status==='unavailable'?[]:entries.filter(e=>e.kind==='request_failure'||/fail|error|denied/.test(e.status)).map(({plugin,image_id,status,kind,run_id,call_id})=>({plugin,image_id,status,kind,run_id,call_id})),
  warnings:status==='partial'?['Synthetic missing manifest <script>window.injected=true</script>']:[]});
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.WORKBENCH_BROWSER_EXECUTABLE?{executablePath:process.env.WORKBENCH_BROWSER_EXECUTABLE}:{})});
 try{
  const page=await browser.newPage({viewport:{width:1400,height:1000}});
  const calls=[],errors=[],policies=[];let delayedRelease=null,failCurrent=false;
  page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(/Content Security Policy|violates the following/.test(m.text()))policies.push(m.text());});
  await page.route('**/*',async route=>{
   const u=new URL(route.request().url());assert.equal(u.origin,'http://localhost');assert.equal(route.request().method(),'GET','Inventory never starts work');calls.push(u.pathname+u.search);
   if(u.pathname==='/api/state')return route.fulfill({json:state});
   if(u.pathname==='/api/plugins')return route.fulfill({json:{total:4,plugins:[
    {name:'windows.synthetic.Plugin4',source:{kind:'native',label:'Native · Volatility 3',url:'https://github.com/volatilityfoundation/volatility3'},description:'Lists synthetic processes.'},
    {name:'windows.synthetic.NotUsed',target_os:'windows',source:{kind:'third_party',label:'Synthetic source',url:'https://github.com/example/synthetic'},description:'Shows a harmless unused fixture.'},
    {name:'windows.synthetic.NotUsed2',target_os:'windows',description:'Checks another synthetic fixture.'},
    {name:'windows.synthetic.Plugin5',description:'Describes another saved run.'}],import_failures:[]}});
   if(u.pathname==='/api/artifacts')return route.fulfill({json:{files:[],truncated:false}});
   if(u.pathname==='/api/file')return route.fulfill({json:{text:u.searchParams.get('path').endsWith('manifest.json')?'{"synthetic":"manifest only"}':'# Synthetic report\n## Investigative workflow\n<!-- report-plugin-inventory -->\nDuplicate generated inventory text\n<!-- /report-plugin-inventory -->\n## Observation\nHarmless fixture only.',size:128,next_offset:128,truncated:false}});
   if(u.pathname==='/api/report-plugins'){
    const id=u.searchParams.get('report'),offset=Number(u.searchParams.get('offset'));assert.equal(u.searchParams.get('limit'),'20');
    if(id==='delayed')await new Promise(resolve=>{delayedRelease=resolve;});
    if(id==='finished-update'||id==='finished-report')return route.fulfill({json:{...payload(id,[{...entries[4],plugin:'windows.synthetic.NotUsed'}]),
     executed_plugin_names:['windows.synthetic.NotUsed'],errored_entries:[{plugin:'windows.synthetic.NewFailure',status:'error',kind:'plugin_run',run_id:'new-run',call_id:'new-call',error_sources:[{path:'artifacts/C-synthetic/manifest.json',label:'Run manifest'}]}]}});
    if(id==='current'&&failCurrent){failCurrent=false;return route.fulfill({status:500,json:{error:'Synthetic inventory failure'}});}
    return route.fulfill({json:id==='legacy'?payload(id,[],'unavailable'):id==='partial'?payload(id,[entries[0]],'partial'):id==='current'?payload(id,entries.slice(offset,offset+20),'available',offset===0?20:null):payload(id,[{...entries[3],plugin:id+'-plugin'}])});
   }
   assert.ok(!u.pathname.startsWith('/api/'),'Unexpected analysis/action '+u.pathname);
   const name=u.pathname==='/'?'index.html':u.pathname.slice(1);
   return route.fulfill({body:fs.readFileSync(path.join(assets,name)),headers:{'content-security-policy':csp},contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':name.endsWith('.svg')?'image/svg+xml':name.endsWith('.png')?'image/png':'text/html'});
  });
  const inventory=page.locator('#reportPluginInventory'),table=inventory.locator('.report-plugin-used-table tbody');
  const choose=async id=>{await page.locator(`.report-version[data-report-id="${id}"] > button:first-child`).click();};
  await page.goto('http://localhost/');
  await page.waitForFunction(()=>document.querySelector('#reportPluginInventory summary')?.textContent.includes('18 recorded executions'));
  const focus=page.locator('#focus');
  const assertReadableFocus=async()=>assert.ok(await focus.evaluate(node=>{
   const style=getComputedStyle(node);
   return node.clientHeight>=2*parseFloat(style.lineHeight)+parseFloat(style.paddingTop)+parseFloat(style.paddingBottom)-1;
  }),'Investigation focus retains at least two readable lines');
  await assertReadableFocus();
  assert.equal(await focus.getAttribute('rows'),'2');
  assert.ok(await focus.evaluate(node=>node.clientHeight<3*parseFloat(getComputedStyle(node).lineHeight)+parseFloat(getComputedStyle(node).paddingTop)+parseFloat(getComputedStyle(node).paddingBottom)), 'Empty prompt defaults to two lines, not three');
  assert.equal(await inventory.locator('> details.report-plugin-inventory').first().getAttribute('open'),null,'Large inventory starts collapsed');
  assert.equal(await inventory.locator('> details').count(),3,'Used, errored, and unused sections are siblings');
  assert.equal(calls.filter(x=>x==='/api/plugins').length,0,'Collapsed sections do not discover the catalog');
  await inventory.locator('> details').nth(1).locator('> summary').click();
  assert.match(await inventory.locator('.report-plugin-errors-table').innerText(),/failed.*No plugin execution recorded/s);
  await inventory.locator('> details').nth(2).locator('> summary').click();
  await page.waitForFunction(()=>document.querySelector('.report-plugin-unused-table')?.textContent.includes('Shows a harmless unused fixture.'));
  assert.deepEqual(await inventory.locator('.report-plugin-unused-table thead th').allTextContents(),['Plugin name','Add to prompt','Quick Description','Source provenance']);
  assert.match(await inventory.locator('.report-plugin-unused-table').innerText(),/windows\.synthetic\.NotUsed.*Shows a harmless unused fixture/s);
  assert.equal(await inventory.locator('> details').nth(2).getAttribute('open'),'','Catalog response preserves the expanded section');
  assert.doesNotMatch(await inventory.locator('.report-plugin-unused-table').innerText(),/windows\.synthetic\.Plugin4/);
  await focus.fill('Investigate persistence.');
  const add=inventory.locator('.report-plugin-unused-table tbody button');
  assert.equal(await add.count(),2);
  await add.first().click();
  assert.match(await focus.inputValue(),/^Investigate persistence\.\nAttempt Volatility plugin `windows\.synthetic\.NotUsed`/);
  await add.first().click();
  assert.equal((await focus.inputValue()).split('windows.synthetic.NotUsed`').length-1,1,'A repeated click does not duplicate the request');
  await add.nth(1).click();
  assert.match(await focus.inputValue(),/windows\.synthetic\.NotUsed2`/);
  assert.ok(await focus.evaluate(node=>node.clientHeight>=node.scrollHeight-2),'Short multi-plugin drafts are fully visible');
  assert.equal(calls.filter(x=>x.startsWith('/api/jobs')).length,0,'Adding to the prompt never submits work');
  assert.equal(await page.locator('#update').evaluate(n=>n.nextElementSibling.id),'report');
  assert.equal(await page.locator('#update').getAttribute('class'),'primary');
  assert.equal(await page.locator('#report').getAttribute('class'),'');
  const bulk=page.getByRole('button',{name:'Add all OS-relevant to prompt',exact:true});
  await bulk.click();
  const bulkDraft=await focus.inputValue();
  assert.match(bulkDraft,/E001 \(windows\): `windows.synthetic.NotUsed`, `windows.synthetic.NotUsed2`/);
  assert.match(bulkDraft,/Check each image's saved OS, build, architecture, symbols/);
  assert.equal(await bulk.isDisabled(),true);
  await focus.fill('Investigate persistence.');assert.equal(await bulk.isEnabled(),true);
  await focus.fill(bulkDraft);assert.equal(await bulk.isDisabled(),true);
  // OS must come from saved image discovery, including mixed-image cases.
  const osChecks=await page.evaluate(()=>{
    const c=caseNow(),oldImages=c.images,oldCatalog=reportPluginCatalog;
    const record=reportPluginCache.get(reportPluginKey);
    reportPluginCatalog={plugins:[{name:'windows.Test',target_os:'windows'},{name:'mac.Test',target_os:'mac'},
      {name:'linux.Test',target_os:'linux'},{name:'unknown.Test',target_os:'other'},
      {name:'windowsMisleading.Test',target_os:'mac'}]};
    c.images=[{id:'E002',discovery:{detected_os:'macos'}},{id:'E003',discovery:{detected_os:'linux'}},{id:'E004',discovery:{detected_os:'unknown'}}];
    const mixed=bulkPluginRequest(record);
    c.images=[{id:'E001',discovery:{detected_os:'mixed'}}];
    const unknown=bulkPluginRequest(record);
    c.images=oldImages;reportPluginCatalog=oldCatalog;
    return {mixed,unknown};
  });
  assert.match(osChecks.mixed.text,/E002 \(macOS\): `mac.Test`, `windowsMisleading.Test`/);
  assert.match(osChecks.mixed.text,/E003 \(linux\): `linux.Test`/);
  assert.doesNotMatch(osChecks.mixed.text,/`windows.Test`|unknown.Test|E004/);
  assert.match(osChecks.mixed.note,/1 image\(s\) have unresolved/);
  assert.equal(osChecks.unknown.text,'');
  assert.equal(calls.filter(x=>x.startsWith('/api/jobs')).length,0);

  if(process.env.WORKBENCH_REPORT_PLUGIN_UNUSED_SCREENSHOT)await page.screenshot({path:process.env.WORKBENCH_REPORT_PLUGIN_UNUSED_SCREENSHOT,fullPage:true});
  await inventory.locator('> details').nth(1).locator('> summary').click();
  await inventory.locator('> details').nth(2).locator('> summary').click();
  await inventory.locator('> details > summary').first().focus();await page.keyboard.press('Space');
  assert.equal(await inventory.locator('> details').first().getAttribute('open'),'');
  assert.equal(await table.locator('tr').count(),20);
  assert.doesNotMatch(await page.locator('#reportView').innerText(),/Duplicate generated inventory text/);
  assert.match(await table.locator('tr').nth(3).innerText(),/Simulated execution record/);
  assert.match(await inventory.innerText(),/earlier saved executions and reuse receipts/);
  assert.match(await inventory.innerText(),/1 execution failures · 1 reuse receipts · 1 request failures/);
  assert.match(await inventory.innerText(),/1 records with unknown execution provenance/);
  assert.match(await inventory.innerText(),/1 explicitly simulated run records/);
  assert.match(await table.locator('tr').nth(1).innerText(),/Saved result reuse.*No execution recorded/s);
  assert.match(await table.locator('tr').nth(2).innerText(),/Failed or denied request.*No execution recorded/s);
  assert.deepEqual(await inventory.locator('.report-plugin-used-table thead th').allTextContents(),
    ['Plugin','Image','Quick Description','Outcome & record kind','Exact arguments','Run provenance & recorded time','Local source','Source provenance']);
  assert.match(await table.locator('tr').nth(4).locator('td').nth(2).innerText(),/Lists synthetic processes/);
  const provenance=table.locator('tr').nth(4).locator('td').nth(5);
  assert.match(await provenance.innerText(),/Run: run-4.*Speed: 1 second.*Source: core_manifest/s);
  assert.doesNotMatch(await provenance.innerText(),/Call:|Started:|Finished:/);
  await provenance.locator('summary').click();
  assert.match(await provenance.innerText(),/Call: call-4.*Started:.*Finished:/s);
  assert.match(await table.locator('tr').nth(1).locator('td').nth(5).innerText(),/Speed: No plugin execution recorded/);
  assert.deepEqual(await page.evaluate(()=>[
    pluginSpeed({kind:'plugin_run',execution_recorded:true,started_at:'20261004T025558.800719Z',finished_at:'20261004T025559.800719Z'}),
    pluginSpeed({kind:'plugin_run',execution_recorded:true,started_at:'2026-10-06 23:59:14Z',finished_at:'2026-10-07 00:00:15Z'}),
    pluginSpeed({kind:'plugin_run',execution_recorded:true,started_at:'2026-10-06 23:59:59+0000',finished_at:'2026-10-07 00:00:01+00:00'}),
    pluginSpeed({kind:'plugin_run',execution_recorded:true,started_at:'2026-10-06 04:22:14.250Z',finished_at:'2026-10-06 04:22:14.750Z'}),
    pluginSpeed({kind:'plugin_run',execution_recorded:true,started_at:'20261006T042214.000000Z',finished_at:'2026-10-06 04:22:15Z'}),
    pluginSpeed({kind:'plugin_run',execution_recorded:true,started_at:'2026-10-06 04:22:14',finished_at:'2026-10-06 04:22:15'}),
    pluginSpeed({kind:'plugin_run',execution_recorded:true,started_at:'bad',finished_at:'2026-10-18T12:00:01Z'}),
    pluginSpeed({kind:'plugin_run',execution_recorded:true,started_at:'2026-10-18T12:00:02Z',finished_at:'2026-10-18T12:00:01Z'})
  ]),['1 second','1 minute 1 second','2 seconds','0.5 seconds','1 second','Not recorded','Not recorded','Not recorded']);
  for(const tableName of ['used','errors','unused']){
    assert.equal(await inventory.locator(`.report-plugin-${tableName}-table th`).last().textContent(),'Source provenance');
  }
  assert.equal(await table.locator('tr').nth(4).locator('td').last().getByRole('link',{name:'Plugin documentation'}).getAttribute('href'),
    'https://volatility3.readthedocs.io/en/latest/volatility3.plugins.windows.synthetic.html');
  const sourceLink=inventory.locator('.report-plugin-unused-table tbody tr').first().locator('td').last().locator('a');
  assert.equal(await sourceLink.getAttribute('href'),'https://github.com/example/synthetic#readme');
  assert.equal(await sourceLink.getAttribute('rel'),'noopener noreferrer');
  assert.equal(await sourceLink.getAttribute('target'),'_blank');
  assert.deepEqual(await page.evaluate(()=>{
    const saved=reportPluginCatalog;
    reportPluginCatalog={plugins:[{name:'unsafe',source:{url:'javascript:alert(1)',label:'Unknown'}},
      {name:'credentials',source:{url:'https://user:secret@example.com',label:'Unknown'}}]};
    const counts=['unsafe','credentials','missing'].map(name=>reportPluginSource(name).querySelectorAll('a').length);
    reportPluginCatalog=saved;return counts;
  }),[0,0,0]);
  assert.equal(await inventory.locator('img,script').count(),0);assert.equal(await page.evaluate(()=>window.injected),undefined);
  assert.equal(await inventory.getByRole('link',{name:'Open manifest'}).count(),1,'Traversal path never becomes link');
  await table.locator('tr').first().locator('td').nth(4).locator('summary').first().click();
  assert.equal(await table.locator('tr').first().locator('pre').first().textContent(),JSON.stringify(entries[0].arguments,null,2));
  const before=calls.filter(x=>x.startsWith('/api/report-plugins')).length;
  await page.waitForTimeout(1700);
  assert.equal(calls.filter(x=>x.startsWith('/api/report-plugins')).length,before,'Polling must not fetch inventory again');
  assert.equal(await table.locator('tr').first().locator('td').nth(4).locator('details').first().getAttribute('open'),'','Polling preserves expanded exact args');
  await inventory.getByRole('button',{name:'More plugin records'}).click();
  await page.waitForFunction(()=>document.querySelectorAll('#reportPluginInventory .report-plugin-used-table tbody tr').length===21);
  assert.equal(await inventory.getByRole('button',{name:'More plugin records'}).count(),0);
  assert.match(await page.evaluate(()=>document.activeElement.textContent),/All saved plugin records loaded/);
  await choose('legacy');
  await page.waitForFunction(()=>document.querySelector('#reportPluginInventory summary')?.textContent.includes('Inventory unavailable'));
  await inventory.locator('> details > summary').first().click();
  assert.match(await inventory.innerText(),/does not mean no plugins ran/);assert.equal(await inventory.locator('table').count(),0);
  assert.doesNotMatch(await inventory.innerText(),/0 recorded executions/);
  await choose('partial');await page.waitForFunction(()=>document.querySelector('#reportPluginInventory .inventory-warning')?.textContent.includes('Partial'));
  await inventory.locator('> details > summary').first().click();assert.match(await inventory.innerText(),/Synthetic missing manifest <script>/);assert.equal(await inventory.locator('script').count(),0);
  await choose('delayed');await page.waitForFunction(()=>document.querySelector('#reportPluginInventory summary')?.textContent.includes('Loading'));
  await choose('current');assert.equal(await table.locator('tr').count(),21,'Returning to cached report preserves pagination');
  assert.ok(delayedRelease);delayedRelease();await page.waitForTimeout(100);
  assert.doesNotMatch(await inventory.innerText(),/delayed-plugin/,'Stale reply never replaces current report');
  await page.getByRole('button',{name:'Synthetic B',exact:true}).click();
  assert.equal(await focus.inputValue(),'','Focus drafts stay with their case');
  await assertReadableFocus();
  await page.waitForFunction(()=>document.querySelector('#reportPluginInventory tbody')?.textContent.includes('other-plugin'));
  await page.getByRole('button',{name:'Synthetic A',exact:true}).click();assert.equal(await table.locator('tr').count(),21);
  assert.match(await focus.inputValue(),/Investigate persistence.*NotUsed2`/s);
  await assertReadableFocus();
  assert.equal(await page.locator('.report-version.selected').getAttribute('data-report-id'),'current');
  failCurrent=true;await inventory.getByRole('button',{name:'Refresh saved inventory'}).click();
  await page.waitForFunction(()=>document.querySelector('#reportPluginInventory [role=alert]'));
  assert.match(await inventory.innerText(),/Synthetic inventory failure/);assert.equal(await table.locator('tr').count(),21,'Failed refresh retains last good snapshot');
  await inventory.getByRole('button',{name:'Retry plugin inventory'}).click();
  await page.waitForFunction(()=>document.querySelectorAll('#reportPluginInventory .report-plugin-used-table tbody tr').length===20);
  assert.equal(await inventory.locator('[role=alert]').count(),0);
  for(const id of await page.evaluate(()=>window.WorkbenchThemes.catalog.map(t=>t.id))){
   await page.locator('#theme').selectOption(id);assert.equal(await table.locator('tr').count(),20);assert.equal(await page.locator('.report-version.selected').getAttribute('data-report-id'),'current');
   await assertReadableFocus();
   const ratio=await table.evaluate(node=>{const c=getComputedStyle(node),parse=s=>s.match(/[\d.]+/g).slice(0,3).map(Number).map(n=>{n/=255;return n<=.04045?n/12.92:((n+.055)/1.055)**2.4;}),lum=a=>a[0]*.2126+a[1]*.7152+a[2]*.0722;const text=lum(parse(c.color)),bg=lum(parse(getComputedStyle(node.closest('.report-plugin-inventory')).backgroundColor));return(text+.05)/(bg+.05);});
   assert.ok(ratio>=4.5,id+' table text contrast');
  }
  if(process.env.WORKBENCH_REPORT_PLUGIN_SCREENSHOT)await page.screenshot({path:process.env.WORKBENCH_REPORT_PLUGIN_SCREENSHOT,fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await assertReadableFocus();
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Only table region scrolls on mobile');
  const region=inventory.getByRole('region');await region.focus();assert.equal(await region.evaluate(e=>getComputedStyle(e).outlineStyle),'solid');
  assert.ok(await region.evaluate(e=>e.scrollWidth>e.clientWidth));
  await page.setViewportSize({width:1400,height:1000});
  await inventory.getByRole('link',{name:'Open manifest'}).click();
  await page.waitForFunction(()=>document.querySelector('#artifactView').textContent.includes('manifest only'));
  assert.ok(calls.some(x=>x.startsWith('/api/file?')&&decodeURIComponent(x).includes('reports/current/artifacts/C-synthetic/manifest.json')));
  await page.locator('[data-tab="reports"]').click();
  // Complete each job type while an older revision is selected. All three lists
  // must follow the new snapshot, even if its draft inventory was already cached.
  for(const kind of ['update','report']){
   const id='finished-'+kind;
   state.cases[0].reports.push({id,status:'draft',created_at:'2026-10-18T13:00:00Z'});
   state.jobs.push({id:'job-'+kind,kind,case_id:'Synthetic A',report_id:id,status:'running',started_at:'2026-10-18T13:00:00Z'});
   await page.evaluate(()=>refresh());await choose(id);
   await page.waitForFunction(id=>reportPluginCache.get(reportPluginKey)?.data?.report_id===id,id);
   await choose('current');
   state.cases[0].reports.at(-1).status='sealed';state.jobs.at(-1).status='completed';
   await page.evaluate(()=>refresh());
   await page.waitForFunction(id=>document.querySelector('.report-version.selected')?.dataset.reportId===id,id);
   await inventory.locator('> details').first().locator('> summary').click();
   await page.waitForFunction(()=>document.querySelector('.report-plugin-used-table')?.textContent.includes('windows.synthetic.NotUsed'));
   await inventory.locator('> details').nth(1).locator('> summary').click();
   assert.match(await inventory.locator('.report-plugin-errors-table').innerText(),/windows.synthetic.NewFailure/);
   await inventory.locator('> details').nth(2).locator('> summary').click();
   assert.doesNotMatch(await inventory.locator('.report-plugin-unused-table').innerText(),/windows.synthetic.NotUsed\s/);
   assert.match(await inventory.locator('.report-plugin-unused-table').innerText(),/windows.synthetic.NotUsed2/);
  }
  state.cases[0].reports=[];await page.evaluate(()=>refresh());
  assert.equal(await page.locator('#report').evaluate(n=>n.nextElementSibling.id),'update');
  assert.equal(await page.locator('#report').getAttribute('class'),'primary');
  assert.equal(await page.locator('#update').isDisabled(),true);
  assert.deepEqual(errors,[]);assert.deepEqual(policies,[]);assert.equal(await page.evaluate(()=>window.injected),undefined);
  console.log('Report plugins browser: counts/scope, errors/unused, descriptions/timing/details, OS-matched bulk prompts/disabled state, primary action order, completion refresh, add-to-prompt without submission, case drafts, paging, races, local manifest, keyboard/mobile, 31 themes passed; only synthetic local GETs.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
