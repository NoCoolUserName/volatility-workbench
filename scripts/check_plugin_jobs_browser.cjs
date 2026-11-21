// Offline durable plugin progress controls; no model or forensic commands.
const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const assets=path.join(__dirname,'../src/volatility_workbench/static');
const sample=id=>({id,title:id,created_at:'2026-10-18T00:00:00Z',images:[],coins:[],readiness:{status:'Unchecked',reasons:[]},reports:[],messages:[],activity:[]});
const state={cases:[sample('case-a'),sample('case-b')],jobs:[],approvals:[],account:{},evidence_root:'/synthetic',plugin_jobs_available:true};
let jobs=[{job_id:'running',plugin:'synthetic.<img src=x onerror=alert(1)>',state:'running',started_at:'2026-10-18T12:00:00Z'},
 {job_id:'queued',plugin:'synthetic.Queued',state:'queued'}],posts=[];
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.WORKBENCH_BROWSER_EXECUTABLE?{executablePath:process.env.WORKBENCH_BROWSER_EXECUTABLE}:{})});
 try{
  const page=await browser.newPage({viewport:{width:1200,height:1000}}),errors=[];
  await page.addInitScript(()=>{window.EventSource=class extends EventTarget{close(){}};window.setInterval=()=>0;});
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('http://localhost/**',async route=>{
   const req=route.request(),url=new URL(req.url());
   if(url.pathname==='/api/state')return route.fulfill({json:state});
   if(url.pathname==='/api/settings/zoom')return route.fulfill({json:{schema:'zoom/1',percent:100}});
   if(url.pathname==='/api/artifacts')return route.fulfill({json:{files:[],truncated:false}});
   if(url.pathname==='/api/plugin-jobs'){
    const items=url.searchParams.get('case')==='case-a'?jobs:[];
    return route.fulfill({json:{jobs:items,max_concurrent_runs:12,active_count:items.filter(j=>['running','queued'].includes(j.state)).length,
      running_count:items.filter(j=>j.state==='running').length,queued_count:items.filter(j=>j.state==='queued').length,omitted_active:0}});
   }
   if(url.pathname==='/api/plugin-jobs/cancel'){
    const body=req.postDataJSON();posts.push(body);assert.equal(body.case_id,'case-a');
    const job=jobs.find(j=>j.job_id===body.job_id);job.state='cancelled';return route.fulfill({json:job});
   }
   if(url.pathname==='/api/stop'){
    posts.push({stop:true});jobs.forEach(j=>j.state='cancelled');return route.fulfill({json:{stopping:true,plugin_cancel_errors:[]}});
   }
   assert.ok(!url.pathname.startsWith('/api/'),'Unexpected action '+url.pathname);
   const name=url.pathname==='/'?'index.html':url.pathname.slice(1);
   return route.fulfill({body:fs.readFileSync(path.join(assets,name)),contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html'});
  });
  await page.goto('http://localhost/?case=case-a');
  await page.locator('#pluginJobsSection').waitFor();
  assert.match(await page.locator('#pluginJobsSummary').innerText(),/1 running · 1 queued · concurrency 12/);
  assert.equal(await page.locator('#pluginJobs img').count(),0,'Untrusted plugin text never becomes markup');
  assert.equal(await page.locator('#stop').isEnabled(),true,'Stop includes background core-only jobs');
  assert.equal(await page.locator('#pluginJobsSettings').getAttribute('href'),'http://localhost/settings.html?case=case-a#execution-title');
  for(const scale of [1,2]){
   await page.evaluate(scale=>document.documentElement.style.setProperty('--text-scale',scale),scale);
   const rows=await page.locator('#pluginJobs li').evaluateAll(nodes=>nodes.map(node=>({row:node.getBoundingClientRect().toJSON(),button:node.querySelector('button').getBoundingClientRect().toJSON()})));
   for(const {row,button} of rows){assert.ok(button.left>=row.left);assert.ok(button.right<=row.right+1);}
  }
  await page.locator('#pluginJobs li').nth(1).getByRole('button',{name:'Cancel plugin',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('#pluginJobsSummary').textContent.includes('0 queued'));
  assert.deepEqual(posts,[{case_id:'case-a',job_id:'queued'}]);
  // The corrected core poll returns completion immediately when the owner
  // finishes during the read. Refresh clears active controls without a retry.
  jobs[0].state='success';jobs[0].error=null;
  await page.evaluate(()=>refreshPluginJobs());
  assert.match(await page.locator('#pluginJobsSummary').innerText(),/^0 running · 0 queued/);
  assert.match(await page.locator('#pluginJobs li').first().innerText(),/success/);
  assert.doesNotMatch(await page.locator('#pluginJobs').innerText(),/interrupted/i);
  assert.equal(await page.locator('#pluginJobs').getByRole('button',{name:'Cancel plugin',exact:true}).count(),0);
  assert.equal(await page.locator('#stop').isHidden(),true);
  assert.deepEqual(posts,[{case_id:'case-a',job_id:'queued'}],'Completion refresh never resubmits work');
  jobs[0].state='running';await page.evaluate(()=>refreshPluginJobs());
  await page.evaluate(()=>choose('case-b'));
  assert.equal(await page.locator('#pluginJobsSection').isHidden(),true,'Switching cases immediately hides previous progress');
  await page.evaluate(()=>refreshPluginJobs());assert.equal(await page.locator('#pluginJobsSection').isHidden(),true);
  await page.evaluate(()=>choose('case-a'));await page.evaluate(()=>refreshPluginJobs());
  await page.locator('#stop').click();
  await page.waitForFunction(()=>document.querySelector('#pluginJobsSummary').textContent.startsWith('0 running · 0 queued'));
  assert.equal(await page.locator('#stop').isHidden(),true);
  assert.deepEqual(posts.at(-1),{stop:true});
  const batch=await page.evaluate(()=>{
    const entry={kind:'request_failure',request_tool:'submit_jobs',plugin:null,state:'request_failed',
      call_id:'UI-batch',execution_recorded:false,error_id:'batch',error_sources:[{path:'artifacts/UI-batch.json',label:'Saved request error'}]};
    const record={key:'batch-fixture',caseId:selected,reportId:'batch-report',entries:[entry],data:{source_status:'available',
      summary:{executions:0,plugins:0,failures:0,reuse_receipts:0,request_failures:1},errored_entries:[entry],executed_plugin_names:[],warnings:[]}};
    reportPluginKey=record.key;reportPluginCache.set(record.key,record);renderReportPlugins(record);
    return {text:document.querySelector('#reportPluginInventory').textContent,prompt:failedPluginRequest(entry,record)};
  });
  assert.match(batch.text,/submit_jobs/);assert.match(batch.text,/0 recorded executions/);
  assert.match(batch.prompt,/"request_tool":"submit_jobs"/);
  assert.match(batch.prompt,/reports\/batch-report\/artifacts\/UI-batch.json/);
  assert.deepEqual(errors,[]);
  console.log('Plugin jobs browser: selected-case progress, terminal completion refresh, escaped text, individual cancellation, background-only Stop, case switching and 100%/200% control bounds; no analysis.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
