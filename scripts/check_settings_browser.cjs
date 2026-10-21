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
  symbols:{installed:{synthetic:false},directory:'/synthetic/symbols',cache:'/synthetic/cache',matching:'Synthetic symbols only',profile:{packs:[{id:'synthetic',label:'Synthetic pack',version:'1',size:8388608,limitations:'Fixture only',url:'https://example.test/pack',sha256:'a'.repeat(64)}],macos_status:'Synthetic fixture'}},
  provider:{default_provider:{provider:'codex',model:'gpt-6-astra',reasoning_effort:'high'},cases:[
    {case_id:'case-a',title:'Synthetic Codex case',provider:{provider:'codex',model:'gpt-6-astra',reasoning_effort:'high'}},
    {case_id:'case-b',title:'Synthetic compatible case',provider:{provider:'compatible',endpoint:'https://synthetic.example/v1',model:'synthetic',reasoning_effort:null}}]},operation:{status:'idle'},
  readiness:{status:'Ready with limitations',reasons:['Synthetic fixture; no analysis']},
  recycle_bin:[{case_id:'case-a',case_title:'Synthetic Codex case',report_id:'recycled-one',status:'sealed',deleted_at:'2026-10-20T00:00:00Z'}],
  hidden_report_cases:[{case_id:'case-a',case_title:'Synthetic Codex case',count:2}],
};
(async()=>{
  const browser=await chromium.launch({headless:true,...(process.env.WORKBENCH_BROWSER_EXECUTABLE?{executablePath:process.env.WORKBENCH_BROWSER_EXECUTABLE}:{})});
  try{
    const page=await browser.newPage({viewport:{width:1200,height:1000}});
    const errors=[],calls=[],saved=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.route('http://workbench.test/**',route=>{
      if (new URL(route.request().url()).pathname === '/api/settings/zoom') return route.fulfill({json:{schema:'zoom/1',percent:100}});
      const url=new URL(route.request().url());
      if(url.pathname==='/api/settings'){
        calls.push(url.pathname);
        return route.fulfill({json:settings});
      }
      if(url.pathname==='/api/settings/provider/models'){
        calls.push(url.pathname);
        const {config}=route.request().postDataJSON();
        if(config.provider==='compatible')return route.fulfill({status:400,json:{error:'Synthetic endpoint does not list models; enter its documented identifier.'}});
        return route.fulfill({json:{provider:'codex',models:[
          {model:'gpt-6-astra',label:'GPT-6 Astra',efforts:['low','medium','high','xhigh'],default_effort:'medium'},
          {model:'synthetic-alternate',label:'Synthetic alternate',efforts:['low','high'],default_effort:'low'}]}});
      }
      if(url.pathname==='/api/settings/provider'){
        const {config}=route.request().postDataJSON();saved.push(config);
        if(config.case_id)settings.provider.cases.find(item=>item.case_id===config.case_id).provider={...config};
        else settings.provider.default_provider={...config};
        return route.fulfill({json:settings.provider});
      }
      if(url.pathname==='/api/reports/restore'){
        assert.deepEqual(route.request().postDataJSON(),{case_id:'case-a',report_id:'recycled-one'});
        settings.recycle_bin=[];return route.fulfill({json:{report_id:'recycled-one',restored:true}});
      }
      if(url.pathname==='/api/reports/purge-hidden'){
        assert.deepEqual(route.request().postDataJSON(),{case_id:'case-a'});
        settings.hidden_report_cases[0].count=0;
        return route.fulfill({json:{deleted:[{report_id:'hidden-one'},{report_id:'hidden-two'}],failed:[]}});
      }
      assert.ok(!url.pathname.startsWith('/api/'),'Unexpected action '+url.pathname);
      const name=url.pathname.slice(1);
      return route.fulfill({body:fs.readFileSync(path.join(assets,name)),contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html'});
    });
    await page.goto('http://workbench.test/settings.html');
    await page.waitForFunction(()=>document.querySelector('#evidence-locations li'));
    assert.match(await page.locator('#recycle-list').innerText(),/recycled-one/);
    await page.getByRole('button',{name:'Restore',exact:true}).click();
    await page.waitForFunction(()=>document.querySelector('#recycle-list').textContent.includes('Recycle Bin is empty.'));
    page.once('dialog',dialog=>dialog.accept());
    await page.getByRole('button',{name:'Permanently delete hidden bundles'}).click();
    await page.waitForFunction(()=>document.querySelector('#hidden-reports').textContent.includes('No hidden report bundles remain.'));
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
    const packButton=page.locator('#symbol-packs button');
    assert.equal(await packButton.textContent(),'Download this pack');
    assert.equal(await packButton.isEnabled(),true);
    settings.operation.status='running';await page.evaluate(()=>refresh());
    assert.equal(await packButton.isDisabled(),true);assert.equal(await page.locator('#all-symbols').isDisabled(),true);
    settings.symbols.installed.synthetic=true;settings.operation.status='succeeded';await page.evaluate(()=>refresh());
    assert.equal(await packButton.textContent(),'Installed');assert.equal(await packButton.isDisabled(),true);
    assert.equal(await page.locator('#all-symbols').textContent(),'Installed');assert.equal(await page.locator('#all-symbols').isDisabled(),true);
    settings.symbols.installed.synthetic=false;await page.evaluate(()=>refresh());
    assert.equal(await packButton.textContent(),'Download this pack');assert.equal(await packButton.isEnabled(),true);
    assert.equal(await page.locator('#all-symbols').textContent(),'Download all supported packs');
    settings.symbols.installed.synthetic=true;

    assert.equal(await page.locator('#model').inputValue(),'gpt-6-astra');
    assert.equal(await page.locator('#reasoning-effort').inputValue(),'high');
    assert.equal(calls.filter(item=>item.endsWith('/models')).length,0,'Opening Settings never contacts a model catalog');
    await page.locator('#load-models').click();
    await page.getByText('2 models loaded.',{exact:false}).waitFor();
    await page.locator('#reasoning-effort').selectOption('xhigh');
    await page.getByRole('button',{name:'Save connection',exact:true}).click();
    await page.waitForFunction(()=>document.querySelector('#provider-result').textContent.includes('xhigh'));
    assert.equal(saved[0].model,'gpt-6-astra');assert.equal(saved[0].reasoning_effort,'xhigh');assert.equal(saved[0].case_id,undefined);
    await page.locator('#provider-case').selectOption('case-a');
    assert.equal(await page.locator('#reasoning-effort').inputValue(),'high','Default-only save leaves existing case settings intact');
    await page.locator('#reasoning-effort').selectOption('xhigh');
    await page.getByRole('button',{name:'Save connection',exact:true}).click();
    await page.waitForFunction(()=>document.querySelector('#provider-result').textContent.includes('case-a'));
    assert.equal(saved[1].case_id,'case-a');assert.equal(saved[1].reasoning_effort,'xhigh');assert.equal(saved[1].new_session,false);
    await page.locator('#model').selectOption('synthetic-alternate');
    assert.deepEqual(await page.locator('#reasoning-effort option').allTextContents(),['Low','High']);
    assert.equal(await page.locator('#reasoning-effort').inputValue(),'low','Unsupported prior effort resets to this model’s advertised default');
    await page.locator('#provider-case').selectOption('case-b');
    assert.equal(await page.locator('#provider').inputValue(),'compatible');
    assert.equal(await page.locator('#reasoning-effort').inputValue(),'','Compatible APIs keep their provider default');
    await page.locator('#load-models').click();
    await page.getByText('Synthetic endpoint does not list models; enter its documented identifier.',{exact:true}).waitFor();
    await page.locator('#model').selectOption('__custom__');
    await page.locator('#custom-model').fill('synthetic-custom');
    await page.locator('#reasoning-effort').selectOption('xhigh');
    await page.getByRole('button',{name:'Save connection',exact:true}).click();
    await page.waitForFunction(()=>document.querySelector('#provider-result').textContent.includes('synthetic-custom'));
    assert.equal(saved[2].model,'synthetic-custom');assert.equal(saved[2].reasoning_effort,'xhigh');assert.equal(saved[2].case_id,'case-b');
    assert.equal(saved[2].codex_executable,undefined);
    await page.reload();
    await page.waitForFunction(()=>document.querySelectorAll('#evidence-locations li').length===2);
    assert.equal(await page.locator('#symbol-packs button').textContent(),'Installed');
    assert.equal(await page.locator('#symbol-packs button').isDisabled(),true);
    assert.deepEqual(errors,[]);
    assert.ok(calls.length>=3);
    if(process.env.WORKBENCH_BROWSER_SCREENSHOT)await page.screenshot({path:process.env.WORKBENCH_BROWSER_SCREENSHOT,fullPage:true});
    console.log('Settings browser: locations; explicit model catalogs; default and per-case model/effort save; supported effort choices; compatible custom-model fallback; zero analysis actions.');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
