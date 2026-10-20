"""Fresh-profile acceptance using only temporary files and a simulated model."""
import asyncio
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from volatility_workbench.app import Workbench
from volatility_workbench.desktop import bootstrap
from volatility_workbench.settings import SettingsManager
from test_ui import FakeCodex
import support as test_backend


class CleanInstallTests(unittest.IsolatedAsyncioTestCase):
    async def wait_job(self, job):
        for _ in range(150):
            if job['status'] not in ('queued', 'running', 'stopping'):
                return
            await asyncio.sleep(.05)
        self.fail('Synthetic job did not finish: ' + repr(job))

    async def test_first_run_report_reopen_and_interrupted_work(self):
        with tempfile.TemporaryDirectory(prefix='workbench-clean-account-') as temporary:
            home = Path(temporary).resolve()/'home'
            home.mkdir()
            resources = Path(temporary)/'App With Spaces.app/Contents/Resources'
            analyzer = resources/'analyzer/bin'
            analyzer.mkdir(parents=True)
            # Fake interpreter and command accept only the test fixture's synthetic protocol.
            fixture = test_backend.BackendFixture()
            fixture.setUp()
            self.addCleanup(fixture.doCleanups)
            for name in ('python3', 'vol'):
                target = analyzer/name
                target.write_bytes(fixture.fake.read_bytes())
                target.chmod(0o700)
            args = SimpleNamespace(preferences_dir=str(home/'Library/Application Support/Volatility Workbench'),
                                   config=None, state_dir=None, clean_setup=True)
            with patch('pathlib.Path.home', return_value=home):
                preferences, config_path, state, prefs = bootstrap(args, resources)
                self.assertFalse(prefs['setup_complete'])
                self.assertEqual(state, home/'Documents/Volatility Workbench/Outputs/workbench')
                self.assertTrue(config_path.is_relative_to(home))
                app = Workbench(config_path, state, codex_factory=FakeCodex)
                settings = SettingsManager(app, config_path, preferences, resources)
                self.assertEqual(settings.snapshot()['readiness']['status'], 'Ready with limitations')
                self.assertEqual(app.state['cases'], [])
                await app.start()
                evidence = app.config.evidence_root/'synthetic.raw'
                evidence.write_text('normal')
                original = evidence.read_bytes()
                case = app.add([str(evidence)])[0]
                case_id = case['id']
                try:
                    ready = app.enqueue(case_id, 'readiness')
                    await self.wait_job(ready)
                    self.assertEqual(ready['status'], 'completed', ready)
                    report_job = app.enqueue(case_id, 'report')
                    await self.wait_job(report_job)
                    self.assertEqual(report_job['status'], 'completed', report_job)
                    report = case['reports'][0]
                    self.assertEqual(report['status'], 'sealed')
                    report_id, thread_id = report['id'], case['thread_id']
                    report_path = app.directory(case)/'reports'/report_id
                    sealed = (report_path/'SHA256SUMS').read_bytes()
                    question = app.enqueue(case_id, 'question', 'Explain the synthetic F001 observation')
                    await self.wait_job(question)
                    self.assertEqual(question['status'], 'completed', question)
                finally:
                    await app.close()

                # A subsequent launch must reuse persisted paths and completed state.
                again = bootstrap(args, resources)
                self.assertEqual(again[1:3], (config_path, state))
                reopened = Workbench(config_path, state, codex_factory=FakeCodex)
                try:
                    restored = reopened.case(case_id)
                    self.assertEqual(restored['thread_id'], thread_id)
                    self.assertEqual([r['id'] for r in restored['reports']], [report_id])
                    self.assertEqual((report_path/'SHA256SUMS').read_bytes(), sealed)
                    self.assertEqual(reopened.report_console(restored, report_job['id'])['job_id'], report_job['id'])
                    self.assertTrue(reopened.citations(restored, report_id)['entries'])
                    self.assertTrue(reopened.queue.empty())
                    await reopened.start()
                    update = reopened.enqueue(case_id, 'update')
                    await self.wait_job(update)
                    self.assertEqual(update['status'], 'completed', update)
                    self.assertEqual(restored['reports'][1]['previous'], report_id)
                    self.assertEqual((report_path/'SHA256SUMS').read_bytes(), sealed)
                finally:
                    await reopened.close()

                # Simulate an abrupt exit after a queued request was persisted.
                saved = json.loads((state/'state.json').read_text())
                saved['jobs'].append({'id':'interrupted-fixture', 'request_id':'interrupted-fixture',
                                      'case_id':case_id, 'kind':'question', 'status':'running'})
                (state/'state.json').write_text(json.dumps(saved))
                recovered = Workbench(config_path, state, codex_factory=FakeCodex)
                self.assertEqual(recovered.state['jobs'][-1]['status'], 'incomplete')
                self.assertTrue(recovered.queue.empty())
                self.assertEqual(evidence.read_bytes(), original)
                self.assertEqual((report_path/'SHA256SUMS').read_bytes(), sealed)
                self.assertEqual([r['id'] for r in recovered.case(case_id)['reports']][0], report_id)


if __name__ == '__main__':
    unittest.main()
