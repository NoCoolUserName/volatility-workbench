'use strict';
const byId=id=>document.getElementById(id);
// Preserve navigation context only; opening Settings never selects a provider
// target or starts/rebinds a case conversation.
const returnCase=new URLSearchParams(location.search).get('case');
if(returnCase)document.querySelector('.settings > header a').href='/?case='+encodeURIComponent(returnCase);
let initialized=false;
let providerState={},formProvider='codex';
const catalogs=new Map(),providerDrafts=new Map();
const defaultCodex={provider:'codex',model:'gpt-6-astra',reasoning_effort:'high'};
const effortLabels={none:'None',minimal:'Minimal',low:'Low',medium:'Medium',high:'High',xhigh:'Extra high',max:'Max',ultra:'Ultra'};
function option(select,value,label){const node=document.createElement('option');node.value=value;node.textContent=label;select.append(node);}
function selectedModel(){return byId('model').value==='__custom__'?byId('custom-model').value.trim():byId('model').value;}
function connectionConfig(provider=byId('provider').value){
  const config={provider,model:selectedModel(),reasoning_effort:byId('reasoning-effort').value||null};
  if(config.provider==='compatible'){config.endpoint=byId('endpoint').value;config.allow_case_content=byId('allow-case-content').checked;}
  else if(byId('codex-executable').value)config.codex_executable=byId('codex-executable').value;
  return config;
}
function catalogKey(config){return config.provider+':'+(config.provider==='compatible'?(config.endpoint||'').trim().replace(/\/$/,''):config.codex_executable||'');}
function modelEntries(config){
  const loaded=catalogs.get(catalogKey(config));
  return loaded?.models||(config.provider==='codex'?[{model:'gpt-6-astra',label:'GPT-6 Astra',efforts:['high','xhigh'],default_effort:'high'}]:[]);
}
function renderEfforts(wanted,changedModel=false){
  const config=connectionConfig(),select=byId('reasoning-effort');
  select.replaceChildren();select.disabled=false;
  if(config.provider==='compatible'){
    option(select,'','Provider default — no override');
    for(const effort of ['none','minimal','low','medium','high','xhigh','max'])option(select,effort,effortLabels[effort]);
    if(wanted&&!Array.from(select.options).some(item=>item.value===wanted))option(select,wanted,wanted+' (saved override)');
    select.value=wanted||'';
    byId('effort-note').textContent='Reasoning controls vary by endpoint and model. Provider default omits the parameter. Select an override only if this endpoint supports the OpenAI-compatible reasoning_effort field, then save and check tool capability. A passed check does not prove the provider honored the effort.';
  }else{
    const entry=modelEntries(config).find(item=>item.model===config.model);
    const efforts=entry?.efforts||[];
    if(!efforts.length){option(select,'','Provider default');select.disabled=true;}
    for(const effort of efforts)option(select,effort,effortLabels[effort]||effort);
    if(!changedModel&&wanted&&!efforts.includes(wanted)){option(select,wanted,wanted+' (saved; load models to verify)');select.disabled=false;}
    const preferred=config.model==='gpt-6-astra'&&efforts.includes('high')?'high':entry?.default_effort;
    select.value=Array.from(select.options).some(item=>item.value===wanted)?wanted:preferred||'';
    byId('effort-note').textContent=catalogs.has(catalogKey(config))?'Choices reflect the selected Codex model’s advertised reasoning levels.':'GPT-6 Astra defaults to High. Extra high is available here; load models to discover other models and their supported levels.';
  }
}
function renderModels(config){
  const select=byId('model'),entries=modelEntries(config),wanted=config.model||'';
  select.replaceChildren();
  for(const item of entries)option(select,item.model,item.label||item.model);
  if(wanted&&!entries.some(item=>item.model===wanted))option(select,wanted,wanted+' (saved; verify availability)');
  if(config.provider==='compatible')option(select,'__custom__','Custom model identifier…');
  select.value=wanted||(config.provider==='compatible'?'__custom__':'gpt-6-astra');
  byId('custom-model').value='';
  byId('custom-model-row').hidden=select.value!=='__custom__';
  renderEfforts('reasoning_effort' in config?config.reasoning_effort:(config.provider==='codex'?'high':''));
}
function loadProvider(config){
  const current=config.provider==='compatible'?config:{...defaultCodex,...config};
  formProvider=current.provider;byId('provider').value=formProvider;
  byId('endpoint').value=current.endpoint||'';byId('allow-case-content').checked=current.allow_case_content===true;
  byId('codex-executable').value=current.codex_executable||'';
  byId('secret').value='';providerFields();renderModels(current);
  byId('model-note').textContent=catalogs.has(catalogKey(current))?'Available model catalog loaded for this connection.':'Load available models for this connection. Workbench defaults to GPT-6 Astra / High; catalog access starts no investigation. Compatible discovery uses only a saved endpoint credential.';
}
async function request(path,body){
  const response=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const data=await response.json();
  if(!response.ok)throw new Error(data.error||'Settings request failed');
  return data;
}
function message(text){byId('settings-message').textContent=text;}
async function act(operation){try{const result=await operation();message('Saved.');await refresh();return result;}catch(error){message(error.message);}}
function providerFields(){byId('api-options').hidden=byId('provider').value!=='compatible';byId('codex-options').hidden=byId('provider').value!=='codex';}
async function refresh(){
  const data=await request('/api/settings');
  window.WorkbenchThemes.sync(data.appearance);
  providerState=data.provider;
  byId('settings-readiness').textContent=data.readiness.status+': '+data.readiness.reasons.join(' ');
  byId('state-root').textContent=data.state_dir;
  const locations=byId('evidence-locations');locations.replaceChildren();
  for(const item of data.evidence_locations||[]){
    const row=document.createElement('li');const path=document.createElement('code');path.textContent=item.path;row.append(path);
    row.append(document.createTextNode((item.default?' — default folder; ':' — ')+item.image_count+' registered image(s), '+item.case_count+' case(s)'));locations.append(row);
  }
  byId('analyzer-path').textContent=data.config.vol_python;
  byId('symbol-path').textContent=data.symbols.directory;
  byId('cache-path').textContent=data.symbols.cache;
  byId('symbol-matching').textContent=data.symbols.matching;
  byId('mac-symbol-note').textContent=data.symbols.profile.macos_status;
  byId('location-note').textContent=data.has_cases?'Existing case paths are preserved. Add images from other physical folders in Workbench; their locations appear below. Changing default roots here is disabled while cases exist.':'Choose physical folders; this does not move or copy evidence. You can skip setup and return to saved material.';
  byId('evidence-root').disabled=data.has_cases;byId('output-root').disabled=data.has_cases;
  document.querySelectorAll('[data-folder]').forEach(button=>button.disabled=data.has_cases||!data.native_folder_picker);
  byId('choose-symbol').disabled=!data.native_folder_picker;
  byId('install-plugins').disabled=!data.managed_runtime_available||data.operation.status==='running';
  byId('plugin-note').textContent=data.managed_runtime_available?'No plugins are installed by opening this page.':'Managed overlay installation is available in the complete desktop package. Your current configured analyzer remains usable.';
  byId('operation').textContent=JSON.stringify(data.operation,null,2);
  const list=byId('symbol-packs');
  if(list.dataset.profile!==JSON.stringify(data.symbols.profile.packs)){
    list.replaceChildren();list.dataset.profile=JSON.stringify(data.symbols.profile.packs);
    for(const pack of data.symbols.profile.packs){
      const div=document.createElement('div');div.className='pack';
      const name=document.createElement('strong');name.textContent=pack.label+' · '+pack.version+' · '+(pack.size/1_000_000).toFixed(2)+' MB';div.append(name);
      const detail=document.createElement('p');detail.textContent=pack.limitations;div.append(detail);
      const provenance=document.createElement('small');provenance.textContent=pack.url+'\nSHA-256: '+pack.sha256;div.append(provenance);
      const button=document.createElement('button');button.dataset.pack=pack.id;button.textContent='Download this pack';button.addEventListener('click',()=>act(()=>request('/api/settings/symbols/download',{pack:pack.id})));div.append(button);list.append(div);
    }
  }
  for(const button of list.querySelectorAll('button[data-pack]')){
    const installed=data.symbols.installed?.[button.dataset.pack]===true;
    button.textContent=installed?'Installed':'Download this pack';
    button.disabled=installed||data.operation.status==='running';
  }
  const allInstalled=data.symbols.profile.packs.length>0&&data.symbols.profile.packs.every(pack=>data.symbols.installed?.[pack.id]===true);
  byId('all-symbols').textContent=allInstalled?'Installed':'Download all supported packs';
  byId('all-symbols').disabled=allInstalled||data.operation.status==='running';
  if(!initialized){
    byId('evidence-root').value=data.config.evidence_root;byId('output-root').value=data.config.output_root;
    const provider=data.provider;
    for(const item of provider.cases||[]){const option=document.createElement('option');option.value=item.case_id;option.textContent=(item.title||item.case_id)+' — '+(item.provider.provider||'codex');byId('provider-case').append(option);}
    const current=typeof provider.default_provider==='object'?provider.default_provider:provider;
    loadProvider({provider:'codex',...current});
    providerFields();initialized=true;message('Settings ready. No analysis was started.');
  }
}
document.querySelectorAll('[data-folder]').forEach(button=>button.addEventListener('click',()=>act(async()=>{const result=await request('/api/settings/pick-folder',{kind:'folder'});if(result.path)byId(button.dataset.folder).value=result.path;})));
byId('locations').addEventListener('submit',event=>{event.preventDefault();act(()=>request('/api/settings/save',{evidence_root:byId('evidence-root').value,output_root:byId('output-root').value}));});
byId('provider').addEventListener('change',()=>{
  const next=byId('provider').value;
  const draft=connectionConfig(formProvider);providerDrafts.set(formProvider,draft);
  loadProvider(providerDrafts.get(next)||{provider:next});
});
byId('provider-case').addEventListener('change',()=>{
  const id=byId('provider-case').value;byId('new-provider-session').disabled=!id;byId('new-provider-session').checked=false;
  const current=id?providerState.cases.find(item=>item.case_id===id)?.provider:providerState.default_provider;
  if(current)loadProvider(current);
});
byId('model').addEventListener('change',()=>{byId('custom-model-row').hidden=byId('model').value!=='__custom__';renderEfforts(byId('reasoning-effort').value,true);});
byId('load-models').addEventListener('click',async()=>{
  const button=byId('load-models');button.disabled=true;
  try{
    const config=connectionConfig(),key=catalogKey(config);byId('model-note').textContent='Loading model catalog; no case content is sent…';
    const result=await request('/api/settings/provider/models',{config});
    catalogs.set(key,result);
    if(catalogKey(connectionConfig())===key){renderModels(config);byId('model-note').textContent=result.models.length+' models loaded. Choose a model, then save. Unsaved secrets are not used for discovery.';}
  }catch(error){byId('model-note').textContent=error.message;}
  finally{button.disabled=false;}
});
byId('endpoint').addEventListener('input',()=>{byId('allow-case-content').checked=false;const config=connectionConfig();renderModels(config);byId('model-note').textContent='Endpoint changed. Load models for this endpoint or enter its documented model identifier.';});
byId('provider-form').addEventListener('submit',event=>{event.preventDefault();act(async()=>{const config=connectionConfig();
if(byId('provider-case').value){config.case_id=byId('provider-case').value;config.new_session=byId('new-provider-session').checked;}
const secret=byId('secret').value;byId('secret').value='';const result=await request('/api/settings/provider',{config,secret:secret||undefined,storage:byId('secret-storage').value});byId('provider-result').textContent=JSON.stringify(result,null,2);});});
byId('check-provider').addEventListener('click',()=>act(async()=>{message('Checking saved connection for the selected scope…');const result=await request('/api/settings/provider/check',{case_id:byId('provider-case').value||null});byId('provider-result').textContent=JSON.stringify(result,null,2);}));
byId('install-plugins').addEventListener('click',()=>act(()=>request('/api/settings/plugins/install',{})));
byId('all-symbols').addEventListener('click',()=>act(()=>request('/api/settings/symbols/download',{pack:'all'})));
byId('choose-symbol').addEventListener('click',()=>act(async()=>{const result=await request('/api/settings/pick-folder',{kind:'symbol'});if(result.path)byId('symbol-file').value=result.path;}));
byId('symbol-import').addEventListener('submit',event=>{event.preventDefault();act(()=>request('/api/settings/symbols/import',{path:byId('symbol-file').value}));});
(async()=>{try{const token=location.hash.slice(1);if(token){await request('/api/unlock',{token});history.replaceState(null,'',location.pathname);}await refresh();setInterval(()=>refresh().catch(error=>message(error.message)),2000);}catch(error){message(error.message);}})();
