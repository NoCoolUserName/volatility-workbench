// Optional offline Chromium checks. Run with Playwright installed in your Node environment.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const assets = path.join(__dirname, '../src/volatility_workbench/static');
const plugin = (name, kind, label, target_os, url = null) => ({name, description: 'Synthetic description <script>window.injected=true</script>',
  plugin_version: [1, 0, 0], target_os, source: {kind, label, url, basis: 'Synthetic attribution fixture'}});
const plugins = [
  plugin('windows.pslist.PsList', 'native', 'Native · Volatility 3', 'windows', 'https://github.com/volatilityfoundation/volatility3'),
  plugin('vol_pypykatz.pypykatz', 'third_party', 'skelsec/pypykatz-volatility3', 'windows', 'https://github.com/skelsec/pypykatz-volatility3'),
  plugin('xpnet.XpNetScan', 'local', 'Local addon · volatility-mcp', 'windows'),
  plugin('linux.example.Plugin', 'unknown', 'Source unknown', 'linux', 'javascript:window.injected=true'),
];
const sampleCase = (id, created_at) => ({id, title: id, created_at, images: [], coins: [], readiness: {status:'Unchecked', reasons:[]}, reports:[], messages:[], activity:[]});
const state = {cases:[sampleCase('Older case', '2026-01-01T00:00:00Z'), sampleCase('Newest case', '2026-02-01T00:00:00Z')], jobs:[], approvals:[], account:{}, evidence_root:'/synthetic/evidence'};
let mode = 'normal', calls = [], errors = [];
(async () => {
  const browser = await chromium.launch({headless:true,...(process.env.WORKBENCH_BROWSER_EXECUTABLE?{executablePath:process.env.WORKBENCH_BROWSER_EXECUTABLE}:{})});
  try {
    const page = await browser.newPage({viewport:{width:1400,height:1000}});
    page.on('pageerror', e => errors.push(e.message));
    await page.route('http://workbench.test/**', async route => {
      if (new URL(route.request().url()).pathname === '/api/settings/zoom') return route.fulfill({json:{schema:'zoom/1',percent:100}});
      const u = new URL(route.request().url());
      if (u.pathname.startsWith('/api/')) {
        calls.push(u.pathname + u.search);
        if (u.pathname === '/api/state') return route.fulfill({json:state});
        if (u.pathname === '/api/artifacts') return route.fulfill({json:{files:[],truncated:false}});
        if (u.pathname === '/api/plugins') {
          if (mode === 'failure') return route.fulfill({status:400,json:{error:'Synthetic discovery failure'}});
          return route.fulfill({json:{plugins:mode === 'empty' ? [] : plugins, total:mode === 'empty' ? 0 : plugins.length,
            volatility_version:'SYNTHETIC', architecture:'arm64', discovered_at:'2026-10-18T01:00:00Z', import_failures:['synthetic.missing_dependency']}});
        }
        throw Error('Unexpected API call: ' + u.pathname);
      }
      const name = u.pathname === '/' ? 'index.html' : u.pathname.slice(1);
      return route.fulfill({body:fs.readFileSync(path.join(assets,name)),contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html'});
    });
    await page.goto('http://workbench.test/');
    await page.waitForFunction(() => document.querySelector('#caseTitle').textContent === 'Newest case');
    await page.getByRole('button',{name:'Older case',exact:true}).click();
    await page.getByRole('button',{name:'Case conversation',exact:true}).click();
    await page.getByRole('button',{name:'Plugins',exact:true}).click();
    await page.waitForFunction(() => document.querySelector('#pluginCount').textContent === '4 shown · 4 discovered');
    assert.equal(await page.locator('#pluginRows tr').count(),4);
    assert.match(await page.locator('#pluginStatus').innerText(),/Volatility3 ver\. SYNTHETIC/);
    await page.locator('#pluginSearch').fill('skelsec');
    assert.equal(await page.locator('#pluginRows tr').count(),1);
    assert.match(await page.locator('#pluginRows').innerText(),/vol_pypykatz/);
    await page.locator('#pluginSearch').fill('');
    await page.locator('#pluginOS').selectOption('linux');
    assert.equal(await page.locator('#pluginRows tr').count(),1);
    assert.equal(await page.locator('#pluginRows a').count(),0);
    await page.locator('#pluginOS').selectOption('');
    await page.locator('#pluginSource summary').click();
    assert.equal(await page.locator('#pluginSourceOptions input[type=checkbox]').count(),5);
    assert.deepEqual(await page.locator('#pluginSourceOptions label span').allTextContents(),
      ['All', 'Native · Volatility 3 (1)', 'Local addon · volatility-mcp (1)',
       'skelsec/pypykatz-volatility3 (1)', 'Source unknown (1)']);
    const all = page.getByRole('checkbox',{name:'All',exact:true});
    assert.equal(await all.isChecked(),true);
    await all.uncheck();
    assert.equal(await page.locator('#pluginRows tr').count(),1);
    assert.match(await page.locator('#pluginRows').innerText(),/No plugins match/);
    assert.equal(await page.locator('#pluginSource summary').innerText(),'Source (0/4)');
    await all.check();
    assert.equal(await page.locator('#pluginRows tr').count(),4);
    const native = page.getByRole('checkbox',{name:'Native · Volatility 3 (1)'});
    const thirdParty = page.getByRole('checkbox',{name:'skelsec/pypykatz-volatility3 (1)'});
    const local = page.getByRole('checkbox',{name:'Local addon · volatility-mcp (1)'});
    const unknown = page.getByRole('checkbox',{name:'Source unknown (1)'});
    await native.uncheck();
    assert.equal(await all.isChecked(),false);
    assert.equal(await all.evaluate(input => input.indeterminate),true);
    assert.equal(await page.locator('#pluginRows tr').count(),3);
    assert.equal(await page.locator('#pluginSource summary').innerText(),'Source (3/4)');
    await thirdParty.uncheck();
    await unknown.uncheck();
    assert.equal(await page.locator('#pluginRows tr').count(),1);
    assert.match(await page.locator('#pluginRows').innerText(),/XpNetScan/);
    await local.uncheck();
    assert.match(await page.locator('#pluginRows').innerText(),/No plugins match/);
    await all.check();
    assert.equal(await page.locator('#pluginRows tr').count(),4);
    assert.equal(await all.isChecked(),true);
    assert.equal(await page.locator('#pluginSource summary').innerText(),'Source');
    await page.locator('#pluginSource summary').click();
    await page.locator('#pluginSearch').fill('does not exist');
    assert.match(await page.locator('#pluginRows').innerText(),/No plugins match/);
    await page.locator('#pluginSearch').fill('');
    await page.locator('#pluginRows summary').first().click();
    assert.equal(await page.locator('#pluginRows details').first().locator('p').first().textContent(), plugins[3].description);
    assert.equal(await page.evaluate(() => window.injected),undefined);
    // Normal 1.5s state polling must preserve catalog, expansion, and cached discovery.
    const before = calls.filter(x => x.startsWith('/api/state')).length;
    await page.waitForFunction(n => document.querySelector('#plugins').hidden === false && document.querySelector('#pluginRows details').open, before);
    await page.waitForTimeout(1650);
    assert.ok(calls.filter(x => x.startsWith('/api/state')).length > before);
    assert.equal(calls.filter(x => x.startsWith('/api/plugins')).length,1);
    assert.equal(await page.locator('#pluginRows details').first().getAttribute('open'),'');
    if (process.env.PLUGIN_SCREENSHOT) await page.screenshot({path:process.env.PLUGIN_SCREENSHOT,fullPage:true});
    await page.getByRole('button',{name:'Back to case',exact:true}).click();
    assert.equal(await page.locator('#caseTitle').innerText(),'Older case');
    assert.equal(await page.locator('#conversation').isVisible(),true);
    await page.locator('#openPlugins').click();
    assert.equal(calls.filter(x => x.startsWith('/api/plugins')).length,1);
    await page.locator('#pluginSource summary').click();
    await page.getByRole('checkbox',{name:'Native · Volatility 3 (1)'}).uncheck();
    mode = 'failure';
    await page.locator('#refreshPlugins').click();
    await page.waitForFunction(() => document.querySelector('#pluginStatus').textContent.includes('refresh failed'));
    assert.equal(await page.locator('#pluginRows tr').count(),3,'Failed refresh retains the three rows selected by the source filter');
    assert.match(await page.locator('#pluginError').innerText(),/Synthetic discovery failure/);
    assert.equal(await page.locator('#pluginSource summary').innerText(),'Source (3/4)');
    mode = 'empty';
    await page.locator('#refreshPlugins').click();
    await page.waitForFunction(() => document.querySelector('#pluginCount').textContent === '0 shown · 0 discovered');
    assert.match(await page.locator('#pluginRows').innerText(),/No plugins were discovered/);
    // A chosen subset survives an empty refresh and returns when the sources reappear.
    mode = 'normal';
    await page.locator('#refreshPlugins').click();
    await page.waitForFunction(() => document.querySelector('#pluginCount').textContent === '3 shown · 4 discovered');
    assert.equal(await page.getByRole('checkbox',{name:'Native · Volatility 3 (1)'}).isChecked(),false);
    // Catalog also remains open during empty-case state polls.
    state.cases = []; mode = 'normal';
    await page.reload();
    await page.locator('#openPlugins').click();
    await page.waitForFunction(() => document.querySelector('#pluginCount').textContent === '4 shown · 4 discovered');
    await page.waitForTimeout(1650);
    assert.equal(await page.locator('#plugins').isVisible(),true);
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),true);
    assert.deepEqual(errors,[]);
    assert.equal(await page.locator('#error').isVisible(),false);
    assert.ok(!calls.some(x => /jobs|pick|coverage|stop/.test(x)));
    console.log('PASS: catalog/search/filters/details/links/refresh/stale+empty states/case preservation/mobile; zero job requests');
  } finally {await browser.close();}
})().catch(e => {console.error(e);process.exitCode=1;});
