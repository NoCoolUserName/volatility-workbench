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
