"""Report-only metadata inventory; harmless fixtures, no analysis or private state."""
import copy
import dataclasses
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from volatility_mcp.api import file_fingerprint
from volatility_workbench import report_plugins as inventory
from volatility_workbench.app import Workbench
from volatility_workbench.storage import Bundle, atomic_json, now
from support_saved import SavedFixture, offline_guard


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve() / 'case/reports/revision'
        self.root.mkdir(parents=True)
        self.manifest = {'case_id':'case', 'synthetic':False, 'runs':[], 'artifacts':[],
                         'evidence':[{'id':'E001', 'path':'/synthetic/image.raw', 'sha256':'a' * 64}]}
        self.steps = []

    def write(self):
        atomic_json(self.root / 'case-manifest.json', self.manifest)
        (self.root / 'investigation.jsonl').write_text(''.join(json.dumps(s) + '\n' for s in self.steps))

    def artifact(self, path, value, rid=None):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic_json(target, value)
        item = {'artifact_id':path, 'path':path, 'run_id':rid,
                'sha256':hashlib.sha256(target.read_bytes()).hexdigest(), 'size_bytes':target.stat().st_size}
        self.manifest['artifacts'] = [a for a in self.manifest['artifacts'] if a['path'] != path] + [item]
        return target

    def add_run(self, rid, status='success', *, commands=True, synthetic=False):
        cid = 'C-' + rid
        run = {'run_id':rid, 'call_id':cid, 'image_id':'E001', 'image_relative_path':'image.raw',
               'source_case_id':'sourcecase', 'status':status, 'started_at':'2026-10-18T00:00:00Z',
               'finished_at':'2026-10-18T00:01:00Z'}
        self.manifest['runs'].append(run)
        original = {'run_id':rid, 'image_relative_path':'image.raw', 'image':'/synthetic/image.raw',
                    'image_sha256_before':'a' * 64, 'image_sha256_after':'a' * 64,
                    'plugin':'windows.pslist.PsList', 'arguments':['--pid','4'], 'status':status,
                    'started_at':run['started_at'], 'completed_at':run['finished_at'],
                    'commands':[{'argv':['python','vol','-r','json','windows.pslist.PsList','--pid','4'],
                                 'returncode':0 if status == 'success' else 1}] if commands else []}
        if synthetic:original.update(synthetic=True, execution_kind='simulated')
        self.artifact('artifacts/' + cid + '/manifest.json', original, rid)
        self.steps.append({'call_id':cid, 'run_id':rid, 'tool':original['plugin'],
                           'arguments':original['arguments'], 'argv':[c['argv'] for c in original['commands']],
                           'status':status, 'timestamp':run['started_at']})
        return run, original

    def derive(self):
        self.write()
        with offline_guard() as counters:
            result = inventory.derive(self.root, 'case', 'revision')
        self.assertEqual(counters['subprocess_launches'], 0)
        self.assertEqual(counters['network_attempts'], 0)
        return result

    def persist(self, result):
        self.artifact('plugin-inventory.json', result)
        self.manifest['plugin_inventory'] = {'schema':inventory.SCHEMA, 'path':'plugin-inventory.json'}
        self.write()

    def test_exact_runs_inspections_reuse_and_failed_requests_are_distinct(self):
        self.add_run('run0')
        self.add_run('run1', status='error')
        self.manifest['runs'].append({'run_id':'inspection-0', 'call_id':'C-inspect', 'image_id':'E001'})
        self.steps.append({'run_id':'inspection-0', 'call_id':'C-inspect', 'tool':'inspect_artifact',
                           'status':'success', 'arguments':{'operation':'strings'}})
        self.steps.append({'call_id':'UI-denied', 'tool':'run_plugin', 'arguments':{'plugin':'windows.pslist.PsList',
                           'arguments':['--pid','bad'], 'image':'/synthetic/image.raw'}, 'status':'error', 'timestamp':'2026-10-18T00:03:00Z'})
        self.steps.append({'call_id':'UI-inspect-denied', 'tool':'inspect_artifact', 'status':'error'})
        receipt = {'run_id':'run0', 'plugin':'windows.pslist.PsList', 'arguments':['--pid','4'],
                   'reused':True, 'integrity_verified':True, 'image_before':{'sha256':'a' * 64},
                   'image_after':{'sha256':'a' * 64}, 'requested_at':'2026-10-18T00:02:00Z'}
        self.artifact('artifacts/coverage/reuse.json', receipt)
        coverage = {'case_id':'case', 'images':[{'image_id':'E001', 'entries':[{'attempts':[{'run_id':'run0',
                    'reuse_receipts':[{'bundle_path':'artifacts/coverage/reuse.json'}]}]}]}]}
        self.artifact('coverage.json', coverage)
        self.manifest['coverage'] = {'path':'coverage.json'}
        result = self.derive()
        self.assertEqual(result['source_status'], 'available')
        self.assertEqual(result['summary'], {'executions':2, 'plugins':1, 'failures':1, 'reuse_receipts':1,
            'request_failures':1, 'unknown_execution_records':0, 'simulated_runs':0, 'run_records':2})
        first = result['entries'][0]
        self.assertEqual(first['arguments'], ['--pid','4'])
        self.assertEqual(first['argv'], [['python','vol','-r','json','windows.pslist.PsList','--pid','4']])
        self.assertEqual(first['source_path'], 'artifacts/C-run0/manifest.json')
        self.assertEqual(first['reuse_count'], 1)
        self.assertEqual(result['entries'][-1]['kind'], 'reuse_receipt')
        self.assertFalse(result['entries'][-1]['execution_recorded'])
        denied = next(e for e in result['entries'] if e['kind'] == 'request_failure')
        self.assertIsNone(denied['run_id']); self.assertFalse(denied['execution_recorded'])
        self.persist(result)
        page = inventory.read(self.root, 'case', 'revision', 0, 1)
        self.assertEqual(page['executed_plugin_names'], ['windows.pslist.PsList'])
        self.assertEqual(len(page['errored_entries']), 2, 'Error list covers the full saved snapshot, not only the visible page')
        self.assertEqual({e['kind'] for e in page['errored_entries']}, {'plugin_run', 'request_failure'})
        self.assertEqual(page['errored_entries'][0]['arguments'], ['--pid','4'])
        self.assertEqual(page['errored_entries'][1]['arguments'], ['--pid','bad'])
        self.assertEqual(page['errored_entries'][1]['requested_image'], '/synthetic/image.raw')

    def test_saved_error_sources_and_request_diagnostic_are_read_only(self):
        self.add_run('failed', status='error')
        self.artifact('artifacts/C-failed/json/stderr.txt', 'Synthetic error only', 'failed')
        self.add_run('other')
        self.artifact('artifacts/C-other/json/stderr.txt', 'Other run', 'other')
        self.steps.append({'call_id':'UI-denied', 'tool':'run_plugin', 'status':'error',
                           'arguments':{'plugin':'windows.example.Plugin', 'arguments':[]}})
        event = {'id':'denied', 'detail':{'arguments':{'plugin':'windows.example.Plugin', 'image':'/synthetic/image.raw', 'arguments':['--pid','bad']},
                 'result':{'content':[{'type':'text', 'text':'Synthetic invalid argument <script>not executable</script>'}]}}}
        saved = self.artifact('artifacts/UI-denied.json', event)
        self.persist(self.derive())
        before = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        with offline_guard():
            result = inventory.read(self.root, 'case', 'revision')
        run, request = result['errored_entries']
        self.assertEqual({s['path'] for s in run['error_sources']},
                         {'artifacts/C-failed/manifest.json', 'artifacts/C-failed/json/stderr.txt'})
        self.assertEqual(request['reason'], event['detail']['result']['content'][0]['text'])
        self.assertEqual(request['error_sources'], [{'path':'artifacts/UI-denied.json', 'label':'Saved request error'}])
        self.assertEqual(request['requested_image'], '/synthetic/image.raw')
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        saved.write_text('{}')
        result = inventory.read(self.root, 'case', 'revision')
        self.assertEqual(result['errored_entries'][1]['error_sources'], [])
        self.assertNotIn('Synthetic invalid', result['errored_entries'][1]['reason'])
        self.assertTrue(any('hash/size' in w for w in result['warnings']))

    def test_saved_stderr_diagnosis_checks_integrity_without_rewriting_history(self):
        self.add_run('failed',status='error')
        path=self.artifact('artifacts/C-failed/json/stderr.txt',"NameError: name 'file_offset' is not defined",'failed')
        self.persist(self.derive())
        before=path.read_bytes()
        with offline_guard():result=inventory.read(self.root,'case','revision')
        self.assertIn('implementation defect',result['errored_entries'][0]['diagnosis'])
        self.assertEqual(result['errored_entries'][0]['status'],'error');self.assertEqual(path.read_bytes(),before)
        path.write_text('Page error changed')
        result=inventory.read(self.root,'case','revision')
        self.assertFalse(result['errored_entries'][0].get('diagnosis'))
        for text,phrase in [('This version of Windows is not supported','does not support'),
                ('This plugin only supports x64 versions of Windows','x64'),
                ('Template guessing is not applicable for NT5','NT5'),('Page error','unreadable'),
                ('Unable to validate the plugin requirements','requirements'),
                ('Enumeration not found _MI_SYSTEM_VA_TYPE','enumeration'),
                ('forbidden shell metacharacters','regex-aware')]:
            self.assertIn(phrase,inventory.error_explanation(text))

    def test_request_diagnostic_rejects_wrong_identity_and_plugin(self):
        self.steps.append({'call_id':'UI-denied', 'tool':'run_plugin', 'status':'error',
                           'arguments':{'plugin':'windows.example.Plugin', 'arguments':[]}})
        for ident, plugin in [('other', 'windows.example.Plugin'), ('denied', 'windows.other.Plugin')]:
            self.artifact('artifacts/UI-denied.json', {'id':ident, 'detail':{'arguments':{'plugin':plugin},
                          'error':'Must not be attached to a different request'}})
            self.write()
            result = inventory.read(self.root, 'case', 'revision')
            self.assertEqual(result['errored_entries'][0]['error_sources'], [])
            self.assertNotIn('Must not', result['errored_entries'][0]['reason'])

    def test_explicit_simulations_never_become_physical_executions(self):
        self.add_run('run0', synthetic=True)
        result = self.derive()
        self.assertEqual(result['summary']['executions'], 0)
        self.assertEqual(result['summary']['simulated_runs'], 1)
        self.assertEqual(result['summary']['unknown_execution_records'], 0)
        self.assertEqual(result['entries'][0]['execution_kind'], 'simulated')
        self.assertTrue(any('excluded from physical' in w for w in result['warnings']))
        self.assertIn('simulated&#41;', inventory.markdown('## Investigative workflow\nSaved.', result))

    def test_legacy_log_fallback_is_partial_not_an_inferred_execution(self):
        self.add_run('run0')
        target = self.root / 'artifacts/C-run0/manifest.json'
        target.unlink()
        self.steps[0].pop('run_id')  # Report spec permits call-ID-only log entries.
        result = self.derive()
        self.assertEqual(result['source_status'], 'partial')
        self.assertEqual(result['entries'][0]['plugin'], 'windows.pslist.PsList')
        self.assertEqual(result['entries'][0]['provenance'], 'investigation_log')
        self.assertIsNone(result['entries'][0]['execution_recorded'])
        self.assertEqual(result['summary']['executions'], 0)
        self.assertEqual(result['summary']['unknown_execution_records'], 1)
        self.assertEqual(result['summary']['request_failures'], 0)
        self.assertEqual(result['entries'][0]['source_path'], 'investigation.jsonl')

    def test_missing_malformed_and_oversized_metadata_are_explicit(self):
        self.write()
        (self.root / 'case-manifest.json').write_text('{')
        result = inventory.read(self.root, 'case', 'revision')
        self.assertEqual(result['source_status'], 'unavailable')
        text = inventory.markdown('## Investigative workflow\nUnknown.\n## Limitations\nStill unknown.', result)
        self.assertIn('Recorded plugin runs: **Unknown**', text)
        self.assertNotIn('Recorded plugin runs: **0**', text)
        self.add_run('run0')
        (self.root / 'artifacts/C-run0/manifest.json').write_text('{bad json')
        result = self.derive()
        self.assertEqual(result['source_status'], 'partial')
        self.assertTrue(any('hash/size' in w for w in result['warnings']))
        self.assertEqual(result['summary']['unknown_execution_records'], 1)
        # Small inspection budget never reads oversized metadata or raw outputs.
        with patch.object(inventory, 'MAX_TOTAL_BYTES', 8):
            self.assertEqual(inventory.derive(self.root, 'case', 'revision')['source_status'], 'unavailable')

    def test_recorded_run_without_argv_still_counts_as_attempt_and_flags_gap(self):
        _, record = self.add_run('run0', status='error')
        record['commands'] = [{'returncode':1}]
        self.artifact('artifacts/C-run0/manifest.json', record, 'run0')
        self.steps[0]['argv'] = None
        result = self.derive()
        self.assertEqual(result['summary']['executions'], 1)
        self.assertEqual(result['summary']['failures'], 1)
        self.assertIsNone(result['entries'][0]['argv'])
        self.assertEqual(result['source_status'], 'partial')

    def test_launch_error_or_missing_exit_code_never_proves_physical_execution(self):
        self.add_run('run0', status='error')
        for code in (None, True, False, '1'):
            record = json.loads((self.root / 'artifacts/C-run0/manifest.json').read_text())
            record['commands'] = [{'argv':['python','vol','windows.pslist.PsList'],
                                   'returncode':code, 'status':'error',
                                   'error':'Cannot execute Volatility'}]
            self.artifact('artifacts/C-run0/manifest.json', record, 'run0')
            result = self.derive()
            self.assertEqual(result['summary']['executions'], 0, code)
            self.assertEqual(result['summary']['unknown_execution_records'], 1, code)
            self.assertEqual(result['source_status'], 'partial')
            self.assertEqual(result['entries'][0]['status'], 'error')
            self.assertIsNone(result['entries'][0]['execution_recorded'])
        for code in (0, 1, -9):
            record['commands'][0]['returncode'] = code
            self.artifact('artifacts/C-run0/manifest.json', record, 'run0')
            result = self.derive()
            self.assertEqual(result['summary']['executions'], 1, code)
            self.assertTrue(result['entries'][0]['execution_recorded'])

    def test_snapshot_pagination_and_read_only_legacy_bytes(self):
        for n in range(23):self.add_run('run' + str(n))
        result = self.derive()
        before = {str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        first = inventory.read(self.root, 'case', 'revision')
        self.assertEqual(len(first['entries']), 20); self.assertEqual(first['next_offset'], 20)
        second = inventory.read(self.root, 'case', 'revision', 20, 20)
        self.assertEqual(len(second['entries']), 3); self.assertIsNone(second['next_offset'])
        self.assertEqual(before, {str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        self.persist(result)
        # Neither later live-case runs nor changes to the historical investigation log
        # can silently extend a saved report inventory.
        analysis = self.root.parents[1] / 'analysis/source/runs/later'
        analysis.mkdir(parents=True); (analysis / 'manifest.json').write_text('{private-like unrelated fixture}')
        (self.root / 'investigation.jsonl').write_text('malformed later log')
        with patch.object(inventory, 'derive', side_effect=AssertionError('Persisted snapshot must be used')):
            self.assertEqual(inventory.read(self.root, 'case', 'revision')['summary']['executions'], 23)
        for offset, limit in ((-1, 20), (True, 20), (0, 101), (0, 0), (0, True)):
            with self.assertRaises(ValueError):inventory.read(self.root, 'case', 'revision', offset, limit)

    def test_snapshot_validation_rejects_missing_fields_or_false_execution_claims(self):
        self.add_run('run0')
        original = self.derive()
        for mutation in ('missing', 'reuse', 'request', 'synthetic', 'image', 'path', 'foreign-run'):
            result = copy.deepcopy(original); entry = result['entries'][0]
            if mutation == 'missing':entry.pop('execution_recorded')
            if mutation == 'reuse':entry['kind'] = 'reuse_receipt'
            if mutation == 'request':entry['kind'] = 'request_failure'
            if mutation == 'synthetic':entry['synthetic'] = True
            if mutation == 'image':entry['image_id'] = 'OTHER'
            if mutation == 'path':entry['source_path'] = 'unregistered.json'
            if mutation == 'foreign-run':entry['run_id'] = 'elsewhere'
            self.persist(result)
            with self.assertRaises(ValueError, msg=mutation):inventory.read(self.root, 'case', 'revision')

    def test_snapshot_and_original_metadata_hashes_are_checked_without_live_fallback(self):
        self.add_run('run0')
        original = self.derive()
        self.persist(original)
        (self.root / 'artifacts/C-run0/manifest.json').write_text('{"untrusted":"changed"}')
        with patch.object(inventory, 'derive', side_effect=AssertionError('Use recorded snapshot only')):
            result = inventory.read(self.root, 'case', 'revision')
        self.assertEqual(result['source_status'], 'partial')
        self.assertEqual(result['summary']['executions'], 1)
        self.assertTrue(any('hash/size' in warning for warning in result['warnings']))
        (self.root / 'plugin-inventory.json').write_text('{"untrusted":"changed snapshot"}')
        result = inventory.read(self.root, 'case', 'revision')
        self.assertEqual(result['source_status'], 'partial')
        self.assertEqual(result['summary']['unknown_execution_records'], 1)

    def test_malformed_coverage_arrays_and_metadata_record_caps(self):
        self.add_run('run0'); self.add_run('run1')
        self.artifact('coverage.json', {'case_id':'case', 'images':{}})
        self.manifest['coverage'] = {'path':'coverage.json'}
        result = self.derive()
        self.assertEqual(result['source_status'], 'partial')
        self.assertEqual(result['summary']['executions'], 2)
        with patch.object(inventory, 'MAX_RECORDS', 1):
            result = inventory.derive(self.root, 'case', 'revision')
        self.assertEqual(len(result['entries']), 1)
        self.assertTrue(any('limit' in warning for warning in result['warnings']))

    def test_cross_case_image_run_traversal_and_symlink_guards(self):
        self.add_run('run0');self.write()
        with self.assertRaisesRegex(ValueError, 'another case'):inventory.read(self.root, 'elsewhere', 'revision')
        for path in ('../outside', '/outside', 'artifacts/../outside', 'a\\b', 'a//b'):
            bad = copy.deepcopy(self.manifest); bad['artifacts'][0]['path'] = path
            atomic_json(self.root / 'case-manifest.json', bad)
            with self.assertRaises(ValueError, msg=path):inventory.derive(self.root, 'case', 'revision')
        self.write()
        target = self.root / 'artifacts/C-run0/manifest.json'; target.unlink()
        outside = self.root.parent / 'outside.json'; outside.write_text('{}')
        target.symlink_to(outside)
        with self.assertRaises(ValueError):inventory.derive(self.root, 'case', 'revision')
        target.unlink()
        _, record = self.add_run('run1');record['image_sha256_before'] = 'b' * 64
        self.artifact('artifacts/C-run1/manifest.json', record, 'run1');self.write()
        with self.assertRaisesRegex(ValueError, 'another image'):inventory.derive(self.root, 'case', 'revision')

    def test_markdown_is_idempotent_escaped_bounded_and_in_required_order(self):
        self.add_run('run0')
        result = self.derive(); entry = result['entries'][0]
        entry['plugin'] = 'evil|<script>\n[remote](https://invalid.test/x)'
        entry['arguments'] = ['A' * 10000]
        text = '# Case\n## Executive summary\nFirst.\n## Investigative workflow and coverage\nActual notes.\n## Limitations\nUnknowns.\n## IOC appendix\nLast.'
        rendered = inventory.markdown(text, result)
        self.assertEqual(rendered, inventory.markdown(rendered, result))
        self.assertEqual(rendered.count(inventory.START), 1)
        self.assertIn('**Plugin:**', rendered)
        self.assertNotIn('| Record |', rendered)
        self.assertIn('evil&#124;&lt;script&gt;', rendered)
        self.assertNotIn('[remote](https://invalid.test/x)', rendered)
        self.assertIn('display abbreviated', rendered);self.assertLess(len(rendered), 7000)
        self.assertLess(rendered.index('## Executive'), rendered.index(inventory.START))
        self.assertLess(rendered.index(inventory.END), rendered.index('## Limitations'))
        self.assertTrue(rendered.endswith('## IOC appendix\nLast.'))
        mixed = inventory.markdown(text.replace('## Investigative workflow', '## iNvEsTiGaTiVe WoRkFlOw'), result)
        self.assertIn(inventory.START, mixed)
        self.assertEqual(inventory.markdown('## Executive summary\nNo workflow.', result), '## Executive summary\nNo workflow.')
        result['entries'] *= 101
        many = inventory.markdown(text, result)
        self.assertIn('first 100 metadata records', many)
        self.assertLess(len(many), 250000)

    def test_app_requires_registered_report_and_safe_id(self):
        self.add_run('run0'); self.write()
        app = object.__new__(Workbench)
        app.directory = lambda case:self.root.parents[1]
        case = {'id':'case', 'reports':[{'id':'revision'}]}
        self.assertEqual(app.report_plugins(case, 'revision')['summary']['executions'], 1)
        for rid in ('../revision', 'unknown'):
            with self.assertRaises(ValueError):app.report_plugins(case, rid)
        case['reports'][0]['deleted_at'] = 'now'
        with self.assertRaises(ValueError):app.report_plugins(case, 'revision')


class NewBundleTests(unittest.TestCase):
    def test_new_bundle_snapshot_is_hashed_sealed_and_never_rewrites_sealed_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = SavedFixture(tmp)
            fixture.case = fixture.root / 'ui/case/analysis' / fixture.case.name
            fixture.backend = type(fixture.backend)(dataclasses.replace(fixture.config, output_root=fixture.case.parent))
            fixture.run('run0', [], {'status':'success', 'returncode':0})
            image = {'id':'E001', **file_fingerprint(fixture.image)}
            case = {'id':'case', 'images':[image], 'notes':{}}
            version = {'id':'revision', 'status':'draft', 'created_at':now()}
            bundle = Bundle(fixture.root / 'ui/case', case, version, coverage_backend=fixture.backend)
            text = '\n'.join(['## Executive summary','F1: Synthetic empty scope only.', '## Scope and evidence','Synthetic.',
                              '## Technical findings','F1: Empty saved output.', '## Investigative workflow and coverage','Saved only.',
                              '## Limitations','Unknowns remain.', '## IOCs','None.'])
            with offline_guard() as counters:
                manifest = bundle.prepare()
                artifact = next(a for a in manifest['artifacts'] if a['path'].endswith('stdout.json'))
                bundle.save(text, [{'finding_id':'F1', 'evidence_refs':[{'artifact_id':artifact['artifact_id'], 'locator':'empty array'}]}], [])
                bundle.seal({'E001':image})
                self.assertEqual(version['status'], 'sealed')
                saved = json.loads((bundle.root / 'case-manifest.json').read_text())
                self.assertEqual(saved['plugin_inventory']['schema'], inventory.SCHEMA)
                row = next(a for a in saved['artifacts'] if a['path'] == 'plugin-inventory.json')
                self.assertEqual(row['sha256'], hashlib.sha256((bundle.root / row['path']).read_bytes()).hexdigest())
                self.assertIn('  plugin-inventory.json', (bundle.root / 'SHA256SUMS').read_text())
                before = {p:p.read_bytes() for p in bundle.root.rglob('*') if p.is_file()}
                self.assertEqual(inventory.read(bundle.root, 'case', 'revision')['summary']['executions'], 1)
                self.assertEqual(before, {p:p.read_bytes() for p in bundle.root.rglob('*') if p.is_file()})
                with self.assertRaisesRegex(ValueError, 'Sealed'):bundle.prepare()
                self.assertEqual(before, {p:p.read_bytes() for p in bundle.root.rglob('*') if p.is_file()})
                report = (bundle.root / 'report.md').read_text()
                self.assertEqual(report.count(inventory.START), 1)
            self.assertEqual(counters['subprocess_launches'], 0)
