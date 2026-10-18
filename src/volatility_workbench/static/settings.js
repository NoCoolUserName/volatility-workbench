'use strict';
const byId=id=>document.getElementById(id);
let initialized=false;
try {const theme=localStorage.getItem('volatility-workbench-theme');if(['matrix','mono','blue'].includes(theme))document.documentElement.dataset.theme=theme;} catch {}
async function request(path,body){
  const response=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const data=await response.json();
  if(!response.ok)throw new Error(data.error||'Settings request failed');
  return data;
}
function message(text){byId('settings-message').textContent=text;}
async function act(operation){try{const result=await operation();message('Saved.');await refresh();return result;}catch(error){message(error.message);}}
function providerFields(){byId('api-options').hidden=byId('provider').value!=='compatible';byId('codex-executable').disabled=byId('provider').value!=='codex';}
async function refresh(){
  const data=await request('/api/settings');
  byId('settings-readiness').textContent=data.readiness.status+': '+data.readiness.reasons.join(' ');
  byId('state-root').textContent=data.state_dir;
  byId('analyzer-path').textContent=data.config.vol_python;
  byId('symbol-path').textContent=data.symbols.directory;
  byId('cache-path').textContent=data.symbols.cache;
  byId('symbol-matching').textContent=data.symbols.matching;
  byId('mac-symbol-note').textContent=data.symbols.profile.macos_status;
  byId('location-note').textContent=data.has_cases?'Your existing paths are authoritative. Changing roots here is disabled while cases exist.':'Choose physical folders; this does not move or copy evidence. You can skip setup and return to saved material.';
  byId('evidence-root').disabled=data.has_cases;byId('output-root').disabled=data.has_cases;
  document.querySelectorAll('[data-folder]').forEach(button=>button.disabled=data.has_cases||!data.native_folder_picker);
  byId('choose-symbol').disabled=!data.native_folder_picker;
  byId('install-plugins').disabled=!data.managed_runtime_available||data.operation.status==='running';
  byId('plugin-note').textContent=data.managed_runtime_available?'No plugins are installed by opening this page.':'Managed overlay installation is available in the complete desktop package. Your current configured analyzer remains usable.';
  byId('operation').textContent=JSON.stringify(data.operation,null,2);
  if(!initialized){
    byId('evidence-root').value=data.config.evidence_root;byId('output-root').value=data.config.output_root;
    const provider=data.provider;
    for(const item of provider.cases||[]){const option=document.createElement('option');option.value=item.case_id;option.textContent=(item.title||item.case_id)+' — '+(item.provider.provider||'codex');byId('provider-case').append(option);}
    const current=typeof provider.default_provider==='object'?provider.default_provider:provider;
    byId('provider').value=current.provider||provider.default_provider||'codex';
    byId('endpoint').value=current.endpoint||'';byId('model').value=current.model||'';byId('allow-case-content').checked=current.allow_case_content===true;
    byId('codex-executable').value=current.codex_executable||'';
    const list=byId('symbol-packs');list.replaceChildren();
    for(const pack of data.symbols.profile.packs){
      const div=document.createElement('div');div.className='pack';
      const name=document.createElement('strong');name.textContent=pack.label+' · '+pack.version+' · '+(pack.size/1024/1024).toFixed(2)+' MiB';div.append(name);
      const detail=document.createElement('p');detail.textContent=pack.limitations;div.append(detail);
      const provenance=document.createElement('small');provenance.textContent=pack.url+'\nSHA-256: '+pack.sha256;div.append(provenance);
      const button=document.createElement('button');button.textContent='Download this pack';button.addEventListener('click',()=>act(()=>request('/api/settings/symbols/download',{pack:pack.id})));div.append(button);list.append(div);
    }
    providerFields();initialized=true;message('Settings ready. No analysis was started.');
  }
}
document.querySelectorAll('[data-folder]').forEach(button=>button.addEventListener('click',()=>act(async()=>{const result=await request('/api/settings/pick-folder',{kind:'folder'});if(result.path)byId(button.dataset.folder).value=result.path;})));
byId('locations').addEventListener('submit',event=>{event.preventDefault();act(()=>request('/api/settings/save',{evidence_root:byId('evidence-root').value,output_root:byId('output-root').value}));});
byId('provider').addEventListener('change',providerFields);
byId('provider-case').addEventListener('change',()=>{byId('new-provider-session').disabled=!byId('provider-case').value;if(!byId('provider-case').value)byId('new-provider-session').checked=false;});
byId('endpoint').addEventListener('input',()=>{byId('allow-case-content').checked=false;});
byId('provider-form').addEventListener('submit',event=>{event.preventDefault();act(async()=>{const config={provider:byId('provider').value};if(config.provider==='compatible'){config.endpoint=byId('endpoint').value;config.model=byId('model').value;config.allow_case_content=byId('allow-case-content').checked;}else if(byId('codex-executable').value){config.codex_executable=byId('codex-executable').value;}
if(byId('provider-case').value){config.case_id=byId('provider-case').value;config.new_session=byId('new-provider-session').checked;}
const secret=byId('secret').value;byId('secret').value='';const result=await request('/api/settings/provider',{config,secret:secret||undefined,storage:byId('secret-storage').value});byId('provider-result').textContent=JSON.stringify(result,null,2);});});
byId('check-provider').addEventListener('click',()=>act(async()=>{message('Checking configured provider…');const result=await request('/api/settings/provider/check',{});byId('provider-result').textContent=JSON.stringify(result,null,2);}));
byId('install-plugins').addEventListener('click',()=>act(()=>request('/api/settings/plugins/install',{})));
byId('all-symbols').addEventListener('click',()=>act(()=>request('/api/settings/symbols/download',{pack:'all'})));
byId('choose-symbol').addEventListener('click',()=>act(async()=>{const result=await request('/api/settings/pick-folder',{kind:'symbol'});if(result.path)byId('symbol-file').value=result.path;}));
byId('symbol-import').addEventListener('submit',event=>{event.preventDefault();act(()=>request('/api/settings/symbols/import',{path:byId('symbol-file').value}));});
(async()=>{try{const token=location.hash.slice(1);if(token){await request('/api/unlock',{token});history.replaceState(null,'',location.pathname);}await refresh();setInterval(()=>refresh().catch(error=>message(error.message)),2000);}catch(error){message(error.message);}})();
