// Offline navigation regression: synthetic report, citations and saved artifacts only.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const assets=path.join(__dirname,'../src/volatility_workbench/static');
const report={id:'synthetic-report',status:'sealed',created_at:'2026-10-18T12:00:00Z'};
const sample=id=>({id,title:id,created_at:'2026-10-18T12:00:00Z',images:[],coins:[],
  readiness:{status:'Unchecked',reasons:[]},reports:[{...report}],messages:[],activity:[]});
const state={cases:[sample('Synthetic A'),sample('Synthetic B')],jobs:[],approvals:[],account:{},evidence_root:'/synthetic'};
const artifactPath='reports/synthetic-report/artifacts/source.jsonl';
const narrative='# Synthetic report\n## Technical findings\n'+
  Array.from({length:100},(_,i)=>'Synthetic finding '+i+'. Harmless text to make a long report.\n\n').join('')+
  '## IOC appendix\n'+Array.from({length:30},(_,i)=>
    '**Type / exact value:** synthetic: example-'+i+'\n\n**Evidence:** [F5:'+i+'](artifacts/source.jsonl#citation=F5:'+i+')\n\n').join('')+
  '[Saved result](artifacts/source.jsonl)\n\nEnd of synthetic report.';
(async()=>{
  const browser=await chromium.launch({headless:true,...(process.env.WORKBENCH_BROWSER_EXECUTABLE?{executablePath:process.env.WORKBENCH_BROWSER_EXECUTABLE}:{})});
  try{
    const page=await browser.newPage({viewport:{width:1400,height:900}}),errors=[],calls=[];
    let delayCitation=false,releaseCitation;
    page.on('pageerror',e=>errors.push(e.message));
    await page.route('http://localhost/**',async route=>{
      const u=new URL(route.request().url());
      assert.equal(route.request().method(),'GET','Navigation must never submit work');
      calls.push(u.pathname);
      if(u.pathname==='/api/state')return route.fulfill({json:state});
      if(u.pathname==='/api/artifacts')return route.fulfill({json:{files:[{path:artifactPath,size_bytes:1024}],truncated:false}});
      if(u.pathname==='/api/report-plugins')return route.fulfill({json:{schema:'report-plugin-inventory/1',report_id:report.id,scope:'bundled_saved_runs',source_status:'unavailable',summary:{},entries:[],next_offset:null,warnings:[]}});
      if(u.pathname==='/api/citations'){
        if(delayCitation){delayCitation=false;await new Promise(resolve=>{releaseCitation=resolve;});}
        return route.fulfill({json:u.searchParams.has('finding')
          ?{artifact_path:artifactPath,finding:'F5',index:Number(u.searchParams.get('index')),validation:'valid'}
          :{entries:[{finding:'F5',index:7,artifact_id:'synthetic-source',validation:'valid'}],next_offset:null}});
      }
      if(u.pathname==='/api/file'){
        if(u.searchParams.get('path').endsWith('/report.md'))return route.fulfill({json:{text:narrative,size:narrative.length,next_offset:narrative.length,truncated:false}});
        assert.equal(u.searchParams.get('path'),artifactPath);
        const offset=Number(u.searchParams.get('offset'));
        return route.fulfill({json:{text:Array.from({length:40},()=>'{"synthetic":"saved evidence only"}').join('\n'),size:1024,next_offset:offset?1024:512,truncated:offset===0}});
      }
      assert.ok(!u.pathname.startsWith('/api/'),'Unexpected API action '+u.pathname);
      const name=u.pathname==='/'?'index.html':u.pathname.slice(1);
      return route.fulfill({body:fs.readFileSync(path.join(assets,name)),contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html'});
    });
    await page.goto('http://localhost/?case=Synthetic%20A');
    const link=page.locator('#reportView').getByRole('link',{name:'F5:7',exact:true});
    await link.waitFor();
    const back=page.getByRole('button',{name:'← Back to report',exact:true});
    assert.equal(await back.isVisible(),false,'No return action before opening report evidence');
    const position=async source=>{
      await source.evaluate(node=>node.scrollIntoView({block:'center'}));
      return source.evaluate(node=>({top:node.getBoundingClientRect().top,y:window.scrollY}));
    };
    const restored=async(source,before)=>{
      await page.waitForFunction(()=>!document.querySelector('#reports').hidden);
      const after=await source.evaluate(node=>({top:node.getBoundingClientRect().top,y:window.scrollY,focused:document.activeElement===node}));
      assert.ok(Math.abs(after.top-before.top)<=2,'Returns clicked link to its original viewport position');
      assert.ok(Math.abs(after.y-before.y)<=2,'Restores deep report scroll position');
      assert.ok(after.focused,'Keyboard focus returns to the clicked source');
      assert.equal(await back.isVisible(),false);
    };
    let before=await position(link);
    assert.ok(before.y>3000,'Fixture starts deep in the report');
    await link.click();
    await back.waitFor({state:'visible'});
    assert.ok(await back.evaluate(node=>document.activeElement===node),'Return action receives keyboard focus');
    assert.match(await page.locator('#artifactView').innerText(),/"index": 7/);
    assert.ok((await back.boundingBox()).y>=0,'Return action is in the viewport');
    await page.getByRole('button',{name:'Read next chunk'}).click();
    await page.waitForFunction(()=>document.querySelector('#more').hidden);
    await page.evaluate(()=>window.scrollTo(0,document.body.scrollHeight));
    assert.ok((await back.boundingBox()).y>=0,'Return action stays visible while reading evidence');
    if(process.env.WORKBENCH_REPORT_RETURN_SCREENSHOT)await page.screenshot({path:process.env.WORKBENCH_REPORT_RETURN_SCREENSHOT});
    await back.focus();await page.keyboard.press('Enter');
    await restored(link,before);

    before=await position(link);await link.focus();await page.keyboard.press('Enter');
    await back.waitFor({state:'visible'});
    await page.waitForTimeout(1700); // Background state polling must preserve the return location.
    await page.getByRole('button',{name:'Reports',exact:true}).click();
    await restored(link,before);

    await page.setViewportSize({width:390,height:844});
    before=await position(link);await link.click();await back.waitFor({state:'visible'});
    assert.ok((await back.boundingBox()).x>=0,'Return action fits a narrow viewport');
    await back.click();await restored(link,before);
    await page.setViewportSize({width:1400,height:900});

    const saved=page.locator('#reportView').getByRole('link',{name:'Saved result',exact:true});
    before=await position(saved);await saved.click();await back.waitFor({state:'visible'});
    await back.click();await restored(saved,before);

    await page.getByRole('button',{name:'Inspect evidence citations'}).click();
    await page.getByRole('button',{name:'F5 · synthetic-source · valid'}).click();
    const raw=page.getByRole('button',{name:'Open supporting artifact'});
    before=await position(raw);await raw.click();await back.waitFor({state:'visible'});
    await back.click();await restored(raw,before);

    await link.click();await back.waitFor({state:'visible'});
    await page.locator('#cases button').filter({hasText:'Synthetic B'}).click();
    assert.equal(await back.isVisible(),false,'A case switch clears the old report return action');
    await page.getByRole('button',{name:'Reports',exact:true}).click();
    await page.waitForFunction(()=>document.querySelector('#reportView').textContent.includes('End of synthetic report.'));
    delayCitation=true;
    await link.click();await page.waitForFunction(()=>document.querySelector('#reports').hidden===false);
    while(!releaseCitation)await page.waitForTimeout(10);
    await page.getByRole('button',{name:'Case conversation',exact:true}).click();
    releaseCitation();await page.waitForTimeout(100);
    assert.equal(await page.locator('#conversation').isVisible(),true,'A delayed citation cannot override newer navigation');
    assert.equal(await back.isVisible(),false);
    assert.deepEqual(errors,[]);
    assert.ok(!calls.some(p=>/jobs|coverage|stop|pick/.test(p)));
    console.log('Report return: exact deep scroll and focus; keyboard; Reports tab; sticky action; artifact pagination; saved-result and citation-panel links; case switch; stale request; zero work submissions.');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
