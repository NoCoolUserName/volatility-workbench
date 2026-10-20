// Offline layout regression using synthetic case metadata; no evidence or analysis.
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const assets = path.join(__dirname, '../src/volatility_workbench/static');
const coin = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/lWQAAAAASUVORK5CYII=';
const state = {cases:[{id:'synthetic-case',title:'Synthetic XP case',created_at:'2026-10-18T00:00:00Z',
  images:[{id:'E001',path:'/synthetic/evidence/example.vmem',size_bytes:536870912,sha256:'a'.repeat(64)}],
  coins:[{image_id:'E001',path:'assets/coins/'+'a'.repeat(64)+'.png',label:'Synthetic coin'}],
  readiness:{status:'Unchecked',reasons:['Synthetic readiness fixture']},
  reports:[{id:'synthetic-report',status:'sealed',created_at:'2026-10-18T12:01:00Z'}],
  messages:[],activity:[]}],jobs:[],approvals:[],account:{},evidence_root:'/synthetic/evidence'};

(async()=>{
  const browser=await chromium.launch({headless:true,...(process.env.WORKBENCH_BROWSER_EXECUTABLE?{executablePath:process.env.WORKBENCH_BROWSER_EXECUTABLE}:{})});
  try{
    const page=await browser.newPage({viewport:{width:1400,height:900}});
    const calls=[],errors=[],requests=[];
    let zoomPercent=100;
    page.on('pageerror',e=>errors.push(e.message));
    // Loopback is a secure browser context, matching the app's crypto.randomUUID use.
    await page.route('http://localhost/**',route=>{
      if (new URL(route.request().url()).pathname === '/api/settings/zoom') {
        if(route.request().method()==='POST')zoomPercent=route.request().postDataJSON().percent;
        return route.fulfill({json:{schema:'zoom/1',percent:zoomPercent}});
      }
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
        if(u.pathname==='/api/report-plugins')return route.fulfill({json:{schema:'report-plugin-inventory/1',report_id:u.searchParams.get('report'),scope:'bundled_saved_runs',source_status:'unavailable',summary:{executions:null,plugins:null,failures:null,reuse_receipts:null,request_failures:null},entries:[],next_offset:null,warnings:['Inventory metadata is absent from this synthetic presentation fixture.']}});
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
    assert.equal(await page.locator('header h1').evaluate(e=>getComputedStyle(e).fontSize),'31px');
    assert.equal(await page.locator('#reportView h1').evaluate(e=>getComputedStyle(e).fontSize),'25px');
    const plugins=await page.locator('#openPlugins').boundingBox(),theme=await page.locator('#toggleTheme').boundingBox();
    const settings=await page.getByRole('link',{name:'Settings',exact:true}).boundingBox();
    assert.ok(theme.y>=plugins.y+plugins.height && Math.abs(theme.x-plugins.x)<2,'Theme button sits directly below Plugins');
    assert.ok(Math.abs(theme.width-plugins.width)<2,'Theme and Plugins buttons align');
    assert.ok(Math.abs(settings.x+settings.width-1368)<2 && settings.y<plugins.y,'Settings sits at the upper right');
    assert.equal(await page.locator('#theme').isHidden(),true);
    await page.locator('#toggleTheme').click();
    assert.equal(await page.locator('#toggleTheme').getAttribute('aria-expanded'),'true');
    assert.equal(await page.locator('#theme').isVisible(),true);
    await page.locator('#toggleTheme').click();
    assert.equal(await page.locator('#theme').isHidden(),true);
    await page.locator('#toggleTheme').click();
    await page.locator('#theme').press('Escape');
    assert.equal(await page.locator('#toggleTheme').getAttribute('aria-expanded'),'false');
    assert.equal(await page.locator('#toggleTheme').evaluate(node=>node===document.activeElement),true);
    assert.equal(await page.locator('.settings-link svg').evaluate(e=>getComputedStyle(e).color),'rgb(192, 192, 192)','Settings gear must be silver');
    assert.equal(await page.locator('header #stop').count(),0,'Stop has moved out of the header');
    assert.equal(await page.locator('#stop').isHidden(),true,'Idle Stop stays with the hidden work panel');
    assert.equal(await page.locator('#stop').isDisabled(),true,'Idle Stop must be disabled');
    assert.equal(await page.locator('#queueSection').isHidden(),true,'Idle queue must not show completed history');
    await control.click();
    await page.waitForFunction(()=>document.querySelector('#readiness').textContent==='Queued…');
    assert.equal(await control.isDisabled(),true);
    assert.equal(await page.locator('#readyDetails').textContent(),'','Prior timestamp must not imply the new check is complete');
    assert.equal(await page.locator('#stop').isEnabled(),true,'Queued work can be stopped');
    assert.equal(await page.locator('#currentWorkHeading #stop').count(),1,'Readiness keeps Stop beside Current work');
    await page.waitForFunction(()=>document.querySelector('#queue').textContent.includes('queued'));
    assert.equal(await page.locator('#queue li').count(),1);
    await page.locator('#queue li').evaluate(item=>item.dataset.stable='yes');
    await page.waitForResponse(response=>response.url().endsWith('/api/state'));
    assert.equal(await page.locator('#queue li').getAttribute('data-stable'),'yes','Unchanged queue must not be rebuilt on refresh');
    assert.equal(requests.length,1);
    const job=state.jobs[0];
    job.status='running';job.started_at=new Date().toISOString();
    for(const progress of ['Checking selected provider readiness','Discovering installed plugins through MCP','Hashing example.vmem: 2,048 / 4,096 bytes','OS/symbol discovery: example.vmem']){
      job.progress=progress;
      await page.waitForFunction(text=>document.querySelector('#readinessProgress').textContent.startsWith(text),progress);
      assert.equal(await control.innerText(),'Checking…');
    }
    assert.match(await page.locator('#queue').innerText(),/OS\/symbol discovery: example\.vmem/);
    const check=await control.boundingBox(),progress=await page.locator('#readinessProgress').boundingBox();
    assert.ok(progress.x>=check.x+check.width,'Live progress must sit to right of control');
    assert.equal(await page.locator('#operation').textContent(),'');
    await page.reload();
    await page.waitForFunction(()=>document.querySelector('#readiness').textContent==='Checking…');
    assert.equal(requests.length,1,'Reconnect must not submit another check');
    job.status='stopping';
    await page.waitForFunction(()=>document.querySelector('#readiness').textContent==='Stopping…');
    assert.equal(await page.locator('#stop').isDisabled(),true,'Already stopping work must disable Stop');
    job.status='completed';
    state.cases[0].readiness={status:'Ready',checked_at:'2026-10-18T12:00:00Z',reasons:['Synthetic readiness fixture','Ready means ready to attempt analysis; plugin compatibility and forensic conclusions still require review.']};
    await page.waitForFunction(()=>document.querySelector('#readiness').textContent==='Ready');
    assert.equal(await control.isEnabled(),true);
    assert.equal(await page.locator('#stop').isDisabled(),true,'Completed work must disable Stop');
    await page.waitForFunction(()=>document.querySelector('#queueSection').hidden);
    assert.equal(await page.locator('#queue li').count(),0,'Completed jobs remain in Activity, not Current work');
    assert.doesNotMatch(await page.locator('#reasons').innerText(),/Ready means ready to attempt analysis/);
    assert.match(await page.locator('#readyDetails').innerText(),/Last checked .* image access and SHA-256 verified then/);
    const readyBox=await control.boundingBox(),checkedBox=await page.locator('#readyDetails').boundingBox();
    assert.ok(checkedBox.x>=readyBox.x+readyBox.width && Math.abs(checkedBox.y-readyBox.y)<10,'Last checked must sit to the right of Ready');
    for(const theme of ['matrix','mono','blue']){
      if(await page.locator('#theme').isHidden())await page.locator('#toggleTheme').click();
      await page.locator('#theme').selectOption(theme);
      const color=await control.evaluate(e=>({text:getComputedStyle(e).color,border:getComputedStyle(e).borderTopColor}));
      assert.deepEqual(color,{text:'rgb(134, 230, 165)',border:'rgb(134, 230, 165)'});
    }
    assert.match(await page.locator('#images').innerText(),/example\.vmem.*536\.87MB · SHA-256 a+/s);
    state.cases[0].images[0].size_bytes=1250000000;
    await page.waitForFunction(()=>document.querySelector('#images').textContent.includes('1.25GB'));
    assert.doesNotMatch(await page.locator('#images').innerText(),/bytes/);
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
    assert.equal(await control.evaluate(e=>getComputedStyle(e).borderTopLeftRadius),'9px');
    assert.equal(await control.evaluate(e=>getComputedStyle(e).minHeight),'34px');
    assert.deepEqual(errors,[]);
    assert.ok(!calls.some(x=>/^\/api\/(stop|plugins)$/.test(x)));
    assert.equal(calls.filter(x=>x==='/api/jobs').length,2);
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    const mobileSettings=await page.locator('.settings-link').boundingBox(),header=await page.locator('body > header').boundingBox();
    const connection=await page.locator('#connection').boundingBox();
    assert.ok(Math.abs(mobileSettings.x+mobileSettings.width-370)<2 && mobileSettings.y>=connection.y+connection.height,
      'Settings sits below the connection text at the upper right on mobile');
    const originalFont=Number.parseFloat(await page.locator('#reportView h1').evaluate(e=>getComputedStyle(e).fontSize));
    const savedZoom=page.waitForResponse(response=>response.url().endsWith('/api/settings/zoom') && response.request().method()==='POST');
    await page.getByRole('button',{name:'Increase text size'}).first().click();await savedZoom;
    assert.equal(zoomPercent,110);
    assert.ok(Number.parseFloat(await page.locator('#reportView h1').evaluate(e=>getComputedStyle(e).fontSize))>originalFont);
    await page.reload();
    await page.waitForFunction(()=>document.querySelector('[data-ui-zoom-value]')?.textContent==='110%');
    assert.equal(await page.locator('#liveConsole').evaluate(e=>getComputedStyle(e).whiteSpace),'pre-wrap');
    assert.equal(await page.locator('#volshellOutput').evaluate(e=>getComputedStyle(e).overflowWrap),'anywhere');
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    await page.evaluate(()=>window.dispatchEvent(new WheelEvent('wheel',{ctrlKey:true,deltaY:-200,cancelable:true})));
    assert.ok(Number.parseInt(await page.locator('[data-ui-zoom-value]').first().innerText())>110,
      'Control plus wheel scales text');
    await page.evaluate(()=>{
      window.dispatchEvent(new Event('gesturestart',{cancelable:true}));
      const gesture=new Event('gesturechange',{cancelable:true});
      Object.defineProperty(gesture,'scale',{value:0.8});
      window.dispatchEvent(gesture);
      window.dispatchEvent(new Event('gestureend',{cancelable:true}));
    });
    assert.ok(Number.parseInt(await page.locator('[data-ui-zoom-value]').first().innerText())<150,
      'Trackpad spread/pinch events scale text');
    console.log('Case header: Theme/Settings and connection/Stop alignment, idle/queued/completed Stop state, hidden legacy readiness sentence, check/progress/Ready/recheck/failure/reconnect, fixed green across themes, mobile layout; two simulated readiness requests, zero real analysis.');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
