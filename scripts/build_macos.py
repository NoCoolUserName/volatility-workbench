#!/usr/bin/env python3
"""Build the pinned standalone ARM64 application; never copy a development venv."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def run(argv, **kw):
    return subprocess.run([str(x) for x in argv], check=True, shell=False, **kw)


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def fetch(url, target, expected):
    if not target.exists() or digest(target) != expected:
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_suffix(target.suffix + '.partial')
        try:
            with urllib.request.urlopen(url, timeout=60) as source, partial.open('wb') as out:
                shutil.copyfileobj(source, out)
            if digest(partial) != expected:
                raise ValueError('Download SHA-256 mismatch: ' + target.name)
            partial.replace(target)
        finally:
            partial.unlink(missing_ok=True)
    return target


def unpack(archive, destination):
    # Python's data filter rejects absolute/traversing paths and unsafe links.
    with tarfile.open(archive, 'r:gz') as source:
        source.extractall(destination, filter='data')


def source_snapshot(destination):
    for name in ('src', 'pyproject.toml', 'README.md', 'LICENSE', 'THIRD_PARTY_NOTICES.md'):
        source = ROOT / name
        if source.is_dir():
            shutil.copytree(source, destination/name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.egg-info'))
        else:
            shutil.copy2(source, destination/name)
    parts = []
    for path in sorted(destination.rglob('*')):
        if path.is_file():
            parts.append(str(path.relative_to(destination)) + '\0' + digest(path))
    return hashlib.sha256('\n'.join(parts).encode()).hexdigest()


def package_inventory(python):
    result = run([python, '-I', '-c', 'import importlib.metadata as m,json; print(json.dumps({d.metadata["Name"]:d.version for d in m.distributions()},sort_keys=True))'], capture_output=True, text=True)
    return json.loads(result.stdout)


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')


def verify_core_sources(root, pin):
    expected = f"volatility-mcp @ git+https://github.com/{pin['repository']}.git@{pin['commit']}"
    dependencies = tomllib.loads((root/'pyproject.toml').read_text())['project']['dependencies']
    locked = [line.strip() for line in (root/'requirements.lock.txt').read_text().splitlines()
              if line.startswith('volatility-mcp @')]
    if dependencies.count(expected) != 1 or locked != [expected]:
        raise ValueError('Core dependency, package metadata, and lock file disagree; refusing release build')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'dist'/'macos')
    parser.add_argument('--cache', type=Path, default=Path.home()/'Library/Caches/Volatility Workbench/build')
    parser.add_argument('--allow-dirty', action='store_true', help='Development artifact only; provenance records uncommitted source')
    parser.add_argument('--sign-identity', default='-', help='Default ad-hoc local signing; no notarization claim')
    args = parser.parse_args()
    if sys.platform != 'darwin' or platform.machine() != 'arm64':
        raise SystemExit('This release profile requires an ARM64 Mac build host')
    if args.sign_identity != '-':
        if args.allow_dirty:
            raise SystemExit('Developer ID builds require clean source; omit --allow-dirty')
        run([sys.executable, ROOT/'scripts/release_macos.py', 'identity', '--identity', args.sign_identity])
    manifest = json.loads((ROOT/'packaging/distribution.json').read_text())
    pin = json.loads((ROOT/manifest['core_pin']).read_text())
    verify_core_sources(ROOT, pin)
    revision = run(['git', '-C', ROOT, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    dirty = bool(run(['git', '-C', ROOT, 'status', '--porcelain'], capture_output=True, text=True).stdout.strip())
    if dirty and not args.allow_dirty:
        raise SystemExit('Commit source before a release build, or explicitly use --allow-dirty for validation')
    output, cache = args.output.resolve(), args.cache.resolve()
    output.mkdir(parents=True, exist_ok=True); cache.mkdir(parents=True, exist_ok=True)
    archive = fetch(manifest['python']['url'], cache/'python.tar.gz', manifest['python']['sha256'])
    with tempfile.TemporaryDirectory(prefix='workbench-build-') as temporary:
        temporary = Path(temporary)
        unpack(archive, temporary/'builder')
        builder = temporary/'builder/python/bin/python3'
        run([builder, '-I', '-m', 'pip', 'install', 'setuptools==84.0.0', 'wheel==0.48.0', 'packaging==26.3'])
        app = temporary/(manifest['application']['name'] + '.app')
        contents, resources = app/'Contents', app/'Contents/Resources'
        resources.mkdir(parents=True); (contents/'MacOS').mkdir()
        for name in ('runtime', 'analyzer'):
            extraction = temporary/('extract-' + name)
            unpack(archive, extraction)
            shutil.move(extraction/'python', resources/name)
        app_python = resources/'runtime/bin/python3'; analyzer = resources/'analyzer/bin/python3'
        wheelhouse = resources/'wheelhouse'; wheelhouse.mkdir()
        app_wheels, analyzer_wheels = wheelhouse/'app', wheelhouse/'analyzer'
        app_wheels.mkdir(); analyzer_wheels.mkdir()
        # Compile source wheels in the clean builder. Every runtime package uses an exact pin.
        base = temporary/'core-dependencies.txt'
        base.write_text('\n'.join(x for x in (ROOT/'requirements.lock.txt').read_text().splitlines() if not x.startswith('volatility-mcp @')) + '\n')
        app_lock = temporary/'application.lock.txt'
        app_lock.write_text(base.read_text() + (ROOT/manifest['desktop_lock']).read_text())
        run([builder, '-I', '-m', 'pip', 'wheel', '--no-deps', '--no-build-isolation', '-r', app_lock, '-w', app_wheels])
        run([builder, '-I', '-m', 'pip', 'wheel', '--no-deps', '--no-build-isolation', '-r', ROOT/manifest['analyzer_lock'], '-w', analyzer_wheels])
        source = temporary/'source'; source.mkdir()
        source_hash = source_snapshot(source)
        run([builder, '-I', '-m', 'pip', 'wheel', '--no-deps', '--no-build-isolation', '-w', app_wheels, source])
        for python, wheels, lock in ((app_python, app_wheels, app_lock), (analyzer, analyzer_wheels, ROOT/manifest['analyzer_lock'])):
            run([python, '-I', '-m', 'pip', 'install', '--no-compile', '--no-deps', '--no-index', '--find-links', wheels, '-r', lock])
        # Preserve and verify exact VCS provenance; ordinary version equality is insufficient.
        run([app_python, '-I', ROOT/'scripts/install_core_pin.py'])
        run([app_python, '-I', '-m', 'pip', 'install', '--no-compile', '--no-deps', '--no-index', '--find-links', app_wheels, 'volatility-workbench==' + manifest['application']['version']])
        run([app_python, '-I', '-m', 'pip', 'check']); run([analyzer, '-I', '-m', 'pip', 'check'])
        for relative in ('packaging/distribution.json', manifest['analyzer_lock'], manifest['desktop_lock'], 'core-dependency.json'):
            shutil.copy2(ROOT/relative, resources/Path(relative).name)
        notices = resources/'notices'; notices.mkdir()
        notice_pin=manifest['python']['notices_archive']
        notice_archive=fetch(notice_pin['url'],cache/'python-full.tar.zst',notice_pin['sha256'])
        notice_extract=temporary/'python-notices'; notice_extract.mkdir()
        run(['/usr/bin/tar','-xf',notice_archive,'-C',notice_extract,'python/licenses','python/PYTHON.json'])
        shutil.copytree(notice_extract/'python',notices/'python-standalone')
        for name in ('LICENSE', 'THIRD_PARTY_NOTICES.md'):
            shutil.copy2(ROOT/name, notices/('workbench-' + name))
        # Only explicitly redistributable sources from the core inventory are included.
        install = r'''
import json,sys,hashlib,urllib.request
from pathlib import Path
from volatility_mcp.addons import profile,prepare,fetch
from volatility_mcp.cli import run
resources=Path(sys.argv[1]); manifest=json.loads((resources/'distribution.json').read_text())
python=resources/'analyzer/bin/python3'
root=Path(run([str(python),'-I','-c','import volatility3,pathlib; print(pathlib.Path(volatility3.__file__).parent)']).stdout.strip())
receipts=[]
for source in profile()['sources']:
 if source['repository'] not in manifest['community']['bundled_sources']: continue
 for item in source['files']:
  raw,adapted=prepare(source,item); (root/'framework/plugins'/item['target']).write_bytes(adapted)
  original=resources/'notices'/source['repository']/item['path']; original.parent.mkdir(parents=True,exist_ok=True); original.write_bytes(raw)
 for item in source.get('notices',[]):
  (resources/'notices'/source['repository']/item['path']).write_bytes(fetch(source,item))
 receipts.append(source)
p=manifest['pypykatz_plugin']
for name,expected in ((p['file'],p['sha256']),('LICENSE',p['license_sha256'])):
 url=f"https://raw.githubusercontent.com/{p['repository']}/{p['commit']}/{name}"
 raw=urllib.request.urlopen(url,timeout=30).read(1024*1024)
 if hashlib.sha256(raw).hexdigest()!=expected: raise ValueError('pypykatz source hash mismatch')
 target=(root/'plugins'/name) if name==p['file'] else resources/'notices/pypykatz-LICENSE'
 target.write_bytes(raw)
(resources/'bundled-addons.json').write_text(json.dumps({'core_profile':profile()['profile'],'sources':receipts,'pypykatz':p},indent=2)+'\n')
'''
        run([app_python, '-I', '-c', install, resources])
        # Entry scripts are used through explicit Python by core. Remove pip's build-time shebangs.
        for runtime in ('runtime', 'analyzer'):
            for entry in (resources/runtime/'bin').iterdir():
                if entry.is_file() and not entry.is_symlink():
                    raw = entry.read_bytes()
                    if raw.startswith(b'#!'):
                        lines = raw.splitlines(keepends=True)
                        if b'workbench-build-' in lines[0] or lines[0].startswith(b'#!/bin/sh'):
                            # pip uses a three-line /bin/sh prologue for paths containing spaces.
                            if lines[0].startswith(b'#!/bin/sh') and len(lines)>2 and b'exec' in lines[1]: lines=lines[3:]
                            else: lines=lines[1:]
                            entry.write_bytes(b'#!/usr/bin/env python3\n'+b''.join(lines))
        # Existing icon artwork, rendered once to the standard ICNS resolutions.
        iconset = temporary/'Workbench.iconset'; iconset.mkdir()
        original = ROOT/'src/volatility_workbench/static/icon.png'
        for size in (16,32,128,256,512):
            for scale in (1,2):
                label=f'icon_{size}x{size}' + ('@2x' if scale==2 else '') + '.png'
                run(['/usr/bin/sips','-z',str(size*scale),str(size*scale),original,'--out',iconset/label],stdout=subprocess.DEVNULL)
        run(['/usr/bin/iconutil','-c','icns',iconset,'-o',resources/'Workbench.icns'])
        run(['xcrun','clang','-arch','arm64','-mmacosx-version-min=13.0','-O2',ROOT/'packaging/macos/launcher.c', '-I'+str(resources/'runtime/include/python3.12'),'-L'+str(resources/'runtime/lib'),'-lpython3.12','-Wl,-rpath,@executable_path/../Resources/runtime/lib','-o',contents/'MacOS/Volatility Workbench'])
        run(['xcrun','clang','-arch','arm64','-mmacosx-version-min=13.0','-fobjc-arc','-fblocks','-O2',ROOT/'packaging/macos/desktop_launcher.m','-framework','Cocoa','-o',resources/'desktop-launcher'])
        plist = {'CFBundleName':manifest['application']['name'],'CFBundleDisplayName':manifest['application']['name'],
            'CFBundleIdentifier':manifest['application']['bundle_id'],'CFBundleExecutable':'Volatility Workbench',
            'CFBundlePackageType':'APPL','CFBundleShortVersionString':manifest['application']['version'],
            'CFBundleVersion':str(int(revision[:7],16)), 'CFBundleIconFile':'Workbench.icns',
            'LSMinimumSystemVersion':manifest['application']['minimum_macos'],'NSHighResolutionCapable':True,
            'NSPrincipalClass':'NSApplication','LSMultipleInstancesProhibited':True}
        (contents/'Info.plist').write_bytes(plistlib.dumps(plist))
        packages={name:package_inventory(resources/name/'bin/python3') for name in ('runtime','analyzer')}
        info={'schema_version':1,'profile':manifest['profile'],'workbench_version':manifest['application']['version'],
              'workbench_commit':revision,'source_dirty':dirty,'source_sha256':source_hash,'core_commit':pin['commit'],
              'python':manifest['python'],'packages':packages,'signing':'ad-hoc' if args.sign_identity=='-' else 'developer-id',
              'notarized':False,'bundle_id':manifest['application']['bundle_id']}
        write_json(resources/'build-info.json',info)
        # -I ignores PYTHONDONTWRITEBYTECODE. The installed site hook prevents all
        # later imports from mutating signed resources; bootstrap caches are built now.
        for runtime in ('runtime', 'analyzer'):
            library=resources/runtime/'lib/python3.12'
            (library/'site-packages/sitecustomize.py').write_text('import sys\nsys.dont_write_bytecode = True\n')
            for directory in list(library.rglob('__pycache__')): shutil.rmtree(directory)
            run([resources/runtime/'bin/python3','-I','-m','compileall','-q','-f',
                 '-d','/__bundled_python__/'+runtime,str(library)])
        # Retain a dependency/source inventory and exact wheel hashes for the build.
        write_json(resources/'wheel-hashes.json',{str(p.relative_to(wheelhouse)):digest(p) for p in sorted(wheelhouse.rglob('*.whl'))})
        run([sys.executable,ROOT/'scripts/release_macos.py','sign-nested',app,'--identity',args.sign_identity])
        # Signing native libraries and normalizing console entry shebangs changes
        # installed bytes. Preserve original wheel hashes; update only preexisting
        # RECORD entries (never classify added community sources as official files).
        import base64,csv
        for record in resources.glob('*/lib/python3.12/site-packages/*.dist-info/RECORD'):
            rows=list(csv.reader(record.open(newline='')))
            for row in rows:
                item=record.parent.parent/row[0]
                if item.is_file() and item.resolve()!=record.resolve():
                    row[1]='sha256='+base64.urlsafe_b64encode(bytes.fromhex(digest(item))).rstrip(b'=').decode()
                    row[2]=str(item.stat().st_size)
                elif item.resolve()==record.resolve(): row[1:]=['','']
            with record.open('w',newline='') as stream: csv.writer(stream).writerows(rows)
        # Re-seal the outer bundle after RECORD updates without altering nested code.
        run([sys.executable,ROOT/'scripts/release_macos.py','seal',app,'--identity',args.sign_identity])
        run(['/usr/bin/codesign','--verify','--deep','--strict',app])
        target=output/app.name
        if target.exists(): shutil.rmtree(target)
        shutil.move(app,target)
        run([sys.executable,ROOT/'scripts/validate_macos.py',target])
        zipped=output/'Volatility-Workbench-macos-arm64.zip'
        run(['/usr/bin/ditto','-c','-k','--sequesterRsrc','--keepParent',target,zipped])
        write_json(output/'artifact.json',{'file':zipped.name,'sha256':digest(zipped),'bytes':zipped.stat().st_size,**info})
        print(json.dumps({'application':str(target),'archive':str(zipped),'sha256':digest(zipped),'source_dirty':dirty}))

if __name__=='__main__': main()
