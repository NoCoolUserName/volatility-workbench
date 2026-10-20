// Entirely offline visual/interaction check: synthetic case/report, no analysis.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const csp="default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'";
const assets=path.join(__dirname,'../src/volatility_workbench/static');
const state={cases:[{id:'theme-fixture',title:'Synthetic theme review',created_at:'2026-10-18T00:00:00Z',
  images:[{id:'E001',path:'/synthetic/example.vmem',size_bytes:4096,sha256:'a'.repeat(64)}],coins:[],
  readiness:{status:'Unchecked',reasons:['Synthetic fixture only']},reports:[{id:'sample-report',status:'sealed',created_at:'2026-10-18T01:00:00Z'}],messages:[],activity:[]}],
  jobs:[],approvals:[],account:{},evidence_root:'/synthetic'};
const settings={config:{evidence_root:'/synthetic',output_root:'/synthetic/output',vol_python:'/synthetic/python'},state_dir:'/synthetic/state',has_cases:true,
  evidence_locations:[],symbols:{directory:'/synthetic/symbols',cache:'/synthetic/cache',matching:'Synthetic only',profile:{packs:[],macos_status:'Synthetic'}},
  provider:{default_provider:{provider:'codex'},cases:[]},operation:{status:'idle'},readiness:{status:'Unchecked',reasons:[]}};
const plugins={plugins:[{name:'windows.synthetic.Example',description:'Harmless synthetic table entry',target_os:'windows',plugin_version:[1,0,0],source:{kind:'native',label:'Synthetic source'}}],total:1,volatility_version:'SYNTHETIC',architecture:'fixture',import_failures:[]};
(async()=>{
  const browser=await chromium.launch({headless:true,...(process.env.WORKBENCH_BROWSER_EXECUTABLE?{executablePath:process.env.WORKBENCH_BROWSER_EXECUTABLE}:{})});
  try{
    const page=await browser.newPage({viewport:{width:1400,height:1050}});
    await page.addInitScript(()=>{window.EventSource=class extends EventTarget {close(){}};});
    async function chooseTheme(id){
      if(await page.locator('#theme').isHidden())await page.locator('#toggleTheme').click();
      await page.locator('#theme').selectOption(id);
    }
    async function presentationStyles(){
      return page.locator('body, body > header, .layout, .layout > aside, .layout > main, #toggleTheme').evaluateAll(elements=>elements.map(element=>{
        const style=getComputedStyle(element);
        return Object.fromEntries(['backgroundColor','backgroundImage','borderTopWidth','borderRadius','boxShadow','fontFamily','color'].map(name=>[name,style[name]]));
      }));
    }
    async function noPageOverflow(label){
      const overflow=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,
        elements:[...document.querySelectorAll('body *')].filter(element=>{const box=element.getBoundingClientRect();return box.width&&box.right>innerWidth+1;}).slice(0,8).map(element=>({tag:element.tagName,id:element.id,className:element.className,width:element.getBoundingClientRect().width,right:element.getBoundingClientRect().right}))}));
      if(overflow.scrollWidth>overflow.width&&screenshotDir)await page.screenshot({path:path.join(screenshotDir,'overflow-'+label.replace(/\W+/g,'-')+'.png'),fullPage:true});
      assert.ok(overflow.scrollWidth<=overflow.width,label+' must not overflow horizontally: '+JSON.stringify(overflow));
    }
    async function headerNoOverlap(label){
      assert.ok(await page.locator('body > header').evaluate(header=>{
        const settings=header.querySelector('.settings-link').getBoundingClientRect();
        return [...header.querySelectorAll('.eyebrow,h1')].every(element=>{const text=element.getBoundingClientRect();
          return settings.left>=text.right||settings.right<=text.left||settings.top>=text.bottom||settings.bottom<=text.top;
        });
      }),label+' Settings link must not cover the title or eyebrow');
    }
    const errors=[],network=[],policyErrors=[];
    page.on('console',message=>{if(/Content Security Policy|violates the following/.test(message.text()))policyErrors.push(message.text());});
    page.on('pageerror',e=>errors.push(e.message));
    await page.route('**/*',route=>{
      if (new URL(route.request().url()).pathname === '/api/settings/zoom') return route.fulfill({json:{schema:'zoom/1',percent:100}});
      const u=new URL(route.request().url()); network.push(u.href);
      assert.equal(u.origin,'http://localhost','No external request allowed');
      if(u.pathname.startsWith('/api/')){
        assert.equal(route.request().method(),'GET','Theme changes must never mutate cases or submit jobs');
        if(u.pathname==='/api/state')return route.fulfill({json:state});
        if(u.pathname==='/api/settings')return route.fulfill({json:settings});
        if(u.pathname==='/api/plugins')return route.fulfill({json:plugins});
        if(u.pathname==='/api/artifacts')return route.fulfill({json:{files:[],truncated:false}});
        if(u.pathname==='/api/report-plugins')return route.fulfill({json:{schema:'report-plugin-inventory/1',report_id:u.searchParams.get('report'),scope:'bundled_saved_runs',source_status:'unavailable',summary:{executions:null,plugins:null,failures:null,reuse_receipts:null,request_failures:null},entries:[],next_offset:null,warnings:['Inventory metadata is absent from this synthetic presentation fixture.']}});
        if(u.pathname==='/api/file')return route.fulfill({json:{text:'# Synthetic report\n\n## Observation\n\nHarmless fixture only.\n\n```\nPID   Process        Result\n123   fixture.exe    Review required\n```',truncated:false}});
        throw Error('Unexpected API '+u.pathname);
      }
      const name=u.pathname==='/'?'index.html':u.pathname.slice(1);
      return route.fulfill({body:fs.readFileSync(path.join(assets,name)),headers:{'content-security-policy':csp},contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':name.endsWith('.png')?'image/png':name.endsWith('.svg')?'image/svg+xml':'text/html'});
    });
    await page.goto('http://localhost/');
    await page.waitForFunction(()=>document.querySelector('.report-version.selected'));
    assert.equal(await page.locator('html').getAttribute('data-theme'),'matrix');
    assert.equal(await page.locator('#theme').inputValue(),'matrix');
    assert.deepEqual(await page.locator('html').evaluate(element=>{
      const style=getComputedStyle(element);return Object.fromEntries(['bg','panel','control-bg','text','muted','accent','privacy-bg','privacy-text','code-bg'].map(name=>[name,style.getPropertyValue('--'+name).trim()]));
    }),{'bg':'#0d1418','panel':'#141f25','control-bg':'#0c171c','text':'#e5eeee','muted':'#9fb2bb','accent':'#9cddb7','privacy-bg':'#1d2a27','privacy-text':'#bed9c9','code-bg':'#091014'},'Default restores the original green Workbench palette');
    const catalog=await page.evaluate(()=>window.WorkbenchThemes.catalog);
    assert.equal(catalog.length,35);
    assert.equal(catalog.filter(t=>t.group==='Fallout').length,16);
    assert.equal(new Set(catalog.map(t=>t.id)).size,35);
    const screenshotDir=process.env.WORKBENCH_THEME_SCREENSHOTS;
    if(screenshotDir)fs.mkdirSync(screenshotDir,{recursive:true});
    const measurements=[];
    const baselineStyles=new Map();
    for(const theme of catalog){
      await chooseTheme(theme.id);
      assert.equal(await page.locator('html').getAttribute('data-theme'),theme.id);
      assert.equal(await page.locator('.skin-scene').textContent(),'','No theme caption or descriptive tagline');
      assert.equal(await page.locator('.skin-scene').isVisible(),theme.shape!=='plain');
      assert.equal(await page.locator('.report-version.selected').count(),1,'Theme must preserve selected report');
      const selectedStyles=await page.locator('.case-button.selected, .tabs .selected, .plugin-nav.selected, .report-version.selected > button:first-child').evaluateAll(elements=>elements.map(element=>{
        const style=getComputedStyle(element);return {shadow:style.boxShadow,left:style.borderLeftWidth,right:style.borderRightWidth};
      }));
      assert.ok(selectedStyles.length>0);
      for(const style of selectedStyles){
        if(theme.id!=='fallout-2')assert.equal(style.shadow,'none','Selected controls have no one-sided inset stripe');
        assert.equal(style.left,style.right,'Selected borders are even on both sides');
      }
      if(['matrix','fallout','fallout-3'].includes(theme.id))baselineStyles.set(theme.id,await presentationStyles());
      if(theme.id==='fallout-2'){
        const surfaces=await page.locator('body, body > header, .skin-scene, .layout, .layout > aside, .layout > main').evaluateAll(elements=>elements.map(element=>{
          const style=getComputedStyle(element);return {backgroundImage:style.backgroundImage,backgroundColor:style.backgroundColor};
        }));
        for(const surface of surfaces)assert.doesNotMatch(surface.backgroundImage,/url\(/,'Fallout 2 chassis scales with CSS instead of image assets');
        for(const surface of surfaces.slice(-2)){
          assert.equal(surface.backgroundImage,'none','Dense case and report surfaces stay free of decorative textures');
          assert.match(surface.backgroundColor,/^rgb\(/,'Screen wells have an opaque background');
        }
        const rail=await page.locator('.skin-scene').boundingBox();
        assert.ok(rail.height>0&&rail.height<=32,'Fallout 2 has a compact CSS ventilation rail');
        const primary=await page.locator('#update.primary').evaluate(element=>{
          const style=getComputedStyle(element),channels=value=>value.match(/[\d.]+/g).slice(0,3).map(Number),
            luminance=rgb=>{const c=rgb.map(n=>n/255).map(n=>n<=.04045?n/12.92:((n+.055)/1.055)**2.4);return c[0]*.2126+c[1]*.7152+c[2]*.0722;};
          const text=luminance(channels(style.color)),stops=[...style.backgroundImage.matchAll(/rgb\([^)]+\)/g)].map(match=>channels(match[0]));
          return {green:stops.length>0&&stops.every(([r,g,b])=>g>r&&g>b),minimumContrast:Math.min(...stops.map(stop=>{const bg=luminance(stop);return(Math.max(text,bg)+.05)/(Math.min(text,bg)+.05);} ))};
        });
        assert.ok(primary.green,'Update report keeps its primary green action');
        assert.ok(primary.minimumContrast>=4.5,'Primary text remains readable across its green bevel');
        await noPageOverflow('Fallout 2 desktop report');
        await headerNoOverlap('Fallout 2 desktop');
      }
      if(theme.id==='fallout-new-vegas'){
        const scene=await page.locator('.skin-scene').evaluate(element=>{
          const styles=[getComputedStyle(element),getComputedStyle(element,'::before'),getComputedStyle(element,'::after')];
          return styles.map(style=>({image:style.backgroundImage,content:style.content,animation:style.animationName}));
        });
        for(const style of scene){
          assert.doesNotMatch(style.image,/url\(/,'New Vegas main sign uses scalable CSS, not the old skyline asset');
          assert.equal(style.animation,'none','Marquee bulbs remain still');
        }
        assert.match(scene[0].image,/rgb\(79, 64, 48\)/,'Marquee includes unlit sockets');
        assert.equal(scene[1].content,'"WELCOME"');
        assert.equal(scene[2].content,'"NEW VEGAS"');
        for(const selector of ['.layout > aside','.layout > main']){
          assert.equal(await page.locator(selector).evaluate(element=>getComputedStyle(element).backgroundImage),'none','New Vegas evidence surfaces remain untextured');
        }
        await noPageOverflow('New Vegas desktop');
        await headerNoOverlap('New Vegas desktop');
      }
      const image=theme.scene===null?null:theme.id==='halloween-noir'?'halloween-night.png':`theme-${theme.scene}.svg`;
      if(image){
      assert.ok(fs.existsSync(path.join(assets,image)),'Artwork skins have a packaged scene');
      if(image.endsWith('.svg')){
        const source=fs.readFileSync(path.join(assets,image),'utf8');
        assert.match(source,/<svg/);assert.doesNotMatch(source,/<script|foreignObject|(?:href|src)=|style=/i,'Art has no script, inline styles or linked resources');
      }
      await page.evaluate(name=>new Promise((resolve,reject)=>{const image=new Image();image.onload=resolve;image.onerror=()=>reject(Error('Scene could not load '+name));image.src='/'+name;}),image);
      }else{
        assert.equal(await page.locator('html').evaluate(element=>element.style.getPropertyValue('--theme-scene')),'none');
        const surfaces=await page.locator('body > header,.skin-scene,.layout,.layout > aside,.layout > main').evaluateAll(nodes=>nodes.map(node=>getComputedStyle(node).backgroundImage));
        assert.ok(surfaces.slice(0,3).every(value=>value.includes('gradient(')&&!value.includes('url(')),'Terminal shell and rail use CSS materials');
        assert.ok(surfaces.slice(-2).every(value=>value==='none'),'Terminal evidence screens remain opaque and untextured');
        await noPageOverflow(theme.id+' desktop');await headerNoOverlap(theme.id+' desktop');
      }
      const contrast=await page.evaluate(()=>{
        const css=getComputedStyle(document.documentElement);
        const luminance=hex=>{
          const x=hex.trim().slice(1).match(/../g).map(n=>parseInt(n,16)/255).map(n=>n<=.04045?n/12.92:((n+.055)/1.055)**2.4);
          return x[0]*.2126+x[1]*.7152+x[2]*.0722;
        };
        const ratio=(a,b)=>{const x=luminance(css.getPropertyValue('--'+a)),y=luminance(css.getPropertyValue('--'+b));return(Math.max(x,y)+.05)/(Math.min(x,y)+.05);};
        return {text:ratio('text','panel'),muted:ratio('muted','panel'),primary:ratio('accent','accent-text'),selection:ratio('accent','panel'),warning:ratio('status','panel'),danger:ratio('danger','panel'),error:ratio('error-text','panel'),border:ratio('border','control-bg')};
      });
      for(const token of ['text','muted','primary','selection','warning','danger','error'])assert.ok(contrast[token]>=4.5,`${theme.id} ${token} contrast ${contrast[token]}`);
      assert.ok(contrast.border>=3,`${theme.id} control border contrast ${contrast.border}`);
      measurements.push({id:theme.id,...contrast});
      await page.locator('#theme').focus();
      assert.equal(await page.locator('#theme').evaluate(e=>getComputedStyle(e).outlineStyle),'solid');
      if(screenshotDir)await page.screenshot({path:path.join(screenshotDir,theme.id+'.png'),fullPage:true});
      if(screenshotDir&&theme.id==='fallout-2'){
        await page.locator('#theme').press('Escape');
        await page.screenshot({path:path.join(screenshotDir,'fallout-2-desktop-viewport.png')});
      }
    }
    // The custom housing must disappear when returning to the default or adjacent skins.
    for(const [id,styles] of baselineStyles){
      await chooseTheme('fallout-2');await chooseTheme(id);
      assert.deepEqual(await presentationStyles(),styles,`${id} must not retain Fallout 2 housing styles`);
      await chooseTheme('fallout-new-vegas');await chooseTheme(id);
      assert.deepEqual(await presentationStyles(),styles,`${id} must not retain New Vegas housing styles`);
      for(const terminal of ['fallout-3-robco','fallout-3-vault-112']){
        await chooseTheme(terminal);await chooseTheme(id);
        assert.deepEqual(await presentationStyles(),styles,`${id} must not retain Fallout 3 terminal housing styles`);
      }
    }
    // Every original preference remains honored on startup, including settings.
    for(const id of ['matrix','mono','blue']){
      await chooseTheme(id);await page.reload();
      assert.equal(await page.locator('#theme').inputValue(),id);
      await page.goto('http://localhost/settings.html');
      assert.equal(await page.locator('#settings-theme').inputValue(),id);
      assert.equal(await page.locator('.settings .skin-scene').textContent(),'');
      assert.equal(await page.locator('.settings .skin-scene').isVisible(),!['matrix','mono','blue'].includes(id));
      await page.goto('http://localhost/');
    }
    await page.goto('http://localhost/settings.html');
    await page.locator('#settings-theme').selectOption('silpheed');
    await page.goto('http://localhost/');
    assert.equal(await page.locator('#theme').inputValue(),'silpheed');
    await page.locator('#openPlugins').click();
    await page.waitForFunction(()=>document.querySelector('#pluginRows tr'));
    for(const id of catalog.map(t=>t.id)){
      await chooseTheme(id);
      assert.equal(await page.locator('#pluginRows tr').count(),1);
      assert.equal(await page.locator('#pluginRows').evaluate(e=>getComputedStyle(e).color),await page.locator('body').evaluate(e=>getComputedStyle(e).color));
    }
    await page.setViewportSize({width:390,height:844});
    for(const id of ['matrix','fallout-new-vegas','fallout-2']){
      await chooseTheme(id);
      await noPageOverflow(id+' mobile plugins');
      await headerNoOverlap(id+' mobile');
      if(screenshotDir)await page.screenshot({path:path.join(screenshotDir,id+'-mobile-plugins.png'),fullPage:true});
    }
    await page.locator('#closePlugins').click();
    for(const width of [390,320]){
      await page.setViewportSize({width,height:844});
      await noPageOverflow('Fallout 2 '+width+'px report');
      await headerNoOverlap('Fallout 2 '+width+'px');
      assert.equal(await page.locator('.report-version.selected').count(),1);
      if(screenshotDir)await page.screenshot({path:path.join(screenshotDir,'fallout-2-mobile-'+width+'.png'),fullPage:true});
    }
    await page.goto('http://localhost/settings.html');
    assert.equal(await page.locator('#settings-theme').inputValue(),'fallout-2');
    await noPageOverflow('Fallout 2 mobile Settings');
    if(screenshotDir)await page.screenshot({path:path.join(screenshotDir,'fallout-2-settings-mobile.png'),fullPage:true});
    await page.setViewportSize({width:1400,height:1050});
    await noPageOverflow('Fallout 2 desktop Settings');
    if(screenshotDir)await page.screenshot({path:path.join(screenshotDir,'fallout-2-settings-desktop.png'),fullPage:true});
    await page.goto('http://localhost/');
    await page.setViewportSize({width:390,height:844});
    await page.emulateMedia({reducedMotion:'reduce',contrast:'more'});
    assert.equal(await page.locator('html').evaluate(e=>getComputedStyle(e).getPropertyValue('--border').trim()),await page.locator('html').evaluate(e=>getComputedStyle(e).getPropertyValue('--muted').trim()));
    await noPageOverflow('Fallout 2 mobile increased contrast');
    if(screenshotDir)await page.screenshot({path:path.join(screenshotDir,'fallout-2-increased-contrast.png'),fullPage:true});
    await page.emulateMedia({reducedMotion:'reduce',contrast:'no-preference'});
    await chooseTheme('fallout-new-vegas');
    for(const width of [1400,390,320]){
      await page.setViewportSize({width,height:1050});
      await noPageOverflow('New Vegas '+width+'px');
      await headerNoOverlap('New Vegas '+width+'px');
      assert.equal(await page.locator('.report-version.selected').count(),1);
      if(screenshotDir)await page.screenshot({path:path.join(screenshotDir,'new-vegas-header-'+width+'.png')});
    }
    await page.goto('http://localhost/settings.html');
    assert.equal(await page.locator('#settings-theme').inputValue(),'fallout-new-vegas');
    await noPageOverflow('New Vegas 320px Settings');
    assert.ok(await page.locator('.skin-scene').evaluate(element=>parseFloat(getComputedStyle(element,'::before').width)<=element.clientWidth),'Welcome discs fit the nested Settings panel');
    assert.equal(await page.locator('.skin-scene').evaluate(element=>getComputedStyle(element,'::after').content),'"NEW VEGAS"');
    if(screenshotDir)await page.screenshot({path:path.join(screenshotDir,'new-vegas-settings-320.png')});
    for(const id of ['fallout-3-robco','fallout-3-vault-112']){
      await page.goto('http://localhost/');await chooseTheme(id);
      for(const width of [1400,390,320]){
        await page.setViewportSize({width,height:1050});
        await noPageOverflow(id+' '+width+'px report');await headerNoOverlap(id+' '+width+'px');
        if(screenshotDir)await page.screenshot({path:path.join(screenshotDir,id+'-report-'+width+'.png')});
      }
      await page.goto('http://localhost/settings.html');
      assert.equal(await page.locator('#settings-theme').inputValue(),id,'Terminal choice survives navigation to Settings');
      for(const width of [1400,390,320]){
        await page.setViewportSize({width,height:1050});await noPageOverflow(id+' '+width+'px Settings');
        if(screenshotDir)await page.screenshot({path:path.join(screenshotDir,id+'-settings-'+width+'.png')});
      }
      await page.goto('http://localhost/');
      await page.evaluate(()=>{document.documentElement.style.setProperty('--text-scale','2');document.documentElement.dataset.textScaled='true';});
      await noPageOverflow(id+' 200% text');
    }
    await page.goto('http://localhost/');
    await chooseTheme('matrix');
    // Storage unavailable and unknown future/removed IDs both keep a usable default.
    await page.evaluate(()=>localStorage.setItem('volatility-workbench-theme','unknown-theme'));
    await page.reload();assert.equal(await page.locator('#theme').inputValue(),'matrix');
    await page.addInitScript(()=>{Object.defineProperty(window,'localStorage',{get(){throw new Error('disabled for fixture');}});});
    await page.reload();assert.equal(await page.locator('#theme').inputValue(),'matrix');
    await chooseTheme('8-bit');
    assert.equal(await page.locator('html').getAttribute('data-theme'),'8-bit');
    assert.deepEqual(errors,[]);
    assert.deepEqual(policyErrors,[],'Production CSP must allow all packaged artwork');
    console.log(`Theme browser: ${catalog.length} skins, 16 Fallout choices, text/control contrast, selected report, focus, legacy prefs, shared Settings, CSS Fallout housings/isolation, both Fallout 3 terminals at desktop/mobile sizes and 200% text, increased contrast and unavailable storage passed. ${network.length} local GET requests; zero analysis/mutation/external requests.`);
    if(screenshotDir)fs.writeFileSync(path.join(screenshotDir,'contrast.json'),JSON.stringify(measurements,null,2)+'\n');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
