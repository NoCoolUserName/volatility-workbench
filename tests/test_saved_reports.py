"""Saved-only fixtures: no analyzer execution during query/report verification."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from mcp import Client
from mcp.client.stdio import StdioServerParameters
from volatility_mcp.backend import EvidenceError, VolatilityBackend, file_fingerprint
from volatility_mcp.cli import decode_result
from volatility_mcp.saved_evidence import reference, resolve_source
from volatility_mcp.reporting import check_bundle, check_citation
from volatility_mcp.scoped import CaseBackend
from volatility_workbench.storage import Bundle, now
from volatility_workbench.app import Workbench
from volatility_mcp.inspect_worker import pe_headers, strings_page
from fixtures.synthetic_pe import synthetic_pe
import io
import support as test_backend




class SavedTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_backend.BackendFixture(); self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.backend = self.fixture.backend
        self.case_dir = self.fixture.root/'workbench'/'synthetic'
        from dataclasses import replace
        self.backend = VolatilityBackend(replace(self.fixture.config, output_root=self.case_dir/'analysis'))
        self.rows = [
            {'PID':4, 'Name':'System', 'Address':18446744073709551600, 'Unknown':None,
             '__children':[{'PID':42, 'Name':'Child.exe', 'Address':4096, '__children':[]}]},
            {'PID':42, 'Name':'Other.exe', 'Address':8192, 'Unknown':'N/A', '__children':[]},
            {'PID':7, 'Name':'Empty', 'Address':0, 'Unknown':None, '__children':[]}]
        self.create_run('saved', self.rows)
        # Count EVERY fake Volatility interpreter launch (catalogs included).
        script=self.fixture.fake.read_text(); line,body=script.split('\n',1)
        counter=self.fixture.root/'all-volatility-launches.txt'
        self.fixture.fake.write_text(line+'\nwith open('+repr(str(counter))+", 'a') as counter: counter.write('launch\\n')\n"+body)
        self.counter=counter

    def create_run(self, rid, payload, status='success'):
        case=self.backend.case_directory(self.fixture.image)
        root=case/'runs'/rid; (root/'json').mkdir(parents=True)
        path=root/'json/stdout.json'; path.write_text(json.dumps(payload))
        image=file_fingerprint(self.fixture.image)
        record={'run_id':rid,'image':str(self.fixture.image),'image_relative_path':'example.raw',
            'image_sha256_before':image['sha256'],'image_sha256_after':image['sha256'],
            'integrity_verified':True,'status':status,'started_at':now(),'completed_at':now(),
            'plugin':'synthetic.PsList','arguments':[], 'volatility_version':'synthetic',
            'volatility_python_version':'synthetic','mcp_sdk_version':'synthetic','server_version':'synthetic',
            'commands':[{'argv':['SIMULATED, NOT EXECUTED'],'stdout_path':str(path),'artifacts':[file_fingerprint(path)]}]}
        (root/'manifest.json').write_text(json.dumps(record))
        return path

    def query(self, **kw):
        return self.backend.query_output('example.raw','saved','json/stdout.json',**kw)

    def ref(self, location='/0/PID'):
        q=self.query(fields=['PID']); ref=copy.deepcopy(q['rows'][0]['reference'])
        ref['locator']['pointer']=location
        return ref

    def test_report_link_and_packaged_integrity_failures(self):
        image=file_fingerprint(self.fixture.image)
        case={'id':'synthetic','images':[{'id':'E001',**image}],'notes':{}}
        version={'id':'links','status':'draft','created_at':now()}
        bundle=Bundle(self.case_dir,case,version)
        m=bundle.prepare();a=next(a for a in m['artifacts'] if a['path'].endswith('stdout.json'))
        ref={'artifact_id':a['artifact_id'],'locator':'/0/PID','structured':self.ref(), 'observable':{'type':'integer','value':4}}
        text='\n\n'.join(['## Executive summary','F1 synthetic only.','## Scope','Fixture.',
            '## Technical findings','LINK','## Investigative workflow','Saved only.','## Limitations','Synthetic.','## IOCs','None.'])
        for fragment in ['absent:0','F1:99']:
            with self.subTest(fragment=fragment),self.assertRaisesRegex(ValueError,'citation'):
                bundle.save(text.replace('LINK',f"[source]({a['path']}#citation={fragment})"),[{'finding_id':'F1','evidence_refs':[ref]}],[])
        path,_,_=resolve_source(self.backend,'example.raw','saved','json/stdout.json')
        path.write_text('[{"PID":999}]')
        with self.assertRaisesRegex(ValueError,'disagrees with execution manifest'):bundle.prepare()

    def test_saved_fixture_report_no_subprocess_and_legacy_readability(self):
        image=file_fingerprint(self.fixture.image)
        case={'id':'synthetic','images':[{'id':'E001',**image}],'notes':{}}
        version={'id':'saved-only','status':'draft','created_at':now()}
        bundle=Bundle(self.case_dir,case,version)
        with patch('subprocess.Popen',side_effect=AssertionError('NO SUBPROCESS AUTHORIZED')) as spy:
            manifest=bundle.prepare()
            a=next(a for a in manifest['artifacts'] if a['path'].endswith('stdout.json'))
            ref={'artifact_id':a['artifact_id'],'locator':'JSON /0/PID','structured':self.ref(), 'observable':{'type':'integer','value':4}}
            markdown='\n\n'.join(['## Executive summary','F1: Synthetic PID 4 observed; no malware inference.',
                '## Scope and evidence','Harmless saved fixture.', '## Technical findings',f"[F1 source]({a['path']})",
                '## Investigative workflow','Saved evidence only.', '## Limitations','Simulated data; no hunt justified.', '## IOCs','None.'])
            checked=bundle.save(markdown,[{'finding_id':'F1','kind':'observation','evidence_refs':[ref]}],[])
            self.assertEqual(checked['citation_validation'][0]['observable_validation'],'matched')
            bundle.seal({'E001':image})
            self.assertEqual(spy.call_count,0)
        self.assertFalse(self.counter.exists())
        before={p:p.read_bytes() for p in bundle.root.rglob('*') if p.is_file()}
        checked=check_bundle(bundle.root)
        self.assertEqual(before,{p:p.read_bytes() for p in before})
        manifest=json.loads((bundle.root/'case-manifest.json').read_text())
        for change in [lambda r:r['observable'].update(value=99),lambda r:r['structured']['source'].update(case_id='other')]:
            bad=copy.deepcopy(ref);change(bad)
            with self.assertRaises(EvidenceError):check_citation(bundle.root,manifest,bad)
        legacy=copy.deepcopy(ref);legacy.pop('structured')
        self.assertEqual(check_citation(bundle.root,manifest,legacy)['observable_validation'],'not_checked')
        # Exercise actual viewer data path without starting jobs or an agent.
        app=object.__new__(Workbench);app.root=self.case_dir.parent
        case['reports']=[version]
        self.assertEqual(app.citations(case,version['id'])['entries'][0]['finding'],'F1')
        resolved=app.citations(case,version['id'],finding='F1')
        self.assertEqual(resolved['value'],4)
        self.assertTrue((self.case_dir/resolved['artifact_path']).is_file())
