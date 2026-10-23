"""Harmless appearance and text-size fixtures; no evidence or analyzer is opened."""
import asyncio
from io import BytesIO
from importlib.resources import files
import json
import multiprocessing
from pathlib import Path
import re
import stat
import tempfile
import time
from types import SimpleNamespace
import unittest

from volatility_workbench.http import Handler
from volatility_workbench.settings import SettingsManager, THEME_IDS


def _appearance_save_worker(preferences, state, theme, ready, start, output):
    """Independent process with its own backend state and shared preferences."""
    try:
        app = SimpleNamespace(root=Path(state), active=None, state={'cases': [], 'jobs': []})
        manager = SettingsManager(app, Path(state)/'config.json', preferences)
        original = manager.appearance
        def slow_read():
            result = original()
            # Deliberately overlap the read/write window: without a shared lock
            # several instances would read and return the same next revision.
            time.sleep(0.01)
            return result
        manager.appearance = slow_read
        ready.put(True)
        if not start.wait(10):
            raise TimeoutError('Concurrent fixture did not start')
        output.put(('ok', [manager.save_appearance({'theme': theme}) for _ in range(8)]))
    except Exception as error:
        output.put(('error', repr(error)))


class ThemePreferencesTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.app = SimpleNamespace(active={'fixture': True}, state={'jobs': [{'status': 'running'}]})
        self.manager = SettingsManager(self.app, self.root/'config.json', self.root/'preferences')

    def save(self, theme, **extra):
        return asyncio.run(self.manager.dispatch('/api/settings/appearance', {'theme': theme, **extra}))

    def test_saved_theme_survives_new_manager_without_touching_case_or_configuration(self):
        sentinels = [self.root/name for name in ('config.json', 'desktop.json', 'synthetic-case.json', 'synthetic-evidence.bin')]
        for file in sentinels:
            file.write_bytes(b'harmless fixture preserved exactly')
        before = {file: file.read_bytes() for file in sentinels}
        self.manager.busy = True
        self.assertEqual(self.manager.appearance(), {'schema': 'appearance/1', 'theme': None, 'revision': 0})
        saved = self.save('fallout-new-vegas')
        self.assertEqual(saved['revision'], 1)
        resumed = SettingsManager(self.app, self.root/'config.json', self.manager.root)
        self.assertEqual(resumed.appearance(), saved)
        self.assertEqual(stat.S_IMODE((self.manager.root/'appearance.json').stat().st_mode), 0o600)
        self.assertEqual(self.save('fallout-2')['revision'], 2)
        self.assertEqual({file: file.read_bytes() for file in sentinels}, before)
        separate = SettingsManager(self.app, self.root/'config.json', self.root/'separate-preferences')
        self.assertIsNone(separate.appearance()['theme'])

    def test_text_scale_is_saved_outside_bundle_and_validated(self):
        self.assertEqual(self.manager.zoom(), {'schema':'zoom/1', 'percent':100})
        saved = asyncio.run(self.manager.dispatch('/api/settings/zoom', {'percent':145}))
        self.assertEqual(saved, {'schema':'zoom/1', 'percent':145})
        resumed = SettingsManager(self.app, self.root/'config.json', self.manager.root)
        self.assertEqual(resumed.zoom(), saved)
        self.assertEqual(stat.S_IMODE((self.manager.root/'zoom.json').stat().st_mode), 0o600)
        for value in (True, 74, 201, 117, '145', None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.manager.save_zoom({'percent':value})
        self.assertEqual(self.manager.zoom(), saved)

    def test_reference_terminal_choices_and_original_ids_survive_reload(self):
        for theme in ('fallout-3-robco', 'fallout-3-vault-112', 'fallout-new-vegas',
                      'fallout-3-robco-2', 'fallout-3-vault-112-2', 'fallout-new-vegas-2'):
            saved = self.save(theme)
            self.assertEqual(SettingsManager(self.app, self.root/'config.json', self.manager.root).appearance(), saved)

    def test_strict_builtin_id_and_request_validation(self):
        invalid = [None, [], 'matrix', {}, {'theme': []}, {'theme': {}}, {'theme': True},
                   {'theme': '../matrix'}, {'theme': 'Fallout-New-Vegas'}, {'theme': 'unknown'},
                   {'theme': 'matrix', 'path': '/tmp/unwanted'}, {'theme': 'matrix', 'expected_revision': True},
                   {'theme': 'matrix', 'expected_revision': 1}, {'theme': 'matrix', 'expected_revision': None}]
        for body in invalid:
            with self.subTest(body=body), self.assertRaises(ValueError):
                self.manager.save_appearance(body)
        self.assertFalse((self.manager.root/'appearance.json').exists())

    def test_retired_fallout_76_preference_uses_field_terminal(self):
        saved = {'schema': 'appearance/1', 'theme': 'fallout-76', 'revision': 7}
        path = self.manager.root/'appearance.json'
        path.write_text(json.dumps(saved))
        self.assertEqual(self.manager.appearance(), {**saved, 'theme': 'fallout-76-field-terminal'})
        self.assertEqual(json.loads(path.read_text()), saved, 'Reading a retired choice does not rewrite preferences')
        self.assertNotIn('fallout-76', THEME_IDS)
        with self.assertRaises(ValueError):
            self.save('fallout-76')
        self.assertEqual(self.save('fallout-76-camden-park')['revision'], 8)

    def test_legacy_migration_cannot_overwrite_newer_selection(self):
        migrated = self.save('fallout', expected_revision=0)
        self.assertEqual(migrated['theme'], 'fallout')
        selected = self.save('fallout-new-vegas')
        self.assertEqual(self.save('matrix', expected_revision=0), selected)
        self.assertEqual(self.manager.appearance(), selected)

    def test_separate_processes_share_monotonic_appearance_revisions(self):
        context = multiprocessing.get_context('spawn')
        ready, output, start = context.Queue(), context.Queue(), context.Event()
        processes = [context.Process(target=_appearance_save_worker, args=(str(self.manager.root), str(self.root/f'state-{index}'), theme, ready, start, output))
                     for index, theme in enumerate(('matrix', 'fallout-2', 'fallout-new-vegas'))]
        try:
            for process in processes:
                process.start()
            for _ in processes:
                self.assertTrue(ready.get(timeout=10))
            start.set()
            results = [output.get(timeout=10) for _ in processes]
            for process in processes:
                process.join(10)
                self.assertEqual(process.exitcode, 0)
            self.assertTrue(all(status == 'ok' for status, _ in results), results)
            saves = [saved for _, records in results for saved in records]
            self.assertEqual(sorted(saved['revision'] for saved in saves), list(range(1, 25)))
            self.assertEqual(self.manager.appearance(), max(saves, key=lambda saved: saved['revision']))
            self.assertEqual(stat.S_IMODE((self.manager.root/'appearance.lock').stat().st_mode), 0o600)
        finally:
            for process in processes:
                if process.is_alive():
                    process.terminate()
                if process.pid is not None:
                    process.join(10)
            ready.close()
            output.close()

    def test_corrupt_bounded_records_are_explicit_and_recoverable(self):
        file = self.manager.root/'appearance.json'
        malformed = ['{', '[]', '{"theme": []}', 'x'*1025, b'\xff',
                     json.dumps({'schema': 'appearance/1', 'theme': {}, 'revision': 1}),
                     json.dumps({'schema': 'appearance/1', 'theme': 'matrix', 'revision': True}),
                     json.dumps({'schema': 'appearance/1', 'theme': 'matrix', 'revision': 2**53})]
        for record in malformed:
            with self.subTest(record=repr(record)[:80]):
                file.write_bytes(record if isinstance(record, bytes) else record.encode())
                result = self.manager.appearance()
                self.assertIsNone(result['theme'])
                self.assertIn('could not be loaded', result['error'])
                self.assertEqual(self.save('fallout-new-vegas')['revision'], 1)

    def test_symlink_is_not_followed_or_overwritten(self):
        target = self.root/'untouched.json'
        target.write_text('private sentinel fixture')
        link = self.manager.root/'appearance.json'
        link.symlink_to(target)
        self.assertIn('error', self.manager.appearance())
        with self.assertRaises(ValueError):
            self.save('fallout-new-vegas')
        self.assertEqual(target.read_text(), 'private sentinel fixture')
        self.assertTrue(link.is_symlink())

    def test_preference_lock_symlink_is_refused(self):
        target = self.root/'untouched-lock'
        target.write_text('harmless sentinel')
        (self.manager.root/'appearance.lock').symlink_to(target)
        with self.assertRaises(ValueError):
            self.save('fallout-new-vegas')
        self.assertEqual(target.read_text(), 'harmless sentinel')
        self.assertFalse((self.manager.root/'appearance.json').exists())

    def test_api_state_exposes_same_preference_without_modifying_snapshot(self):
        original = {'cases': [], 'jobs': []}
        self.app.snapshot = lambda: original
        self.app.settings_manager = self.manager
        handler = object.__new__(Handler)
        handler.server = SimpleNamespace(app=self.app)
        saved = self.save('fallout-new-vegas')
        state = asyncio.run(handler.get_data('/api/state', {}))
        self.assertEqual(state['appearance'], saved)
        self.assertNotIn('appearance', original)

    def test_appearance_post_requires_capability_and_matching_origin(self):
        self.app.settings_manager = self.manager
        server = SimpleNamespace(app=self.app, token='synthetic-capability', authority='127.0.0.1:43101', origin='http://127.0.0.1:43101')
        def post(headers):
            handler = object.__new__(Handler)
            handler.server = server
            body = json.dumps({'theme': 'fallout-new-vegas'}).encode()
            handler.headers = {'Host': server.authority, 'Content-Type': 'application/json', 'Content-Length': str(len(body)), **headers}
            handler.path = '/api/settings/appearance'
            handler.connection = SimpleNamespace(settimeout=lambda seconds: None)
            handler.rfile = BytesIO(body)
            sent = []
            handler.send = lambda status, value: sent.append((status, value))
            handler.invoke = asyncio.run
            handler.do_POST()
            return sent[0]
        cookie = {'Cookie': 'volatility_ui='+server.token}
        for headers in ({'Origin': server.origin}, cookie, {**cookie, 'Origin': 'http://foreign.invalid'},
                        {**cookie, 'Origin': server.origin, 'Sec-Fetch-Site': 'cross-site'}):
            with self.subTest(headers=headers):
                self.assertEqual(post(headers)[0], 403)
                self.assertFalse((self.manager.root/'appearance.json').exists())
        status, result = post({**cookie, 'Origin': server.origin})
        self.assertEqual(status, 200)
        self.assertEqual(result['theme'], 'fallout-new-vegas')

    def test_backend_allowlist_matches_packaged_theme_catalog(self):
        asset = files('volatility_workbench').joinpath('static/themes.js')
        catalog = asset.read_text().split('const catalog = [', 1)[1].split('\n  ];', 1)[0]
        names = re.findall(r"^    \['([^']+)',", catalog, re.MULTILINE)
        self.assertEqual(len(names), 37)
        self.assertEqual(frozenset(names), THEME_IDS)


if __name__ == '__main__':
    unittest.main()
