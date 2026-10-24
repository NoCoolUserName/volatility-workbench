"""Native shell logic and actual loopback host, with harmless fake application."""
import asyncio
import http.client
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

from volatility_mcp.api import Config
from volatility_workbench.desktop import BackendHost, bootstrap, navigation_allowed, visible_geometry


def config_fixture(root):
    config=Config(root/'evidence',root/'outputs',root/'python',root/'vol',cache_path=root/'cache')
    path=root/'config.json';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(config.to_dict()))
    return config,path


class DesktopLogicTests(unittest.TestCase):
    def test_geometry_remains_visible_after_monitor_change(self):
        screen={'x':0,'y':25,'width':1280,'height':775}
        geometry=visible_geometry({'x':4000,'y':-3000,'width':1800,'height':1000},[screen])
        self.assertEqual(geometry,{'x':0,'y':25,'width':1280,'height':775})
        self.assertEqual(visible_geometry(None,[]) ,{'width':1180,'height':820})
        self.assertEqual(visible_geometry({'x':-50,'y':26,'width':500,'height':200},[screen])['width'],800)

    def test_navigation_is_origin_bound_and_external_credentials_rejected(self):
        origin='http://127.0.0.1:12345'
        self.assertTrue(navigation_allowed(origin+'/settings.html',origin))
        self.assertTrue(navigation_allowed('about:blank',origin))
        for url in ('https://example.org','file:///etc/passwd','javascript:alert(1)',
                    'http://127.0.0.1:12346/','http://user@127.0.0.1:12345/',
                    'http://127.0.0.1:12345.evil.example/'):
            self.assertFalse(navigation_allowed(url,origin),url)

    def test_fresh_bundled_setup_provisions_local_symbols_once(self):
        with tempfile.TemporaryDirectory() as temporary:
            home=Path(temporary).resolve()
            resources=home/'App.app/Contents/Resources';resources.mkdir(parents=True)
            (resources/'distribution.json').write_text(json.dumps({'core_bundle':{'sha256':'synthetic'}}))
            args=SimpleNamespace(preferences_dir=str(home/'preferences'),config=None,state_dir=None,clean_setup=True)
            with patch('pathlib.Path.home',return_value=home), patch('volatility_workbench.desktop.install_symbol_packs') as install:
                _, path, _, _=bootstrap(args,resources)
                install.assert_called_once()
                config=install.call_args.args[0]
                self.assertEqual(install.call_args.kwargs['source_dir'], resources/'runtime/lib/python3.12/site-packages/volatility_mcp/resources/symbol-packs')
                self.assertFalse(list(config.evidence_root.iterdir()))
                self.assertFalse(list(config.output_root.iterdir()))
                self.assertEqual(bootstrap(args,resources)[1],path)
                install.assert_called_once()

    def test_failed_symbol_setup_does_not_commit_configuration(self):
        with tempfile.TemporaryDirectory() as temporary:
            home=Path(temporary).resolve()
            resources=home/'App.app/Contents/Resources';resources.mkdir(parents=True)
            (resources/'distribution.json').write_text(json.dumps({'core_bundle':{'sha256':'synthetic'}}))
            args=SimpleNamespace(preferences_dir=str(home/'preferences'),config=None,state_dir=None,clean_setup=True)
            with patch('pathlib.Path.home',return_value=home), patch('volatility_workbench.desktop.install_symbol_packs',side_effect=ValueError('corrupt bundle')):
                with self.assertRaisesRegex(ValueError,'corrupt bundle'):bootstrap(args,resources)
            self.assertFalse((home/'preferences/config.json').exists())
            self.assertFalse((home/'preferences/desktop.json').exists())

    def test_bootstrap_explicit_locations_and_prefs_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();config,path=config_fixture(root)
            before=path.read_bytes();state=root/'existing-state';state.mkdir()
            original_state=b'{"schema_version":1,"cases":[],"jobs":[]}'
            (state/'state.json').write_bytes(original_state)
            args=SimpleNamespace(preferences_dir=str(root/'preferences'),config=str(path),state_dir=str(state),clean_setup=False)
            preferences,selected,selected_state,prefs=bootstrap(args,None)
            self.assertEqual(selected,path);self.assertEqual(selected_state,state)
            self.assertEqual(path.read_bytes(),before);self.assertEqual((state/'state.json').read_bytes(),original_state)
            args.config=None;args.state_dir=None
            self.assertEqual(bootstrap(args,None)[1:3],(path,state))

    def test_bootstrap_imports_operator_config_and_existing_state_without_rewrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            home=Path(temporary).resolve()
            repo=home/'src/Forensics/volatility-mcp';repo.mkdir(parents=True)
            config,path=config_fixture(repo);source=repo/'config.local.json';path.rename(source)
            state=repo.parent/'reports/workbench';state.mkdir(parents=True);(state/'state.json').write_text('{"cases":[],"jobs":[]}')
            original=source.read_bytes();saved=(state/'state.json').read_bytes()
            args=SimpleNamespace(preferences_dir=str(home/'preferences'),config=None,state_dir=None,clean_setup=False)
            with patch('pathlib.Path.home',return_value=home):
                preferences,selected,selected_state,prefs=bootstrap(args,None)
            self.assertNotEqual(source,selected);self.assertEqual(selected_state,state)
            self.assertEqual(source.read_bytes(),original);self.assertEqual((state/'state.json').read_bytes(),saved)
            self.assertTrue(prefs['setup_complete'])


class FakeWorkbench:
    starts=0
    closes=0
    def __init__(self,config_path,root):
        from volatility_mcp.api import load_config
        self.config=load_config(config_path);self.root=root;self.active=None
        self.state={'cases':[],'jobs':[]}
    async def start(self):type(self).starts+=1
    async def close(self):type(self).closes+=1
    def snapshot(self):return {'fixture':True,'active_job':self.active}
    async def plugin_catalog(self,refresh=False):return {'plugins':[],'total':0,'import_failures':[]}


class BackendHostTests(unittest.TestCase):
    def test_actual_http_auth_same_origin_reuse_and_idle_cleanup(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();config,path=config_fixture(root)
            state=root/'state';state.mkdir();preferences=root/'preferences';preferences.mkdir()
            FakeWorkbench.starts=0;FakeWorkbench.closes=0
            with patch('volatility_workbench.app.Workbench',FakeWorkbench),patch('volatility_workbench.http.runtime_fingerprint',return_value='test-runtime'):
                host=BackendHost(path,state,preferences);url=host.start();parsed=urlsplit(url)
                def request(method,path,body=None,headers=None):
                    connection=http.client.HTTPConnection(parsed.hostname,parsed.port,timeout=5)
                    connection.request(method,path,json.dumps(body) if body is not None else None,headers or {})
                    response=connection.getresponse();status=response.status;mime=response.getheader('Content-Type');data=response.read();connection.close()
                    return status,json.loads(data) if mime=='application/json' else data
                try:
                    self.assertEqual(request('GET','/api/settings')[0],403)
                    origin=f'http://{parsed.netloc}'
                    self.assertEqual(request('POST','/api/unlock',{'token':parsed.fragment},{'Content-Type':'application/json','Origin':origin})[0],200)
                    headers={'Cookie':'volatility_ui='+parsed.fragment}
                    status,scene=request('GET','/theme-halloween.svg',headers=headers)
                    self.assertEqual(status,200);self.assertIn(b'<svg',scene)
                    for unknown in ('/theme-missing.svg','/theme-../../AGENTS.md.svg','/theme-%2e%2e%2fAGENTS.md.svg'):
                        self.assertEqual(request('GET',unknown,headers=headers)[0],400)
                    self.assertEqual(request('GET','/api/settings',headers=headers)[0],200)
                    bad=headers|{'Origin':'https://evil.example','Content-Type':'application/json'}
                    self.assertEqual(request('POST','/api/settings/save',{},bad)[0],403)
                    self.assertEqual(request('GET','/api/plugins',headers=headers)[1]['total'],0)
                    again=BackendHost(path,state,preferences);self.assertEqual(again.start(),url)
                    self.assertFalse(again.owned);again.shutdown()
                    self.assertTrue(host.thread.is_alive());self.assertEqual(FakeWorkbench.starts,1)
                    self.assertEqual(host.activity(),{'active':False,'maintenance':False,'owned':True})
                    host.app.state['jobs']=[{'status':'queued'}]
                    self.assertTrue(host.activity()['active'])
                    host.app.settings_manager.busy=True
                    self.assertTrue(host.activity()['maintenance'])
                    host.app.settings_manager.busy=False;host.app.state['jobs']=[]
                    host.app.volshell=SimpleNamespace(busy=True)
                    self.assertTrue(host.activity()['active'],'An interactive shell protects native quit even without a job')
                    host.app.volshell.busy=False
                    self.assertFalse(host.activity()['active'])
                finally:host.shutdown()
                self.assertFalse(host.thread.is_alive());self.assertEqual(FakeWorkbench.closes,1)
