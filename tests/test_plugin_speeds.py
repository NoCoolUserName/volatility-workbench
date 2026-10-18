"""Timing estimates use saved synthetic physical runs, never live analysis."""
import json
from pathlib import Path
import tempfile
import unittest

import support
from volatility_workbench.app import Workbench
from volatility_workbench import plugin_speeds


class PluginSpeedsTests(unittest.TestCase):
    def test_saved_successes_are_bounded_and_failures_do_not_set_speed(self):
        with tempfile.TemporaryDirectory() as temporary:
            case = Path(temporary)
            for index in range(13):
                run_id = f'run-{index:02}'
                folder = case / 'analysis' / 'image-1' / 'runs' / run_id
                folder.mkdir(parents=True)
                (folder / 'manifest.json').write_text(json.dumps({
                    'run_id':run_id, 'plugin':'windows.pslist.PsList', 'status':'success',
                    'started_at':f'2026-10-18T00:{index:02}:00Z',
                    'completed_at':f'2026-10-18T00:{index:02}:02Z'}))
            failure = case / 'analysis' / 'image-1' / 'runs' / 'failure'
            failure.mkdir()
            (failure / 'manifest.json').write_text(json.dumps({
                'run_id':'failure', 'plugin':'windows.pslist.PsList', 'status':'error',
                'started_at':'2026-10-18T01:00:00Z', 'completed_at':'2026-10-18T01:00:01Z'}))
            runs = plugin_speeds.saved_runs(case, 'synthetic')
            self.assertEqual(len(runs), 13)
            history = plugin_speeds.merge({}, runs)
            self.assertEqual(len(history['windows.pslist.PsList']), 10)
            self.assertEqual(history['windows.pslist.PsList'][0]['run_id'], 'run-12')
            self.assertEqual(plugin_speeds.merge(history, runs), history)
            self.assertEqual(plugin_speeds.summary(history)['windows.pslist.PsList'],
                             {'samples':10, 'average_seconds':2})

    def test_missing_invalid_and_unfinished_manifests_have_no_estimate(self):
        with tempfile.TemporaryDirectory() as temporary:
            case = Path(temporary)
            for name, record in [('bad', {'run_id':'bad','plugin':'windows.pslist.PsList',
                                         'status':'success','started_at':'2026-10-18T00:00:00Z'}),
                                 ('unknown', {'run_id':'unknown','plugin':'windows.pslist.PsList',
                                              'status':'unknown','started_at':'2026-10-18T00:00:00Z',
                                              'completed_at':'2026-10-18T00:00:01Z'})]:
                folder = case / 'analysis' / 'image-1' / 'runs' / name
                folder.mkdir(parents=True)
                (folder / 'manifest.json').write_text(json.dumps(record))
            self.assertEqual(plugin_speeds.saved_runs(case, 'synthetic'), [])
            self.assertEqual(plugin_speeds.summary({}), {})

    def test_running_job_exposes_saved_timing_without_launching_analysis(self):
        fixture = support.BackendFixture(); fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        config = fixture.root / 'config.json'
        config.write_text(json.dumps(fixture.config.to_dict()))
        app = Workbench(config, fixture.root / 'ui')
        case = app.add([str(fixture.image)])[0]
        case['readiness'] = {'status':'Ready','reasons':[]}
        job = app.enqueue(case['id'], 'report', 'Attempt `windows.pslist.PsList` then `windows.netscan.NetScan`.')
        self.assertEqual(job['planned_plugins'], ['windows.pslist.PsList','windows.netscan.NetScan'])
        job.update(status='running',started_at='2026-10-18T00:00:00Z')
        app.active = job
        folder = app.directory(case) / 'analysis' / 'image-1' / 'runs' / 'synthetic-run'
        folder.mkdir(parents=True)
        (folder / 'manifest.json').write_text(json.dumps({'run_id':'synthetic-run',
            'plugin':'windows.pslist.PsList','status':'success',
            'started_at':'2026-10-18T00:00:01Z','completed_at':'2026-10-18T00:00:04Z'}))
        view = app.snapshot()
        self.assertEqual(view['plugin_speed_summary']['windows.pslist.PsList'],
                         {'samples':1,'average_seconds':3})
        self.assertEqual(view['jobs'][0]['completed_plugins'], ['windows.pslist.PsList'])
        self.assertEqual(len(json.loads(app.plugin_speeds_path.read_text())['windows.pslist.PsList']),1)
        self.assertFalse((fixture.root / 'analysis-count.jsonl').exists())
