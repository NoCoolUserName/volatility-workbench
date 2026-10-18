// Offline UI check: synthetic sealed reports and a simulated local save endpoint only.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const assets=path.join(__dirname,'../src/volatility_workbench/static');
const versions=['legacy','explicit','uncertain'].map(id=>({id,status:'sealed',created_at:'2026-10-18T12:00:00Z'}));
const state={cases:[{id:'synthetic',title:'Synthetic case',created_at:'2026-10-18T12:00:00Z',images:[],coins:[],
  readiness:{status:'Unchecked',reasons:[]},reports:versions,messages:[],activity:[]}],
  jobs:[],approvals:[],account:{},evidence_root:'/synthetic'};
const narratives={
  legacy:'# Synthetic report\n## Executive summary\nThe evidence supports a high-confidence assessment of host compromise.\n## Scope and evidence\nSynthetic only.',
  explicit:'# Synthetic report\n## Executive summary\nAI Determination: Benign\nThe evidence supports a benign explanation.\n## Scope and evidence\nSynthetic only.',
  uncertain:'# Synthetic report\n## Executive summary\nAI Determination: Undetermined\nAvailable evidence is inconclusive.\n## Scope and evidence\nSynthetic only.',
};
(async()=>{
  const browser=await chromium.launch({headless:true,...(process.env.WORKBENCH_BROWSER_EXECUTABLE?{executablePath:process.env.WORKBENCH_BROWSER_EXECUTABLE}:{})});
  try{
    const page=await browser.newPage({viewport:{width:1100,height:900}}),posts=[],errors=[];
    page.on('pageerror',error=>errors.push(error.message));
    await page.route('http://localhost/**',route=>{
      const u=new URL(route.request().url());
      if(u.pathname==='/api/reports/determination'){
        assert.equal(route.request().method(),'POST');
        const data=route.request().postDataJSON();
        assert.equal(data.case_id,'synthetic');
        assert.ok(['Benign','Malicious','Undetermined',null].includes(data.value));
        const report=versions.find(version=>version.id===data.report_id);
        assert.ok(report);
        if(data.value===null)delete report.human_determination;
        else report.human_determination=data.value;
        posts.push(data);
        return route.fulfill({json:{report_id:report.id,human_determination:data.value}});
      }
      assert.equal(route.request().method(),'GET','Viewing a report must not submit work');
      if(u.pathname==='/api/state')return route.fulfill({json:state});
      if(u.pathname==='/api/report-plugins')return route.fulfill({json:{schema:'report-plugin-inventory/1',
        report_id:u.searchParams.get('report'),scope:'bundled_saved_runs',source_status:'unavailable',summary:{},entries:[],next_offset:null,warnings:[]}});
      if(u.pathname==='/api/file'){
        const id=/reports\/([^/]+)\/report\.md/.exec(u.searchParams.get('path'))?.[1];
        assert.ok(id in narratives);
        return route.fulfill({json:{text:narratives[id],size:narratives[id].length,next_offset:narratives[id].length,truncated:false}});
      }
      if(u.pathname==='/api/artifacts')return route.fulfill({json:{files:[],truncated:false}});
      assert.ok(!u.pathname.startsWith('/api/'),'Unexpected API route '+u.pathname);
      const name=u.pathname==='/'?'index.html':u.pathname.slice(1);
      return route.fulfill({body:fs.readFileSync(path.join(assets,name)),contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html'});
    });
    await page.goto('http://localhost/?case=synthetic');
    const ai=page.locator('.report-determinations .determination-value');
    const human=page.locator('#humanDetermination');
    await ai.waitFor();
    assert.equal(await ai.innerText(),'Undetermined');
    assert.equal(await human.inputValue(),'');
    assert.equal(await ai.evaluate(node=>getComputedStyle(node).color),'rgb(255, 255, 255)');
    assert.equal(await ai.evaluate(node=>getComputedStyle(node).fontWeight),'700');
    assert.equal(await page.locator('#reportView h2').first().innerText(),'Executive summary');
    assert.equal(await page.locator('#reportView h2 + .report-determinations').count(),1);

    await page.locator('[data-report-id="legacy"] button:first-child').click();
    await page.waitForFunction(()=>document.querySelector('.determination-value')?.textContent==='Malicious');
    assert.equal(await ai.evaluate(node=>getComputedStyle(node).color),'rgb(255, 137, 137)');
    await human.selectOption('Benign');
    await page.waitForFunction(()=>document.querySelector('.determination-save-status')?.textContent==='Saved');
    assert.equal(await human.evaluate(node=>getComputedStyle(node).color),'rgb(134, 230, 165)');
    assert.equal(await human.evaluate(node=>getComputedStyle(node).fontWeight),'700');
    assert.equal(versions[0].human_determination,'Benign','Human and AI opinions can differ');
    if(process.env.WORKBENCH_DETERMINATIONS_SCREENSHOT){
      await ai.scrollIntoViewIfNeeded();
      await page.screenshot({path:process.env.WORKBENCH_DETERMINATIONS_SCREENSHOT});
    }
    await page.reload();
    await page.locator('[data-report-id="legacy"] button:first-child').click();
    await page.waitForFunction(()=>document.querySelector('.determination-value')?.textContent==='Malicious');
    assert.equal(await human.inputValue(),'Benign','Human choice survives reload');
    await human.selectOption('Malicious');
    await page.waitForFunction(()=>document.querySelector('.determination-save-status')?.textContent==='Saved');
    assert.equal(await human.evaluate(node=>getComputedStyle(node).color),'rgb(255, 137, 137)');
    await human.selectOption('Undetermined');
    await page.waitForFunction(()=>document.querySelector('.determination-save-status')?.textContent==='Saved');
    assert.equal(await human.evaluate(node=>getComputedStyle(node).color),'rgb(255, 255, 255)');

    await page.locator('[data-report-id="explicit"] button:first-child').click();
    await page.waitForFunction(()=>document.querySelector('.determination-value')?.textContent==='Benign');
    assert.equal(await ai.evaluate(node=>getComputedStyle(node).color),'rgb(134, 230, 165)');
    assert.equal(await human.inputValue(),'','Human opinion belongs to its own report version');
    assert.equal(await page.locator('#reportView > p').getByText('AI Determination: Benign',{exact:true}).count(),0,
      'Saved Markdown determination is represented once by the UI line');
    await page.locator('[data-report-id="uncertain"] button:first-child').click();
    await page.waitForFunction(()=>document.querySelector('.determination-value')?.textContent==='Undetermined');
    assert.equal(await ai.evaluate(node=>getComputedStyle(node).color),'rgb(255, 255, 255)');
    assert.equal(posts.length,3);
    assert.deepEqual(errors,[]);
    console.log('Report determinations: explicit and conservative legacy AI values; three color states; independent human opinion; per-version save and reload; no analysis submissions.');
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
