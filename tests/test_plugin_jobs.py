"""Core job controls use harmless metadata and preserve existing case work."""
import asyncio
import json
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
