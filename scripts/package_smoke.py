#!/usr/bin/env python3
"""Build/install both declared packages in isolation and launch outside the checkouts."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import venv
import zipfile
from build_macos import source_snapshot

ROOT = Path(__file__).resolve().parents[1]


def run(*args, **kwargs):
    subprocess.run(args, check=True, **kwargs)


def main():
    with tempfile.TemporaryDirectory(prefix='workbench-package-') as temp:
        temp = Path(temp).resolve()
        env = temp/'venv'; venv.EnvBuilder(with_pip=True).create(env)
        python = str(env/'bin/python')
        source=temp/'source';source.mkdir()
        source_snapshot(source)
        run(sys.executable, '-m', 'pip', 'wheel', '--no-deps', '--wheel-dir', str(temp), str(source))
        wheel = next(temp.glob('volatility_workbench-*.whl'))
        with zipfile.ZipFile(wheel) as archive:
            for relative in ('LICENSE', 'THIRD_PARTY_NOTICES.md', 'LICENSING.md', 'licenses/DEPENDENCY_LICENSES.txt',
                             'licenses/MIT.txt', 'licenses/LicenseRef-Volatility-Software-License-1.0.txt'):
                matches = [name for name in archive.namelist() if name.endswith('.dist-info/licenses/' + relative)]
                assert len(matches) == 1, f'Missing wheel notice: {relative}'
                assert archive.read(matches[0]) == (ROOT/relative).read_bytes()
        # Installing the wheel itself must bring in the pinned core dependency.
        run(python, '-m', 'pip', 'install', '-c', str(ROOT/'requirements.lock.txt'), str(wheel), cwd=temp)
        run(python, '-m', 'pip', 'check', cwd=temp)
        code = r'''
import asyncio, hashlib, json, os, subprocess, sys, threading, urllib.request
from pathlib import Path
from importlib.resources import files
from importlib.metadata import distribution
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from volatility_mcp.api import Config, report_spec, decode_result
from volatility_mcp.api import linux_symbol_catalog
assert linux_symbol_catalog()["tables"] == 10255
from volatility_workbench.app import Workbench
from volatility_workbench.http import Server
from volatility_workbench.compatibility import require_core
assert require_core().API_VERSION == 1
from volatility_mcp.addons import profile
addon_profile=profile()
for crypto in ('windows.cryptomem.CryptoMem', 'linux.cryptomem.CryptoMem', 'mac.cryptomem.CryptoMem'):
 assert crypto in addon_profile['offline_plugins'] and crypto in addon_profile['manual_only_plugins']
 assert any(crypto in source['plugins'] for source in addon_profile['sources'])
assert 'site-packages' in str(files('volatility_mcp'))
assert 'site-packages' in str(files('volatility_workbench'))
assert distribution('volatility-workbench').read_text('licenses/LICENSING.md')
for name in ('volatility-mcp','volatility-workbench'):
    package=distribution(name)
    assert package.metadata['License-Expression']=='MIT OR LicenseRef-Volatility-Software-License-1.0'
    assert 'Volatility Software License' in package.read_text('licenses/licenses/LicenseRef-Volatility-Software-License-1.0.txt')
    assert 'MIT License' in package.read_text('licenses/licenses/MIT.txt')
assert 'Executive summary' in report_spec()
for p in ['static/app.js','static/volshell.js','static/zoom.js','static/index.html','static/style.css','static/themes.js','static/themes.css','static/theme-halloween.svg','static/halloween-night.png','static/icon.png','static/settings.html','static/settings.js','resources/symbols.json','templates/report.md']:
    assert files('volatility_workbench').joinpath(p).read_bytes()
scenes=[p for p in files('volatility_workbench').joinpath('static').iterdir() if p.name.startswith('theme-') and p.name.endswith('.svg')]
assert len(scenes)==29 and all(p.read_bytes() for p in scenes)
bezel_manifest=json.loads(files('volatility_workbench').joinpath('resources/reference-terminal-assets.json').read_text())
assert len(bezel_manifest['assets'])==3
assert json.loads(files('volatility_workbench').joinpath('resources/reference-terminal-prompts.json').read_text())['mode']=='built-in image_gen'
for asset in bezel_manifest['assets']:
    data=files('volatility_workbench').joinpath('static',asset['asset']).read_bytes()
    assert len(data)==asset['bytes'] and hashlib.sha256(data).hexdigest()==asset['sha256']
root=Path.cwd(); evidence=root/'evidence';evidence.mkdir()
config=Config(evidence, root/'outputs', Path(sys.executable),Path(sys.executable),cache_path=root/'cache',enable_xpnet=False)
path=root/'config.json';path.write_text(json.dumps(config.to_dict()))
async def main():
    # Real SDK stdio discovery in both supported modes, without analysis.
    for mode in ['legacy','auto']:
        async with Client(StdioServerParameters(command=sys.executable,args=['-m','volatility_mcp','serve','--config',str(path)]),mode=mode) as client:
            names={t.name for t in (await client.list_tools()).tools}
            assert len(names)==10 and {'query_output','get_coverage','inspect_artifact'} <= names
    calls=[]
    def forbidden(*a,**kw):calls.append(a);raise AssertionError('No analysis or model subprocess permitted')
    subprocess.Popen=forbidden
    app=Workbench(path,root/'state')
    await app.start()
    server=Server(app,0,asyncio.get_running_loop())
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    def check():
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        paths=['/','/app.js','/volshell.js','/zoom.js','/style.css','/themes.js','/themes.css','/halloween-night.png','/icon.png','/settings.html','/settings.js','/settings.css','/api/state']+['/'+p.name for p in scenes]+['/'+item['asset'] for item in bezel_manifest['assets']]
        for path in paths:
            request=urllib.request.Request(server.origin+path,headers={'Cookie':'volatility_ui='+server.token})
            with opener.open(request) as response: assert response.status==200
    try: await asyncio.to_thread(check)
    finally:
        await app.close();await asyncio.to_thread(server.shutdown);server.server_close()
    assert not calls
asyncio.run(main())
print('Installed wheels: ten MCP tools in both modes; assets, HTTP launch, and zero analysis/model subprocesses passed')
'''
        run(python, '-c', code, cwd=temp)
        run(str(env/'bin/volatility-workbench'), '--help', cwd=temp)
        # Existing application regressions must run against installed packages too.
        run(python, '-m', 'unittest', 'discover', '-s', str(ROOT/'tests'), '-q', cwd=temp)


if __name__ == '__main__': main()
