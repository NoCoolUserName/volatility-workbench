// Offline UI check: synthetic draft/sealed transition and accepted update only.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const assets=path.join(__dirname,'../src/volatility_workbench/static');
const version={id:'synthetic-report',status:'draft',created_at:'2026-10-18T12:00:00Z'};
const job={id:'synthetic-job',case_id:'synthetic',report_id:version.id,kind:'report',status:'running',
  started_at:'2026-10-18T12:00:00Z',progress:'Investigating with Codex',
  planned_plugins:['windows.pslist.PsList','windows.netscan.NetScan'],completed_plugins:[]};
const state={cases:[{id:'synthetic',title:'Synthetic case',created_at:'2026-10-18T12:00:00Z',
  images:[],coins:[],readiness:{status:'Ready',reasons:[]},reports:[version],messages:[],activity:[]}],
  jobs:[job],plugin_speed_summary:{},approvals:[],account:{},evidence_root:'/synthetic'};
const report='# Synthetic report\n## Executive summary\nAI Determination: Undetermined\nSynthetic evidence only.';
(async()=>{
  const browser=await chromium.launch({headless:true,...(process.env.WORKBENCH_BROWSER_EXECUTABLE?{executablePath:process.env.WORKBENCH_BROWSER_EXECUTABLE}:{})});
  try{
    const page=await browser.newPage(),calls=[],errors=[];
    let rejectUpdate=false;
    page.on('pageerror',e=>errors.push(e.message));
    await page.route('http://localhost/**',route=>{
      const u=new URL(route.request().url());
      if(u.pathname==='/api/state')return route.fulfill({json:state});
      if(u.pathname==='/api/jobs'){
        calls.push(route.request().postDataJSON());
        return rejectUpdate ? route.fulfill({status:400,json:{error:'Synthetic submission failure'}})
          : route.fulfill({json:{id:'accepted'}});
      }
      if(u.pathname==='/api/file'){
        assert.equal(version.status,'sealed','Draft must never request report.md');
        calls.push('saved-file');
        return route.fulfill({json:{text:report,size:report.length,next_offset:report.length,truncated:false}});
      }
      if(u.pathname==='/api/report-plugins')return route.fulfill({json:{schema:'report-plugin-inventory/1',
        report_id:version.id,scope:'bundled_saved_runs',source_status:'unavailable',summary:{},entries:[],next_offset:null,warnings:[]}});
      if(u.pathname==='/api/artifacts')return route.fulfill({json:{files:[],truncated:false}});
      assert.ok(!u.pathname.startsWith('/api/'),'Unexpected API route '+u.pathname);
      const name=u.pathname==='/'?'index.html':u.pathname.slice(1);
      return route.fulfill({body:fs.readFileSync(path.join(assets,name)),contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html'});
    });
    await page.goto('http://localhost/?case=synthetic');
    await page.getByRole('heading',{name:'Report running…'}).waitFor();
    assert.equal(calls.includes('saved-file'),false);
    assert.equal(await page.locator('#reportView .dos-progress').getAttribute('aria-valuenow'),null,'New plugin remains indeterminate');
    assert.equal(await page.locator('#reportView .dos-progress.indeterminate').count(),1);
    assert.equal(await page.locator('#reportView .dos-progress-fill').evaluate(node=>getComputedStyle(node).backgroundImage.includes('repeating-linear-gradient')),true);
    assert.match(await page.locator('#reportView').innerText(),/Waiting for saved timing history/);
    assert.doesNotMatch(await page.locator('#reportView').innerText(),/No such file|Errno|report\.md/);
    state.plugin_speed_summary={'windows.pslist.PsList':{samples:2,average_seconds:2},
      'windows.netscan.NetScan':{samples:3,average_seconds:6}};
    job.completed_plugins=['windows.pslist.PsList'];
    await page.reload();
    await page.getByRole('heading',{name:'Report running…'}).waitFor();
    assert.equal(Number(await page.locator('#reportView .dos-progress').getAttribute('aria-valuenow')),25);
    assert.match(await page.locator('#reportView').innerText(),/about 6s of typical plugin runtime remaining/);
    if(process.env.WORKBENCH_RUNNING_SCREENSHOT)
      await page.locator('#reportView').screenshot({path:process.env.WORKBENCH_RUNNING_SCREENSHOT});
    version.status='sealed';job.status='completed';
    await page.reload();
    await page.locator('.report-determinations').waitFor();
    assert.equal(calls.filter(item=>item==='saved-file').length,1);
    await page.locator('#focus').fill('Attempt Volatility plugin `windows.netscan.NetScan` on applicable evidence.');
    rejectUpdate=true;
    await page.locator('#update').click();
    await page.getByText('Synthetic submission failure').waitFor();
    assert.match(await page.locator('#focus').inputValue(),/NetScan/,'Failed submission keeps the prompt');
    rejectUpdate=false;
    await page.locator('#update').click();
    await page.waitForFunction(()=>document.querySelector('#focus')?.value==='');
    assert.equal(await page.locator('#focus').inputValue(),'','Accepted Update report clears the submitted prompt');
    assert.equal(calls.filter(item=>item?.kind==='update').length,2);
    assert.deepEqual(errors,[]);
    console.log('Running report: no missing-file request, indeterminate new-plugin timing, weighted known-plugin timing, sealed transition, and accepted-only prompt clearing.');
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
