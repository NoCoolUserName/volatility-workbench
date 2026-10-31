// Offline UI check: synthetic sealed reports and a simulated local save endpoint only.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const assets=path.join(__dirname,'../src/volatility_workbench/static');
const support='Synthetic **assessment** cites F1 and [evidence](evidence/fixture.txt).';
const benignSupport='Verified **maintenance activity** explains the observed changes (F1) and [evidence](evidence/fixture.txt).';
const legacySupport='The evidence supports a high-confidence assessment of host compromise.';
const versions=['legacy','malicious','explicit','uncertain'].map(id=>({id,status:'sealed',created_at:'2026-10-18T12:00:00Z',
  ai_maliciousness_support:id==='legacy'?[legacySupport]:id==='malicious'?[support,'Synthetic **assessment**','Synthetic scope stays normal.']:id==='explicit'?['Objective filename Benign.exe was recorded.']:[],
  ai_benignness_support:id==='explicit'?[benignSupport,'Verified **maintenance activity**','Synthetic only.']:['Available evidence is inconclusive (F2–F3, F11). Unknown F99 stays plain.']}));
const state={cases:[{id:'synthetic',title:'Synthetic case',created_at:'2026-10-18T12:00:00Z',images:[],coins:[],
  readiness:{status:'Unchecked',reasons:[]},reports:versions,messages:[],activity:[]}],
  jobs:[],approvals:[],account:{},evidence_root:'/synthetic'};
const narratives={
  legacy:'# Synthetic report\n## Executive summary\nThe evidence supports a high-confidence assessment of host compromise.\n## Scope and evidence\nSynthetic only.',
  malicious:'# Synthetic report\n## Executive summary\nAI Determination: Malicious\nSynthetic timestamp 04:31:36 UTC. '+support+' Objective filename Malicious.exe was recorded.\nLimitations are unresolved.\n## Scope and evidence\nSynthetic scope stays normal.\n## Findings\n### F1 — Synthetic finding\nSynthetic finding stays normal.',
  explicit:'# Synthetic report\n## Executive summary\nAI Determination: Benign\nSynthetic timestamp 04:31:36 UTC. '+benignSupport+' Objective filename Benign.exe was recorded.\nCoverage is limited.\n## Scope and evidence\nSynthetic only.\n## Findings\n### F1 — Synthetic maintenance finding\nSynthetic finding stays normal.',
  uncertain:'# Synthetic report\n## Executive summary\nAI Determination: Undetermined\nAvailable evidence is inconclusive (F2–F3, F11). Unknown F99 stays plain.\n## Scope and evidence\nSynthetic only.\n## Findings\n### F2 — Synthetic finding\nFixture text.\n### F3: Another finding\nFixture text.\n### F11 — Last finding\nFixture text.',
};
(async()=>{
  const browser=await chromium.launch({headless:true,...(process.env.WORKBENCH_BROWSER_EXECUTABLE?{executablePath:process.env.WORKBENCH_BROWSER_EXECUTABLE}:{})});
  try{
    const page=await browser.newPage({viewport:{width:1100,height:900}}),posts=[],errors=[];
    let holdNextState=false, heldStateResolve=null, releaseHeldState=null;
    page.on('pageerror',error=>errors.push(error.message));
    await page.route('http://localhost/**',async route=>{
      if (new URL(route.request().url()).pathname === '/api/settings/zoom') return route.fulfill({json:{schema:'zoom/1',percent:100}});
      const u=new URL(route.request().url());
      if(u.pathname==='/api/reports/determination'){
        assert.equal(route.request().method(),'POST');
        const data=route.request().postDataJSON();
        assert.equal(data.case_id,'synthetic');
        assert.ok(['Benign','Malicious','Undetermined',null].includes(data.value));
        const report=versions.find(version=>version.id===data.report_id);
        assert.ok(report);
        if(data.value===null)delete report.human_determination;
        else report.human_determination=data.value;
        posts.push(data);
        return route.fulfill({json:{report_id:report.id,human_determination:data.value}});
      }
      assert.equal(route.request().method(),'GET','Viewing a report must not submit work');
      if(u.pathname==='/api/state'){
        const snapshot=JSON.parse(JSON.stringify(state));
        if(holdNextState){
          holdNextState=false;heldStateResolve();
          return new Promise(resolve=>{releaseHeldState=()=>resolve(route.fulfill({json:snapshot}));});
        }
        return route.fulfill({json:snapshot});
      }
      if(u.pathname==='/api/report-plugins')return route.fulfill({json:{schema:'report-plugin-inventory/1',
        report_id:u.searchParams.get('report'),scope:'bundled_saved_runs',source_status:'unavailable',summary:{},entries:[],next_offset:null,warnings:[]}});
      if(u.pathname==='/api/file'){
        const id=/reports\/([^/]+)\/report\.md/.exec(u.searchParams.get('path'))?.[1];
        assert.ok(id in narratives);
        return route.fulfill({json:{text:narratives[id],size:narratives[id].length,next_offset:narratives[id].length,truncated:false}});
      }
      if(u.pathname==='/api/artifacts')return route.fulfill({json:{files:[],truncated:false}});
      assert.ok(!u.pathname.startsWith('/api/'),'Unexpected API route '+u.pathname);
      const name=u.pathname==='/'?'index.html':u.pathname.slice(1);
      return route.fulfill({body:fs.readFileSync(path.join(assets,name)),contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html'});
    });
    await page.goto('http://localhost/?case=synthetic');
    const ai=page.locator('.report-determinations .determination-value');
    const human=page.locator('#humanDetermination');
    await ai.waitFor();
    assert.equal(await ai.innerText(),'Undetermined');
    assert.equal(await human.inputValue(),'');
    assert.equal(await page.locator('.determination-save-status').innerText(),'');
    const findingLinks=page.locator('#reportView > p a[aria-label^="Jump to finding"]');
    assert.deepEqual(await findingLinks.allTextContents(),['F2','F3','F11']);
    const headingForms=await page.evaluate(()=>{
      const saved=Array.from(document.querySelector('#reportView').childNodes);
      renderMarkdown('## Executive summary\nReferences F1, SYN-F001, F2 and F99.\n## Findings\n### SYN-F001 — Prefixed fixture\nText\n### **F2** — Bold fixture\nText','reports/synthetic');
      const links=Array.from(document.querySelectorAll('#reportView a[aria-label^="Jump to finding"]')).map(n=>n.textContent);
      renderMarkdown('## Executive summary\nAmbiguous F1.\n## Findings\n### A-F001 — One\n### B-F001 — Two','reports/synthetic');
      const ambiguous=document.querySelectorAll('#reportView a[aria-label^="Jump to finding"]').length;
      document.querySelector('#reportView').replaceChildren(...saved);return {links,ambiguous};
    });
    assert.deepEqual(headingForms,{links:['F1','SYN-F001','F2'],ambiguous:0});
    const target=await findingLinks.first().getAttribute('href');
    await findingLinks.first().click();
    assert.equal(await page.evaluate(()=>document.activeElement.id),target.slice(1));
    assert.equal(await page.locator('#reports').isVisible(),true);
    assert.equal(await page.getByRole('link',{name:'Jump to finding F99'}).count(),0);

    assert.equal(await ai.evaluate(node=>getComputedStyle(node).color),'rgb(255, 255, 255)');
    assert.equal(await ai.evaluate(node=>getComputedStyle(node).fontWeight),'700');
    assert.equal(await page.locator('#reportView h2').first().innerText(),'Executive summary');
    assert.equal(await page.locator('#reportView h2 + .report-determinations').count(),1);
    const rowSizes=await page.locator('.report-determinations').evaluate(panel=>{
      const ai=panel.querySelector('p.determination-row');
      const human=panel.querySelector('label.determination-row');
      return [ai,human,human.querySelector('select'),human.querySelector('.determination-save-status')]
        .map(node=>getComputedStyle(node).fontSize);
    });
    assert.deepEqual(rowSizes,[rowSizes[0],rowSizes[0],rowSizes[0],rowSizes[0]],
      'AI and human labels, choice, and save status use the same font size');

    await page.locator('[data-report-id="malicious"] button:first-child').click();
    await page.waitForFunction(()=>document.querySelector('.determination-value')?.textContent==='Malicious');
    const assessmentColors=await page.locator('#reportView').evaluate(article=>{
      const color=node=>getComputedStyle(node).color;
      const paragraph=[...article.querySelectorAll('p')].find(n=>n.textContent.startsWith('Synthetic timestamp'));
      const walker=document.createTreeWalker(paragraph,NodeFilter.SHOW_TEXT), red=[], normal=[];
      while(walker.nextNode()) {
        const node=walker.currentNode;
        (color(node.parentElement)==='rgb(255, 137, 137)'?red:normal).push(node.textContent);
      }
      return {red:red.join(''),normal:normal.join(''),text:paragraph.textContent,
        finding:color(paragraph.querySelector('a[aria-label="Jump to finding F1"] span')),
        evidence:color(paragraph.querySelector('a:not([aria-label]) span')),
        aiLabel:color(article.querySelector('.determination-row strong')),
        humanLabel:color(article.querySelector('label.determination-row strong')),
        scope:color([...article.querySelectorAll('p')].find(n=>n.textContent==='Synthetic scope stays normal.'))};
    });
    assert.equal(assessmentColors.red,'Synthetic assessment cites F1 and evidence.');
    assert.equal(assessmentColors.normal,'Synthetic timestamp 04:31:36 UTC.  Objective filename Malicious.exe was recorded.');
    assert.equal(assessmentColors.text,'Synthetic timestamp 04:31:36 UTC. Synthetic assessment cites F1 and evidence. Objective filename Malicious.exe was recorded.');
    assert.equal(assessmentColors.finding,'rgb(255, 137, 137)');
    assert.equal(assessmentColors.evidence,'rgb(255, 137, 137)');
    assert.equal(assessmentColors.aiLabel,'rgb(255, 137, 137)');
    assert.notEqual(assessmentColors.humanLabel,assessmentColors.aiLabel);
    assert.notEqual(assessmentColors.scope,assessmentColors.aiLabel,'Out-of-summary quotes cannot color other sections');

    await page.locator('[data-report-id="legacy"] button:first-child').click();
    await page.waitForFunction(()=>document.querySelector('.determination-value')?.textContent==='Malicious');
    assert.equal(await ai.evaluate(node=>getComputedStyle(node).color),'rgb(255, 137, 137)');
    assert.equal(await page.locator('#reportView > p').filter({hasText:legacySupport}).locator('.ai-malicious-support')
      .evaluate(node=>getComputedStyle(node).color),'rgb(255, 137, 137)','Legacy malicious assessment is also red');
    await human.selectOption('Benign');
    await page.waitForFunction(()=>document.querySelector('.determination-save-status')?.textContent==='Saved');
    assert.equal(await human.evaluate(node=>getComputedStyle(node).color),'rgb(134, 230, 165)');
    assert.equal(await human.evaluate(node=>getComputedStyle(node).fontWeight),'700');
    assert.equal(versions[0].human_determination,'Benign','Human and AI opinions can differ');
    // The extraction dialog blocks accidental approval until its acknowledgement is checked.
    state.approvals=[{id:'synthetic-consent',case_id:'synthetic',method:'mcpServer/elicitation/request',params:{
      serverName:'volatility',mode:'form',message:'Potentially hazardous extraction\nPlugin: synthetic.dump.Plugin\nRecovered files may contain malware.',
      requestedSchema:{type:'object',properties:{confirm:{type:'boolean',title:'Approve this extraction once'}},required:['confirm']}}}];
    await page.evaluate(()=>refresh());
    const dialog=page.getByRole('dialog',{name:'Confirm potentially hazardous extraction'});
    await dialog.waitFor();assert.equal(await dialog.evaluate(n=>n.open),true);
    const approve=dialog.getByRole('button',{name:'Approve / submit once'});
    assert.equal(await approve.isDisabled(),true);
    await dialog.getByRole('checkbox').check();assert.equal(await approve.isEnabled(),true);
    state.approvals=[];await page.evaluate(()=>refresh());assert.equal(await dialog.count(),0);
    if(process.env.WORKBENCH_DETERMINATIONS_SCREENSHOT){
      await ai.scrollIntoViewIfNeeded();
      await page.screenshot({path:process.env.WORKBENCH_DETERMINATIONS_SCREENSHOT});
    }
    await page.reload();
    await page.locator('[data-report-id="legacy"] button:first-child').click();
    await page.waitForFunction(()=>document.querySelector('.determination-value')?.textContent==='Malicious');
    assert.equal(await human.inputValue(),'Benign','Human choice survives reload');
    assert.equal(await page.locator('.determination-save-status').innerText(),'Saved',
      'An already persisted determination is identified as saved on reopen');
    await human.selectOption('Malicious');
    await page.waitForFunction(()=>document.querySelector('.determination-save-status')?.textContent==='Saved');
    assert.equal(await human.evaluate(node=>getComputedStyle(node).color),'rgb(255, 137, 137)');
    await human.selectOption('Undetermined');
    await page.waitForFunction(()=>document.querySelector('.determination-save-status')?.textContent==='Saved');
    assert.equal(await human.evaluate(node=>getComputedStyle(node).color),'rgb(255, 255, 255)');

    const held=new Promise(resolve=>{heldStateResolve=resolve;});
    holdNextState=true;
    const staleRefresh=page.evaluate(()=>refresh());
    await held;
    await human.selectOption('Benign');
    await page.waitForFunction(()=>document.querySelector('#humanDetermination')?.value==='Benign' &&
      document.querySelector('.determination-save-status')?.textContent==='Saved');
    releaseHeldState();await staleRefresh;
    assert.equal(await human.inputValue(),'Benign','Late older state must not revert a saved selection');
    await page.reload();
    await page.locator('[data-report-id="legacy"] button:first-child').click();
    assert.equal(await human.inputValue(),'Benign','Saved choice survives a fresh view');

    await page.locator('[data-report-id="explicit"] button:first-child').click();
    await page.waitForFunction(()=>document.querySelector('.determination-value')?.textContent==='Benign');
    assert.equal(await ai.evaluate(node=>getComputedStyle(node).color),'rgb(134, 230, 165)');
    assert.equal(await page.locator('#reportView .ai-malicious-support').count(),0,'No red assessment leaks between versions');
    const benignColors=await page.locator('#reportView').evaluate(article=>{
      const color=node=>getComputedStyle(node).color;
      const paragraph=[...article.querySelectorAll('p')].find(n=>n.textContent.startsWith('Synthetic timestamp'));
      const walker=document.createTreeWalker(paragraph,NodeFilter.SHOW_TEXT),green=[],normal=[];
      while(walker.nextNode()) {
        const node=walker.currentNode;
        (color(node.parentElement)==='rgb(134, 230, 165)'?green:normal).push(node.textContent);
      }
      return {green:green.join(''),normal:normal.join(''),
        finding:color(paragraph.querySelector('a[aria-label="Jump to finding F1"] span')),
        evidence:color(paragraph.querySelector('a:not([aria-label]) span')),
        aiLabel:color(article.querySelector('.determination-row strong')),
        humanLabel:color(article.querySelector('label.determination-row strong')),
        scope:color([...article.querySelectorAll('p')].find(n=>n.textContent==='Synthetic only.')),
        limitation:color([...article.querySelectorAll('p')].find(n=>n.textContent==='Coverage is limited.'))};
    });
    assert.equal(benignColors.green,'Verified maintenance activity explains the observed changes (F1) and evidence.');
    assert.equal(benignColors.normal,'Synthetic timestamp 04:31:36 UTC.  Objective filename Benign.exe was recorded.');
    for(const key of ['finding','evidence','aiLabel'])assert.equal(benignColors[key],'rgb(134, 230, 165)',key);
    for(const key of ['humanLabel','scope','limitation'])assert.notEqual(benignColors[key],'rgb(134, 230, 165)',key);
    const benignFinding=page.getByRole('link',{name:'Jump to finding F1'});
    const benignTarget=await benignFinding.getAttribute('href');
    await benignFinding.click();
    assert.equal(await page.evaluate(()=>document.activeElement.id),benignTarget.slice(1));
    if(process.env.WORKBENCH_BENIGN_SCREENSHOT){
      await ai.scrollIntoViewIfNeeded();
      await page.screenshot({path:process.env.WORKBENCH_BENIGN_SCREENSHOT});
    }
    await page.reload();
    await page.locator('[data-report-id="explicit"] button:first-child').click();
    await page.waitForFunction(()=>document.querySelector('.determination-value')?.textContent==='Benign');
    assert.equal(await page.locator('.ai-benign-support').first().evaluate(node=>getComputedStyle(node).color),'rgb(134, 230, 165)',
      'Supporting Benign passages stay green after reload');

    assert.equal(await human.inputValue(),'','Human opinion belongs to its own report version');
    assert.equal(await page.locator('#reportView > p').getByText('AI Determination: Benign',{exact:true}).count(),0,
      'Saved Markdown determination is represented once by the UI line');
    await page.locator('[data-report-id="uncertain"] button:first-child').click();
    await page.waitForFunction(()=>document.querySelector('.determination-value')?.textContent==='Undetermined');
    assert.equal(await ai.evaluate(node=>getComputedStyle(node).color),'rgb(255, 255, 255)');
    assert.equal(await page.locator('#reportView .ai-benign-support, #reportView .ai-malicious-support').count(),0,
      'Undetermined never inherits supporting highlights from another verdict');
    assert.equal(posts.length,4);
    assert.deepEqual(errors,[]);
    console.log('Report determinations: explicit and conservative legacy AI values; three color states; independent human opinion; per-version save and reload; no analysis submissions.');
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
