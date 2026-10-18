"""Offline harmless fixtures for optional desktop setup boundaries."""
import asyncio
import base64
import dataclasses
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from volatility_mcp.api import Config
from volatility_workbench import symbols
from volatility_workbench.settings import SettingsManager
from volatility_workbench.runtime_management import clean_environment, install_community_overlay, rebase_bundled_runtime


def isf(os_name='windows'):
    metadata={'format':'6.2.0'}
    if os_name=='windows':metadata['windows']={'pdb':{'database':'ntkrnlmp.pdb','GUID':'A'*32,'age':1}}
    else:metadata[os_name]={}
    return {'metadata':metadata,'base_types':{},'user_types':{},'symbols':{} if os_name=='windows' else {'linux_banner':{'constant_data':base64.b64encode(b'Linux version exact fixture\n').decode()}}}


class SymbolTests(unittest.TestCase):
    def test_valid_windows_linux_preserved_and_repeatable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();destination=root/'symbols'
            for os_name in ('windows','linux'):
                source=root/(os_name+'.json');raw=json.dumps(isf(os_name)).encode();source.write_bytes(raw)
                first=symbols.import_symbols(source,destination)
                self.assertEqual(symbols.import_symbols(source,destination),first)
                self.assertEqual(source.read_bytes(),raw)
                target=next(destination.glob(os_name+'/managed-*'))
                self.assertTrue((target/first['files'][0]['path']).is_file())
                self.assertEqual(first['files'][0]['identity']['os'],os_name)
            self.assertEqual(first['files'][0]['identity']['banner'],'Linux version exact fixture\n')

    def test_traversal_symlink_hash_size_and_invalid_symbols(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();source=root/'bad.zip';destination=root/'symbols'
            for name in ('../escape.json','/absolute.json','back\\slash.json'):
                with zipfile.ZipFile(source,'w') as archive:archive.writestr(name,json.dumps(isf()))
                with self.assertRaises(ValueError):symbols.import_symbols(source,destination)
            with zipfile.ZipFile(source,'w') as archive:
                entry=zipfile.ZipInfo('link.json');entry.external_attr=(stat.S_IFLNK|0o777)<<16;archive.writestr(entry,'/tmp/x')
            with self.assertRaises(ValueError):symbols.import_symbols(source,destination)
            source=root/'symbols.json';source.write_text(json.dumps(isf()))
            with self.assertRaisesRegex(ValueError,'SHA-256'):symbols.import_symbols(source,destination,expected_hash='0'*64)
            with self.assertRaisesRegex(ValueError,'size'):symbols.import_symbols(source,destination,expected_size=1)
            with patch.object(symbols,'MAX_FILE',10):
                with self.assertRaisesRegex(ValueError,'limit'):symbols.import_symbols(source,destination)
            linked=root/'linked.json';linked.symlink_to(source)
            with self.assertRaisesRegex(ValueError,'symlinks'):symbols.import_symbols(linked,destination)
            source.write_text('{}')
            with self.assertRaisesRegex(ValueError,'metadata'):symbols.import_symbols(source,destination)
            self.assertFalse(list(destination.glob('*/managed-*')))

    def test_changed_installed_symbols_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();source=root/'symbols.json';source.write_text(json.dumps(isf()))
            result=symbols.import_symbols(source,root/'symbols')
            target=next((root/'symbols').glob('windows/managed-*'))/result['files'][0]['path'];target.write_text('changed')
            with self.assertRaisesRegex(ValueError,'changed'):symbols.import_symbols(source,root/'symbols')
            self.assertEqual(target.read_text(),'changed')

    def test_pinned_profile_has_exact_bounds_and_no_default_downloads(self):
        profile=symbols.profile();self.assertEqual(profile['default_downloads'],[])
        self.assertEqual(len(profile['packs']),2)
        for pack in profile['packs']:
            self.assertEqual(len(pack['sha256']),64);self.assertLess(pack['size'],4*1024*1024)
            self.assertTrue(pack['identifiers']);self.assertTrue(pack['url'].startswith('https://github.com/volatilityfoundation/'))


class SettingsTests(unittest.IsolatedAsyncioTestCase):
    def setup_manager(self,root,cases=None):
        config=Config(root/'evidence',root/'outputs',root/'python',root/'vol',cache_path=root/'cache')
        path=root/'config.json';path.write_text(json.dumps(config.to_dict()))
        state=root/'state';state.mkdir()
        app=SimpleNamespace(config=config,root=state,active=None,state={'cases':cases or [],'jobs':[]},agent=None,loaded_threads=set(),directory=lambda case:state/case['id'])
        manager=SettingsManager(app,path,root/'preferences')
        return manager,app,path

    async def test_empty_setup_saves_with_backup_existing_roots_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();manager,app,path=self.setup_manager(root)
            previous=path.read_bytes()
            (manager.root/'desktop.json').write_text(json.dumps({'setup_complete':False,'window':{'width':900}}))
            with patch('volatility_workbench.settings.VolatilityBackend'):
                result=await manager.save_locations({'evidence_root':str(root/'new-evidence'),'output_root':str(root/'new-outputs')})
            prefs=json.loads((manager.root/'desktop.json').read_text());self.assertTrue(prefs['setup_complete']);self.assertEqual(prefs['window'],{'width':900})
            self.assertTrue(result['saved']);self.assertEqual((Path(result['backup'])/'0.json').read_bytes(),previous)
            self.assertEqual(app.config.evidence_root,root/'new-evidence')
            app.state['cases']=[{'id':'example'}]
            with self.assertRaisesRegex(ValueError,'authoritative'):await manager.save_locations({'evidence_root':str(root/'third')})
            app.active={'id':'job'}
            with self.assertRaisesRegex(ValueError,'Wait'):await manager.save_locations({})

    async def test_snapshot_no_analyzer_no_provider_and_operation_recovery(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();manager,app,path=self.setup_manager(root)
            with patch('subprocess.Popen',side_effect=AssertionError('must not execute')),patch('hashlib.file_digest',side_effect=AssertionError('must not hash evidence')):
                data=manager.snapshot()
            self.assertEqual(data['readiness']['status'],'Blocked')
            self.assertEqual(len(data['readiness']['reasons']),2)
            for executable in (app.config.vol_python,app.config.vol_executable):
                executable.write_text('synthetic executable fixture');executable.chmod(0o700)
            self.assertEqual(manager.snapshot()['readiness']['status'],'Ready with limitations')
            app.config.vol_python.chmod(0o600)
            self.assertEqual(manager.snapshot()['readiness']['status'],'Blocked')
            manager.progress(status='running')
            resumed=SettingsManager(app,path,root/'preferences')
            self.assertEqual(resumed.operation['status'],'interrupted')
            self.assertFalse(resumed.busy)

    async def test_failure_preserves_configuration_and_no_duplicate_maintenance(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();manager,app,path=self.setup_manager(root);old=path.read_bytes()
            gate=asyncio.Event()
            async def fail():await gate.wait();raise ValueError('fixture error')
            manager.start_operation('fixture',fail)
            with self.assertRaisesRegex(ValueError,'already running'):manager.start_operation('duplicate',fail)
            gate.set();await manager.task
            self.assertEqual(manager.operation['status'],'failed');self.assertEqual(path.read_bytes(),old)
            self.assertFalse(manager.busy)

    async def test_awaited_settings_actions_hold_exclusive_guard(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();manager,app,path=self.setup_manager(root)
            for route in ('/api/settings/provider','/api/settings/provider/check','/api/settings/save'):
                started=asyncio.Event();release=asyncio.Event()
                async def pending(*args,**kwargs):
                    started.set();await release.wait();raise ValueError('fixture rejection')
                app.configure_provider=pending;app.check_provider=pending
                with patch.object(manager,'_activate',side_effect=pending):
                    task=asyncio.create_task(manager.dispatch(route,{}));await started.wait()
                    self.assertTrue(manager.busy)
                    with self.assertRaisesRegex(ValueError,'already running'):
                        await manager.dispatch('/api/settings/provider',{})
                    with self.assertRaisesRegex(ValueError,'already running'):
                        manager.start_operation('duplicate',pending)
                    release.set()
                    with self.assertRaisesRegex(ValueError,'fixture rejection'):await task
                    self.assertFalse(manager.busy)

    def test_subprocess_environment_never_inherits_provider_secrets(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':'synthetic','ANTHROPIC_API_KEY':'synthetic','PYTHONPATH':'/untrusted','HOME':'/fixture'},clear=True):
            env=clean_environment()
        self.assertEqual(env['HOME'],'/fixture');self.assertNotIn('OPENAI_API_KEY',env);self.assertNotIn('PYTHONPATH',env)

    def test_overlay_fresh_environment_is_kept_in_place_and_failure_preserves_original(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();manager,app,path=self.setup_manager(root)
            resources=root/'App With Spaces/Contents/Resources'
            for item in ('analyzer/bin/python3','runtime/bin/python3','analyzer.lock.txt'):
                target=resources/item;target.parent.mkdir(parents=True,exist_ok=True);target.touch()
            (resources/'wheelhouse/analyzer').mkdir(parents=True)
            (resources/'distribution.json').write_text('{}')
            calls=[]
            def run(argv,*args):
                calls.append([str(v) for v in argv])
                if 'venv' in argv:
                    candidate=Path(argv[-1]);(candidate/'bin').mkdir(parents=True)
                    (candidate/'bin/python3').touch();(candidate/'bin/vol').touch()
            catalog={'plugins':[{'name':'windows.info.Info'}],'total':1,'import_failures':[]}
            with patch('volatility_workbench.runtime_management._run',side_effect=run),patch('volatility_workbench.runtime_management.VolatilityBackend') as backend:
                backend.return_value.list_plugins.return_value=catalog
                configured,result=install_community_overlay(app.config,resources,root/'overlays')
            candidate=Path(result['path'])
            self.assertEqual(calls[0][-1],str(candidate))
            self.assertEqual(configured.vol_python,candidate/'bin/python3')
            self.assertEqual(app.config.vol_python,root/'python')
            self.assertFalse((candidate/'installation-config.json').exists())
            self.assertIn('--no-index',calls[1]);self.assertIn('plugins-install',calls[2])
            with patch('volatility_workbench.runtime_management._run',side_effect=ValueError('fixture failure')),patch('volatility_workbench.runtime_management.VolatilityBackend') as backend:
                backend.return_value.list_plugins.return_value=catalog
                with self.assertRaisesRegex(ValueError,'fixture failure'):
                    install_community_overlay(app.config,resources,root/'overlays')
            self.assertEqual(list((root/'overlays').iterdir()),[candidate])

    def test_runtime_rebase_updates_registered_managed_paths_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();manager,app,path=self.setup_manager(root)
            old=root/'Old App/Contents/Resources/analyzer';resources=root/'New App/Contents/Resources'
            for name in ('python3','vol'):
                target=resources/'analyzer/bin'/name;target.parent.mkdir(parents=True,exist_ok=True);target.touch()
            config=app.config.to_dict();config.update(vol_python=str(old/'bin/python3'),vol_executable=str(old/'bin/vol'))
            path.write_text(json.dumps(config))
            prefs={'bundled_analyzer':str(old),'window':{'width':900}}
            (manager.root/'desktop.json').write_text(json.dumps(prefs))
            state={'cases':[{'id':'managed'},{'id':'external'}],'jobs':[]}
            (app.root/'state.json').write_text(json.dumps(state));state_before=(app.root/'state.json').read_bytes()
            for ident in ('managed','external'):
                folder=app.root/ident;folder.mkdir()
                selected=dict(config)
                if ident=='external':selected['vol_python']='/explicit/python'
                (folder/'mcp.json').write_text(json.dumps({'config':selected,'images':['preserved.raw']}))
                (folder/'report.md').write_text('sealed fixture')
            external=(app.root/'external/mcp.json').read_bytes()
            result=rebase_bundled_runtime(path,app.root,manager.root,resources)
            self.assertTrue(result['changed']);self.assertEqual(result['case_configs_updated'],1)
            scoped=json.loads((app.root/'managed/mcp.json').read_text())
            self.assertEqual(scoped['config']['vol_python'],str(resources/'analyzer/bin/python3'))
            self.assertEqual(scoped['images'],['preserved.raw'])
            self.assertEqual((app.root/'external/mcp.json').read_bytes(),external)
            self.assertEqual((app.root/'state.json').read_bytes(),state_before)
            self.assertEqual((app.root/'managed/report.md').read_text(),'sealed fixture')
            self.assertFalse(rebase_bundled_runtime(path,app.root,manager.root,resources)['changed'])
            self.assertEqual(json.loads((manager.root/'desktop.json').read_text())['window'],{'width':900})

    def test_overlay_fails_before_touching_existing_runtime_when_resources_missing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();manager,app,path=self.setup_manager(root)
            with self.assertRaisesRegex(ValueError,'wheelhouse'):install_community_overlay(app.config,root/'absent',root/'overlays')
            self.assertFalse((root/'overlays').exists())


if __name__=='__main__':unittest.main()
