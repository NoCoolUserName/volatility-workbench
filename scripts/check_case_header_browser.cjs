// Offline layout regression using synthetic case metadata; no evidence or analysis.
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const assets = path.join(__dirname, '../src/volatility_workbench/static');
const coin = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/lWQAAAAASUVORK5CYII=';
const state = {cases:[{id:'synthetic-case',title:'Synthetic XP case',created_at:'2026-10-18T00:00:00Z',
  images:[{id:'E001',path:'/synthetic/evidence/example.vmem',size_bytes:4096,sha256:'a'.repeat(64)}],
  coins:[{image_id:'E001',path:'assets/coins/'+'a'.repeat(64)+'.png',label:'Synthetic coin'}],
  readiness:{status:'Unchecked',reasons:['Synthetic readiness fixture']},
  reports:[{id:'synthetic-report',status:'sealed',created_at:'2026-10-18T12:01:00Z'}],
  messages:[],activity:[]}],jobs:[],approvals:[],account:{},evidence_root:'/synthetic/evidence'};

(async()=>{
  const browser=await chromium.launch({headless:true,...(process.env.WORKBENCH_BROWSER_EXECUTABLE?{executablePath:process.env.WORKBENCH_BROWSER_EXECUTABLE}:{})});
  try{
    const page=await browser.newPage({viewport:{width:1400,height:900}});
    const calls=[],errors=[],requests=[];
    page.on('pageerror',e=>errors.push(e.message));
    // Loopback is a secure browser context, matching the app's crypto.randomUUID use.
    await page.route('http://localhost/**',route=>{
      const u=new URL(route.request().url());
      if(u.pathname.startsWith('/api/')){
        calls.push(u.pathname);
        if(u.pathname==='/api/state')return route.fulfill({json:state});
        if(u.pathname==='/api/jobs'){
          const request=route.request().postDataJSON();
          assert.equal(request.kind,'readiness');
          assert.equal(request.case_id,'synthetic-case');
          requests.push(request);
          const job={id:'check-'+requests.length,case_id:request.case_id,kind:'readiness',status:'queued'};
          state.jobs.push(job);
          return route.fulfill({json:job});
        }
        if(u.pathname==='/api/file')return route.fulfill({json:{text:'# Synthetic report\n![Decorative coin for Synthetic coin](assets/coins/'+ 'a'.repeat(64)+'.png)\n## Finding\nFixture only.',truncated:false}});
        if(u.pathname==='/api/coin')return route.fulfill({body:Buffer.from(coin.split(',')[1],'base64'),contentType:'image/png'});
        if(u.pathname==='/api/artifacts')return route.fulfill({json:{files:[],truncated:false}});
        throw Error('Unexpected action: '+u.pathname);
      }
      const name=u.pathname==='/'?'index.html':u.pathname.slice(1);
      return route.fulfill({body:fs.readFileSync(path.join(assets,name)),contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html'});
    });
    await page.goto('http://localhost/');
    await page.waitForFunction(()=>document.querySelector('#caseTitle').textContent==='Synthetic XP case' && document.querySelector('#reportView .challenge-coin'));
    const control=page.locator('#readiness');
    const title=await page.locator('#caseTitle').boundingBox(),ready=await control.boundingBox();
    assert.ok(ready.y>=title.y+title.height,'Readiness control must sit below case title');
    assert.equal(await control.innerText(),'Check Readiness');
    assert.equal(await page.getByRole('button',{name:'Check Readiness',exact:true}).count(),1);
    assert.equal(await page.locator('.eyebrow').textContent(),'LOCAL MEMORY FORENSICS · EXPERIMENTAL');
    assert.equal(await page.locator('header h1').evaluate(e=>getComputedStyle(e).fontSize),'29px');
    assert.equal(await page.locator('#reportView h1').evaluate(e=>getComputedStyle(e).fontSize),'25px');
    const plugins=await page.locator('#openPlugins').boundingBox(),theme=await page.locator('.theme-control').boundingBox();
    assert.ok(theme.x>=plugins.x+plugins.width && Math.abs(theme.y-plugins.y)<10,'Theme must be to right of Plugins');
    await control.click();
    await page.waitForFunction(()=>document.querySelector('#readiness').textContent==='Queued…');
    assert.equal(await control.isDisabled(),true);
    assert.equal(requests.length,1);
    const job=state.jobs[0];
    job.status='running';job.started_at=new Date().toISOString();
    for(const progress of ['Checking selected provider readiness','Discovering installed plugins through MCP','Hashing example.vmem: 2,048 / 4,096 bytes','OS/symbol discovery: example.vmem']){
      job.progress=progress;
      await page.waitForFunction(text=>document.querySelector('#readinessProgress').textContent.startsWith(text),progress);
      assert.equal(await control.innerText(),'Checking…');
    }
    const check=await control.boundingBox(),progress=await page.locator('#readinessProgress').boundingBox();
    assert.ok(progress.x>=check.x+check.width,'Live progress must sit to right of control');
    assert.equal(await page.locator('#operation').textContent(),'');
    await page.reload();
    await page.waitForFunction(()=>document.querySelector('#readiness').textContent==='Checking…');
    assert.equal(requests.length,1,'Reconnect must not submit another check');
    job.status='completed';
    state.cases[0].readiness={status:'Ready',checked_at:'2026-10-18T12:00:00Z',reasons:['Synthetic readiness fixture']};
    await page.waitForFunction(()=>document.querySelector('#readiness').textContent==='Ready');
    assert.equal(await control.isEnabled(),true);
    assert.match(await page.locator('#readyDetails').innerText(),/Last checked .* image access and SHA-256 verified then/);
    for(const theme of ['matrix','mono','blue']){
      await page.locator('#theme').selectOption(theme);
      const color=await control.evaluate(e=>({text:getComputedStyle(e).color,border:getComputedStyle(e).borderTopColor}));
      assert.deepEqual(color,{text:'rgb(134, 230, 165)',border:'rgb(134, 230, 165)'});
    }
    assert.match(await page.locator('#images').innerText(),/example\.vmem.*4,096 bytes · SHA-256 a+/s);
    assert.equal(await page.locator('#images .challenge-coin').count(),0);
    assert.equal(await page.locator('#reportView .challenge-coin').count(),1);
    assert.equal(await page.locator('#images .image').evaluate(e=>getComputedStyle(e).borderTopWidth),'0px');
    assert.equal(await page.locator('#images .image').evaluate(e=>getComputedStyle(e).backgroundColor),'rgba(0, 0, 0, 0)');
    if(process.env.WORKBENCH_BROWSER_SCREENSHOT)await page.screenshot({path:process.env.WORKBENCH_BROWSER_SCREENSHOT,fullPage:true});
    await control.click();
    await page.waitForFunction(()=>document.querySelector('#readiness').textContent==='Queued…');
    assert.equal(requests.length,2,'Ready control must allow an explicit recheck');
    state.jobs[1].status='failed';
    state.cases[0].readiness={status:'Blocked',reasons:['Synthetic inaccessible image']};
    await page.waitForFunction(()=>document.querySelector('#readiness').textContent==='Check Readiness');
    assert.equal(await control.isEnabled(),true);
    assert.equal(await control.evaluate(e=>e.classList.contains('is-ready')),false);
    assert.match(await page.locator('#readinessProgress').innerText(),/Blocked/);
    state.cases[0].readiness={status:'Ready with limitations',checked_at:'2026-10-18T12:02:00Z',reasons:['Synthetic unresolved symbols']};
    await page.waitForFunction(()=>document.querySelector('#readiness').textContent==='Ready with limitations');
    assert.match(await page.locator('#reasons').innerText(),/unresolved symbols/);
    assert.equal(await page.locator('#images .challenge-coin').count(),0);
    assert.equal(await page.locator('#reportView .challenge-coin').count(),1);
    assert.deepEqual(errors,[]);
    assert.ok(!calls.some(x=>/stop|plugins/.test(x)));
    assert.equal(calls.filter(x=>x==='/api/jobs').length,2);
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    console.log('Case header: combined check/progress/Ready/recheck/failure/reconnect, fixed green across themes, header/mobile layout, report coin retained; two simulated readiness requests, zero real analysis.');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
