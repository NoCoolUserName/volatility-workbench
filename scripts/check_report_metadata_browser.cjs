// Offline renderer check: provider-shaped metadata, synthetic report text only.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const assets=path.join(__dirname,'../src/volatility_workbench/static');
const version={id:'synthetic-report',status:'sealed',created_at:'2026-10-18T12:00:00Z'};
const state={cases:[{id:'synthetic',title:'Synthetic case',created_at:'2026-10-18T12:00:00Z',
  images:[],coins:[],readiness:{status:'Unchecked',reasons:[]},reports:[version],messages:[],activity:[]}],
  jobs:[],approvals:[],account:{},evidence_root:'/synthetic'};
let assessment='Evidence-backed assessment with limitations.';
const badge=hash=>'![Decorative coin for Synthetic](assets/coins/'+hash.repeat(64)+'.png)\n';
const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/lWQAAAAASUVORK5CYII=','base64');
(async()=>{
  const browser=await chromium.launch({headless:true,...(process.env.WORKBENCH_BROWSER_EXECUTABLE?{executablePath:process.env.WORKBENCH_BROWSER_EXECUTABLE}:{})});
  try{
    const page=await browser.newPage({viewport:{width:1400,height:1000}}),calls=[],errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.route('http://localhost/**',route=>{
      const u=new URL(route.request().url());
      if(u.pathname.startsWith('/api/')){
        calls.push(u.pathname);
        if(u.pathname==='/api/state')return route.fulfill({json:state});
        if(u.pathname==='/api/artifacts')return route.fulfill({json:{files:[],truncated:false}});
        if(u.pathname==='/api/coin')return route.fulfill({body:png,contentType:'image/png'});
        if(u.pathname==='/api/file')return route.fulfill({json:{text:badge('a')+badge('a')+badge('b')+'# E001 — Synthetic investigation\n\nCase: synthetic\nReport specification 0.3; manifest schema 0.1. '+assessment+' Prepared 2026-10-18 UTC.\n\n## Executive summary\nSynthetic only.',truncated:false}});
        throw Error('Unexpected request: '+u.pathname);
      }
      const name=u.pathname==='/'?'index.html':u.pathname.slice(1);
      return route.fulfill({body:fs.readFileSync(path.join(assets,name)),contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html'});
    });
    await page.goto('http://localhost/');
    await page.waitForFunction(()=>document.querySelector('#reportView').textContent.includes('Model, reasoning effort'));
    assert.equal(await page.locator('#reportView h1 + p').innerText(),assessment);
    assert.equal(await page.locator('#reportView .challenge-coin').count(),2,'Duplicate old badge suppressed; distinct image coin retained');
    let meta=page.locator('#reportView p').filter({hasText:'Report specification'});
    assert.ok(!(await meta.innerText()).includes(assessment));
    assert.ok((await meta.innerText()).includes('not recorded for this report'));
    assessment='Limited assessment: symbol coverage is unknown. <img src=x onerror=alert(1)>';
    version.generation={summary:'with `synthetic-model` (reasoning effort: `high`) and 1,234 tokens (report-generation turn; final provider count).'};
    await page.reload();
    await page.waitForFunction(()=>document.querySelector('#reportView').textContent.includes('1,234 tokens'));
    assert.equal(await page.locator('#reportView h1 + p').innerText(),assessment);
    assert.equal(await page.locator('#reportView img:not(.challenge-coin)').count(),0,'Assessment text must not become HTML');
    meta=page.locator('#reportView p').filter({hasText:'Report specification'});
    assert.ok((await meta.innerText()).includes('Prepared 2026-10-18 UTC with `synthetic-model`'));
    if(process.env.WORKBENCH_BROWSER_SCREENSHOT)await page.screenshot({path:process.env.WORKBENCH_BROWSER_SCREENSHOT,fullPage:true});
    assert.deepEqual(errors,[]);
    assert.ok(!calls.some(v=>/jobs|coverage|stop|pick/.test(v)));
    console.log('Report metadata: actual dynamic assessment below title; known model/effort/tokens; historical unknowns; safe text; zero work submissions.');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
