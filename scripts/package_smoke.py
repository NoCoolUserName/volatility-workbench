#!/usr/bin/env python3
"""Build/install both declared packages in isolation and launch outside the checkouts."""
import json
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import venv

ROOT = Path(__file__).resolve().parents[1]


def run(*args, **kwargs):
    subprocess.run(args, check=True, **kwargs)


def main():
    with tempfile.TemporaryDirectory(prefix='workbench-package-') as temp:
        temp = Path(temp).resolve()
        env = temp/'venv'; venv.EnvBuilder(with_pip=True).create(env)
        python = str(env/'bin/python')
        source=temp/'source';source.mkdir()
        for name in ('pyproject.toml','README.md','LICENSE','THIRD_PARTY_NOTICES.md'): shutil.copy2(ROOT/name,source/name)
        shutil.copytree(ROOT/'src',source/'src',ignore=shutil.ignore_patterns('__pycache__','*.egg-info','*.pyc'))
        run(sys.executable, '-m', 'pip', 'wheel', '--no-deps', '--wheel-dir', str(temp), str(source))
        wheel = next(temp.glob('volatility_workbench-*.whl'))
        # Installing the wheel itself must bring in the pinned core dependency.
        run(python, '-m', 'pip', 'install', '-c', str(ROOT/'requirements.lock.txt'), str(wheel), cwd=temp)
        run(python, '-m', 'pip', 'check', cwd=temp)
        code = r'''
import asyncio, json, os, subprocess, sys, threading, urllib.request
from pathlib import Path
from importlib.resources import files
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from volatility_mcp.api import Config, report_spec, decode_result
from volatility_workbench.app import Workbench
from volatility_workbench.http import Server
from volatility_workbench.compatibility import require_core
assert require_core().API_VERSION == 1
assert 'site-packages' in str(files('volatility_mcp'))
assert 'site-packages' in str(files('volatility_workbench'))
assert 'Executive summary' in report_spec()
for p in ['static/app.js','static/index.html','static/style.css','templates/report.md']:
    assert files('volatility_workbench').joinpath(p).read_bytes()
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
        for path in ['/','/app.js','/style.css','/api/state']:
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
