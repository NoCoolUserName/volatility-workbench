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
    assert (resources/'desktop-launcher').is_file()
    assert os.access(resources/'desktop-launcher',os.X_OK)
    with tempfile.TemporaryDirectory(prefix='workbench-package-check-') as temporary:
        temp=Path(temporary); env={'HOME':str(temp),'PATH':'/usr/bin:/bin','TMPDIR':str(temp),'LANG':'en_US.UTF-8'}
        native=subprocess.run([str(app/'Contents/MacOS/Volatility Workbench'),'--check-bundled-runtime'],
            cwd=temp,env={k:v for k,v in env.items() if k!='LANG'},capture_output=True,text=True,timeout=30,check=True)
        assert json.loads(native.stdout)['subprocess_unicode'] is True
        print(native.stdout.strip())
        script=r'''
import asyncio,importlib.metadata as m,json,os,platform,subprocess,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from volatility_mcp.api import Config,VolatilityBackend,decode_result
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
for asset in ('static/settings.html','static/settings.js','static/settings.css','static/app.js','static/zoom.js','static/icon.png','static/themes.js','static/themes.css','static/halloween-night.png'):
 assert files('volatility_workbench').joinpath(asset).read_bytes(),asset
scenes=list(files('volatility_workbench').joinpath('static').glob('theme-*.svg'))
assert len(scenes)==30 and all(scene.read_bytes() for scene in scenes)
core=json.loads(m.distribution('volatility-mcp').read_text('direct_url.json'))
assert core['vcs_info']['commit_id']==info['core_commit']
python=resources/'analyzer/bin/python3'; vol=resources/'analyzer/bin/vol'
probe=subprocess.run([str(python),'-I','-c','import platform,volatility3,capstone,yara,Crypto,PIL,Evtx,pypykatz; assert platform.machine()=="arm64"; print("native imports passed")'],capture_output=True,text=True,check=True)
evidence=root/'evidence'; evidence.mkdir(); output=root/'outputs'
config=Config(evidence,output,python,vol,cache_path=root/'symbols-cache')
path=root/'config.json'; path.write_text(json.dumps(config.to_dict()))
catalog=VolatilityBackend(config).list_plugins(refresh=True)
assert not catalog['import_failures'],catalog['import_failures']
plugins={p['name']:p for p in catalog['plugins']}
for name in ['windows.info.Info','windows.pslist.PsList','xpnet.XpNetScan','vol_pypykatz.pypykatz','windows.evtxlog.evtxlog']: assert name in plugins,name
assert plugins['vol_pypykatz.pypykatz']['source']['kind']=='third_party'
assert plugins['windows.evtxlog.evtxlog']['source']['kind']=='third_party'
assert plugins['xpnet.XpNetScan']['source']['kind']=='local'
async def check():
 async with Client(StdioServerParameters(command=sys.executable,args=['-I','-m','volatility_mcp','serve','--config',str(path)])) as client:
  tools=await client.list_tools(); assert {'list_plugins','query_output','get_coverage'} <= {x.name for x in tools.tools}
  result=decode_result(await client.call_tool('list_plugins',{'query':'evtxlog'}))
  assert not result.get('error'),result
  assert any(x['name']=='windows.evtxlog.evtxlog' for x in result['plugins'])
asyncio.run(check())
# A synthetic byte file exercises a real analyzer subprocess; never opens an image from the user.
fixture=evidence/'synthetic.raw'; fixture.write_bytes(b'\x00'*4096+b'Linux version 0.0.0 (SYNTHETIC TEST ONLY)\x00'+b'\x00'*4096)
run=subprocess.run([str(python),'-I',str(vol),'-q','-f',str(fixture),'banners.Banners'],capture_output=True,text=True,timeout=60)
assert run.returncode==0,(run.returncode,run.stderr[-1500:])
assert 'SYNTHETIC TEST ONLY' in run.stdout,run.stdout[-1500:]
print(json.dumps({'status':'passed','plugin_count':catalog['total'],'import_failures':catalog['import_failures'],'core_commit':info['core_commit'],'native_dependency_imports':True,'mcp_catalog_call':True,'synthetic_analyzer_invocations':1,'real_images_opened':0}))
'''
        result=subprocess.run([str(resources/'runtime/bin/python3'),'-I','-c',script,str(resources)],cwd=temp,env=env,capture_output=True,text=True,timeout=180)
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
