import asyncio
import dataclasses
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import unittest
from unittest.mock import patch

from mcp import Client
from mcp.client.stdio import StdioServerParameters
from volatility_mcp.backend import EvidenceError, VolatilityBackend, file_fingerprint
from volatility_mcp.cli import decode_result
from volatility_mcp.inspect_worker import pe_headers, strings_page
from volatility_mcp.scoped import CaseBackend
from volatility_workbench.storage import Bundle, now
from fixtures.synthetic_pe import synthetic_pe
import support as test_backend




class InspectionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fixture = test_backend.BackendFixture(); self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.backend = self.fixture.backend
        self.run = self.backend.run_plugin('example.raw','windows.pslist.PsList',['--dump'])
        self.relative = 'json/files/synthetic.dmp'
        self.source = Path(self.run['artifact_path'])/self.relative
        self.source.write_bytes(synthetic_pe(dll=True))
        manifest = Path(self.run['manifest_path'])
        record = json.loads(manifest.read_text())
        record['commands'][0]['artifacts'].append(file_fingerprint(self.source))
        manifest.write_text(json.dumps(record))

    def inspect(self, **kwargs):
        return self.backend.inspect_artifact('example.raw',self.run['run_id'],self.relative,**kwargs)

    async def test_new_bundle_includes_inspection_provenance_as_separate_run(self):
        result = self.inspect()
        case_dir = self.fixture.root/'ui-case'
        # Existing fixture output layout becomes a private synthetic case analysis root.
        case_dir.mkdir()
        import shutil
        shutil.copytree(self.fixture.config.output_root,case_dir/'analysis')
        case = {'id':'synthetic','images':[{'id':'E001','path':str(self.fixture.image),
            'sha256':file_fingerprint(self.fixture.image)['sha256'],'size_bytes':6}], 'notes':{}}
        version={'id':'new','status':'draft','created_at':now()}
        bundle=Bundle(case_dir,case,version)
        manifest = bundle.prepare()
        self.assertTrue(any(r['run_id'].startswith('inspection-') for r in manifest['runs']))
        self.assertTrue(any(a['path'].endswith('/result.json') for a in manifest['artifacts']))
        artifact=next(a for a in manifest['artifacts'] if a['path'].endswith('/result.json'))
        from test_ui import report_text
        bundle.save(report_text(artifact['path'],artifact['artifact_id']),
                    [{'finding_id':'F001','evidence_refs':[{'artifact_id':artifact['artifact_id'],'locator':'format'}]}],[])
        bundle.seal({'E001':file_fingerprint(self.fixture.image)})
        self.assertEqual(version['status'],'sealed')
