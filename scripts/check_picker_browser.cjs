// Optional offline browser check; synthetic picker responses, no native dialog.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const assets=path.join(__dirname,'../src/volatility_workbench/static');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.WORKBENCH_BROWSER_EXECUTABLE?{executablePath:process.env.WORKBENCH_BROWSER_EXECUTABLE}:{})});
 try{
  const page=await browser.newPage();let mode='cancel';const calls=[],errors=[],browseRequests=[];
  const locations=[{path:'/synthetic',default:true},{path:'/Other disk',default:false}];
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('http://workbench.test/**',route=>{
   const url=new URL(route.request().url());
   if(url.pathname.startsWith('/api/')){
    calls.push(url.pathname);
    if(url.pathname==='/api/state')return route.fulfill({json:{cases:[],jobs:[],approvals:[],account:{},evidence_root:'/synthetic',native_picker:true}});
    if(url.pathname==='/api/browse'){
     const root=url.searchParams.get('location')||'/synthetic';const relative=url.searchParams.get('path')||'';
     browseRequests.push({root,relative});assert.ok(locations.some(x=>x.path===root));
     const entries=root==='/synthetic'?[]:relative?[{name:'another.mem',relative:'nested/another.mem',path:'/Other disk/nested/another.mem',directory:false}]:[{name:'nested',relative:'nested',path:'/Other disk/nested',directory:true}];
     return route.fulfill({json:{root,relative,locations,entries,limit:500}});
    }
    if(url.pathname==='/api/pick'){
     if(mode==='cancel')return route.fulfill({json:{paths:[],cancelled:true}});
     if(mode==='success')return route.fulfill({json:{paths:['/synthetic/Other disk/capture.mem'],cancelled:false}});
     return route.fulfill({status:400,json:{error:'Could not open the file chooser. Enter image paths directly or use Browse folder.'}});
    }
    throw Error('Unexpected action '+url.pathname);
   }
   const name=url.pathname==='/'?'index.html':url.pathname.slice(1);
   return route.fulfill({body:fs.readFileSync(path.join(assets,name)),contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html'});
  });
  await page.goto('http://workbench.test/');
  await page.getByText('Add evidence',{exact:true}).click();
  await page.locator('#paths').fill('/synthetic/typed-before-cancel.mem');
  await Promise.all([page.waitForResponse(r=>r.url().endsWith('/api/pick')),page.locator('#pick').click()]);
  assert.equal(await page.locator('#error').isVisible(),false);
  assert.equal(await page.locator('#paths').inputValue(),'/synthetic/typed-before-cancel.mem');
  mode='success';await page.locator('#pick').click();
  await page.waitForFunction(()=>document.querySelector('#paths').value==='/synthetic/Other disk/capture.mem');
  mode='failure';await page.locator('#pick').click();
  await page.waitForFunction(()=>!document.querySelector('#error').hidden);
  assert.match(await page.locator('#error').innerText(),/Enter image paths directly/);
  assert.equal(await page.locator('#paths').inputValue(),'/synthetic/Other disk/capture.mem');
  mode='cancel';await page.locator('#pick').click();
  await page.waitForFunction(()=>document.querySelector('#error').hidden);
  assert.equal(await page.locator('#paths').inputValue(),'/synthetic/Other disk/capture.mem');
  await page.locator('#browse').click();
  const folders=page.getByRole('combobox',{name:'Browse evidence location'});
  await folders.selectOption('/Other disk');
  await page.getByRole('button',{name:'▸ nested',exact:true}).click();
  await page.getByRole('button',{name:'+ another.mem',exact:true}).click();
  assert.match(await page.locator('#paths').inputValue(),/Other disk\/nested\/another.mem/);
  assert.equal(await folders.inputValue(),'/Other disk');
  assert.deepEqual(browseRequests,[{root:'/synthetic',relative:''},{root:'/Other disk',relative:''},{root:'/Other disk',relative:'nested'}]);
  assert.ok(!calls.some(x=>/jobs|cases|stop/.test(x)));
  assert.deepEqual(errors,[]);
  console.log('Picker browser: Cancel is silent and preserves input; success replaces selection; real failures stay actionable; registered-folder browsing/navigation works; zero case/job submissions.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
