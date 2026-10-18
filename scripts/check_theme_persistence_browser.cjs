// Offline browser fixture: actual packaged UI and simulated appearance API only.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const assets=path.join(__dirname,'../src/volatility_workbench/static');
const key='volatility-workbench-theme';
const empty=()=>({schema:'appearance/1',theme:null,revision:0});
const csp="default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'";
const settings={config:{evidence_root:'/synthetic',output_root:'/synthetic/output',vol_python:'/synthetic/python'},state_dir:'/synthetic/state',has_cases:false,
  evidence_locations:[],symbols:{directory:'/synthetic/symbols',cache:'/synthetic/cache',matching:'Synthetic only',profile:{packs:[],macos_status:'Synthetic'}},
  provider:{default_provider:{provider:'codex'},cases:[]},operation:{status:'idle'},readiness:{status:'Unchecked',reasons:[]}};
const state={cases:[],jobs:[],approvals:[],account:{},evidence_root:'/synthetic'};
function deferred(){let resolve;const promise=new Promise(r=>{resolve=r;});return{promise,resolve};}
(async()=>{
  const browser=await chromium.launch({headless:true,...(process.env.WORKBENCH_BROWSER_EXECUTABLE?{executablePath:process.env.WORKBENCH_BROWSER_EXECUTABLE}:{})});
  const errors=[],requests=[];
  let preference=empty(),holdRead=null,holdSave=null,failSave=false;
  try{
    async function context(legacy){
      const context=await browser.newContext();
      await context.addInitScript(({legacy,key})=>{
        window.EventSource=class extends EventTarget {close(){}};
        // Init scripts also run in the browser's opaque initial document.
        if(legacy&&location.protocol==='http:')localStorage.setItem(key,legacy);
      },{legacy,key});
      context.on('page',page=>page.on('pageerror',error=>errors.push(error.message)));
      await context.route('**/*',async route=>{
        const request=route.request(),url=new URL(request.url());
        assert.equal(url.hostname,'127.0.0.1','No external network requests');
        if(url.pathname.startsWith('/api/')){
          requests.push({method:request.method(),path:url.pathname});
          if(url.pathname==='/api/settings/appearance'){
            assert.equal(request.method(),'POST');
            const body=request.postDataJSON();
            const gate=holdSave;holdSave=null;
            if(gate){gate.started.resolve(body);await gate.release.promise;}
            if(failSave)return route.fulfill({status:403,json:{error:'Synthetic capability rejection'}});
            assert.ok(typeof body.theme==='string');
            if(!('expected_revision' in body)||preference.revision===0)preference={schema:'appearance/1',theme:body.theme,revision:preference.revision+1};
            return route.fulfill({json:preference});
          }
          assert.equal(request.method(),'GET','Only appearance POST is allowed; no jobs, cases, or evidence mutation');
          if(url.pathname==='/api/state'||url.pathname==='/api/settings'){
            const appearance={...preference};
            const gate=holdRead;holdRead=null;
            if(gate){gate.started.resolve();await gate.release.promise;}
            return route.fulfill({json:{...(url.pathname==='/api/state'?state:settings),appearance}});
          }
          throw Error('Unexpected API '+url.pathname);
        }
        const name=url.pathname==='/'?'index.html':url.pathname.slice(1);
        assert.ok(!name.includes('/'),'Only packaged static files');
        return route.fulfill({body:fs.readFileSync(path.join(assets,name)),headers:{'content-security-policy':csp},
          contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':name.endsWith('.svg')?'image/svg+xml':name.endsWith('.png')?'image/png':'text/html'});
      });
      return context;
    }
    async function theme(page,id){await page.waitForFunction(id=>document.documentElement.dataset.theme===id,id);}
    async function choose(page,id){
      const picker=page.locator('[data-theme-picker]');
      if(await picker.isHidden())await page.locator('#toggleTheme').click();
      await picker.selectOption(id);
      await theme(page,id);
    }
    async function persisted(page,id){await page.waitForResponse(async response=>response.url().endsWith('/api/settings/appearance')&&response.ok()&&(await response.json()).theme===id);}
    function gate(){return{started:deferred(),release:deferred()};}
    async function staleStorage(page,id){await page.evaluate(({key,id})=>window.dispatchEvent(new StorageEvent('storage',{key,newValue:id})),{key,id});}

    // An actual main-window selection persists; new port and fresh browser storage
    // restore it after loading the same packaged UI, just as a rebuilt bundle does.
    let ctx=await context(),page=await ctx.newPage();
    await page.goto('http://127.0.0.1:43101/');
    await page.waitForFunction(()=>document.querySelector('#connection').textContent!=='Connecting…');
    let saved=persisted(page,'fallout-new-vegas');await choose(page,'fallout-new-vegas');await saved;
    assert.equal(preference.theme,'fallout-new-vegas');
    await ctx.close();
    ctx=await context();page=await ctx.newPage();
    await page.goto('http://127.0.0.1:43102/');await theme(page,'fallout-new-vegas');
    assert.equal(await page.evaluate(key=>localStorage.getItem(key),key),'fallout-new-vegas');
    assert.match(await page.locator('html').evaluate(el=>el.style.getPropertyValue('--theme-scene')),/theme-fallout-new-vegas\.svg/);
    await staleStorage(page,'matrix');await theme(page,'fallout-new-vegas');
    const settingsPage=await ctx.newPage();
    await settingsPage.goto('http://127.0.0.1:43102/settings.html');await theme(settingsPage,'fallout-new-vegas');
    saved=persisted(settingsPage,'fallout-2');await choose(settingsPage,'fallout-2');await saved;
    await theme(page,'fallout-2');
    saved=persisted(page,'halloween');await choose(page,'halloween');await saved;
    await theme(settingsPage,'halloween');
    await ctx.close();

    // The choice made before the first authenticated state response wins.
    holdRead=gate();const delayed=holdRead;
    ctx=await context();page=await ctx.newPage();
    await page.goto('http://127.0.0.1:43103/',{waitUntil:'domcontentloaded'});await delayed.started.promise;
    await choose(page,'metroid');await staleStorage(page,'matrix');await theme(page,'metroid');
    saved=persisted(page,'metroid');delayed.release.resolve();await saved;await theme(page,'metroid');

    // An old save response or stale snapshot cannot paint over a later choice.
    holdSave=gate();const saving=holdSave;
    await choose(page,'vaporwave');await saving.started.promise;
    await choose(page,'fallout-new-vegas');await staleStorage(page,'matrix');
    await page.evaluate(()=>WorkbenchThemes.sync({schema:'appearance/1',theme:'halloween',revision:1}));
    await theme(page,'fallout-new-vegas');
    saved=persisted(page,'fallout-new-vegas');saving.release.resolve();await saved;
    await staleStorage(page,'matrix');await theme(page,'fallout-new-vegas');
    assert.equal(preference.theme,'fallout-new-vegas');

    // Save rejection remains visible and does not silently claim persistence.
    await page.locator('[data-theme-save-retry]').waitFor({state:'hidden'});
    failSave=true;await choose(page,'retrowave');
    await page.locator('[data-theme-save-status]').filter({hasText:'could not be saved'}).waitFor({state:'visible'});
    await page.getByRole('button',{name:'Retry save',exact:true}).waitFor({state:'visible'});
    assert.equal(preference.theme,'fallout-new-vegas');
    await page.evaluate(()=>WorkbenchThemes.sync({schema:'appearance/1',theme:'fallout-new-vegas',revision:999}));
    await theme(page,'retrowave');
    failSave=false;saved=persisted(page,'retrowave');await page.getByRole('button',{name:'Retry save',exact:true}).click();await saved;
    await page.locator('[data-theme-save-status]').waitFor({state:'hidden'});
    await page.locator('[data-theme-save-retry]').waitFor({state:'hidden'});
    assert.equal(await page.locator('[data-theme-picker]').inputValue(),'retrowave','Retry saves the current selection without changing it');
    await ctx.close();

    // A legacy cache migrates only while stable preferences remain unset.
    preference=empty();ctx=await context('fallout');page=await ctx.newPage();
    saved=persisted(page,'fallout');await page.goto('http://127.0.0.1:43104/');await saved;
    assert.equal(preference.theme,'fallout');await ctx.close();
    ctx=await context('matrix');page=await ctx.newPage();
    const before=requests.filter(r=>r.method==='POST').length;
    await page.goto('http://127.0.0.1:43105/');await theme(page,'fallout');
    assert.equal(requests.filter(r=>r.method==='POST').length,before);
    await ctx.close();

    // If a new choice is saved while a stale migration is in flight, it wins.
    preference=empty();holdSave=gate();const migration=holdSave;
    ctx=await context('matrix');page=await ctx.newPage();
    await page.goto('http://127.0.0.1:43106/');
    const body=await migration.started.promise;assert.equal(body.expected_revision,0);
    preference={schema:'appearance/1',theme:'fallout-new-vegas',revision:1};
    saved=persisted(page,'fallout-new-vegas');migration.release.resolve();await saved;await theme(page,'fallout-new-vegas');
    await ctx.close();

    // Backend-invalid preference is explicit; unknown browser cache falls back.
    preference={...empty(),error:'Saved theme could not be loaded. Choose a theme to save it again.'};
    ctx=await context('unknown-theme');page=await ctx.newPage();
    await page.goto('http://127.0.0.1:43107/settings.html');await theme(page,'matrix');
    await page.locator('[data-theme-save-status]').filter({hasText:'could not be loaded'}).waitFor({state:'visible'});
    saved=persisted(page,'fallout-new-vegas');await choose(page,'fallout-new-vegas');await saved;
    await page.locator('[data-theme-save-status]').waitFor({state:'hidden'});
    await ctx.close();
    assert.deepEqual(errors,[]);
    console.log('Theme persistence browser fixture passed: new port/storage, main/Settings sync, delayed startup/save, stale storage, save failures, migration races, and corrupt fallback. No evidence or job endpoints accessed.');
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
