"""Release safety contracts, offline synthetic bundles and simulated Apple tools."""
import importlib.util
import json
from pathlib import Path
import plistlib
import shutil
import struct
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('release_macos', ROOT / 'scripts/release_macos.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


def macho(path, kind=2):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'\xcf\xfa\xed\xfe' + struct.pack('<IIIIIII', 0x100000c, 0, kind, 0, 0, 0, 0))
    return path


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.app = self.root / 'Volatility Workbench.app'
        self.resources = self.app / 'Contents/Resources'
        self.resources.mkdir(parents=True)
        for name in release.RESOURCE_NAMES:
            path = self.resources / name
            if name in ('runtime', 'analyzer', 'wheelhouse', 'notices'):
                path.mkdir()
            else:
                path.write_text('{}')
        self.executable = macho(self.app / 'Contents/MacOS/Volatility Workbench')
        self.library = macho(self.resources / 'runtime/lib/libpython.dylib', 6)
        self.interpreter = macho(self.resources / 'runtime/bin/python3.12')
        (self.interpreter.parent / 'python3').symlink_to('python3.12')
        self.helper = macho(self.resources / 'desktop-launcher')
        self.manifest = {'application': {'bundle_id': 'org.example.synthetic'},
                         'community': {'bundled_sources': []}, 'pypykatz_plugin': {'commit': 'synthetic'}}
        self.info = {'source_dirty': False, 'workbench_commit': 'a'*40, 'core_commit': 'b'*40,
                     'bundle_id': 'org.example.synthetic', 'signing': 'developer-id'}
        self.write('distribution.json', self.manifest)
        self.write('build-info.json', self.info)
        self.write('bundled-addons.json', {'sources': [], 'pypykatz': self.manifest['pypykatz_plugin']})
        self.write('runtime/lib/python3.12/site-packages/volatility_mcp/resources/addons.json',
                   {'sources': [{'repository': 'synthetic/excluded', 'files': [{'target': 'windows/excluded.py'}]}]})
        for name in ('workbench-LICENSE', 'workbench-THIRD_PARTY_NOTICES.md', 'LICENSING.md', 'pypykatz-LICENSE'):
            (self.resources / 'notices' / name).write_text('SYNTHETIC NOTICE')
        for name in ('dependencies/MIT.txt', 'dependencies/LicenseRef-Volatility-Software-License-1.0.txt',
                     'core/LICENSE', 'core/LICENSING.md', 'core/THIRD_PARTY_NOTICES.md',
                     'core/licenses/MIT.txt', 'core/licenses/LicenseRef-Volatility-Software-License-1.0.txt'):
            path = self.resources / 'notices' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('SYNTHETIC NOTICE')
        self.write('notices/SOURCE_CODE.json', {
            'workbench': {'revision': 'a'*40}, 'core': {'revision': 'b'*40},
            'public_source_required_for_distribution': True})
        (self.resources / 'notices/python-standalone/licenses').mkdir(parents=True)
        (self.app / 'Contents/Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier': self.info['bundle_id']}))
        (self.root / 'packaging').mkdir()
        (self.root / 'packaging/distribution.json').write_text(json.dumps(self.manifest))
        self.addCleanup(patch.stopall)
        patch.object(release, 'ROOT', self.root).start()

    def write(self, name, value):
        path = self.resources / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def test_audit_clean_fixture_and_relative_inventory(self):
        result = release.audit(self.app)
        self.assertEqual(result['status'], 'passed')
        self.assertTrue(all(not Path(x['path']).is_absolute() for x in result['inventory']))
        self.assertEqual(len(result['inventory'][0]['sha256']), 64)

    def test_audit_requires_vsl_notices_and_matching_source_revisions(self):
        notice = self.resources / 'notices/core/licenses/LicenseRef-Volatility-Software-License-1.0.txt'
        notice.unlink()
        with self.assertRaisesRegex(ValueError, 'Missing notice'):
            release.audit(self.app)
        notice.write_text('SYNTHETIC NOTICE')
        self.write('notices/SOURCE_CODE.json', {
            'workbench': {'revision': 'c'*40}, 'core': {'revision': 'b'*40},
            'public_source_required_for_distribution': True})
        with self.assertRaisesRegex(ValueError, 'Source notice differs'):
            release.audit(self.app)

    def test_audit_rejects_private_files_dirty_source_and_unreviewed_profile(self):
        for name in ('config.json', 'example.vmem', '.env', 'signing.p12'):
            path = self.resources / 'runtime' / name
            path.write_text('SYNTHETIC PRIVATE MATERIAL')
            with self.assertRaisesRegex(ValueError, 'private material'):
                release.audit(self.app)
            path.unlink()
        self.write('build-info.json', self.info | {'source_dirty': True})
        with self.assertRaisesRegex(ValueError, 'dirty'):
            release.audit(self.app)
        self.write('build-info.json', self.info)
        self.write('distribution.json', self.manifest | {'unreviewed': True})
        with self.assertRaisesRegex(ValueError, 'reviewed checkout'):
            release.audit(self.app)

    def test_symlink_escape_fails_before_private_target_is_opened(self):
        (self.resources / 'build-info.json').unlink()
        (self.resources / 'build-info.json').symlink_to(self.root / 'not-in-bundle')
        with self.assertRaisesRegex(ValueError, 'external symlink'):
            release.audit(self.app)
        with self.assertRaisesRegex(ValueError, 'external symlink'), patch.object(release, 'run', side_effect=AssertionError('no signing')):
            release.sign(self.app, '-', nested=True)

    def test_excluded_addon_and_missing_notices_are_blocked(self):
        path = self.resources / 'analyzer/lib/python3.12/site-packages/volatility3/framework/plugins/windows/excluded.py'
        path.parent.mkdir(parents=True)
        path.write_text('# SYNTHETIC EXCLUDED PLUGIN')
        with self.assertRaisesRegex(ValueError, 'Excluded community plugin'):
            release.audit(self.app)
        path.unlink()
        for name in ('pypykatz-LICENSE', 'LICENSING.md'):
            notice = self.resources / 'notices' / name
            notice.unlink()
            with self.assertRaisesRegex(ValueError, 'Missing notice'):
                release.audit(self.app)
            notice.write_text('SYNTHETIC NOTICE')

    def test_only_valid_developer_id_identity_is_accepted(self):
        certificate = 'A' * 40
        text = f'1) {certificate} "Developer ID Application: Synthetic (TEAM)"\n2) {"B"*40} "Apple Development: Synthetic"'
        with patch.object(release, 'run', return_value=SimpleNamespace(stdout=text)):
            self.assertEqual(release.identity('Developer ID Application: Synthetic (TEAM)'), certificate)
            self.assertEqual(release.identity(certificate.lower()), certificate)
            for bad in ('Apple Development: Synthetic', 'missing', 'B'*40):
                with self.assertRaisesRegex(ValueError, 'No valid Developer ID'):
                    release.identity(bad)

    def test_explicit_signing_options_for_native_types_and_outer_seal(self):
        with patch.object(release, 'identity', return_value='A'*40), patch.object(release, 'run') as run:
            release.sign(self.app, 'synthetic', nested=True)
            nested = [x.args[0] for x in run.call_args_list]
            self.assertEqual(len(nested), 4)  # real files once; never re-sign interpreter symlinks
            for argv in nested:
                self.assertNotIn('--deep', argv)
                self.assertIn('--timestamp', argv)
                self.assertEqual('--options' in argv, argv[-1] != self.library)
            release.sign(self.app, 'synthetic', nested=False)
            self.assertEqual(run.call_args.args[0][-1], self.app)
        with patch.object(release, 'run') as run:
            release.sign(self.app, '-', nested=True)
            for call in run.call_args_list:
                self.assertNotIn('--timestamp', call.args[0])
                self.assertNotIn('--options', call.args[0])

    def test_universal_executable_slices_and_malformed_header(self):
        thin = self.interpreter.read_bytes()
        path = self.root / 'universal'
        path.write_bytes(b'\xca\xfe\xba\xbe' + struct.pack('>I', 2) +
                         struct.pack('>IIIII', 1, 0, 48, len(thin), 0) +
                         struct.pack('>IIIII', 2, 0, 48+len(thin), len(thin), 0) + thin + thin)
        self.assertEqual(release.macho_types(path), {2})
        path.write_bytes(b'\xca\xfe\xba\xbe' + struct.pack('>I', 999))
        with self.assertRaisesRegex(ValueError, 'architecture count'):
            release.macho_types(path)

    def test_dry_run_does_not_write_sign_or_upload_even_for_adhoc(self):
        self.write('build-info.json', self.info | {'signing': 'ad-hoc'})
        output = self.root / 'release'
        with patch.object(release.subprocess, 'run', side_effect=AssertionError('dry run cannot execute')):
            result = release.notarize(self.app, output, None, dry_run=True)
        self.assertTrue(result['dry_run'])
        self.assertFalse(output.exists())
        self.assertEqual(json.loads((self.resources / 'build-info.json').read_text())['signing'], 'ad-hoc')

    def test_adhoc_not_uploaded_and_existing_outputs_not_overwritten(self):
        output = self.root / 'release'
        self.write('build-info.json', self.info | {'signing': 'ad-hoc'})
        with patch.object(release.subprocess, 'run', side_effect=AssertionError('no upload')):
            with self.assertRaisesRegex(ValueError, 'Rebuild'):
                release.notarize(self.app, output, 'fixture')
        output.mkdir()
        with self.assertRaisesRegex(ValueError, 'never overwritten'):
            release.notarize(self.app, output, 'fixture', dry_run=True)
        with self.assertRaisesRegex(ValueError, 'outside'):
            release.notarize(self.app, self.app / 'release', 'fixture', dry_run=True)

    def apple_tools(self, calls, *, status='Accepted', fail=None):
        def run(argv, **kwargs):
            argv = [str(x) for x in argv]
            calls.append(argv)
            self.assertFalse(kwargs['shell'])
            if fail and fail in argv:
                return SimpleNamespace(returncode=1, stdout='', stderr='SYNTHETIC FAILURE')
            stdout = ''
            if argv[:2] == ['/usr/bin/ditto', str(self.app)]:
                shutil.copytree(argv[1], argv[2], symlinks=True)
            elif argv[0] == '/usr/bin/ditto':
                Path(argv[-1]).write_bytes(b'SYNTHETIC ARCHIVE')
            elif argv[:3] == ['xcrun', 'notarytool', 'submit']:
                stdout = json.dumps({'id': 'synthetic-submission', 'status': status})
            elif argv[:3] == ['xcrun', 'notarytool', 'log']:
                Path(argv[-1]).write_text(json.dumps({'status': status}))
            return SimpleNamespace(returncode=0, stdout=stdout, stderr='')
        return run

    def test_release_stages_input_and_only_claims_success_after_checks(self):
        calls = []
        output = self.root / 'release'
        original = (self.resources / 'build-info.json').read_bytes()
        with patch.object(release.sys, 'platform', 'darwin'), patch.object(release, 'verify_developer_id', return_value='SYNTHETIC_TEAM'), patch.object(release.subprocess, 'run', side_effect=self.apple_tools(calls)):
            result = release.notarize(self.app, output, 'fixture')
        self.assertEqual(result['status'], 'complete')
        self.assertTrue(result['notarized'])
        self.assertEqual((self.resources / 'build-info.json').read_bytes(), original)
        self.assertEqual(result['artifact']['sha256'], release.sha256(output / result['artifact']['file']))
        submit = next(x for x in calls if x[:3] == ['xcrun', 'notarytool', 'submit'])
        self.assertEqual(Path(submit[3]).parent, output)
        self.assertEqual(submit[submit.index('--keychain-profile') + 1], 'fixture')
        self.assertTrue(any(x[0] == '/usr/sbin/spctl' for x in calls))
        self.assertTrue((output / 'bundle-inventory.json').is_file())

    def test_staged_copy_is_audited_again_before_upload(self):
        calls = []
        output = self.root / 'changed-copy'
        normal = self.apple_tools(calls)
        def changed(argv, **kwargs):
            result = normal(argv, **kwargs)
            if argv[:2] == ['/usr/bin/ditto', str(self.app)]:
                (Path(argv[-1]) / 'Contents/Resources/runtime/config.json').write_text('SYNTHETIC PRIVATE CONFIG')
            return result
        with patch.object(release.sys, 'platform', 'darwin'), patch.object(release, 'verify_developer_id', return_value='SYNTHETIC_TEAM'), patch.object(release.subprocess, 'run', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'private material'):
                release.notarize(self.app, output, 'fixture')
        self.assertFalse(any(x[:3] == ['xcrun', 'notarytool', 'submit'] for x in calls))
        state = json.loads((output / 'release-status.json').read_text())
        self.assertEqual(state['step'], 'audit-staged')
        self.assertEqual(state['status'], 'incomplete')

    def test_apple_rejection_and_gatekeeper_failure_stay_incomplete(self):
        for status, fail in [('Invalid', None), ('Accepted', '--assess')]:
            output = self.root / ('release-' + status)
            calls = []
            with patch.object(release.sys, 'platform', 'darwin'), patch.object(release, 'verify_developer_id', return_value='SYNTHETIC_TEAM'), patch.object(release.subprocess, 'run', side_effect=self.apple_tools(calls, status=status, fail=fail)):
                with self.assertRaises(RuntimeError):
                    release.notarize(self.app, output, 'fixture')
            state = json.loads((output / 'release-status.json').read_text())
            self.assertEqual(state['status'], 'incomplete')
            self.assertNotIn('notarized', state)
            self.assertFalse((output / 'Volatility-Workbench-macos-arm64-notarized.zip').exists())
            self.assertTrue((output / 'notary-log.json').exists())

    def test_interrupted_submission_is_recorded_and_input_preserved(self):
        output = self.root / 'interrupted'
        def interrupted(argv, **kwargs):
            if argv[0] == '/usr/bin/ditto':
                return self.apple_tools([])(argv, **kwargs)
            raise KeyboardInterrupt()
        with patch.object(release.sys, 'platform', 'darwin'), patch.object(release, 'verify_developer_id', return_value='SYNTHETIC_TEAM'), patch.object(release.subprocess, 'run', side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                release.notarize(self.app, output, 'fixture')
        state = json.loads((output / 'release-status.json').read_text())
        self.assertEqual(state['status'], 'incomplete')
        self.assertIn('KeyboardInterrupt', state['error'])
        self.assertTrue(self.executable.exists())

    def test_timeout_preserves_partial_output_and_incomplete_state(self):
        output = self.root / 'timed-out'
        normal = self.apple_tools([])
        def timed_out(argv, **kwargs):
            if argv[:3] == ['xcrun', 'notarytool', 'submit']:
                raise subprocess.TimeoutExpired(argv, 1900, output=b'SYNTHETIC PARTIAL OUTPUT', stderr=b'SYNTHETIC TIMEOUT')
            return normal(argv, **kwargs)
        with patch.object(release.sys, 'platform', 'darwin'), patch.object(release, 'verify_developer_id', return_value='SYNTHETIC_TEAM'), patch.object(release.subprocess, 'run', side_effect=timed_out):
            with self.assertRaises(subprocess.TimeoutExpired):
                release.notarize(self.app, output, 'fixture')
        self.assertEqual((output / 'notary-submit.stdout.txt').read_text(), 'SYNTHETIC PARTIAL OUTPUT')
        state = json.loads((output / 'release-status.json').read_text())
        self.assertEqual(state['status'], 'incomplete')
        self.assertEqual(state['step'], 'notary-submit')
        self.assertNotIn('artifact', state)

    def test_signatures_must_have_one_common_team(self):
        def details(argv, **kwargs):
            if '--entitlements' in argv:
                return SimpleNamespace(stdout='', stderr='')
            team = 'OTHER' if argv[-1] == self.library else 'SYNTHETIC'
            return SimpleNamespace(stderr='Authority=Developer ID Application: Synthetic\nTimestamp=today\nCodeDirectory v=20500 flags=0x10000(runtime)\nTeamIdentifier=' + team + '\n')
        with patch.object(release, 'run', side_effect=details):
            with self.assertRaisesRegex(ValueError, 'inconsistent signing team'):
                release.verify_developer_id(self.app)

    def test_signed_executables_require_runtime_timestamp_team_and_no_debug(self):
        def details(argv, **kwargs):
            if '--entitlements' in argv:
                return SimpleNamespace(stdout=plistlib.dumps({'com.apple.security.get-task-allow': True}).decode(), stderr='')
            return SimpleNamespace(stderr='Authority=Developer ID Application: Synthetic\nTimestamp=today\nCodeDirectory v=20500 flags=0x10000(runtime)\nTeamIdentifier=SYNTHETIC\n')
        with patch.object(release, 'run', side_effect=details):
            with self.assertRaisesRegex(ValueError, 'debugger'):
                release.verify_developer_id(self.app)
        for detail in ('Authority=Developer ID Application: Synthetic\nTeamIdentifier=SYNTHETIC\n',
                       'Authority=Developer ID Application: Synthetic\nTimestamp=today\nExecutable=/SYNTHETIC/runtime/python\nTeamIdentifier=SYNTHETIC\n'):
            with patch.object(release, 'run', return_value=SimpleNamespace(stderr=detail)):
                with self.assertRaisesRegex(ValueError, 'runtime'):
                    release.verify_developer_id(self.app)


if __name__ == '__main__':
    unittest.main()
