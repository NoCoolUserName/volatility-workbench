// Offline UI check: pre-draft progress above a long sealed report, then draft/sealed transitions.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const assets=path.join(__dirname,'../src/volatility_workbench/static');
const sealed={id:'saved-report',status:'sealed',created_at:'2026-10-17T12:00:00Z'};
const version={id:'synthetic-report',status:'draft',created_at:'2026-10-18T12:00:00Z'};
const job={id:'synthetic-job',case_id:'synthetic',report_id:null,kind:'update',status:'running',
  text:'Original synthetic investigation focus',
  started_at:'2026-10-18T12:00:00Z',progress:'Starting',
  planned_plugins:['windows.pslist.PsList','windows.netscan.NetScan'],completed_plugins:[]};
const state={cases:[{id:'synthetic',title:'Synthetic case',created_at:'2026-10-18T12:00:00Z',
  images:[],coins:[],readiness:{status:'Ready',reasons:[]},reports:[sealed],messages:[],activity:[]}],
  jobs:[job],plugin_speed_summary:{},approvals:[],account:{},evidence_root:'/synthetic'};
const report='# Synthetic report\n## Executive summary\nAI Determination: Undetermined\nSynthetic evidence only.\n'+Array.from({length:90},(_,i)=>'\nSaved synthetic paragraph '+i+'. '+ 'Synthetic saved detail. '.repeat(12)).join('');
(async()=>{
  const browser=await chromium.launch({headless:true,...(process.env.WORKBENCH_BROWSER_EXECUTABLE?{executablePath:process.env.WORKBENCH_BROWSER_EXECUTABLE}:{})});
  try{
    const page=await browser.newPage({viewport:{width:1400,height:1000}}),calls=[],errors=[];
    let rejectUpdate=false, holdSubmission=false, releaseSubmission;
    page.on('pageerror',e=>errors.push(e.message));
    await page.route('http://localhost/**',async route=>{
      const u=new URL(route.request().url());
      if(u.pathname==='/api/state')return route.fulfill({json:state});
      if(u.pathname==='/api/jobs'){
        calls.push(route.request().postDataJSON());
        if(holdSubmission)await new Promise(resolve=>releaseSubmission=resolve);
        return rejectUpdate ? route.fulfill({status:400,json:{error:'Synthetic submission failure'}})
          : route.fulfill({json:{id:'accepted'}});
      }
      if(u.pathname==='/api/file'){
        assert.ok(u.searchParams.get('path').includes(sealed.id)||version.status==='sealed','Draft must never request report.md');
        calls.push('saved-file');
        return route.fulfill({json:{text:report,size:report.length,next_offset:report.length,truncated:false}});
      }
      if(u.pathname==='/api/report-plugins')return route.fulfill({json:{schema:'report-plugin-inventory/1',
        report_id:u.searchParams.get('report'),scope:'bundled_saved_runs',source_status:'unavailable',summary:{},entries:[],next_offset:null,warnings:[]}});
      if(u.pathname==='/api/artifacts')return route.fulfill({json:{files:[],truncated:false}});
      assert.ok(!u.pathname.startsWith('/api/'),'Unexpected API route '+u.pathname);
      const name=u.pathname==='/'?'index.html':u.pathname.slice(1);
      return route.fulfill({body:fs.readFileSync(path.join(assets,name)),contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html'});
    });
    await page.goto('http://localhost/?case=synthetic');
    await page.locator('.report-determinations').waitFor();
    const active=page.locator('#activeReportProgress');
    await active.getByRole('progressbar').waitFor();
    assert.match(await active.innerText(),/Starting/,'Starting update shows progress before any draft exists');
    assert.equal(await page.locator('#queueSection').evaluate(node=>node.parentElement===document.querySelector('#case').parentElement&&!!(node.compareDocumentPosition(document.querySelector('#case'))&Node.DOCUMENT_POSITION_FOLLOWING)),true,'Current work precedes the entire case and its long report');
    assert.equal(await active.getByRole('progressbar').evaluate(node=>{const box=node.getBoundingClientRect();return box.top>=0&&box.bottom<=innerHeight;}),true,'Progress appears in the initial viewport');
    assert.match(await page.locator('#reportView').innerText(),/Saved synthetic paragraph 89/,'Existing sealed report remains fully accessible while the update starts');
    assert.equal(await page.getByRole('progressbar').count(),1,'One progress indicator for the active update');
    assert.equal(calls.filter(item=>item==='saved-file').length,1);
    await page.locator('#focus').fill('Unsubmitted synthetic focus');
    await page.locator('#focus').focus();
    await active.getByRole('progressbar').evaluate(node=>window.syntheticProgressNode=node);
    await page.evaluate(()=>refresh());
    assert.equal(await active.getByRole('progressbar').evaluate(node=>node===window.syntheticProgressNode),true,'Polling preserves the running animation node');
    assert.equal(await page.locator('#focus').evaluate(node=>node===document.activeElement),true,'Progress polling preserves input focus');
    assert.equal(await page.locator('#focus').inputValue(),'Unsubmitted synthetic focus');
    job.report_id=version.id;job.progress='Investigating with Codex';
    state.cases[0].reports.push(version);
    await page.reload();
    await page.locator('#reportView').getByRole('heading',{name:'Report running…'}).waitFor();
    assert.equal(calls.filter(item=>item==='saved-file').length,1,'Draft must not request a missing report.md');
    assert.equal(await active.getByRole('progressbar').getAttribute('aria-valuenow'),null,'New plugin remains indeterminate');
    assert.equal(await active.locator('.dos-progress.indeterminate').count(),1);
    assert.equal(await active.locator('.dos-progress-fill').evaluate(node=>getComputedStyle(node).backgroundImage.includes('repeating-linear-gradient')),true);
    assert.match(await active.innerText(),/Waiting for saved timing history/);
    assert.equal(await page.getByRole('progressbar').count(),1,'Draft transition does not duplicate the active progress bar');
    assert.doesNotMatch(await page.locator('#reportView').innerText(),/No such file|Errno|report\.md/);
    state.plugin_speed_summary={'windows.pslist.PsList':{samples:2,average_seconds:2},
      'windows.netscan.NetScan':{samples:3,average_seconds:6}};
    job.completed_plugins=['windows.pslist.PsList'];
    await page.reload();
    await page.locator('#reportView').getByRole('heading',{name:'Report running…'}).waitFor();
    assert.equal(Number(await active.getByRole('progressbar').getAttribute('aria-valuenow')),25);
    assert.match(await active.innerText(),/about 6s of typical plugin runtime remaining/);
    if(process.env.WORKBENCH_RUNNING_SCREENSHOT)
      await page.locator('#queueSection').screenshot({path:process.env.WORKBENCH_RUNNING_SCREENSHOT});
    version.status='sealed';job.status='completed';
    await page.reload();
    await page.locator('.report-determinations').waitFor();
    assert.equal(calls.filter(item=>item==='saved-file').length,2);
    assert.equal(await active.isHidden(),true,'Completed report hides active progress');
    assert.equal(await page.getByRole('progressbar').count(),0);
    job.kind='report';job.status='stopping';job.report_id=null;job.planned_plugins=[];
    await page.evaluate(()=>refresh());
    await active.getByRole('heading',{name:'Stopping report…'}).waitFor();
    assert.equal(await active.getByRole('progressbar').isVisible(),true,'Initial-generation stop state still exposes progress without a draft');
    assert.match(await active.innerText(),/plugin plan is adaptive/,'Unknown initial plan has an honest indeterminate estimate');
    job.kind='readiness';job.status='running';
    await page.evaluate(()=>refresh());
    assert.equal(await page.locator('#queueSection').isVisible(),true);
    assert.equal(await active.isHidden(),true,'Readiness does not show fake report progress');
    assert.equal(await page.getByRole('progressbar').count(),0);
    job.status='completed';await page.evaluate(()=>refresh());
    assert.equal(await page.locator('#queueSection').isHidden(),true,'Idle work panel hides');
    job.kind='update';job.status='failed';job.report_id=null;job.error='Synthetic transport failure before a draft was created.';
    state.cases[0].activity.push({time:'2026-10-18T12:01:00Z',kind:'job_failed',detail:{error:job.error}});
    await page.evaluate(()=>refresh());
    await page.locator('#reportJobFailure').waitFor();
    assert.match(await page.locator('#reportJobFailure').innerText(),/Synthetic transport failure/,'Pre-draft failure is visible above the saved report');
    assert.equal(await page.locator('#reportJobFailure').evaluate(node=>!!(node.compareDocumentPosition(document.querySelector('#case'))&Node.DOCUMENT_POSITION_FOLLOWING)),true);
    assert.match(await page.locator('#reportView').innerText(),/Saved synthetic paragraph 89/,'Failure preserves the readable sealed report');
    assert.equal(await page.getByRole('progressbar').count(),0,'Failed work must not keep animating');
    assert.equal(await page.locator('#liveConsoleSection').isHidden(),true);
    const rerun=page.locator('#reportJobFailure').getByRole('button',{name:'Rerun',exact:true});
    await page.locator('#focus').fill('Keep this newer unsubmitted prompt');
    rejectUpdate=true;
    await rerun.click();
    await page.getByText('Synthetic submission failure').waitFor();
    await page.waitForFunction(()=>!document.querySelector('#reportJobFailure button[title]')?.disabled);
    assert.equal(await page.locator('#focus').inputValue(),'Keep this newer unsubmitted prompt','Rejected rerun preserves newer prompt');
    rejectUpdate=false;holdSubmission=true;
    const beforeRerun=calls.filter(item=>item?.kind==='update').length;
    await rerun.click();
    await page.waitForFunction(()=>document.querySelector('#reportJobFailure button[title]')?.disabled);
    await page.evaluate(()=>refresh());
    assert.equal(await rerun.isDisabled(),true,'Polling cannot re-enable an in-flight retry');
    await rerun.evaluate(button=>button.click());
    assert.equal(calls.filter(item=>item?.kind==='update').length,beforeRerun+1,'Repeated activation submits once');
    holdSubmission=false;releaseSubmission();
    await page.waitForFunction(()=>!document.querySelector('#reportJobFailure button[title]')?.disabled);
    const retried=calls.filter(item=>item?.kind==='update').at(-1);
    assert.equal(retried.case_id,'synthetic');assert.equal(retried.text,job.text,'Rerun reuses saved focus instead of newer prompt');
    assert.ok(retried.request_id);assert.notEqual(retried.request_id,calls.filter(item=>item?.kind==='update').at(-2).request_id);
    assert.equal(await page.locator('#focus').inputValue(),'Keep this newer unsubmitted prompt','Accepted rerun preserves newer prompt');
    state.jobs.push({id:'other-work',case_id:'synthetic',kind:'question',status:'queued'});
    await page.evaluate(()=>refresh());assert.equal(await rerun.isDisabled(),true,'Queued case work blocks duplicate reruns');
    state.jobs.pop();state.cases[0].readiness.status='Blocked';
    await page.evaluate(()=>refresh());assert.equal(await rerun.isDisabled(),true,'Readiness must permit rerun');
    state.cases[0].readiness.status='Ready';state.report_cleanup_cases=['synthetic'];
    await page.evaluate(()=>refresh());assert.equal(await rerun.isDisabled(),true,'Cleanup blocks rerun');
    state.report_cleanup_cases=[];job.kind='report';job.text='';
    await page.evaluate(()=>refresh());await rerun.click();
    await page.waitForFunction(()=>!document.querySelector('#reportJobFailure button[title]')?.disabled);
    assert.equal(calls.filter(item=>item?.kind==='report').at(-1).text,'','Initial generation reruns retain kind and blank focus');
    job.kind='update';await page.evaluate(()=>refresh());
    await page.locator('#reportJobFailure').getByRole('button',{name:/Activity/}).click();
    assert.equal(await page.locator('#activity').isVisible(),true,'Failure provides a route to saved job details');
    assert.match(await page.locator('#activityList').innerText(),/job_failed/);
    await page.locator('[data-tab=reports]').click();
    job.status='running';job.progress='Retrying synthetic update';delete job.error;
    await page.evaluate(()=>refresh());
    assert.equal(await page.locator('#reportJobFailure').isHidden(),true,'A current retry replaces the prior failure with active progress');
    assert.equal(await active.getByRole('progressbar').isVisible(),true);
    job.status='completed';await page.evaluate(()=>refresh());
    const updatesBefore=calls.filter(item=>item?.kind==='update').length;
    await page.locator('#focus').fill('Attempt Volatility plugin `windows.netscan.NetScan` on applicable evidence.');
    rejectUpdate=true;
    await page.locator('#update').click();
    await page.getByText('Synthetic submission failure').waitFor();
    assert.match(await page.locator('#focus').inputValue(),/NetScan/,'Failed submission keeps the prompt');
    rejectUpdate=false;
    await page.locator('#update').click();
    await page.waitForFunction(()=>document.querySelector('#focus')?.value==='');
    assert.equal(await page.locator('#focus').inputValue(),'','Accepted Update report clears the submitted prompt');
    assert.equal(calls.filter(item=>item?.kind==='update').length,updatesBefore+2);
    assert.deepEqual(errors,[]);
    console.log('Running report: visible startup progress/console, draft transitions, timing, idle/failure states; Rerun preserves original kind/focus and newer prompt, blocks duplicate/busy/blocked/cleanup requests, recovers from rejection; accepted-only Update prompt clearing.');
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
