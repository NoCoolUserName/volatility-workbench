"""Authenticated optional setup controls shared by browser and native desktop."""
from __future__ import annotations
import asyncio
import dataclasses
import json
import os
from pathlib import Path
import uuid
from volatility_mcp.api import Config, VolatilityBackend
from .storage import atomic_json, now, private_dir
from . import symbols
from .runtime_management import install_community_overlay


class SettingsManager:
    def __init__(self, app, config_path, preferences_root, resources=None, folder_picker=None):
        self.app=app
        self.config_path=Path(config_path).expanduser().absolute()
        self.root=private_dir(Path(preferences_root))
        self.resources=Path(resources) if resources else None
        self.folder_picker=folder_picker
        self.busy=False
        self.operation={'status':'idle'}
        self.task=None
        self.symbol_status_cache={}
        self.operation_path=self.root/'settings-operation.json'
        if self.operation_path.exists():
            self.operation=json.loads(self.operation_path.read_text())
            if self.operation.get('status')=='running':
                self.operation.update(status='interrupted',message='Application stopped during settings maintenance. Existing configuration was preserved; retry explicitly.')
                atomic_json(self.operation_path,self.operation)

    def require_idle(self):
        if getattr(getattr(self.app,'volshell',None),'busy',False):
            raise ValueError('Disconnect VolShell before changing settings')
        if self.app.active or any(j.get('status') in ('queued','running','stopping') for j in self.app.state.get('jobs',[])):
            raise ValueError('Wait for investigations and queued work to finish before changing settings')
        if self.busy: raise ValueError('Settings maintenance is already running')

    def snapshot(self):
        config=self.app.config
        symbol_root=config.symbols or self.root/'symbols'
        symbol_profile=symbols.profile()
        installed={p['id']:bool(symbols.installed_pack(p,symbol_root,self.symbol_status_cache)) for p in symbol_profile['packs']}
        problems=[]
        for label,path in (('Analyzer Python',config.vol_python),('Volatility executable',config.vol_executable)):
            if not path.is_file() or not os.access(path,os.X_OK):
                problems.append(label+' is missing or not executable. Select or restore the intended runtime; saved-case browsing remains available.')
        readiness={'status':'Blocked' if problems else 'Ready with limitations',
            'reasons':problems or ['Configured analyzer paths are executable. No image was hashed or analyzed; exact symbols and provider capability are checked separately.']}
        provider=self.app.provider_status() if hasattr(self.app,'provider_status') else {'default_provider':'codex'}
        titles={case['id']:case.get('title',case['id']) for case in self.app.state['cases']}
        for case in provider.get('cases',[]): case['title']=titles.get(case['case_id'],case['case_id'])
        return {'config':config.to_dict(),'state_dir':str(self.app.root),'has_cases':bool(self.app.state['cases']),
            'evidence_locations':self.app.evidence_locations() if hasattr(self.app,'evidence_locations') else [],
            'native_folder_picker':bool(self.folder_picker),'managed_runtime_available':bool(self.resources and (self.resources/'analyzer/bin/python3').exists()),
            'symbols':{'directory':str(symbol_root),'cache':str(config.cache_path),'profile':symbol_profile,'installed':installed,
                'matching':'Windows uses the exact PDB GUID/age when collection requests symbols. Linux/macOS need matching banners. Installed files do not establish image readiness.'},
            'provider':provider,
            'operation':dict(self.operation),'readiness':readiness}

    def progress(self, **values):
        self.operation.update(values)
        atomic_json(self.operation_path,self.operation)

    async def _activate(self, config):
        """Atomic configuration change, with rollback and existing-case path preservation."""
        if self.app.active or getattr(getattr(self.app,'volshell',None),'busy',False):
            raise ValueError('Investigation or VolShell became active; configuration activation refused')
        backups=private_dir(self.root/'backups'/uuid.uuid4().hex)
        originals={self.config_path:self.config_path.read_bytes()}
        for case in self.app.state['cases']:
            path=self.app.directory(case)/'mcp.json'
            if path.exists(): originals[path]=path.read_bytes()
        for i,(path,content) in enumerate(originals.items()):
            (backups/f'{i}.json').write_bytes(content)
        atomic_json(backups/'manifest.json',{'paths':[str(p) for p in originals],'created_at':now()})
        # Idle model/MCP processes may retain old config. Reconnect when next requested.
        if getattr(self.app,'agent',None):
            await self.app.agent.close();self.app.agent=None
        if hasattr(self.app,'loaded_threads'): self.app.loaded_threads.clear()
        new_backend=VolatilityBackend(config)
        try:
            for path,content in originals.items():
                if path==self.config_path:continue
                data=json.loads(content)
                for key in ('vol_python','vol_executable','symbols','cache_path'):
                    data['config'][key]=config.to_dict()[key]
                atomic_json(path,data)
            atomic_json(self.config_path,config.to_dict())
            self.app.config=config
            self.app.backend=new_backend
        except BaseException:
            for path,content in originals.items():
                atomic_json(path,json.loads(content))
            raise
        return str(backups)

    async def exclusive(self, operation):
        self.require_idle()
        self.busy=True
        try: return await operation()
        finally: self.busy=False

    async def save_locations(self, body):
        return await self.exclusive(lambda:self._save_locations(body))

    async def _save_locations(self, body):
        allowed={'evidence_root','output_root'}
        if set(body)-allowed: raise ValueError('Unknown location setting')
        current=self.app.config.to_dict()
        for key,value in body.items():
            if not isinstance(value,str) or not value.strip(): raise ValueError('Locations must be absolute directory paths')
            path=Path(value).expanduser()
            if not path.is_absolute() or any(p.is_symlink() for p in (path,*path.parents)):
                raise ValueError('Use physical absolute directory paths without symlinks')
            current[key]=str(path)
        proposed=Config.from_dict(current)
        if self.app.state['cases'] and any(getattr(proposed,key)!=getattr(self.app.config,key) for key in allowed):
            raise ValueError('Existing case roots are authoritative. Use a separate new setup to change roots; this screen never moves or rebases evidence.')
        if proposed.evidence_root==self.app.root or proposed.evidence_root.is_relative_to(self.app.root):
            raise ValueError('Case state must not contain the evidence root')
        for path in (proposed.evidence_root,proposed.output_root): private_dir(path)
        backup=await self._activate(proposed)
        desktop_preferences=self.root/'desktop.json'
        if desktop_preferences.exists():
            preferences=json.loads(desktop_preferences.read_text())
            preferences['setup_complete']=True
            atomic_json(desktop_preferences,preferences)
        return {'saved':True,'backup':backup}

    def start_operation(self, kind, operation):
        self.require_idle()
        self.busy=True
        self.operation={'id':uuid.uuid4().hex,'kind':kind,'status':'running','started_at':now(),'stage':'Preparing'}
        atomic_json(self.operation_path,self.operation)
        async def execute():
            try:
                result=await operation()
                self.progress(status='succeeded',finished_at=now(),result=result,stage='Complete')
            except asyncio.CancelledError:
                self.progress(status='interrupted',finished_at=now(),message='Maintenance interrupted. Previous runtime and completed symbol packs are preserved.')
                raise
            except Exception as exc:
                self.progress(status='failed',finished_at=now(),message=str(exc))
            finally: self.busy=False
        self.task=asyncio.create_task(execute())
        return dict(self.operation)

    async def install_plugins(self):
        if not self.resources: raise ValueError('Use the packaged application to create a managed runtime overlay')
        config, result=await asyncio.to_thread(install_community_overlay,self.app.config,self.resources,self.root/'runtimes',self.progress)
        result['backup']=await self._activate(config)
        return result

    async def install_symbols(self, body):
        destination=self.app.config.symbols or self.root/'symbols'
        if 'path' in body:
            self.progress(stage='Validating local symbols')
            result=await asyncio.to_thread(symbols.import_symbols,body['path'],destination)
            result={'imported_files':len(result['files']),'source_sha256':result['source_sha256']}
        else:
            ids=[p['id'] for p in symbols.profile()['packs']] if body.get('pack')=='all' else [body.get('pack')]
            result={'packs':[]}
            for ident in ids:
                receipt=await asyncio.to_thread(symbols.download_pack,ident,destination,self.root/'downloads',self.progress)
                result['packs'].append({'id':ident,'imported_files':len(receipt['files']),'source_sha256':receipt['source_sha256']})
        result['backup']=await self._activate(dataclasses.replace(self.app.config,symbols=destination))
        return result

    async def dispatch(self, path, body):
        if path=='/api/settings/save': return await self.save_locations(body)
        if path=='/api/settings/pick-folder':
            if not self.folder_picker: raise ValueError('Native selection is available in the desktop application; enter a physical path here')
            kind=body.get('kind','folder')
            if kind not in ('folder','symbol'): raise ValueError('Unsupported native selection kind')
            return {'path':await asyncio.to_thread(self.folder_picker,kind)}
        if path=='/api/settings/plugins/install': return self.start_operation('plugins',self.install_plugins)
        if path=='/api/settings/symbols/import': return self.start_operation('symbols',lambda:self.install_symbols({'path':body['path']}))
        if path=='/api/settings/symbols/download': return self.start_operation('symbols',lambda:self.install_symbols({'pack':body['pack']}))
        if path=='/api/settings/provider':
            return await self.exclusive(lambda:self.app.configure_provider(body.get('config',{}),secret=body.get('secret'),storage=body.get('storage','session')))
        if path=='/api/settings/provider/check':
            return await self.exclusive(lambda:self.app.check_provider(body.get('case_id')))
        if path=='/api/settings/provider/models':
            return await self.exclusive(lambda:self.app.provider_models(body.get('config',{})))
        raise ValueError('Unknown settings action')
