"""Distribution snapshots must retain every declared license file."""
import importlib.util
from pathlib import Path
import tempfile
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('build_macos_licenses', ROOT/'scripts/build_macos.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class LicensePackagingTests(unittest.TestCase):
    def test_source_notice_identifies_exact_revisions_without_claiming_public_access(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            pin = {'repository': 'NoCoolUserName/volatility-mcp', 'commit': 'b'*40}
            builder.source_notice(target, 'a'*40, pin, '2.28.2')
            import json
            notice = json.loads((target/'SOURCE_CODE.json').read_text())
            self.assertEqual(notice['workbench']['revision'], 'a'*40)
            self.assertTrue(notice['core']['url'].endswith('/'+'b'*40))
            self.assertTrue(notice['public_source_required_for_distribution'])
            self.assertIn('do not certify public access', notice['publication_note'])

    def test_build_snapshot_retains_license_texts_and_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            builder.source_snapshot(target)
            project = tomllib.loads((target/'pyproject.toml').read_text())['project']
            for pattern in project['license-files']:
                originals = list(ROOT.glob(pattern))
                self.assertTrue(originals, pattern)
                for source in originals:
                    self.assertEqual((target/source.relative_to(ROOT)).read_bytes(), source.read_bytes())
            self.assertEqual((target/'licenses/DEPENDENCIES.json').read_bytes(),
                             (ROOT/'licenses/DEPENDENCIES.json').read_bytes())


if __name__ == '__main__':
    unittest.main()
