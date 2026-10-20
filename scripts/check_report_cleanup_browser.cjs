// Offline UI workflow; filesystem deletion is exercised in test_report_cleanup.py.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const assets=path.join(__dirname,'../src/volatility_workbench/static');
const reports=[['draft-one','incomplete'],['draft-two','incomplete'],['sealed','sealed']].map(([id,status],index)=>
  ({id,status,created_at:`2026-10-1${index+1}T12:00:00Z`}));
reports[2].previous=reports[0].id;
const state={cases:[{id:'synthetic-case',title:'Synthetic case',created_at:'2026-10-18T00:00:00Z',images:[],coins:[],
  readiness:{status:'Unchecked',reasons:[]},reports,messages:[],activity:[]}],jobs:[],approvals:[],account:{},evidence_root:'/synthetic'};
(async()=>{
  const browser=await chromium.launch({headless:true,...(process.env.WORKBENCH_BROWSER_EXECUTABLE?{executablePath:process.env.WORKBENCH_BROWSER_EXECUTABLE}:{})});
  try{
    const page=await browser.newPage({viewport:{width:1400,height:1000}});
    const errors=[],calls=[],actions=[];
    let failDelete=false;
    page.on('pageerror',e=>errors.push(e.message));
    await page.route('http://localhost/**',route=>{
      if (new URL(route.request().url()).pathname === '/api/settings/zoom') return route.fulfill({json:{schema:'zoom/1',percent:100}});
      const u=new URL(route.request().url());
      if(u.pathname.startsWith('/api/')){
        calls.push(u.pathname);
        if(u.pathname==='/api/state')return route.fulfill({json:state});
        if(u.pathname==='/api/artifacts')return route.fulfill({json:{files:[],truncated:false}});
        if(u.pathname==='/api/report-plugins')return route.fulfill({json:{schema:'report-plugin-inventory/1',report_id:u.searchParams.get('report'),scope:'bundled_saved_runs',source_status:'unavailable',summary:{executions:null,plugins:null,failures:null,reuse_receipts:null,request_failures:null},entries:[],next_offset:null,warnings:['Inventory metadata is absent from this synthetic presentation fixture.']}});
        if(u.pathname==='/api/file')return route.fulfill({json:{text:'# Synthetic '+u.searchParams.get('path').split('/')[1],truncated:false}});
        if(u.pathname==='/api/reports/remove'){
          const request=route.request().postDataJSON();
          actions.push(request);assert.equal(request.case_id,'synthetic-case');
          const report=reports.find(r=>r.id===request.report_id);
          assert.ok(['incomplete','sealed'].includes(report.status));
          if(failDelete && request.action==='delete')return route.fulfill({status:400,json:{error:'Synthetic permission failure; report retained'}});
          report.hidden=true;
          if(request.action==='delete')report.deleted_at='2026-10-18T12:00:00Z';
          return route.fulfill({json:{action:request.action,report_id:report.id}});
        }
        throw Error('Unexpected action: '+u.pathname);
      }
      const name=u.pathname==='/'?'index.html':u.pathname.slice(1);
      return route.fulfill({body:fs.readFileSync(path.join(assets,name)),contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html'});
    });
    await page.goto('http://localhost/');
    await page.waitForFunction(()=>document.querySelectorAll('.report-version').length===3);
    assert.equal(await page.locator('.report-remove').count(),3);
    const sealed=page.locator('.report-version').first();
    await page.waitForFunction(()=>document.querySelector('#reportView').textContent.includes('Synthetic sealed'));
    assert.equal(await sealed.getAttribute('class'),'report-version removable selected');
    assert.equal(await sealed.locator('button').first().getAttribute('aria-current'),'true');
    assert.equal(await sealed.locator('button').first().evaluate(e=>getComputedStyle(e).borderTopColor===getComputedStyle(e).color),true);
    await sealed.hover();await sealed.locator('.report-remove').click();
    assert.equal(await page.locator('#reportRemovalTitle').innerText(),'Remove sealed report?');
    await page.keyboard.press('Escape');
    const draft=page.locator('.report-version').nth(1);
    const remove=draft.locator('.report-remove');
    assert.equal(await remove.evaluate(e=>getComputedStyle(e).opacity),'0');
    await draft.hover();
    assert.equal(await remove.evaluate(e=>getComputedStyle(e).opacity),'1');
    await page.waitForTimeout(1650); // Polling must preserve the hovered card.
    await remove.click();
    const dialog=page.locator('#reportRemoval');
    assert.equal(await dialog.isVisible(),true);
    assert.equal(await dialog.getByRole('button',{name:'Delete to Recycle Bin',exact:true}).count(),1);
    assert.equal(await dialog.getByRole('button',{name:'Hide from UI',exact:true}).evaluate(e=>e===document.activeElement),true);
    await page.keyboard.press('Escape');
    assert.equal(actions.length,0,'Dismissing options must not remove anything');
    await draft.locator('button').first().click();
    await page.waitForFunction(()=>document.querySelector('#reportView').textContent.includes('Synthetic draft-two'));
    assert.equal(await draft.locator('button').first().getAttribute('aria-current'),'true');
    assert.equal(await sealed.locator('button').first().getAttribute('aria-current'),null);
    await page.waitForTimeout(1650); // Background state refresh keeps the selected revision.
    assert.equal(await draft.locator('button').first().getAttribute('aria-current'),'true');
    await remove.focus();
    assert.equal(await remove.evaluate(e=>getComputedStyle(e).opacity),'1','Keyboard focus reveals removal control');
    await page.keyboard.press('Enter');
    if(process.env.WORKBENCH_BROWSER_SCREENSHOT)await page.screenshot({path:process.env.WORKBENCH_BROWSER_SCREENSHOT,fullPage:true});
    await dialog.getByRole('button',{name:'Hide from UI',exact:true}).click();
    await page.waitForFunction(()=>document.querySelectorAll('.report-version').length===2 && document.querySelector('#reportView').textContent.includes('Synthetic sealed'));
    assert.equal(await page.locator('.report-version.selected').count(),1);
    assert.equal(await page.locator('.report-version.selected').locator('button').first().getAttribute('aria-current'),'true');
    assert.equal(reports[1].hidden,true);assert.equal(reports[1].deleted_at,undefined);
    await page.reload();
    await page.waitForFunction(()=>document.querySelectorAll('.report-version').length===2);
    const older=page.locator('.report-version').last();
    await older.hover();await older.locator('.report-remove').click();
    assert.equal(await dialog.getByRole('button',{name:'Delete to Recycle Bin'}).isEnabled(),true,
      'A complete successor does not block recycling its predecessor');
    failDelete=true;
    await dialog.getByRole('button',{name:'Delete to Recycle Bin',exact:true}).click();
    await page.waitForFunction(()=>document.querySelector('#reportRemoval [role=alert]').textContent.includes('permission failure'));
    assert.equal(await dialog.isVisible(),true);assert.equal(await page.locator('.report-version').count(),2);
    failDelete=false;
    await dialog.getByRole('button',{name:'Delete to Recycle Bin',exact:true}).click();
    await page.waitForFunction(()=>document.querySelectorAll('.report-version').length===1);
    assert.ok(reports[0].deleted_at);
    assert.equal(await page.locator('.report-remove').count(),1);
    assert.match(await page.locator('#reportView').innerText(),/Synthetic sealed/);
    await page.reload();
    await page.waitForFunction(()=>document.querySelectorAll('.report-version').length===1);
    reports.push({id:'new-sealed',status:'sealed',created_at:'2026-10-18T12:03:00Z'});
    await page.waitForFunction(()=>document.querySelector('#reportView').textContent.includes('Synthetic new-sealed'));
    await page.locator('.report-version').first().hover();
    await page.locator('.report-version').first().locator('.report-remove').click();
    await dialog.getByRole('button',{name:'Hide from UI',exact:true}).click();
    await page.waitForFunction(()=>document.querySelectorAll('.report-version').length===1 && document.querySelector('#reportView').textContent.includes('Synthetic sealed'));
    await page.reload();await page.waitForFunction(()=>document.querySelectorAll('.report-version').length===1);
    await page.locator('.report-version').first().hover();
    await page.locator('.report-version').first().locator('.report-remove').click();
    await dialog.getByRole('button',{name:'Delete to Recycle Bin',exact:true}).click();
    await page.waitForFunction(()=>document.querySelectorAll('.report-version').length===0);
    assert.ok(reports.find(r=>r.id==='sealed').deleted_at);
    assert.deepEqual(actions.map(a=>a.action),['hide','delete','delete','hide','delete']);
    assert.deepEqual(errors,[]);assert.ok(!calls.some(p=>/^\/api\/(jobs|stop|plugins)$/.test(p)));
    console.log('Report removal browser: selected revision on load/click/refresh/fallback, incomplete/sealed controls, hide/delete/retry; zero analysis requests.');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
