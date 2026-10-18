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
const narrative='\n\n## Executive summary\nSynthetic only.\n\n## Scope and evidence\n'
  +'| Item | Recorded value |\n|---|---|\n| Evidence | E001, `synthetic.vmem`, 4,096 bytes |\n'
  +'| Source path | [Saved source](artifacts/source.txt) |\n\n'
  +'## Technical findings\n### F1 — Synthetic observation\n'
  +'| PID | PPID | Significance |\n|---|---|---|\n| 4 | 1 | A\\|B; <img src=x onerror=alert(1)> |\n\n'
  +'**Evidence status:** Synthetic only.\n\n'
  +'## Investigative workflow and coverage\n'
  +'| Run / call | Plugin and exact plugin arguments | Saved result |\n|---|---|---|\n'
  +'| `synthetic-run` / `synthetic-call` | `banners.Banners` [] | [success](artifacts/run.txt) |\n\n'
  +'```\n| literal | code |\n```\n\n## End of saved report\nVisible final sentence.';
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
        if(u.pathname==='/api/report-plugins')return route.fulfill({json:{schema:'report-plugin-inventory/1',report_id:u.searchParams.get('report'),scope:'bundled_saved_runs',source_status:'unavailable',summary:{executions:null,plugins:null,failures:null,reuse_receipts:null,request_failures:null},entries:[],next_offset:null,warnings:['Inventory metadata is absent from this synthetic presentation fixture.']}});
        if(u.pathname==='/api/file'){
          const full=Buffer.from(badge('a')+badge('a')+badge('b')+'# E001 — Synthetic investigation\n\nCase: synthetic\nReport specification 0.3; manifest schema 0.1. '+assessment+' Prepared 2026-10-18 UTC.'+narrative);
          const offset=Number(u.searchParams.get('offset')||0);
          let end=Math.min(offset+256,full.length);
          while(end<full.length && (full[end]&0xc0)===0x80)end++;
          return route.fulfill({json:{text:full.subarray(offset,end).toString('utf8'),size:full.length,next_offset:end,truncated:end<full.length}});
        }
        throw Error('Unexpected request: '+u.pathname);
      }
      const name=u.pathname==='/'?'index.html':u.pathname.slice(1);
      return route.fulfill({body:fs.readFileSync(path.join(assets,name)),contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html'});
    });
    await page.goto('http://localhost/');
    await page.waitForFunction(()=>document.querySelector('#reportView').textContent.includes('Model, reasoning effort'));
    assert.match(await page.locator('#reportView').innerText(),/Visible final sentence\./);
    assert.ok(calls.filter(v=>v==='/api/file').length>1,'Full report loads across bounded chunks');
    assert.equal(await page.getByRole('button',{name:/Report preview truncated/}).count(),0);
    assert.equal(await page.locator('#reportView h1 + p').innerText(),assessment);
    assert.equal(await page.locator('#reportView .challenge-coin').count(),2,'Duplicate old badge suppressed; distinct image coin retained');
    let meta=page.locator('#reportView p').filter({hasText:'Report specification'});
    assert.ok(!(await meta.innerText()).includes(assessment));
    assert.ok((await meta.innerText()).includes('not recorded for this report'));
    assert.deepEqual(await page.locator('#reportView .report-field-list strong').allTextContents(),['Evidence:','Source path:']);
    assert.deepEqual(await page.locator('#reportView .report-field-group:not(.report-field-list) strong').allTextContents(),
      ['PID:','PPID:','Significance:']);
    assert.equal(await page.locator('#reportView .report-field-list').first().innerText(),'Evidence: E001, `synthetic.vmem`, 4,096 bytes');
    assert.equal(await page.locator('#reportView .report-field-list a').count(),1,'Saved evidence links remain clickable');
    assert.deepEqual(await page.locator('#reportView .report-run-table th').allTextContents(),
      ['Run / call','Plugin and exact plugin arguments','Saved result']);
    assert.equal(await page.locator('#reportView .report-run-table tbody tr').count(),1);
    assert.equal(await page.locator('#reportView .report-run-table tbody a').count(),1,'Saved run result link remains clickable');
    assert.equal(await page.locator('#reportView p').filter({hasText:'|---|'}).count(),0,'Pipe-table syntax is absent from narrative display');
    assert.equal(await page.locator('#reportView pre').innerText(),'| literal | code |\n','Code fences keep literal pipes');
    assert.equal(await page.locator('#reportView p strong').filter({hasText:'Evidence status:'}).count(),1,'Markdown field labels render bold');
    assert.equal(await page.locator('#reportView img:not(.challenge-coin)').count(),0,'Untrusted table cells remain text');
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
