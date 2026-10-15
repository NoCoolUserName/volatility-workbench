"""Synthetic relocation launch checks; no memory analysis or case mutation."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from volatility_workbench.cli import main
from volatility_workbench.launcher import ensure_relocation_alias


class LauncherTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(dir='/private/tmp')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.old = self.root/'historical'
        self.new = self.root/'current'
        self.new.mkdir()
        self.mapping = self.root/'relocation.json'
        self.mapping.write_text(json.dumps({'logical_root':str(self.old),'physical_root':str(self.new)}))
        env = patch.dict(os.environ, {'VOLATILITY_MCP_RELOCATION':str(self.mapping)})
        env.start()
        self.addCleanup(env.stop)

    def test_missing_alias_restored_once_without_case_changes(self):
        marker = self.new/'saved-manifest.json'
        marker.write_bytes(b'preserved saved record')
        self.assertTrue(ensure_relocation_alias())
        self.assertTrue(self.old.is_symlink())
        self.assertEqual(self.old.resolve(), self.new)
        self.assertFalse(ensure_relocation_alias())
        self.assertEqual(marker.read_bytes(), b'preserved saved record')

    def test_existing_wrong_alias_or_directory_is_never_replaced(self):
        elsewhere = self.root/'elsewhere'
        elsewhere.mkdir()
        self.old.symlink_to(elsewhere, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'exact registered'):
            ensure_relocation_alias()
        self.assertEqual(self.old.resolve(), elsewhere)
        self.old.unlink()
        self.old.mkdir()
        with self.assertRaises(ValueError):
            ensure_relocation_alias()
        self.assertTrue(self.old.is_dir())
        self.assertFalse(self.old.is_symlink())

    def test_second_launcher_accepts_only_matching_race_winner(self):
        original = Path.symlink_to
        def raced(path, target, *args, **kwargs):
            original(path, target, *args, **kwargs)
            raise FileExistsError('another launcher created the alias')
        with patch.object(Path, 'symlink_to', raced):
            self.assertFalse(ensure_relocation_alias())
        self.assertEqual(self.old.resolve(), self.new)

    def test_invalid_mapping_cannot_create_alias(self):
        self.mapping.write_text(json.dumps({'logical_root':str(self.old),'physical_root':str(self.old/'child')}))
        with self.assertRaisesRegex(ValueError, 'nonoverlapping'):
            ensure_relocation_alias()
        self.assertFalse(self.old.exists())

    def test_cli_repairs_before_loading_application(self):
        with patch('volatility_workbench.http.main', return_value=0) as app:
            self.assertEqual(main([]), 0)
        self.assertTrue(self.old.is_symlink())
        app.assert_called_once_with([])

    def test_help_does_not_change_filesystem(self):
        with patch('volatility_workbench.http.main', return_value=0) as app:
            self.assertEqual(main(['--help']), 0)
        self.assertFalse(self.old.exists())
        app.assert_called_once_with(['--help'])

    def test_no_mapping_is_noop(self):
        with patch.dict(os.environ, {'VOLATILITY_MCP_RELOCATION':''}):
            self.assertFalse(ensure_relocation_alias())
        self.assertFalse(self.old.exists())


if __name__ == '__main__':
    unittest.main()
