// Optional offline browser check; uses synthetic paths and no forensic/model calls.
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const assets = path.join(__dirname, '../src/volatility_workbench/static');
const settings = {
  config:{evidence_root:'/synthetic/default',output_root:'/synthetic/outputs',vol_python:'/synthetic/python'},
  state_dir:'/synthetic/state',has_cases:true,native_folder_picker:false,managed_runtime_available:false,
  evidence_locations:[{path:'/synthetic/default',default:true,image_count:1,case_count:1}],
  symbols:{directory:'/synthetic/symbols',cache:'/synthetic/cache',matching:'Synthetic symbols only',profile:{packs:[{id:'synthetic',label:'Synthetic pack',version:'1',size:8388608,limitations:'Fixture only',url:'https://example.test/pack',sha256:'a'.repeat(64)}],macos_status:'Synthetic fixture'}},
  provider:{default_provider:{provider:'codex'},cases:[]},operation:{status:'idle'},
  readiness:{status:'Ready with limitations',reasons:['Synthetic fixture; no analysis']},
};
(async()=>{
  const browser=await chromium.launch({headless:true,...(process.env.WORKBENCH_BROWSER_EXECUTABLE?{executablePath:process.env.WORKBENCH_BROWSER_EXECUTABLE}:{})});
  try{
    const page=await browser.newPage({viewport:{width:1200,height:1000}});
    const errors=[],calls=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.route('http://workbench.test/**',route=>{
      const url=new URL(route.request().url());
      if(url.pathname==='/api/settings'){
        calls.push(url.pathname);
        return route.fulfill({json:settings});
      }
      assert.ok(!url.pathname.startsWith('/api/'),'Unexpected action '+url.pathname);
      const name=url.pathname.slice(1);
      return route.fulfill({body:fs.readFileSync(path.join(assets,name)),contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html'});
    });
    await page.goto('http://workbench.test/settings.html');
    await page.waitForFunction(()=>document.querySelector('#evidence-locations li'));
    assert.equal(await page.locator('#evidence-locations li').count(),1);
    assert.match(await page.locator('#evidence-locations').innerText(),/default folder; 1 registered image\(s\), 1 case\(s\)/);
    const external='/synthetic/Other disk/<img src=x onerror=alert(1)>';
    settings.evidence_locations.push({path:external,default:false,image_count:2,case_count:3});
    await page.waitForFunction(()=>document.querySelectorAll('#evidence-locations li').length===2);
    assert.equal(await page.locator('#evidence-locations li').last().locator('code').textContent(),external);
    assert.equal(await page.locator('#evidence-locations img').count(),0);
    assert.match(await page.locator('#evidence-locations li').last().innerText(),/2 registered image\(s\), 3 case\(s\)/);
    assert.equal(await page.locator('#evidence-root').isDisabled(),true);
    assert.equal(await page.locator('#evidence-root').inputValue(),'/synthetic/default');
    assert.match(await page.locator('#symbol-packs').innerText(),/Synthetic pack · 1 · 8\.39 MB/);
    assert.doesNotMatch(await page.locator('#symbol-packs').innerText(),/MiB/);
    await page.reload();
    await page.waitForFunction(()=>document.querySelectorAll('#evidence-locations li').length===2);
    assert.deepEqual(errors,[]);
    assert.ok(calls.length>=3);
    if(process.env.WORKBENCH_BROWSER_SCREENSHOT)await page.screenshot({path:process.env.WORKBENCH_BROWSER_SCREENSHOT,fullPage:true});
    console.log('Settings browser: initial locations, live refresh, reload persistence, safe path rendering and unchanged default controls passed; zero analysis actions.');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
