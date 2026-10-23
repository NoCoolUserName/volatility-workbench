// Offline reference-terminal presentation check. All output and requests are synthetic.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const assets=path.join(__dirname,'../src/volatility_workbench/static');
const csp="default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'";
const editions=[
 ['fallout-3-robco','Fallout 3 (RobCo Night) 1','fallout-3-robco-2','Fallout 3 (RobCo Night) 2'],
 ['fallout-3-vault-112','Fallout 3 (Vault 112) 1','fallout-3-vault-112-2','Fallout 3 (Vault 112) 2'],
 ['fallout-new-vegas','Fallout: New Vegas 1','fallout-new-vegas-2','Fallout: New Vegas 2']
];
const state={cases:[{id:'reference-fixture',title:'Synthetic reference terminal',created_at:'2026-10-18T00:00:00Z',images:[],coins:[],readiness:{status:'Unchecked',reasons:[]},reports:[],messages:[],activity:[]}],
 jobs:[{id:'synthetic-job',case_id:'reference-fixture',kind:'update',status:'running',progress:'synthetic_saved_context',started_at:'2026-10-18T00:00:00Z'}],approvals:[],account:{},evidence_root:'/synthetic',
 live_console:{job_id:'synthetic-job',case_id:'reference-fixture',earlier_entries:0,entries:[{id:'1',time:'2026-10-18T00:00:00Z',text:'Live synthetic HTML output\n<img src=x onerror="window.injected=true">\nNo analysis was requested.'}]}};
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.WORKBENCH_BROWSER_EXECUTABLE?{executablePath:process.env.WORKBENCH_BROWSER_EXECUTABLE}:{})});
 try{
  const page=await browser.newPage({viewport:{width:1400,height:1000}}),errors=[],requests=[];
  await page.addInitScript(()=>{window.EventSource=class extends EventTarget{close(){}};Date.now=()=>Date.parse('2026-10-18T00:01:00Z');});
  page.on('pageerror',error=>errors.push(error.message));
  await page.route('**/*',route=>{
   const url=new URL(route.request().url());requests.push({url:url.href,method:route.request().method()});
   assert.equal(url.origin,'http://localhost','Reference terminals never request external resources');
   assert.equal(route.request().method(),'GET','Presentation changes never start analysis or mutate cases');
   if(url.pathname==='/api/settings/zoom')return route.fulfill({json:{schema:'zoom/1',percent:100}});
   if(url.pathname==='/api/state')return route.fulfill({json:state});
   if(url.pathname==='/api/artifacts')return route.fulfill({json:{files:[],truncated:false}});
   if(url.pathname==='/api/report-console')return route.fulfill({json:null});
   assert.ok(!url.pathname.startsWith('/api/'),'Unexpected action '+url.pathname);
   const name=url.pathname==='/'?'index.html':url.pathname.slice(1);
   assert.ok(!name.includes('..'),'Only packaged local assets are requested');
   return route.fulfill({body:fs.readFileSync(path.join(assets,name)),headers:{'content-security-policy':csp},contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':name.endsWith('.png')?'image/png':name.endsWith('.svg')?'image/svg+xml':'text/html'});
  });
  await page.goto('http://localhost/');await page.locator('#liveConsole').waitFor();
  const arrowRatio=await page.locator('.report-console-arrow').evaluate(node=>parseFloat(getComputedStyle(node).fontSize)/parseFloat(getComputedStyle(document.querySelector('#toggleReportConsole')).fontSize));
  assert.ok(arrowRatio>=1.15&&arrowRatio<=1.25,'The Report console arrow is about 20% larger than its original inherited size');
  const catalog=await page.evaluate(()=>WorkbenchThemes.catalog);
  assert.equal(catalog.length,37);assert.equal(catalog.filter(theme=>theme.group==='Fallout').length,18);
  for(const [original,label,reference,referenceLabel] of editions){
   for(const [id,text] of [[original,label],[reference,referenceLabel]]){
    assert.equal(catalog.find(theme=>theme.id===id)?.label,text,'Both numbered choices retain their stable preference IDs');
    assert.equal(await page.locator('#theme option[value="'+id+'"]').textContent(),text);
   }
   assert.equal(catalog.find(theme=>theme.id===reference).scene,null,'Reference art belongs to the monitor bezel');
   await page.evaluate(id=>WorkbenchThemes.apply(id,true),original);await page.reload();
   assert.equal(await page.locator('html').getAttribute('data-theme'),original,'An original saved ID still restores edition 1');
  }
  async function checkMenu(label){
   const button=page.locator('#toggleTheme'),menu=page.locator('#themeMenu');
   const before=await button.evaluate(node=>{const s=getComputedStyle(node);return [s.backgroundColor,s.backgroundImage,s.boxShadow,s.color,s.borderColor].join('|');});
   await button.click();assert.equal(await button.getAttribute('aria-expanded'),'true');assert.equal(await menu.isVisible(),true);
   const after=await button.evaluate(node=>{const s=getComputedStyle(node);return [s.backgroundColor,s.backgroundImage,s.boxShadow,s.color,s.borderColor].join('|');});
   assert.notEqual(after,before,label+' visibly identifies the raised menu');
   assert.ok(await menu.evaluate(node=>{
    const box=node.getBoundingClientRect(),points=[[.1,.1],[.5,.5],[.9,.9]];
    return points.every(([x,y])=>{const px=box.left+box.width*x,py=box.top+box.height*y;if(px<0||px>=innerWidth||py<0||py>=innerHeight)return false;const element=document.elementFromPoint(px,py);return element===node||node.contains(element);});
   }),label+' keeps the full menu above adjacent page layers');
   await page.keyboard.press('Escape');assert.equal(await menu.isHidden(),true);assert.equal(await button.getAttribute('aria-expanded'),'false');
   assert.equal(await button.evaluate(node=>document.activeElement===node),true,'Escape returns menu focus');
  }
  const zoom=page.locator('#consoleZoom'),pre=page.locator('#liveConsole'),expand=page.locator('#expandConsole');
  await pre.evaluate(node=>{window.referenceLiveNode=node;});
  for(const edition of editions.flatMap(([original,,reference])=>[original,reference])){
   await page.evaluate(id=>WorkbenchThemes.apply(id),edition);await expand.click();await zoom.waitFor();
   await page.evaluate(()=>Adventure.launch({edition:'select'}));
   assert.equal(await page.locator('#adventureMenu').isVisible(),true,edition+' retains the Adventure chooser');
   for(const id of ['adventure1977','adventureNew1977','adventure1995','adventureNew1995'])assert.equal(await page.locator('#'+id).isVisible(),true);
   assert.equal(await page.locator('#fieldAdventure1977,#fieldAdventure1995').evaluateAll(nodes=>nodes.every(node=>!node.getClientRects().length)),true,'Field Terminal knobs remain confined to their original theme');
   await page.locator('#adventureExit').click();await page.locator('#consoleOutputMode').click();
   await page.keyboard.press('Escape');await page.waitForFunction(()=>!document.querySelector('#consoleZoom').open);
  }
  for(const [, ,id] of editions){
   await page.evaluate(id=>WorkbenchThemes.apply(id),id);
   if(id==='fallout-new-vegas-2'){
    for(const selector of ['#fieldConsoleCollapse','#consoleVolshellMode']){
     const background=await page.locator(selector).evaluate(node=>getComputedStyle(node).backgroundImage);
     assert.ok(!background.includes('radial-gradient'),'New Vegas '+selector+' has no decorative bulb');
    }
    assert.equal(await page.locator('#consoleVolshellMode .volshell-led').count(),1,'VolShell retains its rectangular connection LED');
   }
   const viewports=[[1400,1000,1],[900,600,1],[390,844,1],[320,844,2]];
   if(id==='fallout-3-robco-2')viewports.push([1200,800,1],[1400,1000,2]);
   for(const [width,height,scale] of viewports){
    const label=`${id} ${width}x${height} ${scale*100}% text`;
    await page.setViewportSize({width,height});
    await page.evaluate(scale=>{document.documentElement.style.setProperty('--text-scale',String(scale));document.documentElement.dataset.textScaled=String(scale!==1);},scale);
    await checkMenu(label);
    await expand.click();await zoom.waitFor();
    assert.equal(await pre.evaluate(node=>node===window.referenceLiveNode),true,label+' reuses live HTML output');
    assert.match(await pre.textContent(),/Live synthetic HTML output/);assert.equal(await pre.locator('img,script').count(),0);assert.equal(await page.evaluate(()=>window.injected),undefined);
    const geometry=await page.evaluate(()=>{
     const box=node=>{const r=node.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width,height:r.height};},monitor=document.querySelector('.crt-monitor'),screen=document.querySelector('.crt-screen'),chin=document.querySelector('.crt-chin'),pseudo=getComputedStyle(monitor,'::before');
     const controls=[...document.querySelectorAll('#consoleOutputMode,#consoleVolshellMode,.crt-power')].filter(node=>node.getClientRects().length).map(node=>{
      const text=node.id==='consoleVolshellMode'?[...node.childNodes].find(child=>child.nodeType===Node.TEXT_NODE&&child.textContent.trim()):node.id==='consoleOutputMode'?node.firstChild:node.querySelector('#consolePowerText');
      const range=document.createRange();range.selectNodeContents(text);const label=range.getBoundingClientRect(),r=box(node),style=getComputedStyle(node);
      return {id:node.id||'power',...r,labelCenter:label.left+label.width/2,paddingTop:parseFloat(style.paddingTop),paddingBottom:parseFloat(style.paddingBottom),font:parseFloat(style.fontSize)};
     });
     const collapse=document.querySelector('#fieldConsoleCollapse'),fallback=[...document.querySelectorAll('.crt-screen button')].filter(node=>node.getClientRects().length&&/Collapse/.test(node.textContent));
     const modeStyle=getComputedStyle(document.querySelector('.crt-mode-controls')),rootStyle=getComputedStyle(document.documentElement);
     return {frame:box(document.querySelector('#consoleZoom')),monitor:box(monitor),screen:box(screen),output:box(document.querySelector('#liveConsole')),chin:box(chin),aspect:Number(rootStyle.getPropertyValue('--reference-aspect')),controlCenter:parseFloat(rootStyle.getPropertyValue('--reference-control-center'))/100,controlPosition:modeStyle.position,direction:modeStyle.flexDirection,image:pseudo.backgroundImage,artLayer:Number(pseudo.zIndex),controlLayer:Number(getComputedStyle(chin).zIndex),controls,sharedCollapse:collapse.getClientRects().length?box(collapse):null,fallback:fallback.map(box),overflow:document.documentElement.scrollWidth>innerWidth};
    });
    if(process.env.WORKBENCH_REFERENCE_SCREENSHOTS){
     fs.mkdirSync(process.env.WORKBENCH_REFERENCE_SCREENSHOTS,{recursive:true});
     const name=path.join(process.env.WORKBENCH_REFERENCE_SCREENSHOTS,`${id}-${width}-${scale*100}`);
     await page.screenshot({path:name+'.png'});fs.writeFileSync(name+'.json',JSON.stringify(geometry,null,2)+'\n');
    }
    assert.equal(geometry.overflow,false,label+' has no page overflow');
    assert.ok(geometry.image.includes('url('),label+' renders packaged reference artwork');
    const art=await page.evaluate(async image=>{
     const url=image.match(/url\(["']?([^"')]+)["']?\)/)?.[1];if(!url)throw Error('Missing bezel URL');
     const imageNode=new Image();imageNode.src=url;await imageNode.decode();
     const canvas=document.createElement('canvas');canvas.width=imageNode.naturalWidth;canvas.height=imageNode.naturalHeight;const context=canvas.getContext('2d');context.drawImage(imageNode,0,0);
     const monitor=document.querySelector('.crt-monitor').getBoundingClientRect(),screen=document.querySelector('.crt-screen').getBoundingClientRect(),x=Math.round(((screen.left+screen.right)/2-monitor.left)/monitor.width*canvas.width),y=Math.round(((screen.top+screen.bottom)/2-monitor.top)/monitor.height*canvas.height);
     const centerAlpha=context.getImageData(x,y,1,1).data[3],pixels=context.getImageData(0,0,canvas.width,canvas.height).data;
     let top=canvas.height,bottom=0;
     for(let index=3;index<pixels.length;index+=4)if(pixels[index]>128){const row=Math.floor((index-3)/4/canvas.width);top=Math.min(top,row);bottom=Math.max(bottom,row+1);}
     return {url,width:canvas.width,height:canvas.height,centerAlpha,visibleTop:top,visibleBottom:bottom};
    },geometry.image);
    assert.equal(new URL(art.url).origin,'http://localhost');assert.ok(fs.existsSync(path.join(assets,new URL(art.url).pathname.slice(1))));
    assert.ok(Math.abs(geometry.aspect-art.width/art.height)<.00001,label+' derives its CSS aspect from the packaged art');
    assert.ok(Math.abs(geometry.frame.width/geometry.frame.height-art.width/art.height)<.002,label+' preserves the reference frame aspect ratio');
    if(id==='fallout-3-robco-2'){
     assert.ok(Math.abs(geometry.monitor.top+geometry.monitor.height*art.visibleTop/art.height)<1,label+' puts the visible painted top edge at the viewport top');
     assert.ok(Math.abs(geometry.monitor.top+geometry.monitor.height*art.visibleBottom/art.height-height)<1,label+' puts the visible painted bottom edge at the viewport bottom');
    }else assert.ok(Math.abs(geometry.frame.top)<1&&Math.abs(geometry.frame.bottom-height)<1,label+' fills the viewport from top to bottom');
    assert.equal(art.centerAlpha,0,label+' leaves the live HTML behind the transparent glass opening');
    assert.ok(geometry.screen.left>=-1&&geometry.screen.right<=width+1&&geometry.screen.top>=-1&&geometry.screen.bottom<=height+1,label+' keeps live text reachable');
    assert.ok(Math.min(geometry.output.bottom,geometry.screen.bottom)-Math.max(geometry.output.top,geometry.screen.top)>=24,label+' keeps actual live output visible inside the glass');
    assert.ok(geometry.controlLayer>geometry.artLayer,label+' places controls above the art');
    assert.equal(geometry.controls.length,3,label+' shows Output, VolShell and status');
    const modeControls=geometry.controls.filter(control=>control.id!=='power');
    if(id==='fallout-3-robco-2'&&width>700)assert.equal(geometry.direction,'column',label+' always keeps the desktop buttons stacked on the right');
    for(const control of geometry.controls){
     assert.ok(control.left>=-1&&control.right<=width+1&&control.top>=0&&control.bottom<=height+1,label+' '+control.id+' stays reachable');
     assert.ok(Math.abs(control.labelCenter-control.left-control.width/2)<1.5,label+' '+control.id+' centers its own label');
     assert.ok(control.bottom<=geometry.screen.top+1||control.top>=geometry.screen.bottom-1||control.right<=geometry.screen.left+1||control.left>=geometry.screen.right-1,label+' '+control.id+' stays on the bezel');
    }
    for(const control of modeControls){
     // RobCo's narrow physical button reserves a separate row for its LED.
     if(id==='fallout-3-robco-2'&&geometry.direction==='column'&&control.id==='consoleVolshellMode')continue;
     assert.ok(control.paddingTop+control.paddingBottom<=control.font*1.1,label+' keeps mode button padding compact');
    }
    if(id==='fallout-3-robco-2'&&geometry.direction==='column'){
     assert.ok(modeControls.every(control=>control.left>=geometry.screen.right-1),label+' puts stacked RobCo controls on the right bezel rim');
     assert.ok(modeControls[1].top>=modeControls[0].bottom-1,label+' stacks Output above VolShell');
     assert.ok(Math.abs(modeControls[0].left+modeControls[0].width/2-modeControls[1].left-modeControls[1].width/2)<1,label+' aligns the stack');
     assert.ok(geometry.sharedCollapse.top>=geometry.monitor.top+geometry.monitor.height*.6,label+' keeps Collapse on the lower-right bezel');
     assert.ok(Math.abs(modeControls[0].top-geometry.sharedCollapse.bottom-6)<1,label+' groups Collapse directly above Output');
     const status=geometry.controls.find(control=>control.id==='power');
     assert.ok(Math.abs(status.top-modeControls[1].bottom-6)<1,label+' groups Saved directly below VolShell');
     // Independently measured usable metal in the 1536x1024 source image.
     // Keep the full outline inside it, rather than testing only outside-glass placement.
     for(const selector of ['#fieldConsoleCollapse','#consoleOutputMode','#consoleVolshellMode','.crt-power']){
      const node=page.locator(selector);if(selector!=='.crt-power')await node.focus();
      const bounds=await node.evaluate(element=>{const r=element.getBoundingClientRect(),style=getComputedStyle(element),outset=element.matches(':focus-visible')?Math.max(0,parseFloat(style.outlineWidth)+parseFloat(style.outlineOffset)):0;const text=[...element.childNodes].find(child=>child.nodeType===Node.TEXT_NODE&&child.textContent.trim())||element.querySelector('#consolePowerText');const range=document.createRange();range.selectNodeContents(text);const label=range.getBoundingClientRect();return {left:r.left-outset,right:r.right+outset,top:r.top-outset,bottom:r.bottom+outset,singleLine:range.getClientRects().length===1,labelFits:label.left>=r.left&&label.right<=r.right};});
      const source={left:(bounds.left-geometry.monitor.left)/geometry.monitor.width*1536,right:(bounds.right-geometry.monitor.left)/geometry.monitor.width*1536,top:(bounds.top-geometry.monitor.top)/geometry.monitor.height*1024,bottom:(bounds.bottom-geometry.monitor.top)/geometry.monitor.height*1024};
      assert.ok(source.left>=1290&&source.right<=1410&&source.top>=680&&source.bottom<=930,label+' '+selector+' including focus fits the actual lower-right metal strip: '+JSON.stringify(source));
      assert.ok(bounds.singleLine&&bounds.labelFits,label+' '+selector+' keeps its whole label on one line inside the button');
     }
    }else{
     const groupLeft=Math.min(...modeControls.map(control=>control.left)),groupRight=Math.max(...modeControls.map(control=>control.right));
     const center=id==='fallout-3-vault-112-2'&&geometry.controlPosition==='absolute'?geometry.monitor.left+geometry.monitor.width*geometry.controlCenter:width/2;
     assert.ok(Math.abs((groupLeft+groupRight)/2-center)<2,label+' centers the Output/VolShell button group on its vent or responsive footer');
    }
    if(geometry.sharedCollapse){
     const collapse=geometry.sharedCollapse;assert.ok(collapse.left>=0&&collapse.right<=width&&collapse.top>=0&&collapse.bottom<=height,label+' exposes shared Collapse');
     assert.ok(collapse.bottom<=geometry.screen.top+1||collapse.top>=geometry.screen.bottom-1||collapse.right<=geometry.screen.left+1||collapse.left>=geometry.screen.right-1,label+' places shared Collapse outside the glass');
    }else assert.ok(geometry.fallback.some(control=>control.left>=0&&control.right<=width&&control.top>=geometry.screen.top&&control.bottom<=geometry.screen.bottom),label+' provides a reachable Collapse fallback');
    if(id==='fallout-3-vault-112-2'&&geometry.controlPosition==='absolute'){
     const [output,shell]=modeControls;
     assert.ok(Math.abs(output.left-geometry.monitor.left-geometry.monitor.width*.31)<1,label+' places Output immediately after the left screw');
     assert.ok(Math.abs(shell.right-geometry.monitor.left-geometry.monitor.width*.555)<1,label+' places VolShell immediately before the right screw');
     assert.ok(shell.left>=output.right,label+' leaves the vent only in the gap between the buttons');
     assert.ok(output.top<=geometry.monitor.top+geometry.monitor.height*.902&&output.bottom>=geometry.monitor.top+geometry.monitor.height*.945,label+' covers vent slits above and below Output');
    }
    if(id==='fallout-3-vault-112-2'){
     assert.ok(geometry.sharedCollapse,label+' exposes the amber power button as Collapse');
     assert.ok(geometry.sharedCollapse.width>=44&&geometry.sharedCollapse.height>=44,label+' provides a 44px power-button target');
     assert.match(await page.locator('#fieldConsoleCollapse').getAttribute('aria-label'),/Collapse/i);
     assert.match(await page.locator('#fieldConsoleCollapse').getAttribute('title'),/Collapse/i);
    }
    await page.locator('#consoleOutputMode').focus();await page.keyboard.press('Tab');
    assert.equal(await page.locator('#consoleVolshellMode').evaluate(node=>document.activeElement===node&&getComputedStyle(node).outlineStyle==='solid'),true,label+' retains visible keyboard focus');
    const collapse=geometry.sharedCollapse?page.locator('#fieldConsoleCollapse'):expand;
    await collapse.focus();assert.equal(await collapse.evaluate(node=>getComputedStyle(node).outlineStyle),'solid',label+' gives Collapse visible keyboard focus');
    if(id==='fallout-3-vault-112-2'&&width===1400){
     const feedback=()=>collapse.evaluate(node=>{const style=getComputedStyle(node);return ['transform','filter','boxShadow','backgroundImage','backgroundColor','opacity'].map(name=>style[name]).join('|');});
     const resting=await feedback(),button=await collapse.boundingBox();
     await page.mouse.move(button.x+button.width/2,button.y+button.height/2);await page.mouse.down();
     assert.notEqual(await feedback(),resting,'The amber power Collapse button gives visible press feedback');
     await page.mouse.up();await page.waitForFunction(()=>!document.querySelector('#consoleZoom').open);
     await expand.click();await zoom.waitFor();await collapse.focus();
    }
    await page.keyboard.press('Enter');await page.waitForFunction(()=>!document.querySelector('#consoleZoom').open);
   }
  }
  assert.deepEqual(errors,[]);assert.ok(requests.every(request=>request.method==='GET'));
  console.log('Reference terminals: six numbered choices, original preference IDs and Adventure choosers; three local transparent frames, preserved aspect ratios and live HTML; compact centered labels, right-stacked RobCo controls, bezel status, reachable Collapse/focus; raised Theme menus above page layers at desktop, short desktop, mobile and 200% text. Zero analysis, mutation or external requests.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
