#!/usr/bin/env python3
"""Validate a built app using its real Python interpreters and synthetic data."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('app',type=Path)
    args=parser.parse_args(); app=args.app.resolve(); resources=app/'Contents/Resources'
    if not (resources/'build-info.json').is_file(): raise SystemExit('Not a Workbench build')
    info=json.loads((resources/'build-info.json').read_text())
    adventure = resources/'adventure'
    game = json.loads((adventure/'manifest.json').read_text())
    assert set(game['editions']) == {'1977', '1995'}
    assert info['adventure'] == game
    for edition in ('350', '430'):
        assert (adventure/('COPYING-'+edition)).read_bytes() == (resources/('notices/adventure-'+edition+'-COPYING')).read_bytes()
    executable = adventure/game['editions']['1995']['executable']
    import hashlib
    assert hashlib.sha256(executable.read_bytes()).hexdigest() == game['editions']['1995']['sha256']
    classic = adventure/game['editions']['1977']['executable']
    assert hashlib.sha256(classic.read_bytes()).hexdigest() == game['editions']['1977']['sha256']
    assert hashlib.sha256((adventure/'glorkz-350').read_bytes()).hexdigest() == game['editions']['1977']['game_data_sha256']
    for binary in (executable, classic):
        architecture = subprocess.run(['/usr/bin/lipo','-archs',str(binary)],capture_output=True,text=True,check=True).stdout.split()
        assert architecture == ['arm64'],architecture
    assert (resources/'desktop-launcher').is_file()
    assert os.access(resources/'desktop-launcher',os.X_OK)
    with tempfile.TemporaryDirectory(prefix='workbench-package-check-') as temporary:
        temp=Path(temporary).resolve(); env={'HOME':str(temp),'PATH':'/usr/bin:/bin','TMPDIR':str(temp),'LANG':'en_US.UTF-8'}
        native=subprocess.run([str(app/'Contents/MacOS/Volatility Workbench'),'--check-bundled-runtime'],
            cwd=temp,env={k:v for k,v in env.items() if k!='LANG'},capture_output=True,text=True,timeout=30,check=True)
        assert json.loads(native.stdout)['subprocess_unicode'] is True
        print(native.stdout.strip())
        gameplay=subprocess.run([str(executable),'-o','-a',str(temp/'adventure.save'),'-'],
            input='no\nquit\nyes\n',cwd=temp,env=env,capture_output=True,text=True,timeout=20)
        if gameplay.returncode or 'road' not in gameplay.stdout.lower():
            raise SystemExit('Packaged 430-point Adventure gameplay smoke failed: '+gameplay.stdout[-500:]+gameplay.stderr[-500:])
        assert (temp/'adventure.save').is_file()
        print(json.dumps({'adventure_430':'gameplay-and-save-passed','architecture':architecture}))
        classic_env = {**env, 'VOLATILITY_ADVENTURE_SAVE':str(temp/'classic.save')}
        classic_run=subprocess.run([str(classic)],input='no\nsuspend\nyes\n',cwd=temp,
            env=classic_env,capture_output=True,text=True,timeout=20)
        if classic_run.returncode or 'road' not in classic_run.stdout.lower() or not (temp/'classic.save').is_file():
            raise SystemExit('Packaged 350-point Adventure gameplay or save failed: '+classic_run.stdout[-500:]+classic_run.stderr[-500:])
        print(json.dumps({'adventure_350':'gameplay-and-save-passed','architecture':architecture}))
        script=r'''
import asyncio,hashlib,importlib.metadata as m,json,os,platform,subprocess,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from volatility_mcp.api import Config,VolatilityBackend,decode_result
from volatility_mcp.api import linux_symbol_catalog
assert linux_symbol_catalog()["tables"] == 10255
import volatility_workbench,webview,AppKit,WebKit
from importlib.resources import files
from volatility_workbench import desktop,settings,symbols,providers,runtime_management
resources=Path(sys.argv[1]); root=Path.cwd(); info=json.loads((resources/'build-info.json').read_text())
assert platform.machine()=='arm64'
assert Path(sys.executable).resolve().is_relative_to(resources)
assert Path(volatility_workbench.__file__).resolve().is_relative_to(resources)
assert not list((resources/'runtime').rglob('*.egg-link'))
assert all(Path(x).resolve().is_relative_to(resources) for x in sys.path),sys.path
assert sys.dont_write_bytecode
manifest=json.loads((resources/'distribution.json').read_text())
profile=json.loads(files('volatility_workbench').joinpath('resources/symbols.json').read_text())
assert profile['profile']==manifest['symbols']['profile']
for asset in ('static/settings.html','static/settings.js','static/settings.css','static/app.js','static/zoom.js','static/icon.png','static/themes.js','static/themes.css','static/adventure.js','static/halloween-night.png'):
 assert files('volatility_workbench').joinpath(asset).read_bytes(),asset
scenes=list(files('volatility_workbench').joinpath('static').glob('theme-*.svg'))
assert len(scenes)==29 and all(scene.read_bytes() for scene in scenes)
core=json.loads(m.distribution('volatility-mcp').read_text('direct_url.json'))
assert core['archive_info']['hashes']['sha256']==manifest['core_bundle']['sha256']
assert info['core_bundle']==manifest['core_bundle']
bundle=json.loads(files('volatility_mcp').joinpath('resources/symbol-bundle.json').read_text())
assert bundle['source_revision']==info['core_commit'] and len(bundle['packs'])==4
assert files('volatility_mcp').joinpath('resources/SYMBOL_PACK_NOTICES.md').read_bytes()
# Exercise actual first-run provisioning with all network access forbidden.
from types import SimpleNamespace
from unittest.mock import patch
from volatility_mcp import symbol_packs
args=SimpleNamespace(preferences_dir=str(root/'fresh-preferences'),config=None,state_dir=None,clean_setup=True)
with patch.object(symbol_packs, '_download', side_effect=AssertionError('no symbol download')), patch('socket.create_connection', side_effect=AssertionError('no network')):
 preferences, fresh_path, _, _=desktop.bootstrap(args, resources)
from volatility_mcp.api import load_config
fresh=load_config(fresh_path)
for pack in bundle['packs']:
 with (fresh.symbols/pack['name']).open('rb') as stream:
  assert hashlib.file_digest(stream,'sha256').hexdigest()==pack['sha256']
assert not list(fresh.evidence_root.iterdir()) and not list(fresh.output_root.iterdir())
print(json.dumps({'bundled_symbol_packs':4,'first_run_symbol_downloads':0,'private_images_opened':0}))
python=resources/'analyzer/bin/python3'; vol=resources/'analyzer/bin/vol'
probe=subprocess.run([str(python),'-I','-c','import platform,volatility3,capstone,yara,Crypto,PIL,Evtx,pypykatz; assert platform.machine()=="arm64"; print("native imports passed")'],capture_output=True,text=True,check=True)
evidence=root/'evidence'; evidence.mkdir(); output=root/'outputs'
config=Config(evidence,output,python,vol,cache_path=root/'symbols-cache')
path=root/'config.json'; path.write_text(json.dumps(config.to_dict()))
catalog=VolatilityBackend(config).list_plugins(refresh=True)
assert not catalog['import_failures'],catalog['import_failures']
plugins={p['name']:p for p in catalog['plugins']}
for name in ['windows.info.Info','windows.pslist.PsList','xpnet.XpNetScan','vol_pypykatz.pypykatz','windows.evtxlog.evtxlog','windows.cryptomem.CryptoMem','linux.cryptomem.CryptoMem']: assert name in plugins,name
assert plugins['vol_pypykatz.pypykatz']['source']['kind']=='third_party'
assert plugins['windows.evtxlog.evtxlog']['source']['kind']=='third_party'
assert plugins['xpnet.XpNetScan']['source']['kind']=='local'
crypto='windows.cryptomem.CryptoMem'
assert plugins[crypto]['source']['kind']=='third_party' and plugins[crypto]['manual_only']
assert plugins[crypto]['plugin_version']==[0,3,0]
linux_crypto='linux.cryptomem.CryptoMem'
assert plugins[linux_crypto]['plugin_version']==[0,3,0] and plugins[linux_crypto]['manual_only']
from volatility_mcp.addons import profile as addon_profile
inventory=addon_profile()
assert {crypto,linux_crypto} <= set(inventory['offline_plugins'])
from dataclasses import replace
without_xp=VolatilityBackend(replace(config,enable_xpnet=False)).list_plugins(refresh=True)
assert {crypto,linux_crypto} <= {p['name'] for p in without_xp['plugins']}
assert not without_xp['import_failures']
source=next(s for s in inventory['sources'] if crypto in s['plugins'])
for item in source['files']:
 original=resources/'notices'/source['repository']/item['path']
 installed=resources/'analyzer/lib/python3.12/site-packages/volatility3/framework/plugins'/item['target']
 assert hashlib.sha256(original.read_bytes()).hexdigest()==item['sha256']
 assert hashlib.sha256(installed.read_bytes()).hexdigest()==item['installed_sha256']
for item in source['notices']:
 assert hashlib.sha256((resources/'notices'/source['repository']/item['path']).read_bytes()).hexdigest()==item['sha256']
# Exercise the installed detector with a public format vector, without an image.
vector="from volatility3.plugins.windows.cryptomem_formats import find_artifacts; rows=list(find_artifacts(b' 1BoatSLRHtKNngkdXEeobR76b53LETtpyT ', {'BTC'})); assert len(rows)==1 and rows[0]['offset']==1 and rows[0]['validation']=='checksum_valid'"
subprocess.run([str(python),'-I','-c',vector],cwd=root,env=os.environ,check=True)
# Generated arbitrary payload, not a real wallet; checks the installed Monero path.
monero="from volatility3.plugins.windows.cryptomem_formats import find_artifacts; rows=list(find_artifacts(b' 41d7ke5VQnR2BDNSgrTE9j3X8QQ5Bnbbs4s3SMTX7y416CxUJqrTLW97YsWGEBnhxH8tnYDcX85QRAEhaAzrTSrZ89rbBUS ', {'XMR'})); assert len(rows)==1 and rows[0]['offset']==1 and rows[0]['validation']=='checksum_valid' and rows[0]['format']=='Monero-standard'"
subprocess.run([str(python),'-I','-c',monero],cwd=root,env=os.environ,check=True)

fixture=evidence/'synthetic.raw'; fixture.write_bytes(b'\x00'*4096+b'Linux version 0.0.0 (SYNTHETIC TEST ONLY)\x00'+b'\x00'*4096)
original_hash=hashlib.sha256(fixture.read_bytes()).hexdigest()
async def check():
 async with Client(StdioServerParameters(command=sys.executable,args=['-I','-m','volatility_mcp','serve','--config',str(path)])) as client:
  tools=await client.list_tools(); assert len(tools.tools)==10 and {'list_plugins','query_output','get_coverage'} <= {x.name for x in tools.tools}
  result=decode_result(await client.call_tool('list_plugins',{'query':'evtxlog'}))
  assert not result.get('error'),result
  assert any(x['name']=='windows.evtxlog.evtxlog' for x in result['plugins'])
  for name in (crypto,linux_crypto):
   result=decode_result(await client.call_tool('list_plugins',{'query':name}))
   assert not result.get('error') and len(result['plugins'])==1,result
   assert result['plugins'][0]['name']==name and result['plugins'][0]['manual_only']
  result=decode_result(await client.call_tool('run_plugin',{'image':'synthetic.raw','plugin':linux_crypto,'arguments':['--pid','42']}))
  assert result['status']=='error' and result['integrity_verified'] and not result['reuse_eligible'],result
  assert '--offline' in result['commands'][0]['argv']
  assert hashlib.sha256(fixture.read_bytes()).hexdigest()==original_hash
asyncio.run(check())
# A synthetic byte file exercises a real analyzer subprocess; never opens an image from the user.
run=subprocess.run([str(python),'-I',str(vol),'-q','-f',str(fixture),'banners.Banners'],capture_output=True,text=True,timeout=60)
assert run.returncode==0,(run.returncode,run.stderr[-1500:])
assert 'SYNTHETIC TEST ONLY' in run.stdout,run.stdout[-1500:]
print(json.dumps({'status':'passed','plugin_count':catalog['total'],'import_failures':catalog['import_failures'],'core_commit':info['core_commit'],'native_dependency_imports':True,'mcp_catalog_call':True,'cryptomem_discovery_and_vector':True,'synthetic_analyzer_invocations':2,'linux_cryptomem_mcp_failure':True,'real_images_opened':0}))
'''
        result=subprocess.run([str(resources/'runtime/bin/python3'),'-I','-c',script,str(resources)],cwd=temp,env=env,capture_output=True,text=True,timeout=1800)
        if result.returncode:
            print(result.stdout); print(result.stderr,file=sys.stderr); raise SystemExit(result.returncode)
        print(result.stdout.strip())
    subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(app)],check=True)
    # No Mach-O may require a developer's Python/Homebrew directory.
    for path in app.rglob('*'):
        if not path.is_file() or path.is_symlink(): continue
        with path.open('rb') as stream: header=stream.read(4)
        if header not in (b'\xcf\xfa\xed\xfe',b'\xfe\xed\xfa\xcf',b'\xca\xfe\xba\xbe',b'\xbe\xba\xfe\xca'): continue
        linked=subprocess.run(['/usr/bin/otool','-L',str(path)],capture_output=True,text=True,check=True).stdout
        # LC_ID_DYLIB is this library's label, not a loaded dependency. Wheels
        # can retain build labels while all consumers use @loader_path correctly.
        identities=subprocess.run(['/usr/bin/otool','-D',str(path)],capture_output=True,text=True,check=True).stdout
        own_ids={line.strip() for line in identities.splitlines() if line and not line.endswith(':')}
        for line in linked.splitlines():
            if not line.startswith('\t'): continue  # skip per-architecture universal Mach-O headers
            dependency=line.strip().split(' (')[0]
            if dependency in own_ids: continue
            if dependency.startswith('/') and not dependency.startswith(('/usr/lib/','/System/Library/')):
                raise SystemExit('Nonportable linked library: '+dependency)
    print(json.dumps({'codesign':'verified','native_linkage':'system-or-bundle-relative','workbench_commit':info['workbench_commit'],'source_dirty':info['source_dirty']}))

if __name__=='__main__': main()
