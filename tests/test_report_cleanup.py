"""Explicit incomplete/sealed-bundle cleanup, with no analysis or private evidence."""
import asyncio
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch, AsyncMock
import urllib.error
import urllib.request

import support
from volatility_workbench.app import Workbench
from volatility_workbench.http import Server
from volatility_workbench.storage import delete_report_bundle


class ReportCleanupTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        fixture = support.BackendFixture(); fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture = fixture
        self.config = fixture.root / 'config.json'
        self.config.write_text(json.dumps(fixture.config.to_dict()))
        self.app = Workbench(self.config, fixture.root / 'ui')
        self.case = self.app.add([str(fixture.image)])[0]
        self.shared = self.app.directory(self.case) / 'analysis' / 'saved.txt'
        self.shared.parent.mkdir(); self.shared.write_text('shared original output')
        self.source = fixture.image.read_bytes()

    def report(self, ident='old', status='incomplete', case=None):
        case = case or self.case
        record = {'id':ident, 'status':status, 'created_at':'2026-10-18T12:00:00Z', 'previous':None}
        case['reports'].append(record)
        folder = self.app.directory(case) / 'reports' / ident
        folder.mkdir(parents=True)
        (folder/'report.md').write_text('Synthetic report, not an investigation')
        (folder/'artifacts').mkdir(); (folder/'artifacts'/'copy.txt').write_text('private report copy')
        (folder/'case-manifest.json').write_text(json.dumps({'case_id':case['id'],
            'status':'complete_with_limitations' if status=='sealed' else 'in_progress'}))
        self.app.save()
        return record, folder

    def assert_preserved(self):
        self.assertEqual(self.fixture.image.read_bytes(), self.source)
        self.assertEqual(self.shared.read_text(), 'shared original output')
        self.assertFalse((self.fixture.root/'analysis-count.jsonl').exists())

    async def test_hide_is_durable_without_changing_report_files(self):
        record, folder = self.report()
        before = {p.relative_to(folder):p.read_bytes() for p in folder.rglob('*') if p.is_file()}
        await self.app.remove_report(self.case['id'], record['id'], 'hide')
        reopened = Workbench(self.config, self.app.root)
        self.assertTrue(reopened.case(self.case['id'])['reports'][0]['hidden'])
        self.assertEqual(before, {p.relative_to(folder):p.read_bytes() for p in folder.rglob('*') if p.is_file()})
        self.assertEqual(self.case['activity'][-1]['kind'], 'report_hidden')
        self.assert_preserved()

    async def test_delete_recycles_only_bundle_retains_history_and_is_idempotent(self):
        record, folder = self.report()
        sealed, sealed_folder = self.report('sealed', 'sealed')
        original = (sealed_folder/'report.md').read_bytes()
        self.app.state['jobs'].append({'id':'old-job','case_id':self.case['id'],'report_id':record['id'],'status':'incomplete'})
        with patch.object(self.app.backend, 'run_plugin', side_effect=AssertionError('analysis forbidden')):
            await self.app.remove_report(self.case['id'], record['id'], 'delete')
        self.assertFalse(folder.exists())
        recycled = self.app.recycle_case_dir(self.case)/'reports'/record['id']
        self.assertTrue(recycled.exists())
        self.assertEqual((sealed_folder/'report.md').read_bytes(), original)
        self.assertTrue(record['hidden']); self.assertTrue(record['deleted_at'])
        self.assertEqual(len(self.app.state['recycle_bin']), 1)
        self.assertEqual(self.app.state['jobs'][0]['report_id'], record['id'])
        reopened = Workbench(self.config, self.app.root)
        self.assertTrue(reopened.case(self.case['id'])['reports'][0]['deleted_at'])
        self.assertTrue((await self.app.remove_report(self.case['id'], record['id'], 'delete'))['already_deleted'])
        self.assert_preserved()

    async def test_recycle_restore_and_permanent_purge(self):
        record, folder = self.report('recoverable', 'sealed')
        original = {p.relative_to(folder):p.read_bytes() for p in folder.rglob('*') if p.is_file()}
        await self.app.remove_report(self.case['id'], record['id'], 'delete')
        self.assertEqual(len(self.app.recycle_bin_snapshot()), 1)
        await self.app.restore_recycled_report(self.case['id'], record['id'])
        self.assertEqual(original, {p.relative_to(folder):p.read_bytes() for p in folder.rglob('*') if p.is_file()})
        self.assertNotIn('deleted_at', record)
        self.assertFalse(record.get('hidden'))
        self.assertEqual(self.app.recycle_bin_snapshot(), [])
        await self.app.remove_report(self.case['id'], record['id'], 'delete')
        await self.app.purge_recycled_report(self.case['id'], record['id'])
        self.assertFalse(folder.exists())
        self.assertFalse((self.app.recycle_case_dir(self.case)/'reports'/record['id']).exists())
        self.assertEqual(self.app.recycle_bin_snapshot(), [])
        self.assertTrue(record['deleted_at'])
        self.assert_preserved()

    async def test_recycle_keeps_only_last_seven_bundles(self):
        records = [self.report(f'revision-{index}', 'sealed')[0] for index in range(8)]
        for record in records:
            await self.app.remove_report(self.case['id'], record['id'], 'delete')
        recycled = self.app.recycle_case_dir(self.case)/'reports'
        self.assertFalse((recycled/records[0]['id']).exists())
        self.assertEqual([entry['report_id'] for entry in self.app.state['recycle_bin']],
            [record['id'] for record in records[1:]])
        self.assertTrue(all((recycled/record['id']).exists() for record in records[1:]))
        self.assert_preserved()

    async def test_hidden_bundle_purge_is_permanent_and_preserves_visible_successor(self):
        old, folder = self.report('old-hidden', 'sealed')
        child, child_folder = self.report('visible-successor', 'sealed')
        child['previous'] = old['id']
        original = (child_folder/'report.md').read_bytes()
        await self.app.remove_report(self.case['id'], old['id'], 'hide')
        result = await self.app.purge_hidden_reports(self.case['id'])
        self.assertEqual([item['report_id'] for item in result['deleted']], [old['id']])
        self.assertEqual(result['failed'], [])
        self.assertFalse(folder.exists())
        self.assertEqual((child_folder/'report.md').read_bytes(), original)
        self.assertTrue(old['deleted_at'])
        self.assertEqual(self.app.recycle_bin_snapshot(), [])
        self.assert_preserved()

    async def test_draft_wrong_case_and_unknown_actions_are_rejected(self):
        record, folder = self.report('draft', 'draft')
        for action in ('hide', 'delete'):
            with self.assertRaisesRegex(ValueError, 'Only incomplete or sealed'):
                await self.app.remove_report(self.case['id'], record['id'], action)
        self.assertTrue(folder.exists())
        other = self.app.add([str(self.fixture.image)])[0]
        record, folder = self.report('other-case-report', case=other)
        with self.assertRaisesRegex(ValueError, 'Unknown report'):
            await self.app.remove_report(self.case['id'], record['id'], 'delete')
        with self.assertRaisesRegex(ValueError, 'Choose hide or delete'):
            await self.app.remove_report(other['id'], record['id'], 'anything')
        self.assertTrue(folder.exists()); self.assert_preserved()

    async def test_active_queued_work_blocks_deletion_but_predecessors_can_be_recycled(self):
        record, folder = self.report()
        for status in ('queued','running','stopping'):
            self.app.state['jobs'] = [{'case_id':self.case['id'],'status':status}]
            with self.assertRaisesRegex(ValueError, 'active and queued'):
                await self.app.remove_report(self.case['id'], record['id'], 'delete')
        self.app.state['jobs'] = []
        child, _ = self.report('child', 'sealed'); child['previous'] = record['id']
        await self.app.remove_report(self.case['id'], record['id'], 'delete')
        self.assertFalse(folder.exists())
        self.assertEqual(child['previous'], record['id'])
        self.assertTrue((self.app.directory(self.case)/'reports'/child['id']).exists())
        self.assert_preserved()

    async def test_paths_symlinks_source_overlap_and_completed_manifest_rejected(self):
        record, folder = self.report()
        outside = self.fixture.root/'outside'; outside.mkdir(); sentinel = outside/'keep'; sentinel.write_text('keep')
        for name in ('../outside', '/outside', '..', 'x\\y'):
            with self.assertRaises(ValueError):
                delete_report_bundle(self.app.directory(self.case), name, [])
        bad_case = {**self.case, 'id':str(outside)}
        self.app.state['cases'].append(bad_case)
        with self.assertRaisesRegex(ValueError, 'state root'):
            await self.app.remove_report(bad_case['id'], record['id'], 'hide')
        self.app.state['cases'].remove(bad_case)
        link = folder/'escape'; link.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlinks'):
            await self.app.remove_report(self.case['id'], record['id'], 'delete')
        self.assertTrue((folder/'report.md').exists()); link.unlink()
        physical = folder.with_name('physical-copy')
        folder.rename(physical); folder.symlink_to(physical, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            await self.app.remove_report(self.case['id'], record['id'], 'delete')
        folder.unlink(); physical.rename(folder)
        with self.assertRaisesRegex(ValueError, 'source evidence'):
            delete_report_bundle(self.app.directory(self.case), record['id'], [folder/'artifacts/copy.txt'])
        manifest = folder/'case-manifest.json'
        manifest.write_text(json.dumps({'case_id':self.case['id'],'status':'complete_with_limitations'}))
        with self.assertRaisesRegex(ValueError, 'Completed report'):
            await self.app.remove_report(self.case['id'], record['id'], 'delete')
        manifest.write_text(json.dumps({'case_id':'another-case','status':'in_progress'}))
        with self.assertRaisesRegex(ValueError, 'another case'):
            await self.app.remove_report(self.case['id'], record['id'], 'delete')
        self.assertEqual(sentinel.read_text(), 'keep'); self.assert_preserved()

    async def test_missing_and_malformed_incomplete_bundles_can_be_cleaned(self):
        record, folder = self.report()
        (folder/'case-manifest.json').write_text('{broken draft')
        await self.app.remove_report(self.case['id'], record['id'], 'delete')
        self.assertFalse(folder.exists())
        record, folder = self.report('missing')
        import shutil
        shutil.rmtree(folder)
        await self.app.remove_report(self.case['id'], record['id'], 'hide')
        result = await self.app.purge_hidden_reports(self.case['id'])
        self.assertEqual(result['failed'], []); self.assertTrue(record['deleted_at'])
        self.assert_preserved()

    async def test_io_failure_keeps_card_and_records_error_for_retry(self):
        record, folder = self.report()
        def partial(*args, **kwargs):
            (folder/'report.md').unlink()
            raise OSError('Synthetic permission failure after partial cleanup')
        with patch('volatility_workbench.app.recycle_report_bundle', side_effect=partial):
            with self.assertRaises(OSError):
                await self.app.remove_report(self.case['id'], record['id'], 'delete')
        self.assertNotIn('deleted_at', record); self.assertFalse(record.get('hidden'))
        self.assertIn('permission', record['deletion_error']); self.assertTrue(folder.exists())
        self.assertTrue((folder/'artifacts/copy.txt').exists())
        await self.app.remove_report(self.case['id'], record['id'], 'delete')
        self.assertNotIn('deletion_error', record); self.assertFalse(folder.exists())
        self.assert_preserved()

    async def test_cleanup_blocks_duplicate_jobs_and_shutdown_waits_for_completion(self):
        record, folder = self.report()
        entered, release = threading.Event(), threading.Event()
        def slow(*args, **kwargs):
            entered.set()
            if not release.wait(5): raise RuntimeError('Fixture cleanup release timed out')
            from volatility_workbench.storage import recycle_report_bundle
            return recycle_report_bundle(*args, **kwargs)
        await self.app.start()
        closing = None
        with patch('volatility_workbench.app.recycle_report_bundle', side_effect=slow):
            task = asyncio.create_task(self.app.remove_report(self.case['id'], record['id'], 'delete'))
            try:
                self.assertTrue(await asyncio.to_thread(entered.wait, 2))
                self.assertEqual(self.app.snapshot()['report_cleanup_cases'], [self.case['id']])
                with self.assertRaisesRegex(ValueError, 'cleanup'):
                    self.app.enqueue(self.case['id'], 'question', 'synthetic')
                with self.assertRaisesRegex(ValueError, 'already in progress'):
                    await self.app.remove_report(self.case['id'], record['id'], 'delete')
                closing = asyncio.create_task(self.app.close())
                await asyncio.sleep(.02)
                self.assertFalse(closing.done())
            finally:
                release.set()
                await task
                if closing is not None: await closing
                else: await self.app.close()
        self.assertFalse(folder.exists()); self.assert_preserved()

    async def test_sealed_hide_persists_and_explicit_delete_recycles_its_bundle(self):
        record, folder = self.report('sealed', 'sealed')
        original = {p.relative_to(folder):p.read_bytes() for p in folder.rglob('*') if p.is_file()}
        await self.app.remove_report(self.case['id'], record['id'], 'hide')
        self.assertTrue(Workbench(self.config,self.app.root).case(self.case['id'])['reports'][0]['hidden'])
        self.assertEqual(original,{p.relative_to(folder):p.read_bytes() for p in folder.rglob('*') if p.is_file()})
        with patch('subprocess.Popen', side_effect=AssertionError('No analysis or model allowed')):
            await self.app.remove_report(self.case['id'], record['id'], 'delete')
        self.assertFalse(folder.exists())
        self.assertTrue((self.app.recycle_case_dir(self.case)/'reports'/record['id']).exists())
        self.assertTrue(record['deleted_at']);self.assertEqual(record['status'],'sealed')
        self.assertTrue((await self.app.remove_report(self.case['id'], record['id'], 'delete'))['already_deleted'])
        self.assert_preserved()

    async def test_human_determination_is_per_version_and_preserves_sealed_bundle(self):
        first, folder = self.report('first', 'sealed')
        second, other_folder = self.report('second', 'sealed')
        original = {p.relative_to(folder):p.read_bytes() for p in folder.rglob('*') if p.is_file()}
        with patch('subprocess.Popen', side_effect=AssertionError('No model or analysis allowed')):
            for value in ('Benign', 'Malicious', 'Undetermined'):
                result = self.app.set_human_determination(self.case['id'], first['id'], value)
                self.assertEqual(result['human_determination'], value)
            self.assertEqual(self.app.set_human_determination(self.case['id'], first['id'], None)['human_determination'], None)
            self.app.set_human_determination(self.case['id'], first['id'], 'Malicious')
        self.assertNotIn('human_determination', second)
        self.assertEqual(Workbench(self.config, self.app.root).case(self.case['id'])['reports'][0]['human_determination'], 'Malicious')
        self.assertEqual(original, {p.relative_to(folder):p.read_bytes() for p in folder.rglob('*') if p.is_file()})
        self.assertTrue(other_folder.exists())
        self.assertEqual(self.case['activity'][-1]['detail']['value'], 'Malicious')
        with self.assertRaisesRegex(ValueError, 'Choose Benign'):
            self.app.set_human_determination(self.case['id'], first['id'], 'Probably malicious')
        draft, _ = self.report('draft', 'incomplete')
        with self.assertRaisesRegex(ValueError, 'sealed report'):
            self.app.set_human_determination(self.case['id'], draft['id'], 'Benign')
        with self.assertRaisesRegex(ValueError, 'sealed report'):
            self.app.set_human_determination(self.case['id'], 'unknown', 'Benign')
        self.assert_preserved()

    async def test_update_carries_human_opinion_without_modifying_parent_or_ai(self):
        for value in ('Benign','Malicious','Undetermined'):
            parent,folder=self.report('parent-'+value,'sealed')
            self.app.set_human_determination(self.case['id'],parent['id'],value)
            original=(folder/'report.md').read_bytes()
            self.case['thread_id']='synthetic'
            self.case['images'][0]['sha256']='synthetic-hash'
            job={'id':'update-'+value,'kind':'update','text':'Synthetic update'}
            with patch.object(self.app,'ensure_thread',new=AsyncMock()), \
                 patch.object(self.app,'fingerprint',new=AsyncMock(return_value={'sha256':'synthetic-hash'})), \
                 patch.object(self.app,'codex_turn',new=AsyncMock(side_effect=RuntimeError('stop before model'))), \
                 patch('volatility_workbench.app.Bundle'):
                with self.assertRaisesRegex(RuntimeError,'stop before model'):
                    await self.app._execute(self.case,job)
            child=self.case['reports'][-1]
            self.assertEqual(child['human_determination'],value)
            self.assertEqual(child['human_determination_inherited_from'],parent['id'])
            self.assertEqual(child['human_determination_at'],parent['human_determination_at'])
            self.assertNotIn('ai_determination',child)
            changed='Benign' if value!='Benign' else 'Malicious'
            self.app.set_human_determination(self.case['id'],parent['id'],changed)
            self.assertEqual(child['human_determination'],changed)
            self.app.set_human_determination(self.case['id'],parent['id'],None)
            self.assertNotIn('human_determination',child)
            self.app.set_human_determination(self.case['id'],parent['id'],value)
            self.assertEqual(child['human_determination'],value)

            self.assertEqual((folder/'report.md').read_bytes(),original)
            child['status']='sealed'
            self.app.set_human_determination(self.case['id'],child['id'],'Benign' if value!='Benign' else 'Malicious')
            self.assertNotIn('human_determination_inherited_from',child)
            self.assertEqual(parent['human_determination'],value)
        self.assert_preserved()

    async def test_sealed_delete_keeps_active_and_source_guards(self):
        record, folder = self.report('sealed', 'sealed')
        self.app.state['jobs']=[{'case_id':self.case['id'],'status':'running'}]
        with self.assertRaisesRegex(ValueError,'active and queued'):
            await self.app.remove_report(self.case['id'], record['id'], 'delete')
        self.app.state['jobs']=[]
        child,_=self.report('child','sealed');child['previous']=record['id']
        with self.assertRaisesRegex(ValueError,'source evidence'):
            delete_report_bundle(self.app.directory(self.case),record['id'],[folder/'artifacts/copy.txt'],allow_completed=True)
        await self.app.remove_report(self.case['id'], record['id'], 'delete')
        self.assertTrue((self.app.directory(self.case)/'reports'/child['id']).exists())
        self.assertFalse(folder.exists());self.assert_preserved()

    async def test_actual_http_requires_origin_and_auth_then_hides_and_deletes(self):
        record, folder = self.report()
        server = Server(self.app, 0, asyncio.get_running_loop())
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        def request(action, auth=True, origin=True):
            headers = {'Content-Type':'application/json'}
            if auth: headers['Cookie'] = 'volatility_ui='+server.token
            if origin: headers['Origin'] = server.origin
            body = json.dumps({'case_id':self.case['id'],'report_id':record['id'],'action':action}).encode()
            req = urllib.request.Request(server.origin+'/api/reports/remove', body, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=5) as response:return response.status
            except urllib.error.HTTPError as error:return error.code
        try:
            self.assertEqual(await asyncio.to_thread(request, 'delete', False), 403)
            self.assertEqual(await asyncio.to_thread(request, 'delete', True, False), 403)
            self.assertTrue(folder.exists())
            self.assertEqual(await asyncio.to_thread(request, 'hide'), 200)
            self.assertTrue(folder.exists())
            self.assertEqual(await asyncio.to_thread(request, 'delete'), 200)
            self.assertFalse(folder.exists()); self.assert_preserved()
        finally:
            await asyncio.to_thread(server.shutdown); server.server_close()

    async def test_http_human_determination_saves_without_touching_sealed_report(self):
        record, folder = self.report('sealed', 'sealed')
        saved_bytes = (folder/'report.md').read_bytes()
        server = Server(self.app, 0, asyncio.get_running_loop())
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        def request(value, auth=True, origin=True):
            headers = {'Content-Type':'application/json'}
            if auth: headers['Cookie'] = 'volatility_ui='+server.token
            if origin: headers['Origin'] = server.origin
            body = json.dumps({'case_id':self.case['id'],'report_id':record['id'],'value':value}).encode()
            req = urllib.request.Request(server.origin+'/api/reports/determination', body, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=5) as response:
                    return response.status, json.load(response)
            except urllib.error.HTTPError as error:
                return error.code, json.load(error)
        try:
            self.assertEqual((await asyncio.to_thread(request, 'Benign', False))[0], 403)
            self.assertEqual((await asyncio.to_thread(request, 'Benign', True, False))[0], 403)
            self.assertEqual((await asyncio.to_thread(request, 'Unknown'))[0], 400)
            status, result = await asyncio.to_thread(request, 'Malicious')
            self.assertEqual(status, 200)
            self.assertEqual(result['human_determination'], 'Malicious')
            self.assertEqual((folder/'report.md').read_bytes(), saved_bytes)
            self.assertEqual(Workbench(self.config,self.app.root).case(self.case['id'])['reports'][0]['human_determination'], 'Malicious')
            self.assert_preserved()
        finally:
            await asyncio.to_thread(server.shutdown); server.server_close()


if __name__ == '__main__': unittest.main()
