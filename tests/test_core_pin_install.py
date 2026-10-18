"""A same-version VCS update must replace and verify the installed core wheel."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('install_core_pin', Path(__file__).resolve().parents[1] / 'scripts/install_core_pin.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)
build_spec = importlib.util.spec_from_file_location('build_macos', Path(__file__).resolve().parents[1] / 'scripts/build_macos.py')
builder = importlib.util.module_from_spec(build_spec)
build_spec.loader.exec_module(builder)


class PinInstallTests(unittest.TestCase):
    def test_release_builder_rejects_disagreeing_core_pins(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pin = {'repository': installer.REPOSITORY, 'commit': 'a' * 40}
            expected = 'volatility-mcp @ git+https://github.com/' + installer.REPOSITORY + '.git@' + pin['commit']
            (root/'pyproject.toml').write_text('[project]\ndependencies = ["' + expected + '"]\n')
            lock = root/'requirements.lock.txt'
            lock.write_text('mcp==2.3.0\n' + expected + '\n')
            builder.verify_core_sources(root, pin)
            lock.write_text('mcp==2.3.0\n' + expected[:-40] + 'b' * 40 + '\n')
            with self.assertRaisesRegex(ValueError, 'disagree'): builder.verify_core_sources(root, pin)
            lock.write_text('mcp==2.3.0\n' + expected + '\n')
            (root/'pyproject.toml').write_text('[project]\ndependencies = ["' + expected[:-40] + 'b' * 40 + '"]\n')
            with self.assertRaisesRegex(ValueError, 'disagree'): builder.verify_core_sources(root, pin)

    def test_same_version_revision_change_is_reinstalled_and_verified(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'core-dependency.json').write_text(json.dumps({'repository': installer.REPOSITORY, 'commit': 'a' * 40}))
            with patch.object(installer, 'installed_commit', side_effect=['b' * 40, 'a' * 40]), patch.object(installer.subprocess, 'run') as run:
                self.assertEqual(installer.install(root, '/synthetic/python'), 'a' * 40)
                args, kwargs = run.call_args
                self.assertIn('--force-reinstall', args[0]); self.assertIn('--no-deps', args[0])
                self.assertFalse(kwargs['shell'])
            with patch.object(installer, 'installed_commit', return_value='a' * 40), patch.object(installer.subprocess, 'run') as run:
                installer.install(root)
                run.assert_not_called()
            with patch.object(installer, 'installed_commit', return_value='b' * 40), patch.object(installer.subprocess, 'run'):
                with self.assertRaisesRegex(RuntimeError, 'provenance'): installer.install(root)
