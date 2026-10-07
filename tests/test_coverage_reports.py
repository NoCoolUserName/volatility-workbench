"""Offline coverage/state contracts and real stdio calls on harmless saved data."""
import asyncio
import copy
import dataclasses
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from volatility_mcp.backend import VolatilityBackend, EvidenceError, file_fingerprint
from volatility_mcp.coverage import snapshot, set_plan, job_view
from volatility_mcp.cli import decode_result
from volatility_workbench.storage import Bundle, now
from volatility_mcp.reporting import check_bundle
from support_saved import SavedFixture, offline_guard




class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.f=SavedFixture(self.tmp.name);self.b=self.f.backend
        self.data=[{'PID':4,'Name':'System','__children':[]}]

    def plan(self,args=None):
        return {'profile':'Requested process examination','entries':[{'id':'processes','question':'Which processes were observed?',
            'plugin':'windows.pslist.PsList','arguments':args or []}]}

    def test_saved_report_coverage_zero_analysis(self):
        self.f.case=self.f.root/'ui'/'case'/'analysis'/self.f.case.name
        self.b=VolatilityBackend(dataclasses.replace(self.f.config,output_root=self.f.case.parent));self.f.backend=self.b
        self.f.run('run0',[],{'status':'success','returncode':0})
        set_plan(self.b,'synthetic.raw',self.plan(['--pid','99']))
        image={'id':'E001',**file_fingerprint(self.f.image)}
        case={'id':'case','images':[image],'notes':{}}
        version={'id':'revision','status':'draft','created_at':now()}
        bundle=Bundle(self.f.root/'ui/case',case,version,coverage_backend=self.b)
        with offline_guard() as counts:
            m=bundle.prepare();a=next(a for a in m['artifacts'] if a['path'].endswith('stdout.json'))
            text='\n\n'.join(['## Executive summary','F1: Synthetic empty scope only.','## Scope','Synthetic.',
                '## Technical findings','F1: Empty saved output.','## Investigative workflow','Saved only.','## Limitations','Unknowns remain.','## IOCs','None.'])
            result=bundle.save(text,[{'finding_id':'F1','evidence_refs':[{'artifact_id':a['artifact_id'],'locator':'empty array'}]}],[])
            self.assertEqual(result['status'],'valid')
            # A changed derived count cannot override the original empty table,
            # even when its artifact hash is mechanically updated.
            coverage_path=bundle.root/'coverage.json';coverage=json.loads(coverage_path.read_text())
            attempt=next(e for e in coverage['images'][0]['entries'] if e['attempts'])['attempts'][0]
            attempt.update(availability='rows_present',row_count=1)
            coverage_path.write_text(json.dumps(coverage))
            mp=bundle.root/'case-manifest.json';record=json.loads(mp.read_text());fp=file_fingerprint(coverage_path)
            next(a for a in record['artifacts'] if a['artifact_id']=='coverage-snapshot').update(sha256=fp['sha256'],size_bytes=fp['size_bytes'])
            mp.write_text(json.dumps(record))
            with self.assertRaisesRegex(ValueError,'row count contradicts'):check_bundle(bundle.root)
            # An explicitly extended plan after saving changes the authoritative
            # snapshot. Sealing refreshes only its mechanical limitations block.
            plan=self.plan(['--pid','99'])
            plan['entries'].append({'id':'another-scope','question':'Synthetic second scope',
                                    'plugin':'windows.pslist.PsList','arguments':['--pid','100']})
            set_plan(self.b,'synthetic.raw',plan)
            bundle.seal({'E001':image});before=(bundle.root/'report.md').read_bytes()
            self.assertIn(b'2 recorded scopes have missing/partial/unknown results',before)
            self.assertIn(b'F1: Empty saved output.',before)
            self.assertEqual(before.count(b'<!-- coverage-summary -->'),1)
            self.assertEqual(check_bundle(bundle.root)['status'],'valid')
            self.assertEqual(before,(bundle.root/'report.md').read_bytes())
        self.assertEqual(counts['subprocess_launches'],0)
