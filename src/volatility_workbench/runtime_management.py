"""Opt-in managed analyzer overlays, using fresh venvs and the core installer."""
from __future__ import annotations
import dataclasses
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid
from volatility_mcp.api import VolatilityBackend
from .storage import atomic_json, private_dir


def clean_environment():
    # Provider credentials and interactive-shell settings must never enter analyzers.
    return {key:value for key,value in os.environ.items() if key in ('HOME','TMPDIR','LANG','LC_ALL','SYSTEMROOT')} | {'PATH':'/usr/bin:/bin:/usr/sbin:/sbin','PYTHONNOUSERSITE':'1'}


def _run(argv, progress, label, timeout=600):
    progress(stage=label)
    with tempfile.TemporaryFile() as output:
        result=subprocess.run([str(a) for a in argv],shell=False,env=clean_environment(),
            stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,timeout=timeout)
        if result.returncode:
            output.seek(0,2);length=output.tell();output.seek(max(0,length-3000))
            raise ValueError(label+' failed: '+output.read().decode('utf-8','replace'))


def install_community_overlay(config, resources, overlays, progress=lambda **kwargs:None):
    """The candidate venv stays at its original path; only config activation changes."""
    resources=Path(resources).resolve()
    base=resources/'analyzer/bin/python3'
    app_python=resources/'runtime/bin/python3'
    wheels=resources/'wheelhouse/analyzer'
    lock=resources/'analyzer.lock.txt'
    if not all(p.exists() for p in (base,app_python,wheels,lock)):
        raise ValueError('Managed analyzer wheelhouse is unavailable. Use the packaged desktop distribution or the documented core plugins-install command for your existing environment.')
    overlays=private_dir(Path(overlays))
    if any(p.is_symlink() for p in (overlays,*overlays.parents)):
        raise ValueError('Managed runtime location must not contain symlinks')
    previous_catalog=VolatilityBackend(config).list_plugins()
    previous_names={p['name'] for p in previous_catalog.get('plugins',[])}
    candidate=overlays/('analyzer-'+uuid.uuid4().hex)
    try:
        _run([base,'-I','-m','venv',candidate],progress,'Creating isolated analyzer')
        _run([candidate/'bin/python3','-I','-m','pip','install','--no-index','--find-links',wheels,'-r',lock],progress,'Installing locked analyzer dependencies')
        # Preserve the exact eligible addon bytes carried by the immutable bundle.
        import hashlib
        manifest=json.loads((resources/'distribution.json').read_text())
        entry=manifest.get('pypykatz_plugin')
        if entry:
            relative=Path('lib/python3.12/site-packages/volatility3/plugins/vol_pypykatz.py')
            source=resources/'analyzer'/relative
            target=candidate/relative
            if source.is_symlink() or target.is_symlink():
                raise ValueError('Invalid bundled addon source')
            content=source.read_bytes()
            if hashlib.sha256(content).hexdigest()!=entry['sha256']:
                raise ValueError('Bundled pypykatz addon hash mismatch')
            if target.exists() and target.read_bytes()!=content:
                raise ValueError('Bundled addon conflicts with installed dependency')
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(content)
        staged=dataclasses.replace(config,vol_python=candidate/'bin/python3',vol_executable=candidate/'bin/vol')
        configuration=candidate/'installation-config.json'
        atomic_json(configuration,staged.to_dict())
        _run([app_python,'-I','-m','volatility_mcp','plugins-install','--config',configuration],progress,'Downloading pinned optional community sources',900)
        configuration.unlink()
        catalog=VolatilityBackend(staged).list_plugins(refresh=True)
        missing=previous_names-{p['name'] for p in catalog.get('plugins',[])}
        if missing:
            raise ValueError('Managed candidate would omit existing plugins; previous analyzer preserved: '+', '.join(sorted(missing)))
        if catalog.get('import_failures'):
            raise ValueError('Managed candidate has plugin import failures; previous analyzer remains selected')
        atomic_json(candidate/'workbench-overlay.json',{'schema_version':1,'plugin_count':catalog['total'],
            'source':'Packaged runtime wheelhouse and explicit core pinned community profile',
            'verification':'discovery/import only; no memory image analyzed'})
        return staged,{'plugin_count':catalog['total'],'path':str(candidate),'import_failures':[]}
    except BaseException:
        shutil.rmtree(candidate,ignore_errors=True)
        raise


def rebase_bundled_runtime(config_path, state_dir, preferences_root, resources):
    """Rebase recognized managed paths only, while caller holds the case app.lock.

    The caller must acquire the existing state-directory lock before invoking this
    function. It never discovers/moves evidence or touches reports/state.json.
    """
    from .storage import safe_file, now
    config_path=Path(config_path)
    state_dir=Path(state_dir)
    preferences_root=Path(preferences_root)
    prefs_path=preferences_root/'desktop.json'
    if not resources or not prefs_path.is_file():return {'changed':False}
    resources=Path(resources).resolve()
    prefs=json.loads(prefs_path.read_text())
    previous=prefs.get('bundled_analyzer')
    current=resources/'analyzer'
    if not previous or Path(previous)==current:return {'changed':False}
    config_data=json.loads(config_path.read_text())
    if config_data.get('vol_python')!=str(Path(previous)/'bin/python3'):
        return {'changed':False,'reason':'Explicit external/overlay analyzer preserved'}
    python=current/'bin/python3';vol=current/'bin/vol'
    if not python.is_file() or not vol.is_file():raise ValueError('Replacement bundled analyzer is incomplete; original configuration retained')
    replacements={config_path:config_data,prefs_path:prefs}
    state_path=state_dir/'state.json'
    if state_path.is_file():
        state=json.loads(state_path.read_text())
        for case in state.get('cases',[]):
            ident=case.get('id')
            if not isinstance(ident,str) or '/' in ident or '\\' in ident or ident in ('.','..'):
                raise ValueError('Invalid registered case identity; runtime rebase refused')
            path=state_dir/ident/'mcp.json'
            if not path.exists():continue
            path=safe_file(state_dir,ident+'/mcp.json')
            value=json.loads(path.read_text())
            if value.get('config',{}).get('vol_python')==str(Path(previous)/'bin/python3'):
                replacements[path]=value
    originals={path:path.read_bytes() for path in replacements}
    backup=private_dir(preferences_root/'backups'/('runtime-rebase-'+uuid.uuid4().hex))
    for index,(path,content) in enumerate(originals.items()):
        (backup/f'{index}.json').write_bytes(content)
    atomic_json(backup/'manifest.json',{'created_at':now(),'paths':[str(p) for p in originals],
        'reason':'Installed bundled analyzer location changed; evidence and report paths unchanged'})
    try:
        for path,data in replacements.items():
            if path==prefs_path:
                data['bundled_analyzer']=str(current)
            else:
                values=data if path==config_path else data['config']
                values.update(vol_python=str(python),vol_executable=str(vol))
            atomic_json(path,data)
    except BaseException:
        for path,content in originals.items():atomic_json(path,json.loads(content))
        raise
    return {'changed':True,'backup':str(backup),'case_configs_updated':len(replacements)-2}
