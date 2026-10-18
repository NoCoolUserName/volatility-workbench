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
  readiness:{status:'Ready',checked_at:'2026-10-18T12:00:00Z',reasons:['Synthetic readiness fixture']},
  reports:[{id:'synthetic-report',status:'sealed',created_at:'2026-10-18T12:01:00Z'}],
  messages:[],activity:[]}],jobs:[],approvals:[],account:{},evidence_root:'/synthetic/evidence'};

(async()=>{
  const browser=await chromium.launch({headless:true,...(process.env.WORKBENCH_BROWSER_EXECUTABLE?{executablePath:process.env.WORKBENCH_BROWSER_EXECUTABLE}:{})});
  try{
    const page=await browser.newPage({viewport:{width:1400,height:900}});
    const calls=[],errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.route('http://workbench.test/**',route=>{
      const u=new URL(route.request().url());
      if(u.pathname.startsWith('/api/')){
        calls.push(u.pathname);
        if(u.pathname==='/api/state')return route.fulfill({json:state});
        if(u.pathname==='/api/file')return route.fulfill({json:{text:'# Synthetic report\n![Decorative coin for Synthetic coin](assets/coins/'+ 'a'.repeat(64)+'.png)\n## Finding\nFixture only.',truncated:false}});
        if(u.pathname==='/api/coin')return route.fulfill({body:Buffer.from(coin.split(',')[1],'base64'),contentType:'image/png'});
        if(u.pathname==='/api/artifacts')return route.fulfill({json:{files:[],truncated:false}});
        throw Error('Unexpected action: '+u.pathname);
      }
      const name=u.pathname==='/'?'index.html':u.pathname.slice(1);
      return route.fulfill({body:fs.readFileSync(path.join(assets,name)),contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html'});
    });
    await page.goto('http://workbench.test/');
    await page.waitForFunction(()=>document.querySelector('#caseTitle').textContent==='Synthetic XP case' && document.querySelector('#reportView .challenge-coin'));
    const title=await page.locator('#caseTitle').boundingBox(),ready=await page.locator('#ready').boundingBox();
    assert.ok(ready.y>=title.y+title.height,'Ready must sit below case title');
    assert.match(await page.locator('#readyDetails').innerText(),/Last checked .* image access and SHA-256 verified then/);
    assert.match(await page.locator('#images').innerText(),/example\.vmem.*4,096 bytes · SHA-256 a+/s);
    assert.equal(await page.locator('#images .challenge-coin').count(),0);
    assert.equal(await page.locator('#reportView .challenge-coin').count(),1);
    assert.equal(await page.locator('#images .image').evaluate(e=>getComputedStyle(e).borderTopWidth),'0px');
    assert.equal(await page.locator('#images .image').evaluate(e=>getComputedStyle(e).backgroundColor),'rgba(0, 0, 0, 0)');
    if(process.env.WORKBENCH_BROWSER_SCREENSHOT)await page.screenshot({path:process.env.WORKBENCH_BROWSER_SCREENSHOT,fullPage:true});
    await page.waitForTimeout(1650);
    assert.equal(await page.locator('#images .challenge-coin').count(),0);
    assert.equal(await page.locator('#reportView .challenge-coin').count(),1);
    assert.deepEqual(errors,[]);
    assert.ok(!calls.some(x=>/jobs|readiness|stop|plugins/.test(x)));
    console.log('Case header: saved Ready under title, unboxed path/hash, no header coin, report coin retained through refresh; zero analysis actions.');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
