"""Core job controls use harmless metadata and preserve existing case work."""
import asyncio
import fcntl
import json
import os
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import support
from volatility_workbench.app import Workbench, core_job_records
from volatility_workbench.http import Handler
from volatility_workbench.settings import SettingsManager


class PluginJobTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        fixture = support.BackendFixture(); fixture.setUp(); self.addCleanup(fixture.doCleanups)
        self.fixture = fixture
        self.config = fixture.root/'config.json'
        self.config.write_text(json.dumps(fixture.config.to_dict()))
        self.app = Workbench(self.config, fixture.root/'ui')
        self.case = self.app.add([str(fixture.image)])[0]
        self.manager = SettingsManager(self.app, self.config, fixture.root/'preferences')

    def test_progress_rereads_completion_after_owner_unlock_without_restarting_analysis(self):
        # Use the real case-scoped core and saved results. Only the persistence
        # timing is controlled: completion lands after the poll's first read.
        from volatility_mcp.execution import JobManager
        from volatility_mcp.reuse import _open_lock
        backend = self.app.case_backend(self.case)
        self.addCleanup(backend.shutdown_jobs)
        result = backend.run_plugin(str(self.fixture.image), 'windows.pslist.PsList', ['--pid', '42'])
        manifest = Path(result['manifest_path'])
        saved_manifest = manifest.read_bytes()
        counter = self.fixture.root/'analysis-count.jsonl'
        invocations = counter.read_bytes()
        self.assertEqual(len(invocations.splitlines()), 1)
        manager = backend._job_manager()
        job_id = 'completed-during-progress'
        running = {'job_id': job_id, 'image': str(self.fixture.image),
                   'plugin': 'windows.pslist.PsList', 'arguments': ['--pid', '42'],
                   'state': 'running', 'result': None, 'error': None}
        terminal = {**running, 'state': 'success', 'result': result,
                    'completed_at': '2026-11-20 00:00:00Z'}
        manager._save(running)
        owner = _open_lock(manager._path(job_id, '.lock'))
        fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        original_read = JobManager._read
        reads = []

        def finish_after_first_read(observer, selected_id):
            nonlocal owner
            record = original_read(observer, selected_id)
            reads.append(record['state'])
            if len(reads) == 1:
                manager._save(terminal)
                os.close(owner)
                owner = None
            return record

        try:
            with patch.object(JobManager, '_read', new=finish_after_first_read), \
                 patch('subprocess.Popen', side_effect=AssertionError('Polling must not launch work')):
                progress = self.app.plugin_jobs(self.case)
        finally:
            if owner is not None:
                os.close(owner)
        self.assertEqual(reads, ['running', 'success'])
        self.assertEqual(progress['jobs'][0]['state'], 'success')
        self.assertIsNone(progress['jobs'][0]['error'])
        self.assertNotIn('result', progress['jobs'][0])
        self.assertEqual((progress['count'], progress['active_count']), (1, 0))
        with patch('subprocess.Popen', side_effect=AssertionError('Readback/cancel must not launch work')):
            self.assertEqual(backend.get_job(job_id)['result'], result)
            cancelled = self.app.cancel_plugin_job(self.case, job_id)
            self.assertEqual(cancelled['state'], 'success')
            self.assertEqual(cancelled['result'], result)
            self.assertFalse(cancelled['cancel_requested'])
            self.assertEqual(self.app.plugin_jobs(self.case)['jobs'][0]['state'], 'success')
            self.assertEqual(backend.case_history(str(self.fixture.image))['entries'][0]['status'], 'success')
            # A truly abandoned active record must still be reported interrupted.
            manager._save({**running, 'job_id': 'abandoned-job'})
            abandoned = {job['job_id']: job for job in self.app.plugin_jobs(self.case)['jobs']}
            self.assertEqual(abandoned['abandoned-job']['state'], 'interrupted')
            self.assertEqual(abandoned[job_id]['state'], 'success')
        self.assertEqual(original_read(manager, job_id), terminal)
        self.assertEqual(original_read(manager, 'abandoned-job')['state'], 'running')
        self.assertFalse(manager._path(job_id, '.cancel').exists())
        self.assertEqual(manifest.read_bytes(), saved_manifest)
        self.assertEqual(counter.read_bytes(), invocations)

    async def test_execution_setting_persists_without_changing_case_paths_or_evidence(self):
        scoped = self.app.directory(self.case)/'mcp.json'
        previous = json.loads(scoped.read_text())
        original = self.fixture.image.read_bytes()
        with patch('subprocess.Popen', side_effect=AssertionError('No analysis or model allowed')):
            saved = await self.manager.dispatch('/api/settings/execution', {'max_concurrent_runs': 12})
            self.assertTrue(saved['saved'])
            self.assertEqual(self.app.config.max_concurrent_runs, 12)
            self.assertEqual(json.loads(self.config.read_text())['max_concurrent_runs'], 12)
            expected = json.loads(json.dumps(previous)); expected['config']['max_concurrent_runs'] = 12
            self.assertEqual(json.loads(scoped.read_text()), expected)
            reopened = Workbench(self.config, self.app.root)
            self.assertEqual(reopened.config.max_concurrent_runs, 12)
            self.assertEqual(self.app.plugin_jobs(self.case)['active_count'], 0)
        self.assertEqual(self.fixture.image.read_bytes(), original)
        self.assertFalse((self.fixture.root/'analysis-count.jsonl').exists())

    async def test_invalid_busy_and_background_settings_are_fail_closed(self):
        original = self.config.read_bytes()
        for value in (True, 0, 65, '4', 4.5, None):
            with self.assertRaisesRegex(ValueError, 'integer between 1 and 64'):
                await self.manager.save_execution({'max_concurrent_runs': value})
        self.app.active = {'id': 'active'}
        with self.assertRaisesRegex(ValueError, 'finish'):
            await self.manager.save_execution({'max_concurrent_runs': 4})
        self.app.active = None
        with patch.object(self.app, 'plugin_jobs', return_value={'active_count': 1}), \
             patch.object(self.manager, '_activate', side_effect=AssertionError('Must remain idle')):
            with self.assertRaisesRegex(ValueError, 'plugins to finish'):
                await self.manager.save_execution({'max_concurrent_runs': 4})
        with patch.object(self.app, 'plugin_jobs', side_effect=ValueError('Unavailable core records')):
            with self.assertRaisesRegex(ValueError, 'Unavailable core records'):
                await self.manager.save_execution({'max_concurrent_runs': 4})
        self.assertFalse(self.manager.busy)
        self.assertEqual(self.config.read_bytes(), original)

    def paged_backend(self):
        records = [{'job_id': str(i), 'state': 'success', 'plugin': 'synthetic.Plugin',
                    'submitted_at': f'2026-10-18T00:{i:04d}', 'result': {'large': 'not progress'}} for i in range(260)]
        records += [{'job_id': 'late-running', 'state': 'running', 'plugin': 'synthetic.Plugin'},
                    {'job_id': 'late-queued', 'state': 'queued', 'plugin': 'synthetic.Plugin'}]
        calls = []; cancelled = []
        def listing(offset=0, limit=100):
            calls.append((offset, limit)); end = min(offset+limit, len(records))
            return {'jobs': records[offset:end], 'next_offset': end if end < len(records) else None}
        return SimpleNamespace(config=self.app.config, list_jobs=listing,
                               cancel_job=lambda ident: cancelled.append(ident)), calls, cancelled

    async def test_pagination_progress_and_stop_continue_after_unavailable_old_case(self):
        backend, calls, cancelled = self.paged_backend()
        with patch.object(self.app, 'case_backend', return_value=backend):
            progress = self.app.plugin_jobs(self.case)
        self.assertEqual(calls, [(0, 256), (256, 256)])
        self.assertEqual((progress['count'], progress['active_count']), (262, 2))
        self.assertEqual(len(progress['jobs']), 12)
        self.assertFalse(any('result' in job for job in progress['jobs']))
        # Missing historical case must not block the actual model/VolShell shutdown.
        stale = {'id': 'stale'}; self.app.state['cases'].insert(0, stale)
        def scoped(case):
            if case is stale: raise ValueError('Old case configuration unavailable')
            return backend
        self.app.volshell.shutdown = AsyncMock()
        self.app.volshell_agent.shutdown = AsyncMock()
        self.app._drain_report_deletions = AsyncMock()
        with patch.object(self.app, 'case_backend', side_effect=scoped):
            result = await self.app.stop()
        self.assertEqual(cancelled, ['late-running', 'late-queued'])
        self.assertEqual(result['plugin_cancel_errors'][0]['case_id'], 'stale')
        self.app.volshell.shutdown.assert_awaited_once()
        self.app.volshell_agent.shutdown.assert_awaited_once()
        self.assertTrue(self.app.cancel.is_set())

    async def test_http_routes_resolve_exact_case_and_job(self):
        handler = Handler.__new__(Handler); handler.server = SimpleNamespace(app=self.app)
        backend, _, cancelled = self.paged_backend()
        with patch.object(self.app, 'case_backend', return_value=backend):
            progress = await handler.get_data('/api/plugin-jobs', {'case': [self.case['id']]})
            self.assertEqual(progress['case_id'], self.case['id'])
            await handler.dispatch('/api/plugin-jobs/cancel', {'case_id': self.case['id'], 'job_id': 'late-running'})
        self.assertEqual(cancelled, ['late-running'])
        with self.assertRaisesRegex(RuntimeError, 'StopIteration'):
            await handler.get_data('/api/plugin-jobs', {'case': ['not-this-case']})

    def test_invalid_pagination_fails_instead_of_looping(self):
        backend = SimpleNamespace(list_jobs=lambda **kwargs: {'jobs': [], 'next_offset': 0})
        with self.assertRaisesRegex(ValueError, 'invalid continuation'):
            list(core_job_records(backend))
